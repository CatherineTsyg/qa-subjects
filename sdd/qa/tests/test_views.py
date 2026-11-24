from django.contrib.auth.models import User
from django.urls import reverse

from config.test_utils import CacheMediaTestCase
from qa.models import Answer, Question, Subject, Vote


class ReadingViewTests(CacheMediaTestCase):
    def setUp(self):
        super().setUp()
        self.author = User.objects.create_user(
            "author", password="StrongPass123!"
        )

    def test_subject_list_shows_names_and_question_counts(self):
        math = Subject.objects.create(name="Математика")
        Subject.objects.create(name="Физика")
        Question.objects.create(
            subject=math, author=self.author, title="Первый", body="Текст"
        )

        response = self.client.get(reverse("subject_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Математика")
        self.assertContains(response, "Физика")
        self.assertContains(response, "Вопросов: 1")
        self.assertContains(response, "Вопросов: 0")

    def test_subject_list_is_sorted_by_name(self):
        Subject.objects.create(name="Физика")
        Subject.objects.create(name="Алгебра")

        response = self.client.get(reverse("subject_list"))
        content = response.content.decode()

        self.assertLess(content.index("Алгебра"), content.index("Физика"))

    def test_subject_list_shows_empty_message(self):
        response = self.client.get(reverse("subject_list"))
        self.assertContains(response, "Пока нет ни одного предмета")

    def test_subject_detail_orders_questions_newest_first(self):
        subject = Subject.objects.create(name="Математика")
        older = Question.objects.create(
            subject=subject, author=self.author, title="Старый", body="Текст"
        )
        newer = Question.objects.create(
            subject=subject, author=self.author, title="Новый", body="Текст"
        )

        response = self.client.get(
            reverse("subject_detail", args=[subject.pk])
        )
        content = response.content.decode()

        self.assertLess(content.index(newer.title), content.index(older.title))

    def test_subject_detail_shows_empty_message(self):
        subject = Subject.objects.create(name="Математика")
        response = self.client.get(
            reverse("subject_detail", args=[subject.pk])
        )
        self.assertContains(response, "пока нет вопросов")

    def test_question_detail_orders_answers_by_rating_then_date(self):
        subject = Subject.objects.create(name="Математика")
        question = Question.objects.create(
            subject=subject, author=self.author, title="Вопрос", body="Текст"
        )
        low = Answer.objects.create(
            question=question, author=self.author, body="Низкий рейтинг"
        )
        high = Answer.objects.create(
            question=question, author=self.author, body="Высокий рейтинг"
        )
        voter = User.objects.create_user("voter", password="StrongPass123!")
        Vote.objects.create(answer=high, user=voter, value=1)

        response = self.client.get(
            reverse("question_detail", args=[question.pk])
        )
        content = response.content.decode()

        self.assertLess(
            content.index(high.body), content.index(low.body)
        )

    def test_pagination_limits_to_20_items(self):
        subject = Subject.objects.create(name="Математика")
        for index in range(21):
            Question.objects.create(
                subject=subject,
                author=self.author,
                title=f"Вопрос {index}",
                body="Текст",
            )

        first_page = self.client.get(
            reverse("subject_detail", args=[subject.pk])
        )
        second_page = self.client.get(
            reverse("subject_detail", args=[subject.pk]) + "?page=2"
        )

        self.assertEqual(len(first_page.context["page_obj"].object_list), 20)
        self.assertEqual(len(second_page.context["page_obj"].object_list), 1)

    def test_missing_objects_return_404(self):
        self.assertEqual(
            self.client.get(reverse("subject_detail", args=[999])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("question_detail", args=[999])).status_code,
            404,
        )

    def test_anonymous_can_read_question_and_answers(self):
        subject = Subject.objects.create(name="Математика")
        question = Question.objects.create(
            subject=subject, author=self.author, title="Вопрос", body="Текст"
        )
        Answer.objects.create(
            question=question, author=self.author, body="Ответ"
        )

        response = self.client.get(
            reverse("question_detail", args=[question.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ответ")

    def test_user_vote_is_shown_for_current_user(self):
        subject = Subject.objects.create(name="Математика")
        question = Question.objects.create(
            subject=subject, author=self.author, title="Вопрос", body="Текст"
        )
        answer = Answer.objects.create(
            question=question, author=self.author, body="Ответ"
        )
        voter = User.objects.create_user("voter", password="StrongPass123!")
        Vote.objects.create(answer=answer, user=voter, value=1)
        self.client.force_login(voter)

        response = self.client.get(
            reverse("question_detail", args=[question.pk])
        )

        self.assertEqual(response.context["user_votes"], {answer.pk: 1})

    def test_page_queries_are_bounded(self):
        subject = Subject.objects.create(name="Математика")
        question = Question.objects.create(
            subject=subject, author=self.author, title="Вопрос", body="Текст"
        )
        Answer.objects.create(
            question=question, author=self.author, body="Ответ"
        )

        with self.assertNumQueries(2):
            self.client.get(reverse("subject_list"))
        with self.assertNumQueries(3):
            self.client.get(reverse("subject_detail", args=[subject.pk]))
        with self.assertNumQueries(4):
            self.client.get(reverse("question_detail", args=[question.pk]))


class PublishingViewTests(CacheMediaTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            "student", password="StrongPass123!"
        )
        self.subject = Subject.objects.create(name="Математика")
        self.client.force_login(self.user)

    def test_question_can_be_created(self):
        response = self.client.post(
            reverse("question_create", args=[self.subject.pk]),
            {"title": "Новый вопрос", "body": "Текст вопроса"},
        )

        question = Question.objects.get(title="Новый вопрос")
        self.assertRedirects(
            response, reverse("question_detail", args=[question.pk])
        )
        self.assertEqual(question.author, self.user)

    def test_question_requires_title_and_body(self):
        response = self.client.post(
            reverse("question_create", args=[self.subject.pk]),
            {"title": "", "body": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.count(), 0)

    def test_question_title_length_is_limited(self):
        response = self.client.post(
            reverse("question_create", args=[self.subject.pk]),
            {"title": "x" * 201, "body": "Текст"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.count(), 0)

    def test_answer_can_be_created(self):
        question = Question.objects.create(
            subject=self.subject,
            author=self.user,
            title="Вопрос",
            body="Текст",
        )

        response = self.client.post(
            reverse("answer_create", args=[question.pk]),
            {"body": "Мой ответ"},
        )

        self.assertRedirects(
            response, reverse("question_detail", args=[question.pk])
        )
        self.assertTrue(
            Answer.objects.filter(question=question, body="Мой ответ").exists()
        )

    def test_answer_requires_body(self):
        question = Question.objects.create(
            subject=self.subject,
            author=self.user,
            title="Вопрос",
            body="Текст",
        )

        response = self.client.post(
            reverse("answer_create", args=[question.pk]), {"body": ""}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Answer.objects.count(), 0)

    def test_answer_length_is_limited(self):
        question = Question.objects.create(
            subject=self.subject,
            author=self.user,
            title="Вопрос",
            body="Текст",
        )

        response = self.client.post(
            reverse("answer_create", args=[question.pk]),
            {"body": "x" * 10001},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Answer.objects.count(), 0)

    def test_anonymous_post_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.post(
            reverse("question_create", args=[self.subject.pk]),
            {"title": "Вопрос", "body": "Текст"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertEqual(Question.objects.count(), 0)

    def test_end_to_end_registration_question_and_answer(self):
        self.client.logout()

        register_response = self.client.post(
            reverse("register"),
            {
                "username": "newstudent",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(register_response, "/")

        question_response = self.client.post(
            reverse("question_create", args=[self.subject.pk]),
            {"title": "Сквозной вопрос", "body": "Текст"},
        )
        question = Question.objects.get(title="Сквозной вопрос")
        self.assertRedirects(
            question_response,
            reverse("question_detail", args=[question.pk]),
            fetch_redirect_response=False,
        )

        answer_response = self.client.post(
            reverse("answer_create", args=[question.pk]),
            {"body": "Сквозной ответ"},
        )
        self.assertRedirects(
            answer_response,
            reverse("question_detail", args=[question.pk]),
            fetch_redirect_response=False,
        )

        self.client.logout()
        page = self.client.get(reverse("question_detail", args=[question.pk]))
        self.assertContains(page, "Сквозной вопрос")
        self.assertContains(page, "Сквозной ответ")
