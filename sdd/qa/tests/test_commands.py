from io import StringIO

from django.core.management import call_command

from config.test_utils import CacheMediaTestCase
from qa.models import Answer, Question, Subject


class SeedDemoCommandTests(CacheMediaTestCase):
    def test_seed_creates_requested_volume_and_is_idempotent(self):
        output = StringIO()
        options = {
            "questions": 4,
            "answers": 8,
            "subjects": 2,
            "users": 2,
            "stdout": output,
        }

        call_command("seed_demo", **options)

        self.assertEqual(
            Subject.objects.filter(name__startswith="Демо-предмет").count(),
            2,
        )
        self.assertEqual(Question.objects.count(), 4)
        self.assertEqual(Answer.objects.count(), 8)

        call_command("seed_demo", **options)

        self.assertEqual(Question.objects.count(), 4)
        self.assertEqual(Answer.objects.count(), 8)
        self.assertIn("уже существуют", output.getvalue())
