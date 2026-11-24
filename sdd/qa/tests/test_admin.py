from django.contrib.auth.models import User
from django.urls import reverse

from config.test_utils import CacheMediaTestCase
from qa.models import Question, Subject


class AdminSubjectDeleteTests(CacheMediaTestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_superuser(
            "staff", "staff@example.com", "StrongPass123!"
        )
        self.client.force_login(self.staff)
        self.author = User.objects.create_user(
            "author", password="StrongPass123!"
        )

    def test_non_empty_subject_is_not_deleted_and_message_is_shown(self):
        subject = Subject.objects.create(name="Математика")
        Question.objects.create(
            subject=subject,
            author=self.author,
            title="Вопрос",
            body="Текст",
        )

        response = self.client.post(
            reverse("admin:qa_subject_delete", args=[subject.pk]),
            {"post": "yes"},
            follow=True,
        )

        self.assertTrue(Subject.objects.filter(pk=subject.pk).exists())
        self.assertContains(
            response, "Нельзя удалить предмет, в котором есть вопросы"
        )

    def test_empty_subject_is_deleted(self):
        subject = Subject.objects.create(name="Физика")

        response = self.client.post(
            reverse("admin:qa_subject_delete", args=[subject.pk]),
            {"post": "yes"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Subject.objects.filter(pk=subject.pk).exists())
