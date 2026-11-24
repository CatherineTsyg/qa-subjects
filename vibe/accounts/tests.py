from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class RegistrationTests(TestCase):
    def test_register_page_renders(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Регистрация")

    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("qa:subject_list"))
        user = User.objects.get(username="newuser")
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(
            int(self.client.session["_auth_user_id"]), user.pk
        )

    def test_register_rejects_password_mismatch(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "password1": "StrongPass123!",
                "password2": "AnotherPass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newuser").exists())


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="StrongPass123!"
        )

    def test_login(self):
        response = self.client.post(
            reverse("login"),
            {"username": "alice", "password": "StrongPass123!"},
        )
        self.assertRedirects(response, "/")
        self.assertEqual(
            int(self.client.session["_auth_user_id"]), self.user.pk
        )

    def test_login_with_wrong_password(self):
        response = self.client.post(
            reverse("login"),
            {"username": "alice", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        get_response = self.client.get(reverse("logout"))
        self.assertEqual(get_response.status_code, 405)

        post_response = self.client.post(reverse("logout"))
        self.assertRedirects(post_response, "/")
        self.assertNotIn("_auth_user_id", self.client.session)
