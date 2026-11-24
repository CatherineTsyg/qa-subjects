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
└── sdd/                                # версия «на 5» (спека, план, задачи, код)
```

## Требования

- Docker и Docker Compose v2
- [opencode](https://opencode.ai) — для работы с агентом

## Запуск

Одинаково для обеих версий (подставьте `vibe` или `sdd`):

```bash
cd vibe
cp .env.example .env
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Приложение: http://localhost:8000, админка: http://localhost:8000/admin/.

Тесты:

```bash
docker compose exec web python manage.py test
```

Остановка: `docker compose down` (с удалением данных: `docker compose down -v`).

## Настройка агента

- **MCP:** в [`opencode.json`](opencode.json) подключён remote-сервер [context7](https://context7.com) — актуальная документация библиотек. Проверка: `opencode mcp list`.
- **Skill:** [`django-feature`](.opencode/skills/django-feature/SKILL.md) — чек-лист добавления фичи в Django (модель → миграция → админка → вью → тесты).
- **AGENTS.md:** [`AGENTS.md`](AGENTS.md) — стек, команды, правила кода и запреты.

## Отчёты

- [`docs/LAB3.md`](docs/LAB3.md) — настройка агента: MCP, Skill, AGENTS.md
- [`docs/VIBE.md`](docs/VIBE.md) — промпты и ревью вайб-версии
- [`docs/COMPARISON.md`](docs/COMPARISON.md) — сравнение вайб и SDD
