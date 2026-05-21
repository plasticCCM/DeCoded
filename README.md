# DeCoded

DeCoded is a local Flask app that explains complex topics in simple styles and reinforces learning with mini-games, progress levels, and a lightweight local profile.

## Features

- AI explanations in several styles: grandma, meme, RPG, food, child, professor.
- Mini-games for reinforcement:
  - quick true/false check;
  - fill in the blanks;
  - sentence ordering;
  - best explanation choice.
- Understanding progress by topic with ranks: Coal, Bronze, Silver, Gold, Ruby, Diamond.
- Local profile with studied topics, progress, overall rank, and saved cards.
- SQLite persistence between server restarts.
- No accounts and no external database required.

## Tech Stack

- Python
- Flask
- SQLite
- Vanilla JavaScript
- HTML/CSS

## Project Structure

```text
.
├── app.py
├── run_local_server.py
├── requirements.txt
├── README.md
├── .env.example
├── templates/
│   └── index.html
└── static/
    ├── css/
    │   └── style.css
    ├── img/
    └── js/
        └── app.js
```

## Setup

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.env` from `.env.example`:

```bash
copy .env.example .env
```

Fill in the values:

```env
FLASK_SECRET_KEY=change-me
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_URL=https://api.example.com/v1/chat/completions
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TIMEOUT=90
```

## Run

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000/
```

If your local virtual environment has path issues on Windows, use:

```bash
python run_local_server.py
```

## Local Data

The app creates a local SQLite database:

```text
decoded.sqlite3
```

It stores:

- local user record;
- studied topics;
- topic progress;
- saved repetition cards;
- completed mini-games.

The database is ignored by Git.

## Security Notes

Do not commit `.env`, API keys, or local SQLite databases. The repository ignores:

- `.env`
- `*.sqlite3`
- virtual environments
- Python cache files

Use `.env.example` as the public configuration template.
