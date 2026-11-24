from django.contrib.auth.models import User
from django.urls import reverse

from config.test_utils import CacheMediaTestCase


class AuthenticationTests(CacheMediaTestCase):
    def test_registration_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "student",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, "/")
        self.assertTrue(User.objects.filter(username="student").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_registration_rejects_duplicate_username(self):
        User.objects.create_user("student", password="StrongPass123!")

        response = self.client.post(
            reverse("register"),
            {
                "username": "student",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "уже существует")
        self.assertEqual(User.objects.filter(username="student").count(), 1)

    def test_registration_rejects_password_mismatch(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "student",
                "password1": "StrongPass123!",
                "password2": "OtherPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="student").exists())

    def test_login_with_valid_credentials(self):
        User.objects.create_user("student", password="StrongPass123!")

        response = self.client.post(
            reverse("login"),
            {"username": "student", "password": "StrongPass123!"},
        )

        self.assertRedirects(response, "/")
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_with_invalid_credentials_is_rejected(self):
        User.objects.create_user("student", password="StrongPass123!")

        response = self.client.post(
            reverse("login"),
            {"username": "student", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "Неверное имя пользователя или пароль")

    def test_logout_requires_post(self):
        user = User.objects.create_user("student", password="StrongPass123!")
        self.client.force_login(user)

        get_response = self.client.get(reverse("logout"))
        self.assertEqual(get_response.status_code, 405)

        post_response = self.client.post(reverse("logout"))
        self.assertRedirects(post_response, "/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_anonymous_is_redirected_to_login(self):
        from qa.models import Subject

        subject = Subject.objects.create(name="Математика")
        response = self.client.get(
            reverse("question_create", args=[subject.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
