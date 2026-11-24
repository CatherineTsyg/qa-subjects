import os

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Answer, Attachment, Vote
from .validators import validate_attachment

MAX_ATTACHMENTS = 5


def vote(user, answer, value):
    """Ставит, меняет или снимает голос. Возвращает итоговое значение или None."""
    if value not in (1, -1):
        raise ValueError("Недопустимое значение голоса.")
    if answer.author_id == user.pk:
        raise PermissionError("Нельзя голосовать за свой ответ.")

    with transaction.atomic():
        existing = Vote.objects.filter(user=user, answer=answer).first()
        if existing is not None:
            if existing.value == value:
                existing.delete()
                return None
            existing.value = value
            existing.save(update_fields=["value", "updated_at"])
            return value

        try:
            with transaction.atomic():
                Vote.objects.create(user=user, answer=answer, value=value)
        except IntegrityError:
            existing = Vote.objects.get(user=user, answer=answer)
            if existing.value == value:
                existing.delete()
                return None
            existing.value = value
            existing.save(update_fields=["value", "updated_at"])
        return value


def add_attachment(answer, uploaded_file):
    content_type = validate_attachment(uploaded_file)

    with transaction.atomic():
        locked_answer = Answer.objects.select_for_update().get(pk=answer.pk)
        if locked_answer.attachments.count() >= MAX_ATTACHMENTS:
            raise ValidationError("К ответу можно прикрепить не более 5 файлов.")

        attachment = Attachment.objects.create(
            answer=locked_answer,
            file=uploaded_file,
            original_name=os.path.basename(uploaded_file.name),
            content_type=content_type,
            size=uploaded_file.size,
        )
    return attachment
