# Tasks: База ответов по предметам

**Input**: Design documents from `/specs/001-subject-answers/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/http-endpoints.md`, `quickstart.md`

**Tests**: включены обязательно (конституция, принцип VI; SC-003 и SC-004 требуют
автоматических тестов; AGENTS.md требует тесты для новой функциональности). Тесты пишутся
до реализации и должны падать до её завершения.

**Organization**: задачи сгруппированы по пользовательским историям, чтобы каждую можно было
реализовать и проверить независимо.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: можно выполнять параллельно (разные файлы, нет зависимостей)
- **[Story]**: история пользователя (`US1`–`US5`); в Setup, Foundational и Polish не указывается
- Все пути указаны от корня репозитория и начинаются с `sdd/`
- В конце каждой задачи в скобках указаны покрываемые требования FR/SC

## Path Conventions

Единый Django-проект внутри `sdd/`: приложения `sdd/accounts/` и `sdd/qa/`, настройки в
`sdd/config/`, общие шаблоны в `sdd/templates/`, тестовые утилиты в `sdd/config/test_utils.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Инициализация проекта, зависимостей и Docker-окружения.

- [X] T001 Создать `sdd/requirements.txt` с закреплёнными версиями зависимостей для Python 3.12: Django 5.2.x LTS, `psycopg[binary]` 3.x, `redis`, `gunicorn`, `whitenoise` (FR-001–FR-023, SC-001, SC-007)
- [X] T002 [P] Создать `sdd/Dockerfile` (python:3.12-slim, установка зависимостей, `RUN SECRET_KEY=build-only python manage.py collectstatic --noinput` — фиктивный ключ только на шаг сборки, не сохраняется в образе; запуск `gunicorn config.wsgi:application --bind 0.0.0.0:8001 --workers 4 --threads 4 --timeout 60`) и `sdd/.dockerignore` (SC-001, SC-007)
- [X] T003 [P] Создать `sdd/docker-compose.yml`: сервисы `db` (PostgreSQL 16, healthcheck `pg_isready`), `valkey` (Valkey 8, healthcheck `valkey-cli ping`), `web` (healthcheck Python `urllib` на `http://localhost:8001/healthz/`), `depends_on: condition: service_healthy`, порт `${WEB_PORT:-8001}:8001`, volumes `postgres_data` и `media_data` (SC-001, SC-007)
- [X] T004 [P] Создать `sdd/.env.example` со всеми переменными (`SECRET_KEY`, `DEBUG=false`, `ALLOWED_HOSTS=localhost,127.0.0.1,web`, `CSRF_TRUSTED_ORIGINS`, `POSTGRES_*`, `VALKEY_URL`, `WEB_PORT=8001`) и безопасными локальными значениями (FR-019, SC-005)
- [X] T005 Создать `sdd/manage.py`, `sdd/config/__init__.py`, `sdd/config/wsgi.py`, `sdd/config/asgi.py` для проекта `config` (FR-001–FR-023)
- [X] T006 Создать `sdd/config/settings.py`: конфигурация только из env с `DEBUG=False` по умолчанию, `ALLOWED_HOSTS` по умолчанию `localhost,127.0.0.1,web`, PostgreSQL, `RedisCache` через `VALKEY_URL`, `MEDIA_ROOT=/app/media`, `LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL`, `CSRF_TRUSTED_ORIGINS`, whitenoise, приложения `accounts` и `qa` (FR-019, SC-001, SC-007)
- [X] T007 Создать `sdd/config/urls.py` с маршрутами `admin/` и заготовкой для healthcheck; подключение URL приложений добавляется в их историях (FR-001, FR-014)
- [X] T008 [P] Создать `sdd/templates/base.html` с русским интерфейсом, навигацией, блоками `content` и подключением статики через whitenoise; добавить минимальный `sdd/static/css/app.css` (FR-001, FR-003)
- [X] T009 [P] Создать скелеты приложений `sdd/accounts/` и `sdd/qa/`: `__init__.py`, `apps.py`, пустые `migrations/__init__.py`, `tests/__init__.py` (FR-001–FR-023)

**Checkpoint**: `docker compose up --build -d` поднимает `db`, `valkey` и `web`; каркас проекта готов.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Общие модели, миграции, кеш, сигналы, тестовая инфраструктура и healthcheck, без которых не работает ни одна история.

