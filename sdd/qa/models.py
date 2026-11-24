from django.conf import settings
from django.db import models
from django.db.models import Q


class Subject(models.Model):
    name = models.CharField("название", max_length=120, unique=True)
    description = models.TextField("описание", blank=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        verbose_name = "предмет"
        verbose_name_plural = "предметы"

    def __str__(self):
        return self.name


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
    body = models.TextField("текст")
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        verbose_name = "вопрос"
        verbose_name_plural = "вопросы"
        indexes = [
            models.Index(
                fields=["subject", "-created_at"],
                name="question_subject_created_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(title=""), name="question_title_not_empty"
            ),
            models.CheckConstraint(
                condition=~Q(body=""), name="question_body_not_empty"
            ),
        ]

    def __str__(self):
        return self.title


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
    body = models.TextField("текст")
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        verbose_name = "ответ"
        verbose_name_plural = "ответы"
        indexes = [
            models.Index(fields=["question"], name="answer_question_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(body=""), name="answer_body_not_empty"
            ),
        ]

    def __str__(self):
        return f"Ответ #{self.pk}"


class Vote(models.Model):
    answer = models.ForeignKey(
        Answer,
        on_delete=models.CASCADE,
        related_name="votes",
        verbose_name="ответ",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="votes",
        verbose_name="пользователь",
    )
    value = models.SmallIntegerField("голос")
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        verbose_name = "голос"
        verbose_name_plural = "голоса"
        indexes = [
            models.Index(fields=["answer"], name="vote_answer_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "answer"], name="vote_unique_user_answer"
            ),
            models.CheckConstraint(
                condition=Q(value__in=[1, -1]), name="vote_value_allowed"
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.answer}: {self.value}"


class Attachment(models.Model):
    answer = models.ForeignKey(
        Answer,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="ответ",
    )
    file = models.FileField("файл", upload_to="attachments/%Y/%m/%d/")
    original_name = models.CharField("имя файла", max_length=255)
    content_type = models.CharField("MIME-тип", max_length=100)
    size = models.PositiveBigIntegerField("размер")
    created_at = models.DateTimeField("загружен", auto_now_add=True)

    class Meta:
        verbose_name = "вложение"
        verbose_name_plural = "вложения"
        indexes = [
            models.Index(fields=["answer"], name="attachment_answer_idx"),
        ]

    def __str__(self):
        return self.original_name
