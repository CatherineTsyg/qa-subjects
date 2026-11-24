from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import (
    SUBJECTS_VERSION_KEY,
    bump_version,
    question_version_key,
)
from .models import Answer, Attachment, Question, Subject, Vote


def _bump(key):
    transaction.on_commit(lambda: bump_version(key))


def _bump_subjects():
    _bump(SUBJECTS_VERSION_KEY)


def _bump_question(question_id):
    if question_id is not None:
        _bump(question_version_key(question_id))


def _vote_question_id(instance):
    """Идентификатор вопроса вычисляется в момент сигнала, не в on_commit."""
    if not instance.answer_id:
        return None
    try:
        return instance.answer.question_id
    except Answer.DoesNotExist:
        return None


def _attachment_question_id(instance):
    if not instance.answer_id:
        return None
    try:
        return instance.answer.question_id
    except Answer.DoesNotExist:
        return None


@receiver(post_save, sender=Subject)
@receiver(post_delete, sender=Subject)
def invalidate_subject(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    _bump_subjects()


@receiver(post_save, sender=Question)
@receiver(post_delete, sender=Question)
def invalidate_question(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    _bump_subjects()
    _bump_question(instance.pk)


@receiver(post_save, sender=Answer)
@receiver(post_delete, sender=Answer)
def invalidate_answer(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    _bump_question(instance.question_id)


@receiver(post_save, sender=Vote)
@receiver(post_delete, sender=Vote)
def invalidate_vote(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    _bump_question(_vote_question_id(instance))


@receiver(post_save, sender=Attachment)
@receiver(post_delete, sender=Attachment)
def invalidate_attachment(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    _bump_question(_attachment_question_id(instance))


@receiver(post_delete, sender=Attachment)
def delete_attachment_file(sender, instance, **kwargs):
    if instance.file:
        try:
            instance.file.delete(save=False)
        except OSError:
            pass
