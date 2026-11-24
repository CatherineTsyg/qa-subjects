from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import AnswerForm, QuestionForm
from .models import Answer, AnswerVote, Attachment, Question, Subject


def answers_with_rating():
    """Answers ordered by rating (likes minus dislikes), then by date."""
    return (
        Answer.objects.select_related("author")
        .prefetch_related("attachments")
        .annotate(
            rating=Coalesce(Sum("votes__value"), Value(0)),
            like_count=Count(
                "votes", filter=Q(votes__value=AnswerVote.LIKE)
            ),
            dislike_count=Count(
                "votes", filter=Q(votes__value=AnswerVote.DISLIKE)
            ),
        )
        .order_by("-rating", "created_at")
    )


class AuthorOrStaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        obj = self.get_object()
        return self.request.user.is_staff or obj.author_id == self.request.user.id


class SubjectListView(ListView):
    model = Subject
    template_name = "qa/subject_list.html"
    context_object_name = "subjects"

    def get_queryset(self):
        return Subject.objects.annotate(
            question_count=Count("questions")
        ).order_by("name")


class SubjectDetailView(DetailView):
    model = Subject
    template_name = "qa/subject_detail.html"
    context_object_name = "subject"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return Subject.objects.annotate(question_count=Count("questions"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["questions"] = (
            self.object.questions.select_related("author", "subject")
            .annotate(answer_count=Count("answers"))
            .order_by("-created_at")
        )
        return context


class QuestionDetailView(DetailView):
    model = Question
    template_name = "qa/question_detail.html"
    context_object_name = "question"

    def get_queryset(self):
        return Question.objects.select_related("subject", "author")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        answers = list(
            answers_with_rating().filter(question=self.object)
        )
        user_votes = {}
        if self.request.user.is_authenticated:
            user_votes = dict(
                AnswerVote.objects.filter(
                    user=self.request.user,
                    answer__question=self.object,
                ).values_list("answer_id", "value")
            )
        for answer in answers:
            answer.user_vote = user_votes.get(answer.pk)
        context["answers"] = answers
        context["answer_form"] = AnswerForm()
        return context


class QuestionCreateView(LoginRequiredMixin, CreateView):
    model = Question
    form_class = QuestionForm
    template_name = "qa/question_form.html"

    def get_initial(self):
        initial = super().get_initial()
        subject = Subject.objects.filter(
            slug=self.request.GET.get("subject", "")
        ).first()
        if subject:
            initial["subject"] = subject
        return initial

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, "Вопрос опубликован.")
        return super().form_valid(form)


class QuestionUpdateView(AuthorOrStaffRequiredMixin, UpdateView):
    model = Question
    form_class = QuestionForm
    template_name = "qa/question_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Вопрос обновлён.")
        return super().form_valid(form)


class QuestionDeleteView(AuthorOrStaffRequiredMixin, DeleteView):
    model = Question
    template_name = "qa/question_confirm_delete.html"

    def get_success_url(self):
        messages.success(self.request, "Вопрос удалён.")
        return self.object.subject.get_absolute_url()


class AnswerCreateView(LoginRequiredMixin, CreateView):
    model = Answer
    form_class = AnswerForm
    template_name = "qa/answer_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.question = get_object_or_404(
            Question.objects.select_related("subject"), pk=kwargs["pk"]
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["question"] = self.question
        return context

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.author = self.request.user
            form.instance.question = self.question
            self.object = form.save()
            form.save_attachments(self.object)
        messages.success(self.request, "Ответ опубликован.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        url = reverse(
            "qa:question_detail", kwargs={"pk": self.question.pk}
        )
        return f"{url}#answer-{self.object.pk}"


class AnswerUpdateView(AuthorOrStaffRequiredMixin, UpdateView):
    model = Answer
    form_class = AnswerForm
    template_name = "qa/answer_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["question"] = self.object.question
        return context

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            form.save_attachments(self.object)
        messages.success(self.request, "Ответ обновлён.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        url = reverse(
            "qa:question_detail", kwargs={"pk": self.object.question_id}
        )
        return f"{url}#answer-{self.object.pk}"


class AnswerDeleteView(AuthorOrStaffRequiredMixin, DeleteView):
    model = Answer
    template_name = "qa/answer_confirm_delete.html"

    def get_success_url(self):
        question_id = self.object.question_id
        messages.success(self.request, "Ответ удалён.")
        url = reverse("qa:question_detail", kwargs={"pk": question_id})
        return url


def _apply_vote(vote, value):
    if vote.value == value:
        vote.delete()
    else:
        vote.value = value
        vote.save(update_fields=["value", "updated_at"])


@login_required
@require_POST
def answer_vote(request, pk):
    raw_value = request.POST.get("value")
    if raw_value not in {"1", "-1"}:
        return HttpResponseBadRequest("Некорректный голос.")
    value = int(raw_value)

    with transaction.atomic():
        answer = get_object_or_404(
            Answer.objects.select_for_update(), pk=pk
        )
        if answer.author_id == request.user.id:
            raise PermissionDenied("Нельзя голосовать за свой ответ.")

        vote = (
            AnswerVote.objects.select_for_update()
            .filter(answer=answer, user=request.user)
            .first()
        )
        if vote is None:
            try:
                with transaction.atomic():
                    AnswerVote.objects.create(
                        answer=answer, user=request.user, value=value
                    )
            except IntegrityError:
                # Параллельный запрос уже создал голос: применяем
                # голосование к существующей записи.
                vote = AnswerVote.objects.select_for_update().get(
                    answer=answer, user=request.user
                )
                _apply_vote(vote, value)
        else:
            _apply_vote(vote, value)

    return redirect(answer.get_absolute_url())


@login_required
@require_POST
def attachment_delete(request, pk):
    attachment = get_object_or_404(
        Attachment.objects.select_related("answer"), pk=pk
    )
    is_owner = attachment.answer.author_id == request.user.id
    if not (request.user.is_staff or is_owner):
        raise PermissionDenied

    question_id = attachment.answer.question_id
    answer_id = attachment.answer_id
    original_name = attachment.original_name
    attachment.delete()
    messages.success(request, f"Файл «{original_name}» удалён.")
    url = reverse("qa:question_detail", kwargs={"pk": question_id})
    return redirect(f"{url}#answer-{answer_id}")