**⚠️ CRITICAL**: Ни одна пользовательская история не начинается до завершения этой фазы.

- [X] T010 Создать пять моделей в `sdd/qa/models.py`: `Subject` (`name` CharField(120) unique NOT NULL, `description` TextField blank, `created_at`/`updated_at`), `Question` (`subject` FK PROTECT `related_name="questions"`, `author` FK CASCADE, `title` CharField(200) непустой, `body` TextField непустой, даты), `Answer` (`question` FK CASCADE, `author` FK CASCADE, `body` TextField непустой, даты), `Vote` (`answer`/`user` FK CASCADE, `value` SmallIntegerField только `1`/`-1`, `UniqueConstraint(fields=["user","answer"], name="vote_unique_user_answer")`, `CheckConstraint(condition=Q(value__in=[1,-1]), name="vote_value_allowed")`), `Attachment` (`answer` FK CASCADE, `file` FileField `upload_to="attachments/%Y/%m/%d/"`, `original_name` CharField(255), `content_type` CharField(100), `size` PositiveBigIntegerField, `created_at`); добавить индексы `Question(subject,-created_at)`, `Answer(question)`, `Vote(answer)`, `Attachment(answer)` и проверки непустых `title`/`body` (FR-006, FR-007, FR-009, FR-010, FR-012, FR-017, FR-018, SC-004, SC-006)
- [X] T011 Создать и закоммитить миграцию `sdd/qa/migrations/0001_initial.py` командой `python manage.py makemigrations qa` (FR-001–FR-023)
- [X] T012 [P] Зарегистрировать `Subject`, `Question`, `Answer`, `Vote`, `Attachment` в `sdd/qa/admin.py` с `list_display` и поиском (FR-002, FR-015)
- [X] T013 Создать `sdd/qa/cache.py`: ключи `qa:v1:subjects:list:version`, `qa:v1:subjects:list:v{version}:page:{n}`, `qa:v1:question:{id}:answers:version`, `qa:v1:question:{id}:answers:v{version}:page:{n}`; `get_version(key)` возвращает `cache.get(key) or 1`; TTL страниц 300 с, версии без TTL; инвалидация через `cache.add(version_key, 1)` + `cache.incr(version_key)`; функции чтения/записи страниц (FR-003, FR-008, FR-020, FR-022, SC-001)
- [X] T014 Создать `sdd/qa/signals.py` и подключить в `sdd/qa/apps.py::ready()`: `post_save`/`post_delete` для `Subject`, `Question`, `Answer`, `Vote`, `Attachment` планируют инвалидацию через `transaction.on_commit` по нормативной таблице `contracts/http-endpoints.md`; пропускать `raw=True`; `post_delete` вложения удаляет файл; сервисы и представления ключи не трогают. В обработчике `Vote` вычислить `question_id = instance.answer.question_id` сразу в момент сигнала и передать его в лямбду, не обращаться к `instance.answer` внутри `on_commit` (при каскаде ответ уже удалён к коммиту) (FR-009, FR-017, FR-018, FR-022, SC-002)
- [X] T015 [P] Реализовать healthcheck `GET /healthz/` в `sdd/qa/views.py` и подключить маршрут в `sdd/config/urls.py`; ответ `200` без обращения к БД и кешу (SC-007)
- [X] T016 [P] Создать `sdd/templates/includes/pagination.html` с сохранением query-параметров и русскими подписями (FR-020)
- [X] T017 Создать `sdd/config/test_utils.py`: `LOCMEM_CACHES` с `django.core.cache.backends.locmem.LocMemCache`, `TempMediaMixin` (временный `MEDIA_ROOT` через `tempfile.mkdtemp()`, `override_settings`, очистка `shutil.rmtree` в `tearDownClass`) и базовый `CacheMediaTestCase`; все тесты, включая `TransactionTestCase`, используют эти утилиты (FR-013, SC-006)
- [X] T018 Создать `sdd/qa/tests/test_models.py` на базе `sdd/config/test_utils.py`: уникальность голоса (через вложенный `transaction.atomic` вокруг `IntegrityError`), `CheckConstraint` значения голоса, `PROTECT` непустого предмета (FR-009, FR-010, FR-011, FR-017, FR-018, SC-004)

