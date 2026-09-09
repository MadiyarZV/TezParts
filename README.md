# TezParts — Telegram-агент для управления контентом

Личная панель управления контент-пайплайном @tez.parts в Telegram.
Не бот для клиентов: доступ только по whitelist, один-два пользователя.

## Что он делает (этап 1)

- `/post <тема>` — прогоняет тему через ваши скиллы (`threads-post-writer` →
  `humanizer-ru`) и присылает готовый текст с кнопками.
- `/fix <id> <правка>` — переписывает черновик.
- `/drafts` — черновики, ждущие решения.
- Ничего не публикуется без вашего явного нажатия.

## Архитектура

```
Telegram (long polling)
   ↓  bot/handlers.py      — команды, кнопки, whitelist
   ↓  bot/worker.py        — очередь: одна задача агента за раз
   ↓  bot/agent.py         — Claude Agent SDK, единственное место о нём знающее
   ↓  workspace/.claude/skills/  — ваши скиллы, как есть
   ↓  bot/db.py            — SQLite: черновики и статусы
   ↓  bot/publishers/      — граница публикации (manual | publora)
```

Два решения, на которых всё держится:

1. **Скиллы не переписываются.** Агент запускается с `cwd = workspace`, откуда
   подхватывает `.claude/skills`. Качество текста остаётся тем же, что в
   Claude Code.
2. **Состояние в SQLite, а не в контексте модели.** Каждый прогон агента
   stateless — бота можно рестартить, не теряя работу.

## Установка

```bash
cp .env.example .env      # заполнить токены и ALLOWED_USER_IDS
mkdir -p workspace/.claude/skills data
cp -r <ваши скиллы> workspace/.claude/skills/
docker compose up -d --build
```

Без Docker:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
npm install -g @anthropic-ai/claude-code
python -m bot.main
```

`ALLOWED_USER_IDS` обязателен — без него бот не стартует.

## Что дальше

- **Этап 2** — `/plan 7`: недельный план через `threads-ceo`, слоты в БД,
  утренние напоминания.
- **Этап 3** — реальная публикация. Канал ещё не выбран: `ManualPublisher`
  работает сейчас, `PubloraPublisher` — заглушка под решение. Meta API
  напрямую потребует отдельной работы с токенами и ревью приложения.
- **Этап 4** — Instagram, аналитика по факту публикаций.

Перед постановкой на расписание прогнать один полный цикл и замерить стоимость
в токенах: `threads-ceo` на неделю контента — это заметный объём.
