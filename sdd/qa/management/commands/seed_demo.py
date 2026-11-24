from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction

from qa.models import Answer, Question, Subject

DEMO_SUBJECT_PREFIX = "Демо-предмет"


class Command(BaseCommand):
    help = "Наполняет базу детерминированными демонстрационными данными."

    def add_arguments(self, parser):
        parser.add_argument("--questions", type=int, default=10_000)
        parser.add_argument("--answers", type=int, default=100_000)
        parser.add_argument("--subjects", type=int, default=10)
        parser.add_argument("--users", type=int, default=100)

    @transaction.atomic
    def handle(self, *args, **options):
        questions_total = options["questions"]
        answers_total = options["answers"]
        subjects_total = options["subjects"]
        users_total = options["users"]

        if Subject.objects.filter(name__startswith=DEMO_SUBJECT_PREFIX).exists():
            self.stdout.write(
                self.style.WARNING(
                    "Демонстрационные данные уже существуют; наполнение пропущено."
                )
            )
            return

        subjects = Subject.objects.bulk_create(
            [
                Subject(
                    name=f"{DEMO_SUBJECT_PREFIX} {index:02d}",
                    description=f"Демонстрационный предмет {index}",
                )
                for index in range(1, subjects_total + 1)
            ]
        )

        users = []
        for index in range(1, users_total + 1):
            user = User(username=f"demo_user_{index:03d}")
            user.set_unusable_password()
            users.append(user)
        User.objects.bulk_create(users, batch_size=1000)
        users = list(User.objects.filter(username__startswith="demo_user_"))

        questions = []
        for index in range(questions_total):
            questions.append(
                Question(
                    subject=subjects[index % len(subjects)],
                    author=users[index % len(users)],
                    title=f"Демо-вопрос {index + 1}",
                    body=(
                        f"Демонстрационный вопрос {index + 1}. "
                        "Текст вопроса для проверки производительности."
                    ),
                )
            )
        Question.objects.bulk_create(questions, batch_size=1000)
        questions = list(
            Question.objects.filter(title__startswith="Демо-вопрос").order_by("id")
        )

        answers_per_question = max(1, answers_total // max(1, len(questions)))
        answers = []
        counter = 1
        for question in questions:
            for _ in range(answers_per_question):
                answers.append(
                    Answer(
                        question=question,
                        author=users[counter % len(users)],
                        body=(
                            f"Демонстрационный ответ {counter}. "
                            "Текст ответа для проверки страницы вопроса."
                        ),
                    )
                )
                counter += 1
                if len(answers) >= answers_total:
                    break
            if len(answers) >= answers_total:
                break
        Answer.objects.bulk_create(answers, batch_size=1000)

        # bulk_create не отправляет post_save, поэтому кеш очищается явно.
        cache.clear()

        self.stdout.write(
            self.style.SUCCESS(
                "Создано: "
                f"{len(subjects)} предметов, {len(questions)} вопросов, "
                f"{len(answers)} ответов, {len(users)} пользователей."
            )
        )