**Checkpoint**: Схема БД, кеш-ключи, сигналы, тестовая инфраструктура и healthcheck готовы; истории можно реализовывать параллельно.

---

## Phase 3: User Story 1 - Просмотр предметов, вопросов и ответов (Priority: P1) 🎯 MVP

**Goal**: Анонимный посетитель читает список предметов со счётчиками, вопросы предмета от новых к
старым и ответы по рейтингу; страницы кешируются и открываются без N+1.

**Independent Test**: Наполнить БД предметами, вопросами и ответами с разным рейтингом, открыть
`/`, `/subjects/<id>/`, `/questions/<id>/` без входа; проверить счётчики, сортировку, пагинацию,
пустые состояния, 404 и число запросов.

### Tests for User Story 1 ⚠️

> **NOTE: сначала написать тесты и убедиться, что они падают.**

- [X] T019 [P] [US1] Написать тесты чтения в `sdd/qa/tests/test_views.py`: названия и число вопросов, сортировка предметов по названию, пустой список, вопросы от новых к старым, ответы по `-rating` и `-created_at`, пустой предмет, пагинация 20, 404, доступ анонима, `assertNumQueries` для трёх страниц (FR-001, FR-003, FR-008, FR-020, FR-021, FR-023, SC-001)
- [X] T020 [P] [US1] Написать тесты кеша в `sdd/qa/tests/test_cache.py`: попадание на страницах 1..N с ключами `page:{n}`, `get_version()` возвращает `1` при отсутствии ключа и первый запрос не создаёт ключ `vNone`, рост версии инвалидирует все страницы, ключ жив до выполнения `captureOnCommitCallbacks`, изменение через админку и каскадное удаление пользователя инвалидируют кеш, голос пользователя не попадает в значение кеша (FR-003, FR-008, FR-022, SC-002)
- [X] T021 [P] [US1] Написать тесты админки в `sdd/qa/tests/test_admin.py`: staff удаляет предмет с вопросом — удаление не выполняется, показывается «Нельзя удалить предмет, в котором есть вопросы»; пустой предмет удаляется (FR-002)

### Implementation for User Story 1

- [X] T022 [US1] Реализовать список предметов в `sdd/qa/views.py`: `annotate(Count("questions"))`, сортировка по `name`, пагинация 20, чтение/запись кеша `qa:v1:subjects:list:v{version}:page:{n}`, сообщение об отсутствии предметов (FR-003, FR-020)
- [X] T023 [US1] Реализовать страницу предмета в `sdd/qa/views.py`: `select_related("author")`, `order_by("-created_at")`, пагинация 20, сообщение об отсутствии вопросов (FR-020, FR-023)
- [X] T024 [US1] Реализовать страницу вопроса в `sdd/qa/views.py`: `annotate(rating=Coalesce(Sum("votes__value"), 0))`, `select_related("author")`, `prefetch_related("attachments")`, `order_by("-rating", "-created_at")`, пагинация 20, кеш страницы и отдельный запрос голосов текущего пользователя (не кешируется, для анонима не выполняется) (FR-001, FR-008, FR-020, FR-022)
- [X] T025 [P] [US1] Создать `sdd/qa/templates/qa/subject_list.html` с названием, числом вопросов, пагинацией и пустым состоянием (FR-003, FR-020)
- [X] T026 [P] [US1] Создать `sdd/qa/templates/qa/subject_detail.html` с вопросами, автором, датой, пагинацией и пустым состоянием (FR-020, FR-023)
- [X] T027 [P] [US1] Создать `sdd/qa/templates/qa/question_detail.html` с заголовком, текстом, автором, рейтингом, ответами и пагинацией; предусмотреть места для кнопок голосования и вложений (FR-008, FR-022)
- [X] T028 [US1] Создать `sdd/qa/urls.py` с маршрутами `/`, `/subjects/<id>/`, `/questions/<id>/` и подключить `qa.urls` в `sdd/config/urls.py` (FR-001, FR-008)
- [X] T029 [US1] Настроить управление предметами в `sdd/qa/admin.py`: staff создаёт и изменяет предметы; при удалении непустого предмета перехватывать `ProtectedError` и показывать «Нельзя удалить предмет, в котором есть вопросы» (FR-002)
- [X] T030 [US1] Подключить `sdd/templates/includes/pagination.html` в шаблоны списков и вывести русские пустые состояния и сообщение «не найдено» для отсутствующих объектов (FR-003, FR-020, FR-021)
- [X] T031 [US1] Запустить `python manage.py test qa.tests.test_views qa.tests.test_cache qa.tests.test_admin`, используя файлы `sdd/qa/tests/test_views.py`, `sdd/qa/tests/test_cache.py`, `sdd/qa/tests/test_admin.py`, и устранить расхождения (FR-001, FR-003, FR-008, FR-020, FR-022, FR-023, SC-001)

