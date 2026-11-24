import shutil
import tempfile

from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings

LOCMEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "qa-tests",
    }
}


def run_commit_callbacks(callbacks):
    for callback in callbacks:
        callback()



class TempMediaMixin:
    """Подменяет MEDIA_ROOT временным каталогом и удаляет его после тестов."""

    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp(prefix="qa-media-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)


@override_settings(CACHES=LOCMEM_CACHES)
class CacheMediaTestCase(TempMediaMixin, TestCase):
    def setUp(self):
        cache.clear()
        super().setUp()


@override_settings(CACHES=LOCMEM_CACHES)
class CacheMediaTransactionTestCase(TempMediaMixin, TransactionTestCase):
    def setUp(self):
        cache.clear()
        super().setUp()
