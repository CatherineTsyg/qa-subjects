from django.contrib import admin
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from .models import Answer, AnswerVote, Attachment, Question, Subject


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "question_count", "created_at")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            questions_total=Count("questions")
        )

    @admin.display(description="вопросов", ordering="questions_total")
    def question_count(self, obj):
        return obj.questions_total


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "author", "answer_count", "created_at")
    list_filter = ("subject", "created_at")
    search_fields = ("title", "body", "author__username")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("subject", "author")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("subject", "author")
            .annotate(answers_total=Count("answers"))
        )

    @admin.display(description="ответов", ordering="answers_total")
    def answer_count(self, obj):
        return obj.answers_total


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "author", "rating", "created_at")
    list_filter = ("created_at",)
    search_fields = ("body", "question__title", "author__username")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("question", "author")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("question", "author")
            .annotate(total_rating=Coalesce(Sum("votes__value"), 0))
        )

    @admin.display(description="рейтинг", ordering="total_rating")
    def rating(self, obj):
        return obj.total_rating


@admin.register(AnswerVote)
class AnswerVoteAdmin(admin.ModelAdmin):
    list_display = ("answer", "user", "value", "created_at")
    list_filter = ("value", "created_at")
    search_fields = ("answer__body", "user__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "answer", "uploaded_at")
    search_fields = ("original_name", "answer__body")
    readonly_fields = ("uploaded_at",)