**Checkpoint**: US1 полностью работает и проверяется без регистрации и без остальных историй.

---

## Phase 4: User Story 2 - Учётная запись и публикация вопросов и ответов (Priority: P2)

**Goal**: Пользователь регистрируется, входит, создаёт вопрос и ответ; аноним видит результат,
но не может публиковать.

**Independent Test**: Зарегистрировать пользователя, войти, создать вопрос и ответ, выйти и
убедиться, что аноним видит их на страницах предмета и вопроса; проверить отказ при занятом
имени, неверном пароле и анонимном POST.

### Tests for User Story 2 ⚠️

- [X] T032 [P] [US2] Написать тесты аутентификации в `sdd/accounts/tests/test_auth.py`: регистрация с уникальным именем, отказ при занятом имени, вход с верными и неверными данными, выход только POST, редирект анонима на вход (FR-004, FR-005, SC-003)
- [X] T033 [P] [US2] Написать тесты публикации в `sdd/qa/tests/test_views.py`: создание вопроса с `title` 1–200 и непустым `body`, создание ответа с `body` 1–10 000, отказ при пустых/слишком длинных полях, появление контента у анонима, сквозной сценарий SC-003 «регистрация → вход → вопрос → ответ» (FR-006, FR-007, FR-021, SC-003)

### Implementation for User Story 2

- [X] T034 [US2] Создать `sdd/accounts/forms.py`: форма регистрации с уникальным `username`, валидаторами пароля Django и подтверждением пароля; форма входа (FR-004, FR-005)
- [X] T035 [US2] Создать `sdd/accounts/views.py`: регистрация с автоматическим входом, вход, выход только через POST (FR-004, FR-005, FR-019)
- [X] T036 [US2] Создать `sdd/accounts/urls.py` с маршрутами `register/`, `login/`, `logout/` и подключить в `sdd/config/urls.py` (FR-004, FR-005)
- [X] T037 [P] [US2] Создать `sdd/accounts/templates/accounts/register.html` и `sdd/accounts/templates/accounts/login.html` с русскими сообщениями об ошибках (FR-004, FR-005)
- [X] T038 [US2] Создать `sdd/qa/forms.py`: `QuestionForm` (`title` 1–200, `body` непустой) и `AnswerForm` (`body` 1–10 000) с русскими сообщениями (FR-006, FR-007, FR-021)
- [X] T039 [US2] Реализовать создание вопроса в `sdd/qa/views.py`: `login_required`, POST с CSRF, проверка формы, `302` на страницу вопроса (FR-006, FR-019)
- [X] T040 [US2] Реализовать создание ответа в `sdd/qa/views.py`: `login_required`, POST с CSRF, проверка формы, `302` на страницу вопроса (FR-007, FR-019)
- [X] T041 [US2] Добавить в `sdd/qa/urls.py` маршруты создания вопроса и ответа (FR-006, FR-007)
- [X] T042 [US2] Создать `sdd/qa/templates/qa/question_form.html` и `sdd/qa/templates/qa/answer_form.html` (FR-006, FR-007)
- [X] T043 [US2] Добавить в `sdd/templates/base.html` ссылки входа/регистрации и POST-форму выхода; добавить кнопки создания вопроса и ответа в шаблоны US1 (FR-005, FR-006, FR-007)
- [X] T044 [US2] Запустить `python manage.py test accounts qa.tests.test_views`, используя файлы `sdd/accounts/tests/test_auth.py` и `sdd/qa/tests/test_views.py`, и устранить расхождения (FR-004–FR-007, FR-019, FR-021, SC-003)

**Checkpoint**: US1 и US2 работают независимо; публикация видна анонимному посетителю.

