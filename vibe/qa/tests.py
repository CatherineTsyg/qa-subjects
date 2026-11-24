import os
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Answer,
    AnswerVote,
    Attachment,
    Question,
    Subject,
)
from .validators import validate_file_size


class MediaTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.media_dir = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(shutil.rmtree, self.media_dir, ignore_errors=True)


class BaseQaTestCase(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.author = User.objects.create_user(
            username="alice", password="StrongPass123!"
        )
        self.other = User.objects.create_user(
            username="bob", password="StrongPass123!"
        )
        self.staff = User.objects.create_user(
            username="moderator",
            password="StrongPass123!",
            is_staff=True,
        )
        self.subject = Subject.objects.create(
            name="Математика", slug="matematika", description="Алгебра и геометрия"
        )
        self.question = Question.objects.create(
            subject=self.subject,
            author=self.author,
            title="Что такое производная?",
            body="Объясните простыми словами.",
        )
        self.answer = Answer.objects.create(
            question=self.question,
            author=self.other,
            body="Производная — это скорость изменения функции.",
        )


class SubjectViewTests(BaseQaTestCase):
    def test_subject_list_shows_subjects_with_question_count(self):
        response = self.client.get(reverse("qa:subject_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Математика")
        self.assertEqual(response.context["subjects"][0].question_count, 1)

    def test_subject_detail_lists_questions(self):
        response = self.client.get(
            reverse("qa:subject_detail", kwargs={"slug": self.subject.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.question.title)
        self.assertEqual(response.context["questions"][0].answer_count, 1)

    def test_question_detail_sorts_answers_by_rating(self):
        better_answer = Answer.objects.create(
            question=self.question,
            author=self.author,
            body="Более полный ответ.",
        )
        AnswerVote.objects.create(
            answer=better_answer, user=self.author, value=AnswerVote.LIKE
        )
        AnswerVote.objects.create(
            answer=better_answer, user=self.staff, value=AnswerVote.LIKE
        )
        AnswerVote.objects.create(
            answer=self.answer, user=self.staff, value=AnswerVote.DISLIKE
        )

        response = self.client.get(self.question.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        answers = list(response.context["answers"])
        self.assertEqual(answers[0].pk, better_answer.pk)
        self.assertEqual(answers[0].rating, 2)
        self.assertEqual(answers[0].like_count, 2)
        self.assertEqual(answers[1].rating, -1)

    def test_question_detail_shows_attachment_name(self):
        Attachment.objects.create(
            answer=self.answer,
            file=SimpleUploadedFile(
                "notes.pdf", b"%PDF-1.4 test", content_type="application/pdf"
            ),
            original_name="notes.pdf",
        )
        response = self.client.get(self.question.get_absolute_url())
        self.assertContains(response, "notes.pdf")

    def test_anonymous_sees_login_prompt_instead_of_answer_form(self):
        response = self.client.get(self.question.get_absolute_url())
        self.assertContains(response, "чтобы ответить")
        self.assertNotContains(response, "Отправить ответ")


class QuestionCrudTests(BaseQaTestCase):
    def test_create_question_requires_login(self):
        response = self.client.post(
            reverse("qa:question_create"),
            {"subject": self.subject.pk, "title": "Новый", "body": "Текст"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('login')}?next={reverse('qa:question_create')}",
        )
        self.assertEqual(Question.objects.count(), 1)

    def test_authenticated_user_can_create_question(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("qa:question_create"),
            {
                "subject": self.subject.pk,
                "title": "Новый вопрос",
                "body": "Подробности",
            },
        )
        question = Question.objects.get(title="Новый вопрос")
        self.assertRedirects(response, question.get_absolute_url())
        self.assertEqual(question.author, self.other)

    def test_question_form_preselects_subject_from_query_string(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse("qa:question_create"), {"subject": self.subject.slug}
        )
        self.assertEqual(
            response.context["form"].initial["subject"], self.subject
        )

    def test_only_author_or_staff_can_update_question(self):
        url = reverse("qa:question_update", kwargs={"pk": self.question.pk})

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.author)
        response = self.client.post(
            url,
            {
                "subject": self.subject.pk,
                "title": "Обновлённый вопрос",
                "body": "Новый текст",
            },
        )
        self.assertRedirects(response, self.question.get_absolute_url())
        self.question.refresh_from_db()
        self.assertEqual(self.question.title, "Обновлённый вопрос")

    def test_only_author_or_staff_can_delete_question(self):
        url = reverse("qa:question_delete", kwargs={"pk": self.question.pk})

        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Question.objects.filter(pk=self.question.pk).exists())

        self.client.force_login(self.author)
        response = self.client.post(url)
        self.assertRedirects(response, self.subject.get_absolute_url())
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())

    def test_deleting_question_removes_attachment_files(self):
        attachment = Attachment.objects.create(
            answer=self.answer,
            file=SimpleUploadedFile(
                "notes.txt", b"notes", content_type="text/plain"
            ),
            original_name="notes.txt",
        )
        file_path = attachment.file.path
        self.assertTrue(os.path.exists(file_path))

        self.client.force_login(self.author)
        self.client.post(
            reverse("qa:question_delete", kwargs={"pk": self.question.pk})
        )
        self.assertFalse(os.path.exists(file_path))


class AnswerCrudTests(BaseQaTestCase):
    def test_create_answer_requires_login(self):
        response = self.client.post(
            reverse("qa:answer_create", kwargs={"pk": self.question.pk}),
            {"body": "Анонимный ответ"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Answer.objects.count(), 1)

    def test_create_answer_with_attachments(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("qa:answer_create", kwargs={"pk": self.question.pk}),
            {
                "body": "Ответ с файлами",
                "files": [
                    SimpleUploadedFile(
                        "photo.jpg",
                        b"\xff\xd8\xff\xe0fake-jpeg",
                        content_type="image/jpeg",
                    ),
                    SimpleUploadedFile(
                        "document.pdf",
                        b"%PDF-1.4 test",
                        content_type="application/pdf",
                    ),
                ],
            },
        )
        answer = Answer.objects.get(body="Ответ с файлами")
        self.assertEqual(answer.author, self.other)
        self.assertEqual(answer.attachments.count(), 2)
        expected = f"{self.question.get_absolute_url()}#answer-{answer.pk}"
        self.assertRedirects(response, expected)
        attachment = answer.attachments.get(original_name="photo.jpg")
        self.assertTrue(attachment.is_image)

    def test_create_answer_rejects_forbidden_extension(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("qa:answer_create", kwargs={"pk": self.question.pk}),
            {
                "body": "Ответ с вирусом",
                "files": SimpleUploadedFile(
                    "virus.exe", b"MZ", content_type="application/octet-stream"
                ),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("files", response.context["form"].errors)
        self.assertFalse(Answer.objects.filter(body="Ответ с вирусом").exists())

    @override_settings(MAX_UPLOAD_SIZE=10)
    def test_create_answer_rejects_oversized_file(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("qa:answer_create", kwargs={"pk": self.question.pk}),
            {
                "body": "Ответ с большим файлом",
                "files": SimpleUploadedFile(
                    "big.txt", b"x" * 11, content_type="text/plain"
                ),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("files", response.context["form"].errors)
        self.assertFalse(
            Answer.objects.filter(body="Ответ с большим файлом").exists()
        )

    def test_only_author_or_staff_can_update_answer(self):
        url = reverse("qa:answer_update", kwargs={"pk": self.answer.pk})

        self.client.force_login(self.author)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.other)
        response = self.client.post(url, {"body": "Исправленный ответ"})
        self.assertEqual(response.status_code, 302)
        self.answer.refresh_from_db()
        self.assertEqual(self.answer.body, "Исправленный ответ")

    def test_only_author_or_staff_can_delete_answer(self):
        url = reverse("qa:answer_delete", kwargs={"pk": self.answer.pk})

        self.client.force_login(self.author)
        self.assertEqual(self.client.post(url).status_code, 403)

        self.client.force_login(self.other)
        response = self.client.post(url)
        self.assertRedirects(response, self.question.get_absolute_url())
        self.assertFalse(Answer.objects.filter(pk=self.answer.pk).exists())

    def test_attachment_delete_permissions(self):
        attachment = Attachment.objects.create(
            answer=self.answer,
            file=SimpleUploadedFile(
                "doc.txt", b"hello", content_type="text/plain"
            ),
            original_name="doc.txt",
        )
        url = reverse(
            "qa:attachment_delete", kwargs={"pk": attachment.pk}
        )

        self.client.force_login(self.author)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Attachment.objects.filter(pk=attachment.pk).exists())

        self.client.force_login(self.other)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Attachment.objects.filter(pk=attachment.pk).exists())


class VotingTests(BaseQaTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse(
            "qa:answer_vote", kwargs={"pk": self.answer.pk}
        )

    def test_vote_requires_login(self):
        response = self.client.post(self.url, {"value": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AnswerVote.objects.exists())

    def test_vote_requires_post(self):
        self.client.force_login(self.other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_like_then_toggle_then_dislike(self):
        self.client.force_login(self.author)

        response = self.client.post(self.url, {"value": "1"})
        self.assertEqual(response.status_code, 302)
        vote = AnswerVote.objects.get(answer=self.answer, user=self.author)
        self.assertEqual(vote.value, AnswerVote.LIKE)

        self.client.post(self.url, {"value": "1"})
        self.assertFalse(AnswerVote.objects.exists())

        self.client.post(self.url, {"value": "-1"})
        vote = AnswerVote.objects.get(answer=self.answer, user=self.author)
        self.assertEqual(vote.value, AnswerVote.DISLIKE)

        self.client.post(self.url, {"value": "1"})
        vote.refresh_from_db()
        self.assertEqual(vote.value, AnswerVote.LIKE)
        self.assertEqual(
            AnswerVote.objects.filter(
                answer=self.answer, user=self.author
            ).count(),
            1,
        )

    def test_invalid_vote_value_is_rejected(self):
        self.client.force_login(self.author)
        response = self.client.post(self.url, {"value": "5"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AnswerVote.objects.exists())

    def test_anonymous_cannot_see_active_vote_buttons(self):
        response = self.client.get(self.question.get_absolute_url())
        self.assertContains(response, "disabled")


class VoteConstraintTests(BaseQaTestCase):
    def test_vote_is_unique_per_user_and_answer(self):
        AnswerVote.objects.create(
            answer=self.answer, user=self.author, value=AnswerVote.LIKE
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AnswerVote.objects.create(
                    answer=self.answer,
                    user=self.author,
                    value=AnswerVote.DISLIKE,
                )

    def test_vote_value_check_constraint(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AnswerVote.objects.create(
                    answer=self.answer, user=self.author, value=0
                )


class AttachmentValidatorTests(MediaTestCase):
    @override_settings(MAX_UPLOAD_SIZE=5)
    def test_size_validator(self):
        big_file = SimpleUploadedFile(
            "big.txt", b"123456", content_type="text/plain"
        )
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            validate_file_size(big_file)


class AdminSmokeTests(BaseQaTestCase):
    def test_admin_pages_open(self):
        superuser = User.objects.create_superuser(
            username="root", password="StrongPass123!"
        )
        self.client.force_login(superuser)
        urls = [
            reverse("admin:index"),
            reverse("admin:qa_subject_changelist"),
            reverse("admin:qa_subject_add"),
            reverse("admin:qa_question_changelist"),
            reverse("admin:qa_question_add"),
            reverse("admin:qa_answer_changelist"),
            reverse("admin:qa_answer_add"),
            reverse("admin:qa_answervote_changelist"),
            reverse("admin:qa_answervote_add"),
            reverse("admin:qa_attachment_changelist"),
            reverse("admin:qa_attachment_add"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
