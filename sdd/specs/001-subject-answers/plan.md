# Implementation Plan: База ответов по предметам

**Branch**: `001-subject-answers` | **Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-subject-answers/spec.md`

## Summary

Серверное веб-приложение на Django 5.x для подготовки к экзаменам: staff заводит предметы,
пользователи регистрируются, задают вопросы и пишут ответы, голосуют лайком/дизлайком, а автор
или staff управляют своими материалами. Рейтинг ответа не хранится, а вычисляется агрегатом по
голосам. Список предметов со счётчиками вопросов и отсортированный список ответов вопроса
кешируются в Valkey; инвалидация выполняется только после коммита через `transaction.on_commit`
в сигналах моделей `post_save`/`post_delete`, поэтому срабатывает и для админки, и для каскадных
удалений. Вложения хранятся в docker volume и проверяются по расширению, содержимому, размеру и
количеству.

Технический подход: два Django-приложения (`accounts`, `qa`), PostgreSQL 16, Valkey 8 как
`RedisCache`, Docker Compose с сервисами `web`, `db`, `valkey` и healthcheck, веб-порт `8001`.
Тесты — `django.test.TestCase` с `LocMemCache`; для `transaction.on_commit` и гонок —
`TestCase.captureOnCommitCallbacks` или `TransactionTestCase`.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Django 5.x (5.2 LTS, точный патч фиксируется в `requirements.txt`);
`psycopg[binary]` 3.x; `redis` (клиент для `django.core.cache.backends.redis.RedisCache`);
`gunicorn` (WSGI-сервер при `DEBUG=False`); `whitenoise` (отдача статики админки без отдельного
сервиса). Дополнительных библиотек для валидации файлов не требуется — проверка сигнатур
реализуется стандартной библиотекой.

**Storage**: PostgreSQL 16 (данные), Valkey 8 (кеш Django), docker volume `media_data`
(вложения), docker volume `postgres_data`.

**Testing**: `django.test.TestCase` + `django.core.cache.backends.locmem.LocMemCache`;
`TransactionTestCase` и `TestCase.captureOnCommitCallbacks` для сценариев с коммитом и гонками.
Запуск: `docker compose exec web python manage.py test`.

**Target Platform**: Linux-контейнеры, Docker Compose v2; браузерный клиент.

**Project Type**: web-приложение (server-rendered Django, без отдельного frontend).

**Performance Goals**: 95% открытий списка предметов, страницы предмета и страницы вопроса —
менее 1 с при 10 000 вопросов и 100 000 ответов; 100 одновременно активных пользователей;
отсутствие N+1 запросов на кешируемых страницах.

**Constraints**: только `sdd/`; секреты из env; `DEBUG=False` по умолчанию; CSRF на всех POST;
изменения — только автор или staff; инвалидация кеша только через `transaction.on_commit` в
сигналах моделей; лимиты вложений 5 файлов / 5 МБ (изображения) / 10 МБ (документы); порт `8001`.
`collectstatic` на этапе сборки образа выполняется с фиктивным `SECRET_KEY`, который передаётся
только в команду `RUN` и не сохраняется в образе.

**Scale/Scope**: 10 000 вопросов, 100 000 ответов, 100 одновременных пользователей; 2
Django-приложения, 5 моделей домена, 5 пользовательских историй уровня UI.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Принцип | Проверка | Статус |
|---------|----------|--------|
| I. Изоляция версий | Все артефакты и код — в `sdd/`; `vibe/` не читается и не импортируется | PASS |
| II. Стек и Compose | Python 3.12, Django 5.x, PostgreSQL 16, Valkey 8, сервисы `web`/`db`/`valkey` с healthcheck, порт `8001`, зависимости закреплены | PASS |
| III. Безопасность | Секреты только из env, `DEBUG=False`, CSRF на POST, права автора/staff, проверка загрузок, файлы не раскрывают путь на диске; персональные голоса не попадают в кеш | PASS |
| IV. Целостность данных | `UniqueConstraint` на голос, `CheckConstraint` на значение, `PROTECT` для непустого предмета, `transaction.atomic` для изменений, рейтинг — агрегат; инвалидация регистрируется в сигналах моделей | PASS |
| V. Производительность и кеш | `select_related`/`prefetch_related`/`annotate`, Valkey с версионными ключами страниц, инвалидация через `transaction.on_commit` в `post_save`/`post_delete` | PASS |
| VI. Тестирование | `TestCase` + `LocMemCache`; `captureOnCommitCallbacks`/`TransactionTestCase` для `on_commit` и гонок; тесты инвалидации через админку, каскадное удаление и пагинацию | PASS |
| VII. Простота | Штатные auth/admin/forms/ORM; `gunicorn` и `whitenoise` — минимально необходимые для работы при `DEBUG=False`; иных зависимостей нет | PASS |

Нарушений нет. Complexity Tracking не заполняется.

**Post-design re-check (Phase 1)**: PASS — модель данных, контракты и quickstart не вводят
нарушений; инвалидация кеша остаётся только в `transaction.on_commit` внутри сигналов,
персональные голоса не кешируются, тестовая стратегия соответствует принципу VI.

## Project Structure

### Documentation (this feature)

```text
specs/001-subject-answers/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── http-endpoints.md
├── checklists/
│   └── requirements.md
└── spec.md
```

### Source Code (repository root)

```text
sdd/
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── config/
│   ├── __init__.py
│   ├── settings.py          # env-only конфигурация
│   ├── test_utils.py        # LocMemCache и временный MEDIA_ROOT
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── accounts/
│   ├── forms.py             # регистрация и вход
│   ├── views.py             # register / login / logout
│   ├── urls.py
│   ├── tests/
│   │   └── test_auth.py
│   └── templates/accounts/
│       ├── register.html
│       └── login.html
├── qa/
│   ├── models.py            # Subject, Question, Answer, Vote, Attachment
│   ├── admin.py
│   ├── forms.py             # QuestionForm, AnswerForm, AttachmentForm
│   ├── validators.py        # расширение, MIME, сигнатура, размер, пустота
│   ├── cache.py             # версионные ключи, get_version, bump-функции
│   ├── services.py          # голосование (savepoint), вложения, удаление
│   ├── views.py
│   ├── urls.py
│   ├── signals.py           # on_commit-инвалидация, Vote: question_id в сигнале
│   ├── management/
│   │   └── commands/
│   │       └── seed_demo.py # 10 000 вопросов, 100 000 ответов
│   ├── migrations/
│   ├── templates/qa/
│   │   ├── subject_list.html
│   │   ├── subject_detail.html
│   │   ├── question_detail.html
│   │   ├── question_form.html
│   │   ├── answer_form.html
│   │   ├── attachment_form.html
│   │   └── confirm_delete.html
│   └── tests/
│       ├── test_models.py
│       ├── test_views.py
│       ├── test_permissions.py
│       ├── test_votes.py
│       ├── test_attachments.py
│       ├── test_cache.py
│       ├── test_admin.py
│       ├── test_csrf.py
│       └── test_commands.py
├── scripts/
│   └── benchmark_pages.py   # p95, urllib + ThreadPoolExecutor
├── static/
│   └── css/
│       └── app.css
└── templates/
    └── base.html