---

## Phase 5: User Story 3 - Голосование и рейтинг ответов (Priority: P3)

**Goal**: Лайк, дизлайк, смена и снятие голоса меняют рейтинг и порядок ответов; один голос на
пару, самоголосование запрещено, гонки не дают дубликатов и ошибок.

**Independent Test**: Два пользователя голосуют за один ответ, меняют и снимают голоса;
проверить точные изменения рейтинга (`+1`, `−1`, `±2`, возврат), порядок ответов, `403` за свой
ответ и отсутствие дубликата при одновременных запросах.

### Tests for User Story 3 ⚠️

- [X] T045 [P] [US3] Написать тесты голосования в `sdd/qa/tests/test_votes.py`: лайк `+1`, дизлайк `−1`, смена `±2`, снятие, запрет самоголосования `403`, один голос на пару, пересортировка ответов, голос за удалённый ответ → `404`, `value` вне `like/dislike` → `400` без изменения голоса, инвалидация кеша после коммита, конкурентные запросы одного пользователя в `TransactionTestCase` (FR-009, FR-010, FR-011, FR-022, SC-004)
- [X] T046 [US3] Реализовать голосование в `sdd/qa/services.py`: внешний `transaction.atomic`; вставка во вложенном `transaction.atomic` (savepoint) с повтором обновлением после `IntegrityError`; поддержка `1`/`-1`; запрет голоса за свой ответ; снятие при повторном том же значении (FR-009, FR-010, FR-011)
- [X] T047 [US3] Реализовать представление голосования в `sdd/qa/views.py`: `login_required`, POST, CSRF, `value=like|dislike`, значение вне этого набора → `400` без изменения голоса, `403` за свой ответ, `404` для удалённого ответа, `302` на вопрос (FR-009, FR-010, FR-019)
- [X] T048 [US3] Добавить маршрут `/answers/<id>/vote/` в `sdd/qa/urls.py` (FR-009)
- [X] T049 [US3] Добавить в `sdd/qa/templates/qa/question_detail.html` отображение рейтинга и кнопки лайка/дизлайка с подсветкой голоса текущего пользователя из переданного отдельного запроса; скрывать кнопки у собственных ответов и у анонима (FR-009, FR-011)
- [X] T050 [US3] Запустить `python manage.py test qa.tests.test_votes qa.tests.test_cache`, используя файлы `sdd/qa/tests/test_votes.py` и `sdd/qa/tests/test_cache.py`, и устранить расхождения (FR-009–FR-011, FR-022, SC-004)

**Checkpoint**: Голосование работает поверх US1–US2 и не ломает их.

---

## Phase 6: User Story 4 - Вложения к ответу (Priority: P4)

**Goal**: Автор ответа прикрепляет изображения и документы, посетитель открывает или скачивает
их; недопустимые, пустые, слишком большие файлы и превышение количества отклоняются.

**Independent Test**: Приложить PNG/JPG ≤ 5 МБ и PDF ≤ 10 МБ, скачать их и проверить заголовки;
отклонить `.exe`, пустой файл, файл с неверной сигнатурой, превышение размера и шестое вложение.

### Tests for User Story 4 ⚠️

- [X] T051 [P] [US4] Написать тесты вложений в `sdd/qa/tests/test_attachments.py`: допустимые расширения и сигнатуры JPEG/PNG/WebP/PDF/DOC/DOCX/TXT, MIME из таблицы `data-model.md`, пустой файл, несоответствие содержимого расширению, лимиты 5 МБ/10 МБ, максимум 5 вложений, добавление только автором ответа (`403`), скачивание с `Content-Type` из `content_type`, `inline` для изображений и `attachment` для документов (FR-012, FR-013, FR-014, SC-006)

### Implementation for User Story 4

