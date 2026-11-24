from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from config.test_utils import CacheMediaTestCase
from qa.models import Answer, Attachment, Question, Subject, Vote


class CsrfProtectionTests(CacheMediaTestCase):
    def setUp(self):
        super().setUp()
        self.author = User.objects.create_user(
            "author", password="StrongPass123!"
        )
        self.voter = User.objects.create_user(
            "voter", password="StrongPass123!"
        )
        self.subject = Subject.objects.create(name="Математика")
        self.question = Question.objects.create(
            subject=self.subject,
            author=self.author,
            title="Вопрос",
            body="Текст",
        )
        self.answer = Answer.objects.create(
            question=self.question, author=self.author, body="Ответ"
        )
        self.attachment = Attachment.objects.create(
            answer=self.answer,
            file=SimpleUploadedFile("note.txt", b"hello"),
            original_name="note.txt",
            content_type="text/plain",
            size=5,
        )
        self.client = Client(enforce_csrf_checks=True)

    def _assert_forbidden(self, url, data=None):
        response = self.client.post(url, data or {})
        self.assertEqual(response.status_code, 403)
        return response

    def test_question_create_without_csrf_is_rejected(self):
        self.client.force_login(self.author)

        self._assert_forbidden(
            reverse("question_create", args=[self.subject.pk]),
            {"title": "Новый", "body": "Текст"},
        )
        self.assertEqual(Question.objects.count(), 1)

    def test_answer_create_without_csrf_is_rejected(self):
        self.client.force_login(self.author)

        self._assert_forbidden(
            reverse("answer_create", args=[self.question.pk]),
            {"body": "Новый ответ"},
        )
        self.assertEqual(Answer.objects.count(), 1)

    def test_question_edit_without_csrf_is_rejected(self):
        self.client.force_login(self.author)

        self._assert_forbidden(
            reverse("question_edit", args=[self.question.pk]),
            {"title": "Изменён", "body": "Изменён"},
        )
        self.question.refresh_from_db()
        self.assertEqual(self.question.title, "Вопрос")

    def test_question_delete_without_csrf_is_rejected(self):
        self.client.force_login(self.author)

        self._assert_forbidden(
            reverse("question_delete", args=[self.question.pk])
        )
        self.assertTrue(Question.objects.filter(pk=self.question.pk).exists())

    def test_answer_edit_without_csrf_is_rejected(self):
        self.client.force_login(self.author)

        self._assert_forbidden(
            reverse("answer_edit", args=[self.answer.pk]),
            {"body": "Изменён"},
        )
        self.answer.refresh_from_db()
        self.assertEqual(self.answer.body, "Ответ")

    def test_answer_delete_without_csrf_is_rejected(self):
        self.client.force_login(self.author)

        self._assert_forbidden(
            reverse("answer_delete", args=[self.answer.pk])
        )
        self.assertTrue(Answer.objects.filter(pk=self.answer.pk).exists())

    def test_vote_without_csrf_is_rejected(self):
        self.client.force_login(self.voter)

        self._assert_forbidden(
            reverse("answer_vote", args=[self.answer.pk]),
            {"value": "like"},
        )
        self.assertEqual(Vote.objects.count(), 0)

    def test_attachment_create_without_csrf_is_rejected(self):
        self.client.force_login(self.author)

        self._assert_forbidden(
            reverse("attachment_create", args=[self.answer.pk]),
            {"file": SimpleUploadedFile("new.txt", b"hello")},
        )
        self.assertEqual(Attachment.objects.count(), 1)

    def test_attachment_delete_without_csrf_is_rejected(self):
        self.client.force_login(self.author)

        self._assert_forbidden(
            reverse("attachment_delete", args=[self.attachment.pk])
        )
        self.assertTrue(
            Attachment.objects.filter(pk=self.attachment.pk).exists()
        )

    def test_logout_without_csrf_is_rejected(self):
        self.client.force_login(self.author)

        self._assert_forbidden(reverse("logout"))
        self.assertIn("_auth_user_id", self.client.session)