```

**Structure Decision**: Single-project Django web application внутри `sdd/`. Домен вынесен в
`qa`, аутентификация и регистрация — в `accounts`; общий шаблон — в `templates/base.html`.
Ключи кеша и bump-функции находятся в `qa/cache.py`, планирование инвалидации после коммита — в
`qa/signals.py`, изменяющие операции — в `qa/services.py`; тестовые утилиты — в
`config/test_utils.py`.

## Design Overview

### Маршруты и представления

- Список предметов и страницы чтения — публичные, server-rendered, с пагинацией по 20.
- Создание/редактирование/удаление — только через POST с CSRF; аноним перенаправляется на вход,
  пользователь без прав получает `403`.
- Голосование — отдельный POST на ответ; повторное нажатие того же значения снимает голос.
- Вложения: добавление — только автор ответа, удаление — автор ответа или staff; скачивание —
  через `FileResponse` с `Content-Type` из проверенного `content_type`: документы отдаются с
  `Content-Disposition: attachment`, изображения — inline; путь на диске не раскрывается.
- Healthcheck `GET /healthz/` для docker healthcheck; проверка выполняется Python-скриптом
  (`urllib.request`), `localhost` входит в `ALLOWED_HOSTS`.

### Кеш

Ключи включают номер страницы, а инвалидация выполняется через версию ключа, поэтому удаляются
все страницы сразу:

| Назначение | Ключ |
|------------|------|
| Версия списка предметов | `qa:v1:subjects:list:version` |
| Страница списка предметов | `qa:v1:subjects:list:v{version}:page:{n}` |
| Версия ответов вопроса | `qa:v1:question:{id}:answers:version` |
| Страница ответов вопроса | `qa:v1:question:{id}:answers:v{version}:page:{n}` |

Ключи версий хранятся без TTL. `get_version(key)` возвращает `cache.get(key) or 1`, поэтому
первый запрос без ключа версии использует версию `1` и не создаёт ключ `vNone`. Инвалидация
выполняет атомарную последовательность `cache.add(version_key, 1)` и `cache.incr(version_key)`:
версия создаётся при первом изменении и увеличивается на каждом следующем. Старые страницы
становятся недостижимы сразу и удаляются по TTL (300 секунд). Шаблонное удаление
(`delete_pattern`) не используется: встроенный `RedisCache` его не предоставляет, а версия
надёжнее и атомарна.

Нормативная таблица «событие модели → инвалидируемые версии» находится в
[контрактах](./contracts/http-endpoints.md#кеш-и-побочные-эффекты-нормативная-таблица-инвалидации);
plan.md и data-model.md не дублируют её. Инвалидация регистрируется в `qa/signals.py` для
`post_save`/`post_delete` всех доменных моделей и выполняется через `transaction.on_commit`.
В обработчике `Vote` идентификатор вопроса вычисляется в момент сигнала
(`instance.answer.question_id`) и передаётся в лямбду, потому что при каскадном удалении ответа
к моменту коммита связь уже недоступна.

Сигналы срабатывают и при изменениях через админку, и при каскадных удалениях (например,
удаление пользователя удаляет его вопросы, ответы, голоса и вложения). Подключение
`post_delete`-приёмников отключает fast-delete Django, поэтому каскад не пропускает сигналы.
Для `raw=True` (загрузка фикстур) обработчик ничего не делает.

Кешируются только общие данные: текст ответа, автор, дата, рейтинг и метаданные вложений.
Голос текущего пользователя в кеш не попадает: после чтения страницы из кеша одним отдельным
запросом выбираются голоса пользователя для ответов этой страницы и передаются в шаблон для
подсветки кнопок. Для анонима этот запрос не выполняется.

### Целостность и права

- `Vote`: `UniqueConstraint(user, answer)` и `CheckConstraint(value in {1, -1})`.
- `Subject`: удаление запрещено при наличии вопросов (`on_delete=PROTECT` + понятное сообщение
  в админке).
- `Question`/`Answer`: каскадное удаление зависимых объектов; файлы вложений удаляются сигналом.
- Проверка прав выполняется на сервере в каждом изменяющем представлении, UI — не защита.
- Голосование: внешний `transaction.atomic`; вставка голоса выполняется во вложенном
  `transaction.atomic` (точка сохранения), чтобы `IntegrityError` откатил только попытку, а не всю
  транзакцию PostgreSQL; после конфликта — повтор обновлением. В итоге не более одного голоса.

### Тестирование

- Общая инфраструктура: `sdd/config/test_utils.py` задаёт `LocMemCache` и временный `MEDIA_ROOT`
  через `tempfile.mkdtemp()` с очисткой после тестов; её используют все тестовые классы, включая
  `TransactionTestCase`.
- Модели и ограничения БД: уникальность голоса, допустимые значения, `PROTECT` предмета,
  каскады.
- Представления: чтение без входа, публикация, редактирование, права автора/staff, `403/404`.
- Админка: удаление непустого предмета не выполняется и показывает сообщение, пустой удаляется.
- Голосование: лайк, дизлайк, смена, снятие, запрет самоголосования, одновременные голоса,
  голос за удалённый ответ (`404`), недопустимое значение (`400`).
- Вложения: расширение, MIME, сигнатура, пустой файл, размер, количество, права, скачивание.
- CSRF: `Client(enforce_csrf_checks=True)` для создания, редактирования, удаления, голоса,
  вложений и выхода — отказ `403` без изменения данных.
- Кеш: попадание, `get_version()` по умолчанию, инвалидация после коммита (до выполнения callback
  ключ сохраняется), отсутствие инвалидации при неуспешной операции, смена страницы, инвалидация
  всех страниц через версию, инвалидация при изменении через админку и при каскадном удалении
  пользователя.
- Персональные данные: голос текущего пользователя не кешируется и отображается отдельно для
  каждого пользователя при общем кеше страницы.
- Производительность: `assertNumQueries` для страниц списка и ответов, включая отдельный запрос
  голосов пользователя; management-команда `seed_demo` наполняет 10 000 вопросов и 100 000
  ответов, скрипт `scripts/benchmark_pages.py` измеряет p95 времени ответа трёх страниц при 100
  потоках через `urllib` и `ThreadPoolExecutor`, результат фиксируется в `quickstart.md`.
- Management-команда `seed_demo`: создаёт заданный объём данных и идемпотентна при повторном
  запуске.

## Complexity Tracking

Нарушений конституции нет; дополнительные абстракции и зависимости не вводятся.