- [X] T052 [US4] Создать `sdd/qa/validators.py`: белый список расширений (jpg, jpeg, png, webp, pdf, txt, doc, docx); таблица расширение → MIME из `data-model.md`; сигнатуры JPEG `FF D8 FF`, PNG `89 50 4E 47 0D 0A 1A 0A`, WebP `RIFF....WEBP`, PDF `%PDF-`, DOC `D0 CF 11 E0 A1 B1 1A E1`; DOCX — ZIP с `[Content_Types].xml`; TXT — без нулевых байтов и декодируется как UTF-8; запрет пустых файлов; лимиты 5 МБ для изображений и 10 МБ для документов; очистка имени через `os.path.basename` (FR-012, FR-013)
- [X] T053 [US4] Создать `sdd/qa/forms.py::AttachmentForm` и добавление вложения в `sdd/qa/services.py`: проверка валидаторов, `select_for_update` ответа, отказ при 5 вложениях, сохранение `original_name`, `content_type`, `size` (FR-012, FR-013)
- [X] T054 [US4] Реализовать добавление вложения в `sdd/qa/views.py`: `login_required`, доступ только автору ответа (`403` иначе), POST с CSRF, `302` на вопрос (FR-012, FR-013, FR-019)
- [X] T055 [US4] Реализовать скачивание в `sdd/qa/views.py`: `FileResponse`, `Content-Type` только из сохранённого `content_type`, `Content-Disposition: attachment` для pdf/txt/doc/docx и `inline` для jpg/jpeg/png/webp, очищенное имя файла, `404` для отсутствующего (FR-014)
- [X] T056 [US4] Добавить маршруты добавления и скачивания вложений в `sdd/qa/urls.py` (FR-012, FR-014)
- [X] T057 [P] [US4] Создать `sdd/qa/templates/qa/attachment_form.html` и добавить форму вложения в шаблон ответа (FR-012)
- [X] T058 [US4] Вывести вложения и ссылки на скачивание в `sdd/qa/templates/qa/question_detail.html` (FR-014)
- [X] T059 [US4] Запустить `python manage.py test qa.tests.test_attachments`, используя файл `sdd/qa/tests/test_attachments.py`, и устранить расхождения (FR-012–FR-014, SC-006)

**Checkpoint**: Вложения работают, недопустимые файлы не сохраняются, путь на диске не раскрывается.

---

## Phase 7: User Story 5 - Редактирование и удаление авторского контента (Priority: P5)

**Goal**: Автор и staff редактируют и удаляют вопросы, ответы и вложения; чужой контент изменить
нельзя; удаление каскадно очищает связанные данные и кеш.

**Independent Test**: От имени автора, другого пользователя, staff и анонима попытаться изменить
и удалить вопрос, ответ и вложение; успех только у автора и staff, данные остальных попыток не
меняются.

### Tests for User Story 5 ⚠️

- [X] T060 [P] [US5] Написать тесты прав в `sdd/qa/tests/test_permissions.py`: матрица «аноним / пользователь / автор / staff» для вопроса, ответа и вложения; `403` чужим, `302` на вход анониму, staff может всё, staff не добавляет вложение в чужой ответ (FR-015, FR-016, SC-005)
- [X] T061 [P] [US5] Написать тесты каскадов в `sdd/qa/tests/test_models.py`: удаление вопроса удаляет ответы, голоса, вложения и файлы; удаление ответа удаляет голоса и вложения; удаление вложения удаляет файл; после удаления соответствующие версии кеша меняются (FR-017, FR-018, SC-005)
- [X] T062 [P] [US5] Написать тесты CSRF в `sdd/qa/tests/test_csrf.py` с `Client(enforce_csrf_checks=True)`: POST без токена на создание вопроса/ответа, редактирование и удаление вопроса/ответа/вложения, голос, добавление вложения и выход → `403`; проверить, что объекты, голоса и файлы не изменились (FR-019, SC-005)

### Implementation for User Story 5

