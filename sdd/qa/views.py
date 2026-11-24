import os

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .cache import (
    SUBJECTS_VERSION_KEY,
    get_cached_page,
    get_version,
    question_page_key,
    question_version_key,
    set_cached_page,
    subjects_page_key,
)
from .forms import AnswerForm, AttachmentForm, QuestionForm
from .models import Answer, Attachment, Question, Subject, Vote
from .services import add_attachment, vote as vote_service

PAGE_SIZE = 20


def _page_from_data(data):
    paginator = Paginator(range(data["total"]), PAGE_SIZE)
    page_obj = paginator.get_page(data["number"])
    page_obj.object_list = data["items"]
    return page_obj


def _subject_page(page_number):
    version = get_version(SUBJECTS_VERSION_KEY)
    key = subjects_page_key(version, page_number)
    data = get_cached_page(key)
    if data is None:
        queryset = Subject.objects.annotate(
            question_count=Count("questions")
        ).order_by("name")
        paginator = Paginator(queryset, PAGE_SIZE)
        page_obj = paginator.get_page(page_number)
        data = {
            "items": [
                {
                    "id": subject.id,
                    "name": subject.name,
                    "question_count": subject.question_count,
                }
                for subject in page_obj
            ],
            "total": paginator.count,
            "number": page_obj.number,
        }
        set_cached_page(subjects_page_key(version, page_obj.number), data)
    return _page_from_data(data)


def _answer_page(question, page_number):
    version = get_version(question_version_key(question.pk))
    key = question_page_key(question.pk, version, page_number)
    data = get_cached_page(key)
    if data is None:
        queryset = (
            Answer.objects.filter(question=question)
            .select_related("author")
            .annotate(rating=Coalesce(Sum("votes__value"), 0))
            .prefetch_related("attachments")
            .order_by("-rating", "-created_at")
        )
        paginator = Paginator(queryset, PAGE_SIZE)
        page_obj = paginator.get_page(page_number)
        items = []
        for answer in page_obj:
            items.append(
                {
                    "id": answer.id,
                    "body": answer.body,
                    "author_id": answer.author_id,
                    "author_username": answer.author.username,
                    "created_at": answer.created_at,
                    "rating": answer.rating,
                    "attachments": [
                        {
                            "id": attachment.id,
                            "original_name": attachment.original_name,
                            "content_type": attachment.content_type,
                            "size": attachment.size,
                        }
                        for attachment in answer.attachments.all()
                    ],
                }
            )
        data = {
            "items": items,
            "total": paginator.count,
            "number": page_obj.number,
        }
        set_cached_page(
            question_page_key(question.pk, version, page_obj.number), data
        )
    return _page_from_data(data)


def healthz(request):
    return HttpResponse("ok")


def subject_list(request):
    page_obj = _subject_page(request.GET.get("page", 1))
    return render(request, "qa/subject_list.html", {"page_obj": page_obj})


