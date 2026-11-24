from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse

from config.test_utils import CacheMediaTestCase, run_commit_callbacks
from qa.cache import (
    SUBJECTS_VERSION_KEY,
    get_version,
    question_page_key,
    question_version_key,
    subjects_page_key,
)
from qa.models import Answer, Question, Subject, Vote


class CacheTests(CacheMediaTestCase):
    def setUp(self):
        super().setUp()
        self.author = User.objects.create_user(
            "author", password="StrongPass123!"
        )
        self.subject = Subject.objects.create(name="Математика")

    def test_get_version_defaults_to_one(self):
        self.assertEqual(get_version(SUBJECTS_VERSION_KEY), 1)
        self.assertIsNone(cache.get(SUBJECTS_VERSION_KEY))

    def test_first_request_uses_version_one_and_does_not_create_vnone(self):
        response = self.client.get(reverse("subject_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(cache.get(subjects_page_key(1, 1)))
        self.assertIsNone(cache.get(subjects_page_key(None, 1)))
        self.assertIsNone(cache.get("qa:v1:subjects:list:vNone:page:1"))

    def test_pages_are_cached_separately(self):
        for index in range(25):
            Subject.objects.create(name=f"Предмет {index:02d}")

        self.client.get(reverse("subject_list"))
        self.client.get(reverse("subject_list") + "?page=2")

        self.assertIsNotNone(cache.get(subjects_page_key(1, 1)))
        self.assertIsNotNone(cache.get(subjects_page_key(1, 2)))

    def test_version_bump_invalidates_all_pages_after_commit(self):
        self.client.get(reverse("subject_list"))
        old_version = get_version(SUBJECTS_VERSION_KEY)

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            Subject.objects.create(name="Физика")
            self.assertEqual(get_version(SUBJECTS_VERSION_KEY), old_version)

        run_commit_callbacks(callbacks)
        new_version = get_version(SUBJECTS_VERSION_KEY)

        self.assertGreater(new_version, old_version)
        response = self.client.get(reverse("subject_list"))
        self.assertContains(response, "Физика")

    def test_admin_change_invalidates_cache(self):
        staff = User.objects.create_superuser(
            "staff", "staff@example.com", "StrongPass123!"
        )
        self.client.force_login(staff)
        self.client.get(reverse("subject_list"))
        old_version = get_version(SUBJECTS_VERSION_KEY)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("admin:qa_subject_change", args=[self.subject.pk]),
                {"name": "Математика и логика", "description": ""},
            )

        self.assertGreater(get_version(SUBJECTS_VERSION_KEY), old_version)

    def test_cascade_user_delete_invalidates_cache(self):
        author = User.objects.create_user(
            "second", password="StrongPass123!"
        )
        Question.objects.create(
            subject=self.subject, author=author, title="Вопрос", body="Текст"
        )
        self.client.get(reverse("subject_list"))
        old_version = get_version(SUBJECTS_VERSION_KEY)

        with self.captureOnCommitCallbacks(execute=True):
            author.delete()

        self.assertGreater(get_version(SUBJECTS_VERSION_KEY), old_version)

    def test_question_answers_page_is_cached(self):
        question = Question.objects.create(
            subject=self.subject,
            author=self.author,
            title="Вопрос",
            body="Текст",
        )
        Answer.objects.create(
            question=question, author=self.author, body="Первый ответ"
        )
        self.client.get(reverse("question_detail", args=[question.pk]))

        version = get_version(question_version_key(question.pk))
        cached = cache.get(question_page_key(question.pk, version, 1))
        self.assertIsNotNone(cached)
        self.assertEqual(cached["items"][0]["body"], "Первый ответ")

        Answer.objects.filter(question=question).update(body="Изменено в обход")
        response = self.client.get(
            reverse("question_detail", args=[question.pk])
        )
        self.assertContains(response, "Первый ответ")
        self.assertNotContains(response, "Изменено в обход")

    def test_user_vote_is_not_part_of_cached_page(self):
        question = Question.objects.create(
            subject=self.subject,
            author=self.author,
            title="Вопрос",
            body="Текст",
        )
        answer = Answer.objects.create(
            question=question, author=self.author, body="Ответ"
        )
        voter = User.objects.create_user("voter", password="StrongPass123!")
        Vote.objects.create(answer=answer, user=voter, value=1)

        self.client.get(reverse("question_detail", args=[question.pk]))
        version = get_version(question_version_key(question.pk))
        cached = cache.get(question_page_key(question.pk, version, 1))

        self.assertNotIn("user_votes", cached)
        self.assertNotIn("user_vote", cached)
        self.assertNotIn("voter", str(cached))

    def test_question_cache_stays_until_on_commit_callbacks_run(self):
        question = Question.objects.create(
            subject=self.subject,
            author=self.author,
            title="Вопрос",
            body="Текст",
        )
        Answer.objects.create(
            question=question, author=self.author, body="Старый ответ"
        )
        self.client.get(reverse("question_detail", args=[question.pk]))
        version = get_version(question_version_key(question.pk))
        key = question_page_key(question.pk, version, 1)

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            Answer.objects.create(
                question=question, author=self.author, body="Новый ответ"
            )
            self.assertIsNotNone(cache.get(key))

        run_commit_callbacks(callbacks)
        self.assertGreater(
            get_version(question_version_key(question.pk)), version
        )
