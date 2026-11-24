import threading
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.db.models import Sum
from django.urls import reverse

from config.test_utils import CacheMediaTestCase, CacheMediaTransactionTestCase
from qa.cache import get_version, question_version_key
from qa.models import Answer, Question, Subject, Vote
from qa.services import vote as vote_service


class VoteViewTests(CacheMediaTestCase):
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
            question=self.question, author=self.author, body="Первый ответ"
        )

    def _rating(self):
        return self.answer.votes.aggregate(total=Sum("value"))["total"] or 0

    def test_like_creates_vote_and_increases_rating(self):
        self.client.force_login(self.voter)

        response = self.client.post(
            reverse("answer_vote", args=[self.answer.pk]),
            {"value": "like"},
        )

        self.assertRedirects(
            response, reverse("question_detail", args=[self.question.pk])
        )
        self.assertEqual(
            Vote.objects.get(answer=self.answer, user=self.voter).value, 1
        )
        self.assertEqual(self._rating(), 1)

    def test_dislike_creates_vote_and_decreases_rating(self):
        self.client.force_login(self.voter)

        self.client.post(
            reverse("answer_vote", args=[self.answer.pk]),
            {"value": "dislike"},
        )

        self.assertEqual(self._rating(), -1)

    def test_changing_vote_replaces_it(self):
        self.client.force_login(self.voter)
        self.client.post(
            reverse("answer_vote", args=[self.answer.pk]),
            {"value": "like"},
        )
        self.client.post(
            reverse("answer_vote", args=[self.answer.pk]),
            {"value": "dislike"},
        )

        self.assertEqual(Vote.objects.count(), 1)
        self.assertEqual(
            Vote.objects.get(answer=self.answer, user=self.voter).value, -1
        )
        self.assertEqual(self._rating(), -1)

    def test_repeating_same_vote_removes_it(self):
        self.client.force_login(self.voter)
        self.client.post(
            reverse("answer_vote", args=[self.answer.pk]),
            {"value": "like"},
        )
        self.client.post(
            reverse("answer_vote", args=[self.answer.pk]),
            {"value": "like"},
        )

        self.assertEqual(Vote.objects.count(), 0)
        self.assertEqual(self._rating(), 0)

    def test_own_answer_vote_is_forbidden(self):
        self.client.force_login(self.author)

        response = self.client.post(
            reverse("answer_vote", args=[self.answer.pk]),
            {"value": "like"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Vote.objects.count(), 0)

    def test_vote_for_missing_answer_returns_404(self):
        self.client.force_login(self.voter)
        answer_pk = self.answer.pk
        self.answer.delete()

        response = self.client.post(
            reverse("answer_vote", args=[answer_pk]),
            {"value": "like"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Vote.objects.count(), 0)

    def test_invalid_value_returns_400_without_changes(self):
        self.client.force_login(self.voter)

        response = self.client.post(
            reverse("answer_vote", args=[self.answer.pk]),
            {"value": "maybe"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Vote.objects.count(), 0)

    def test_vote_buttons_hidden_for_anonymous_and_author(self):
        vote_url = reverse("answer_vote", args=[self.answer.pk])

        anonymous = self.client.get(
            reverse("question_detail", args=[self.question.pk])
        )
        self.assertNotContains(anonymous, vote_url)

        self.client.force_login(self.author)
        own_answer = self.client.get(
            reverse("question_detail", args=[self.question.pk])
        )
        self.assertNotContains(own_answer, vote_url)

    def test_vote_buttons_visible_for_other_user(self):
        self.client.force_login(self.voter)

        response = self.client.get(
            reverse("question_detail", args=[self.question.pk])
        )

        self.assertContains(
            response, reverse("answer_vote", args=[self.answer.pk])
        )

    def test_answers_are_reordered_after_vote(self):
        second = Answer.objects.create(
            question=self.question, author=self.author, body="Второй ответ"
        )
        self.client.force_login(self.voter)
        self.client.post(
            reverse("answer_vote", args=[second.pk]), {"value": "like"}
        )

        response = self.client.get(
            reverse("question_detail", args=[self.question.pk])
        )
        content = response.content.decode()

        self.assertLess(
            content.index("Второй ответ"), content.index("Первый ответ")
        )

    def test_vote_invalidates_cache_after_commit(self):
        self.client.force_login(self.voter)
        self.client.get(reverse("question_detail", args=[self.question.pk]))
        old_version = get_version(question_version_key(self.question.pk))

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("answer_vote", args=[self.answer.pk]),
                {"value": "like"},
            )

        self.assertGreater(
            get_version(question_version_key(self.question.pk)), old_version
        )


class ConcurrentVoteTests(CacheMediaTransactionTestCase):
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
            question=self.question, author=self.author, body="Первый ответ"
        )

    def _worker(self, value, barrier, errors):
        close_old_connections()
        try:
            user = User.objects.get(pk=self.voter.pk)
            answer = Answer.objects.get(pk=self.answer.pk)
            barrier.wait(timeout=10)
            vote_service(user, answer, value)
        except Exception as exc:  # pragma: no cover - сообщение в assertion
            errors.append(exc)
        finally:
            close_old_connections()

    def test_concurrent_votes_do_not_create_duplicates_or_fail(self):
        barrier = threading.Barrier(2)
        errors = []

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(self._worker, value, barrier, errors)
                for value in (1, 1)
            ]
            for future in futures:
                future.result(timeout=20)

        self.assertEqual(errors, [])
        self.assertLessEqual(
            Vote.objects.filter(
                answer=self.answer, user=self.voter
            ).count(),
            1,
        )
