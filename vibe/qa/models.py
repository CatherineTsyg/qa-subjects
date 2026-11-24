import uuid
from pathlib import Path

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse

from .validators import (
    ALLOWED_EXTENSIONS,
    is_image_file,
    validate_file_size,
)


def answer_upload_to(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"answers/{instance.answer_id}/{uuid.uuid4().hex}{suffix}"


class Subject(models.Model):
    name = models.CharField("название", max_length=120, unique=True)
    slug = models.SlugField("slug", max_length=140, unique=True)
    description = models.TextField("описание", blank=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "предмет"
        verbose_name_plural = "предметы"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("qa:subject_detail", kwargs={"slug": self.slug})


class Question(models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="questions",
        verbose_name="предмет",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="автор",
    )
    title = models.CharField("заголовок", max_length=200)
    body = models.TextField("текст вопроса")
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "вопрос"
        verbose_name_plural = "вопросы"
        indexes = [
            models.Index(
                fields=["subject", "-created_at"],
                name="question_subject_created_idx",
            )
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("qa:question_detail", kwargs={"pk": self.pk})


class Answer(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="вопрос",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="автор",
    )
    body = models.TextField("текст ответа")
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "ответ"
        verbose_name_plural = "ответы"

    def __str__(self):
        return f"Ответ #{self.pk} к «{self.question.title}»"

    def get_absolute_url(self):
        url = reverse("qa:question_detail", kwargs={"pk": self.question_id})
        return f"{url}#answer-{self.pk}"


class AnswerVote(models.Model):
    LIKE = 1
    DISLIKE = -1

    answer = models.ForeignKey(
        Answer,
        on_delete=models.CASCADE,
        related_name="votes",
        verbose_name="ответ",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="answer_votes",
        verbose_name="пользователь",
    )
    value = models.SmallIntegerField("голос")
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "голос"
        verbose_name_plural = "голоса"
        constraints = [
            models.UniqueConstraint(
                fields=["answer", "user"],
                name="unique_answer_vote_per_user",
            ),
            models.CheckConstraint(
                condition=Q(value__in=[1, -1]),
                name="answer_vote_value_is_like_or_dislike",
            ),
        ]

    def __str__(self):
        label = "лайк" if self.value == self.LIKE else "дизлайк"
        return f"{label} от {self.user} к ответу #{self.answer_id}"


class Attachment(models.Model):
    answer = models.ForeignKey(
        Answer,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="ответ",
    )
    file = models.FileField(
        "файл",
        upload_to=answer_upload_to,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS),
            validate_file_size,
        ],
    )
    original_name = models.CharField("исходное имя файла", max_length=255)
    uploaded_at = models.DateTimeField("загружен", auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "вложение"
        verbose_name_plural = "вложения"

    def __str__(self):
        return self.original_name

    @property
    def is_image(self):
        return is_image_file(self.file.name)


@receiver(post_delete, sender=Attachment)
def delete_attachment_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
