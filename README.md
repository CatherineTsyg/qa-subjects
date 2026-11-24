# QA Subjects — база ответов по предметам

Лабораторная работа: разработка веб-приложения с помощью AI-агента (opencode).

**Предметная область.** Предметы (категории) добавляются через админку. Пользователи задают вопросы по предмету и пишут ответы, к ответу можно прикрепить фото и документы. Ответам ставят лайк или дизлайк, самые залайканные ответы показываются первыми.

Приложение сделано дважды:

| Версия | Подход | Стек |
|--------|--------|------|
| [`vibe/`](vibe/) | вайб-кодинг | Django, PostgreSQL, Docker Compose |
| [`sdd/`](sdd/) | Spec-Driven Development | Django, PostgreSQL, **Valkey** (кеш), Docker Compose |

Сравнение подходов: [`docs/COMPARISON.md`](docs/COMPARISON.md).

## Структура репозитория

```
.
├── AGENTS.md                           # инструкции для агента
├── opencode.json                       # конфиг opencode, MCP-сервер context7
├── .opencode/skills/django-feature/    # собственный Skill
├── docs/                               # отчёты, промпты, сравнение
├── vibe/                               # версия «на 4»
└── sdd/                                # версия «на 5»
    ├── .specify/memory/constitution.md # конституция проекта
    ├── .opencode/commands/             # команды Spec Kit /speckit.*
    ├── specs/001-subject-answers/      # спека, план, research, модель данных, контракты, задачи
    ├── accounts/, qa/, config/         # код приложения
    └── scripts/benchmark_pages.py      # замер производительности
```

## Требования

- Docker и Docker Compose v2
- [opencode](https://opencode.ai) — для работы с агентом

## Запуск

Обе версии запускаются одинаково и могут работать одновременно (разные порты):

| Версия | Сервисы | Адрес |
|--------|---------|-------|
| `vibe` | web (`runserver`), db | http://localhost:8000 |
| `sdd` | web (`gunicorn`), db, valkey | http://localhost:8001 |

```bash
cd vibe   # или cd sdd
cp .env.example .env
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Админка — `/admin/` на том же адресе.

Тесты:

```bash
docker compose exec web python manage.py test
```

Остановка: `docker compose down` (с удалением данных: `docker compose down -v`).

### Особенности SDD-версии

- `DEBUG=false` по умолчанию; статика отдаётся через `whitenoise`, вложения — через отдельное представление
  скачивания, поэтому всё работает без режима отладки.
- Кеш — Valkey (`VALKEY_URL`): страницы списка предметов и ответов вопроса, инвалидация после коммита.
- В образе собирается статика, поэтому после изменения кода нужен `docker compose up --build -d`.
- Демо-данные и замер производительности (10 000 вопросов, 100 000 ответов, p95 при 100 потоках):

  ```bash
  docker compose exec web python manage.py seed_demo
  docker compose exec web python scripts/benchmark_pages.py --base-url http://localhost:8001 --threads 100
  ```

Подробный сценарий проверки — [`sdd/specs/001-subject-answers/quickstart.md`](sdd/specs/001-subject-answers/quickstart.md).

## Настройка агента

- **MCP:** в [`opencode.json`](opencode.json) подключён remote-сервер [context7](https://context7.com) — актуальная документация библиотек. Проверка: `opencode mcp list`.
- **Skill:** [`django-feature`](.opencode/skills/django-feature/SKILL.md) — чек-лист добавления фичи в Django (модель → миграция → админка → вью → тесты).
- **AGENTS.md:** [`AGENTS.md`](AGENTS.md) — стек, команды, правила кода и запреты.

## Отчёты

- [`docs/LAB3.md`](docs/LAB3.md) — настройка агента: MCP, Skill, AGENTS.md
- [`docs/VIBE.md`](docs/VIBE.md) — промпты и ревью вайб-версии
- [`docs/SDD.md`](docs/SDD.md) — шаги Spec Kit, промпты и ревью каждого артефакта SDD-версии
- [`docs/COMPARISON.md`](docs/COMPARISON.md) — сравнение вайб и SDD
