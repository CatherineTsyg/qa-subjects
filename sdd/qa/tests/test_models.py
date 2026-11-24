from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from config.test_utils import CacheMediaTestCase
from qa.models import Answer, Attachment, Question, Subject, Vote


class ModelConstraintTests(CacheMediaTestCase):
    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User

        self.author = User.objects.create_user("author", password="StrongPass123!")
        self.voter = User.objects.create_user("voter", password="StrongPass123!")
        self.subject = Subject.objects.create(name="Математика")
        self.question = Question.objects.create(
            subject=self.subject,
            author=self.author,
            title="Что такое интеграл?",
            body="Объясните понятие интеграла.",
        )
        self.answer = Answer.objects.create(
            question=self.question,
            author=self.author,
            body="Интеграл — это площадь под графиком.",
        )

    def test_vote_unique_per_user_and_answer(self):
        Vote.objects.create(answer=self.answer, user=self.voter, value=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Vote.objects.create(answer=self.answer, user=self.voter, value=-1)

    def test_vote_value_is_limited(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Vote.objects.create(answer=self.answer, user=self.voter, value=0)

    def test_subject_with_questions_is_protected(self):
        with self.assertRaises(ProtectedError):
            self.subject.delete()
        self.assertTrue(Subject.objects.filter(pk=self.subject.pk).exists())

    def test_empty_subject_can_be_deleted(self):
        empty = Subject.objects.create(name="Физика")
        empty.delete()
        self.assertFalse(Subject.objects.filter(pk=empty.pk).exists())

    def test_deleting_question_cascades_answers_votes_and_files(self):
        Vote.objects.create(answer=self.answer, user=self.voter, value=1)
        attachment = Attachment.objects.create(
            answer=self.answer,
            file=SimpleUploadedFile("note.txt", b"hello", content_type="text/plain"),
            original_name="note.txt",
            content_type="text/plain",
            size=5,
        )
        file_name = attachment.file.name

        self.question.delete()

        self.assertFalse(Answer.objects.filter(pk=self.answer.pk).exists())
        self.assertEqual(Vote.objects.count(), 0)
        self.assertEqual(Attachment.objects.count(), 0)
        self.assertFalse(attachment.file.storage.exists(file_name))

    def test_deleting_answer_cascades_votes_and_attachments(self):
        Vote.objects.create(answer=self.answer, user=self.voter, value=-1)
        attachment = Attachment.objects.create(
            answer=self.answer,
            file=SimpleUploadedFile("note.txt", b"hello", content_type="text/plain"),
            original_name="note.txt",
            content_type="text/plain",
            size=5,
        )
        file_name = attachment.file.name

        self.answer.delete()

        self.assertEqual(Vote.objects.count(), 0)
        self.assertEqual(Attachment.objects.count(), 0)
        self.assertFalse(attachment.file.storage.exists(file_name))

    def test_deleting_attachment_removes_file(self):
        attachment = Attachment.objects.create(
            answer=self.answer,
            file=SimpleUploadedFile("note.txt", b"hello", content_type="text/plain"),
            original_name="note.txt",
            content_type="text/plain",
            size=5,
        )
        file_name = attachment.file.name

        attachment.delete()

        self.assertFalse(attachment.file.storage.exists(file_name))