- [X] T063 [US5] Реализовать редактирование и удаление вопроса в `sdd/qa/views.py`: доступ автору или staff, `403` остальным, POST с CSRF, `302` после успеха, `404` для отсутствующего (FR-015, FR-016, FR-019)
- [X] T064 [US5] Реализовать редактирование и удаление ответа в `sdd/qa/views.py`: доступ автору или staff, `403` остальным, POST с CSRF, `302` на вопрос (FR-015, FR-016, FR-019)
- [X] T065 [US5] Реализовать удаление вложения в `sdd/qa/views.py`: доступ автору ответа или staff, `403` остальным, POST с CSRF, `302` на вопрос (FR-015, FR-016, FR-019)
- [X] T066 [US5] Добавить маршруты редактирования и удаления вопроса/ответа/вложения в `sdd/qa/urls.py` (FR-015)
- [X] T067 [US5] Создать `sdd/qa/templates/qa/confirm_delete.html` с подтверждением удаления и русским текстом (FR-015)
- [X] T068 [US5] Добавить в `sdd/qa/templates/qa/subject_detail.html` и `sdd/qa/templates/qa/question_detail.html` ссылки редактирования и удаления, видимые только автору и staff (FR-015, FR-016)
- [X] T069 [US5] Запустить `python manage.py test qa.tests.test_permissions qa.tests.test_models qa.tests.test_cache qa.tests.test_csrf`, используя файлы `sdd/qa/tests/test_permissions.py`, `sdd/qa/tests/test_models.py`, `sdd/qa/tests/test_cache.py`, `sdd/qa/tests/test_csrf.py`, и устранить расхождения (FR-015–FR-019, SC-005)

**Checkpoint**: Все пять историй работают; права, каскады и CSRF подтверждены тестами.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Сквозная проверка, безопасность, производительность и чистота кода.

- [X] T070 [P] Пройти сценарии `sdd/specs/001-subject-answers/quickstart.md` в Docker и устранить найденные расхождения (FR-001–FR-023, SC-003, SC-005, SC-006)
- [X] T071 [P] Проверить безопасность в `sdd/config/settings.py` и `sdd/qa/validators.py`: секреты только из env, `DEBUG=False`, CSRF на всех POST, `ALLOWED_HOSTS`, лимиты загрузок, отсутствие пути к файлу в ответах (FR-019, SC-005, SC-006)
- [X] T072 [P] Проверить производительность по числу запросов: `assertNumQueries` для `/`, `/subjects/<id>/`, `/questions/<id>/`, наличие индексов из `sdd/qa/models.py`, отсутствие N+1 (FR-020, SC-001, SC-007)
- [X] T073 [P] Создать `sdd/qa/management/commands/seed_demo.py` (10 000 вопросов, 100 000 ответов, детерминированные данные) и `sdd/scripts/benchmark_pages.py` на stdlib: `urllib.request` + `concurrent.futures.ThreadPoolExecutor`, 100 потоков, замер p95 времени ответа `/`, `/subjects/<id>/`, `/questions/<id>/`; записать команды и результаты в `sdd/specs/001-subject-answers/quickstart.md` (SC-001, SC-007)
- [X] T074 [P] Убрать мёртвый код и привести `sdd/` к PEP 8 без изменения поведения (FR-001–FR-023)
- [X] T075 Запустить полный набор `docker compose exec web python manage.py test` и проверить healthcheck командой `docker compose ps`, используя `sdd/docker-compose.yml` (SC-003, SC-004, SC-005, SC-006)
- [X] T076 При необходимости обновить `sdd/specs/001-subject-answers/quickstart.md` по результатам сквозной проверки и замера, не меняя `docs/` (SC-001, SC-007)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: без зависимостей, начинается сразу.
- **Foundational (Phase 2)**: зависит от Setup и блокирует все истории.
- **US1 (Phase 3)**: после Foundational; зависимостей от других историй нет.
- **US2 (Phase 4)**: после Foundational; для редиректов и отображения использует страницы US1.
- **US3 (Phase 5)**: после Foundational; использует страницу вопроса US1 и аутентификацию US2.
- **US4 (Phase 6)**: после Foundational; использует ответы US2 и страницу вопроса US1.
- **US5 (Phase 7)**: после Foundational; использует контент US2 и вложения US4.
- **Polish (Phase 8)**: после всех выбранных историй.

### User Story Dependencies

- **US1 (P1)**: независима после Foundational, даёт MVP.
- **US2 (P2)**: может разрабатываться параллельно с US1, но сквозной тест требует страниц US1.
- **US3 (P3)**: требует `Answer` и страницу вопроса; голосование не влияет на US2.
- **US4 (P4)**: требует `Answer` и авторизацию; добавление вложения не зависит от голосования.
- **US5 (P5)**: требует объекты US2 и US4 для проверки прав, каскадов и CSRF.

### Within Each User Story

- Тесты пишутся первыми и должны падать.
- Модели и миграции уже готовы в Foundational.
- Формы и сервисы — до представлений.
- Представления — до маршрутов и шаблонов.
- В конце истории — прогон её тестов и исправления.

