from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import Answer, Attachment, Question, Subject, Vote


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name", "description")
    ordering = ("name",)

    def delete_view(self, request, object_id, extra_context=None):
        subject = self.get_object(request, object_id)
        if subject is not None and subject.questions.exists():
            self.message_user(
                request,
                "Нельзя удалить предмет, в котором есть вопросы",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse("admin:qa_subject_changelist")
            )
        return super().delete_view(request, object_id, extra_context)

    def delete_queryset(self, request, queryset):
        for subject in queryset:
            if subject.questions.exists():
                self.message_user(
                    request,
                    f"Нельзя удалить предмет «{subject.name}»: в нём есть вопросы",
                    level=messages.ERROR,
                )
                continue
            subject.delete()


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "author", "created_at")
    search_fields = ("title", "body", "author__username", "subject__name")
    list_select_related = ("subject", "author")


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "author", "created_at")
    search_fields = ("body", "author__username", "question__title")
    list_select_related = ("question", "author")


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("id", "answer", "user", "value", "created_at")
    search_fields = ("user__username", "answer__body")
    list_select_related = ("answer", "user")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "answer", "content_type", "size", "created_at")
    search_fields = ("original_name", "answer__body")
    list_select_related = ("answer",)
