from django.core.cache import cache

PAGE_TTL = 300

SUBJECTS_VERSION_KEY = "qa:v1:subjects:list:version"


def subjects_page_key(version, page_number):
    return f"qa:v1:subjects:list:v{version}:page:{page_number}"


def question_version_key(question_id):
    return f"qa:v1:question:{question_id}:answers:version"


def question_page_key(question_id, version, page_number):
    return f"qa:v1:question:{question_id}:answers:v{version}:page:{page_number}"


def get_version(key):
    """Версия набора; до первой инвалидации равна 1."""
    return cache.get(key) or 1


def bump_version(key):
    """Атомарно увеличивает версию, делая старые страницы недостижимыми."""
    cache.add(key, 1, timeout=None)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 2, timeout=None)


def get_cached_page(key):
    return cache.get(key)


def set_cached_page(key, value):
    cache.set(key, value, PAGE_TTL)