### Parallel Opportunities

- Setup: T002, T003, T004, T008, T009 независимы.
- Foundational: T012, T015, T016 независимы после моделей и настроек.
- US1: тесты T019–T021; шаблоны T025–T027.
- US2: тесты T032 и T033; шаблоны T037.
- US3: один тестовый файл, параллелизм внутри истории ограничен.
- US4: тест T051 и шаблон T057.
- US5: тесты T060–T062.
- Polish: T070–T074 независимы.

---

## Parallel Example: User Story 1

```bash
# Тесты US1 (разные файлы):
Task: "Написать тесты чтения в sdd/qa/tests/test_views.py"
Task: "Написать тесты кеша в sdd/qa/tests/test_cache.py"
Task: "Написать тесты админки в sdd/qa/tests/test_admin.py"

# Шаблоны US1 (разные файлы):
Task: "Создать sdd/qa/templates/qa/subject_list.html"
Task: "Создать sdd/qa/templates/qa/subject_detail.html"
Task: "Создать sdd/qa/templates/qa/question_detail.html"
```

## Parallel Example: User Story 2

```bash
# Тесты US2 (разные файлы):
Task: "Написать тесты аутентификации в sdd/accounts/tests/test_auth.py"
Task: "Написать тесты публикации в sdd/qa/tests/test_views.py"

# Шаблоны аутентификации:
Task: "Создать sdd/accounts/templates/accounts/register.html"
Task: "Создать sdd/accounts/templates/accounts/login.html"
```

## Parallel Example: User Story 3

```bash
# Один файл тестов, последовательная реализация:
Task: "Написать sdd/qa/tests/test_votes.py"
Task: "Реализовать sdd/qa/services.py::vote"
Task: "Добавить кнопки голосования в sdd/qa/templates/qa/question_detail.html"
```

## Parallel Example: User Story 4

```bash
Task: "Написать sdd/qa/tests/test_attachments.py"
Task: "Создать sdd/qa/validators.py"
Task: "Создать sdd/qa/templates/qa/attachment_form.html"
```

## Parallel Example: User Story 5

```bash
# Тесты US5 (разные файлы):
Task: "Написать sdd/qa/tests/test_permissions.py"
Task: "Написать тесты каскадов в sdd/qa/tests/test_models.py"
Task: "Написать тесты CSRF в sdd/qa/tests/test_csrf.py"

# Реализация:
Task: "Реализовать удаление вложения в sdd/qa/views.py"
Task: "Создать sdd/qa/templates/qa/confirm_delete.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Завершить Phase 1: Setup.
2. Завершить Phase 2: Foundational (блокирует всё).
3. Завершить Phase 3: US1.
4. **STOP and VALIDATE**: прогнать `qa.tests.test_views`, `qa.tests.test_cache`, `qa.tests.test_admin`, открыть страницы без входа.
5. Демонстрировать MVP.

### Incremental Delivery

1. Setup + Foundational → каркас, схема и тестовая инфраструктура готовы.
2. US1 → публичное чтение (MVP).
3. US2 → регистрация и публикация.
4. US3 → голосование и рейтинг.
5. US4 → вложения.
6. US5 → редактирование, удаление и CSRF-тесты.
7. Polish → сквозная проверка, безопасность, производительность.

### Parallel Team Strategy

1. Команда завершает Setup и Foundational.
2. После Foundational:
   - Разработчик A: US1.
   - Разработчик B: US2 (после появления страниц US1 — интеграция).
   - Разработчик C: US3 и US4 после US2.
3. US5 выполняется после US2 и US4; Polish — после всех историй.

---

## Notes

- `[P]` — разные файлы и отсутствие зависимостей; один файл (`qa/views.py`, `qa/urls.py`,
  `qa/services.py`, `question_detail.html`) редактируется последовательно.
- `[Story]` связывает задачу с историей и упрощает трассировку.
- Каждая история завершается собственным прогоном тестов.
- Все тесты используют `sdd/config/test_utils.py`: `LocMemCache` и временный `MEDIA_ROOT`.
- Коммит после каждой задачи или логической группы; `.env`, `media/`, `__pycache__` не коммитятся.
- Не читать и не использовать `vibe/`, `docs/` и историю git; работать только в `sdd/`.
