from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from config.test_utils import CacheMediaTestCase
from qa.models import Answer, Attachment, Question, Subject


class PermissionTests(CacheMediaTestCase):
    def setUp(self):
        super().setUp()
        self.author = User.objects.create_user(
            "author", password="StrongPass123!"
        )
        self.other = User.objects.create_user(
            "other", password="StrongPass123!"
        )
        self.staff = User.objects.create_user(
            "staff", password="StrongPass123!", is_staff=True
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

    def test_question_edit_permissions(self):
        url = reverse("question_edit", args=[self.question.pk])

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.author)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_question_delete_permissions(self):
        url = reverse("question_delete", args=[self.question.pk])

        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Question.objects.filter(pk=self.question.pk).exists())

        self.client.force_login(self.author)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())

    def test_staff_can_delete_foreign_question(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("question_delete", args=[self.question.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())

    def test_answer_edit_permissions(self):
        url = reverse("answer_edit", args=[self.answer.pk])

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.author)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_answer_delete_permissions(self):
        url = reverse("answer_delete", args=[self.answer.pk])

        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Answer.objects.filter(pk=self.answer.pk).exists())

        self.client.force_login(self.staff)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Answer.objects.filter(pk=self.answer.pk).exists())

    def test_attachment_delete_permissions(self):
        url = reverse("attachment_delete", args=[self.attachment.pk])

        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(
            Attachment.objects.filter(pk=self.attachment.pk).exists()
        )

        self.client.force_login(self.author)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Attachment.objects.filter(pk=self.attachment.pk).exists()
        )

    def test_staff_can_delete_foreign_attachment(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("attachment_delete", args=[self.attachment.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Attachment.objects.filter(pk=self.attachment.pk).exists()
        )

    def test_attachment_add_permissions(self):
        url = reverse("attachment_create", args=[self.answer.pk])

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.author)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_anonymous_edit_redirects_to_login(self):
        response = self.client.get(
            reverse("question_edit", args=[self.question.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