def subject_detail(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    queryset = (
        Question.objects.filter(subject=subject)
        .select_related("author")
        .order_by("-created_at")
    )
    page_obj = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page", 1))
    return render(
        request,
        "qa/subject_detail.html",
        {"subject": subject, "page_obj": page_obj},
    )


def question_detail(request, pk):
    question = get_object_or_404(
        Question.objects.select_related("author", "subject"), pk=pk
    )
    page_obj = _answer_page(question, request.GET.get("page", 1))

    user_votes = {}
    if request.user.is_authenticated:
        answer_ids = [answer["id"] for answer in page_obj.object_list]
        if answer_ids:
            user_votes = dict(
                Vote.objects.filter(
                    user=request.user, answer_id__in=answer_ids
                ).values_list("answer_id", "value")
            )

    return render(
        request,
        "qa/question_detail.html",
        {
            "question": question,
            "page_obj": page_obj,
            "user_votes": user_votes,
        },
    )


@login_required
def question_create(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == "POST":
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.subject = subject
            question.author = request.user
            question.save()
            return redirect("question_detail", pk=question.pk)
    else:
        form = QuestionForm()
    return render(
        request,
        "qa/question_form.html",
        {"form": form, "subject": subject},
    )


@login_required
def answer_create(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if request.method == "POST":
        form = AnswerForm(request.POST)
        if form.is_valid():
            answer = form.save(commit=False)
            answer.question = question
            answer.author = request.user
            answer.save()
            return redirect("question_detail", pk=question.pk)
    else:
        form = AnswerForm()
    return render(
        request,
        "qa/answer_form.html",
        {"form": form, "question": question},
    )


def _require_author_or_staff(request, author_id):
    if request.user.pk != author_id and not request.user.is_staff:
        raise PermissionDenied("Недостаточно прав для изменения объекта.")


@login_required
def question_edit(request, pk):
    question = get_object_or_404(Question, pk=pk)
    _require_author_or_staff(request, question.author_id)
    if request.method == "POST":
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            return redirect("question_detail", pk=question.pk)
    else:
        form = QuestionForm(instance=question)
    return render(
        request,
        "qa/question_form.html",
        {"form": form, "question": question, "subject": question.subject},
    )


@login_required
def question_delete(request, pk):
    question = get_object_or_404(Question, pk=pk)
    _require_author_or_staff(request, question.author_id)
    if request.method == "POST":
        subject_id = question.subject_id
        question.delete()
        return redirect("subject_detail", pk=subject_id)
    return render(
        request,
        "qa/confirm_delete.html",
        {"object": question, "object_type": "вопрос"},
    )


@login_required
def answer_edit(request, pk):
    answer = get_object_or_404(Answer, pk=pk)
    _require_author_or_staff(request, answer.author_id)
    if request.method == "POST":
        form = AnswerForm(request.POST, instance=answer)
        if form.is_valid():
            form.save()
            return redirect("question_detail", pk=answer.question_id)
    else:
        form = AnswerForm(instance=answer)
    return render(
        request,
        "qa/answer_form.html",
        {"form": form, "question": answer.question},
    )


@login_required
def answer_delete(request, pk):
    answer = get_object_or_404(Answer, pk=pk)
    _require_author_or_staff(request, answer.author_id)
    if request.method == "POST":
        question_id = answer.question_id
        answer.delete()
        return redirect("question_detail", pk=question_id)
    return render(
        request,
        "qa/confirm_delete.html",
        {"object": answer, "object_type": "ответ"},
    )


@login_required
@require_POST
def answer_vote(request, pk):
    answer = get_object_or_404(
        Answer.objects.select_related("author"), pk=pk
    )
    if answer.author_id == request.user.pk:
        raise PermissionDenied("Нельзя голосовать за свой ответ.")

    value = {"like": 1, "dislike": -1}.get(request.POST.get("value"))
    if value is None:
        return HttpResponseBadRequest("Недопустимое значение голоса.")

    vote_service(request.user, answer, value)
    return redirect("question_detail", pk=answer.question_id)


@login_required
def attachment_create(request, pk):
    answer = get_object_or_404(
        Answer.objects.select_related("author"), pk=pk
    )
    if answer.author_id != request.user.pk:
        raise PermissionDenied("Добавлять вложения может только автор ответа.")

    if request.method == "POST":
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                add_attachment(answer, form.cleaned_data["file"])
            except ValidationError as exc:
                form.add_error("file", exc)
            else:
                return redirect("question_detail", pk=answer.question_id)
    else:
        form = AttachmentForm()
    return render(
        request,
        "qa/attachment_form.html",
        {"form": form, "answer": answer},
    )


@login_required
def attachment_delete(request, pk):
    attachment = get_object_or_404(
        Attachment.objects.select_related("answer__author"), pk=pk
    )
    _require_author_or_staff(request, attachment.answer.author_id)
    if request.method == "POST":
        question_id = attachment.answer.question_id
        attachment.delete()
        return redirect("question_detail", pk=question_id)
    return render(
        request,
        "qa/confirm_delete.html",
        {"object": attachment, "object_type": "вложение"},
    )


def attachment_download(request, pk):
    attachment = get_object_or_404(Attachment, pk=pk)
    try:
        response = FileResponse(
            attachment.file.open("rb"),
            content_type=attachment.content_type,
            as_attachment=not attachment.content_type.startswith("image/"),
            filename=os.path.basename(attachment.original_name),
        )
    except OSError as exc:
        raise Http404("Файл не найден.") from exc
    return response
