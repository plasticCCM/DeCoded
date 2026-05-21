from flask import Flask, render_template, request, jsonify, session
import os
import requests
import markdown
import html
import json
import re
import sqlite3
from datetime import datetime
from random import randint
from markupsafe import Markup
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# DeepSeek через ChatAnywhere
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") 
DEEPSEEK_URL = os.getenv("DEEPSEEK_URL")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL")
API_TIMEOUT = int(os.getenv("DEEPSEEK_TIMEOUT", "90"))
DATABASE_PATH = os.getenv("DECODED_DATABASE", os.path.join(app.root_path, "decoded.sqlite3"))
LOCAL_USER_ID = 1

SYSTEM_MESSAGE = {"role": "system", "content": "Ты дружелюбный помощник, который объясняет сложные темы простым языком."}

STYLE_PROMPTS = {
    "👵 Как бабушка": """
Режим: "Как бабушка".
Объясняй очень тепло, спокойно и просто, как близкий человек за кухонным столом.
Используй 1-2 бытовые аналогии. Избегай мемов, профессионального тона и длинных терминологических блоков.
""",
    "😂 Как мем": """
Режим: "Как мем".
Объясняй коротко, живо и смешно, через мемные ситуации и узнаваемые интернет-аналогии.
Важно: не превращай ответ в лекцию. Не используй профессорский тон.
Структура: короткий заход, 2-3 мемные аналогии, затем "если совсем коротко" с главным смыслом.
Сарказм можно, но добрый. Длина ответа: до 2200 символов.
""",
    "🎮 Как RPG": """
Режим: "Как RPG".
Объясняй так, будто тема — игровая механика: уровни, квесты, персонажи, прокачка, боссы.
Не уходи в мемный или профессорский стиль. Термины объясняй через игровые роли и действия.
""",
    "🍔 Через еду": """
Режим: "Через еду".
Объясняй через кухню, ингредиенты, рецепты, готовку и хранение еды.
Не используй игровые и мемные аналогии, если они не нужны. Главная метафора — еда.
""",
    "🧒 Как ребёнку": """
Режим: "Как ребёнку".
Объясняй максимально просто: короткие предложения, простые слова, один пример из жизни.
Без сарказма, без сложных терминов и без длинных списков.
""",
    "📚 Как профессор": """
Режим: "Как профессор".
Объясняй строго, последовательно и научно, но понятно.
Можно использовать термины, но каждый важный термин нужно пояснить простыми словами.
Без мемов и бытового панибратского тона.
"""
}


def mode_instruction(mode):
    return STYLE_PROMPTS.get(mode, "Режим: простой. Объясни тему простым языком, без лишних терминов.")


def build_answer_messages(topic, mode):
    return [
        SYSTEM_MESSAGE.copy(),
        {
            "role": "system",
            "content": (
                f"{mode_instruction(mode)}\n"
                "Это обязательный контракт стиля, а не подсказка. В каждом абзаце должны ощущаться тон, метафоры и лексика выбранного режима. "
                "Не пиши нейтральный учебниковый ответ, если выбран образный режим. "
                "Строго соблюдай выбранный режим. Если режим изменился, игнорируй стиль прошлых ответов. "
                "Отвечай по теме пользователя и не смешивай стили."
            )
        },
        {"role": "user", "content": f"Тема: {topic}"}
    ]

def ensure_messages():
    if 'messages' not in session:
        session['messages'] = [SYSTEM_MESSAGE.copy()]
    return session['messages']


def ensure_recent_topics():
    if 'recent_topics' not in session:
        session['recent_topics'] = []
    return session['recent_topics']


def add_recent_topic(topic):
    topic = (topic or "").strip()
    if not topic:
        return ensure_recent_topics()

    topics = [item for item in ensure_recent_topics() if item.casefold() != topic.casefold()]
    topics.insert(0, topic)
    session['recent_topics'] = topics[:5]
    return session['recent_topics']


def get_last_answer():
    last_answer = session.get('last_answer')
    if last_answer:
        return last_answer

    for msg in reversed(session.get('messages', [])):
        if msg.get('role') == 'assistant':
            return msg.get('content')

    return None


def model_messages(messages):
    return [{"role": msg["role"], "content": msg["content"]} for msg in messages if "role" in msg and "content" in msg]


def render_answer(text):
    escaped_text = html.escape(text or "", quote=False)
    return markdown.markdown(escaped_text, extensions=["extra", "sane_lists"], output_format="html5")


@app.template_filter("render_markdown")
def render_markdown_filter(text):
    return Markup(render_answer(text))


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


def db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database():
    with db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, normalized_title),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                topic_id INTEGER NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                correct_attempts INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, topic_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(topic_id) REFERENCES topics(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS saved_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                topic_id INTEGER NOT NULL,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'answer',
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(topic_id) REFERENCES topics(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS completed_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                topic_id INTEGER NOT NULL,
                game_type TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                UNIQUE(user_id, topic_id, game_type),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(topic_id) REFERENCES topics(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO users (id, display_name, created_at)
            VALUES (?, ?, ?)
            """,
            (LOCAL_USER_ID, "Локальный профиль", now_iso()),
        )


def get_or_create_topic(topic):
    title = re.sub(r"\s+", " ", (topic or "").strip()) or "Тема не выбрана"
    normalized = normalize_topic_key(title)
    timestamp = now_iso()

    with db_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO topics (user_id, title, normalized_title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (LOCAL_USER_ID, title, normalized, timestamp, timestamp),
        )
        conn.execute(
            """
            UPDATE topics
            SET title = ?, updated_at = ?
            WHERE user_id = ? AND normalized_title = ?
            """,
            (title, timestamp, LOCAL_USER_ID, normalized),
        )
        return conn.execute(
            """
            SELECT id, title
            FROM topics
            WHERE user_id = ? AND normalized_title = ?
            """,
            (LOCAL_USER_ID, normalized),
        ).fetchone()


def save_card(topic, front, back, source="answer"):
    topic_row = get_or_create_topic(topic)
    clean_front = clean_text(front, topic_row["title"], 160)
    clean_back = clean_text(back, limit=700)

    if not clean_back:
        return

    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO saved_cards (user_id, topic_id, front, back, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (LOCAL_USER_ID, topic_row["id"], clean_front, clean_back, source, now_iso()),
        )


def completed_games_for_topic(topic):
    topic = (topic or current_topic() or "").strip()
    if not topic:
        return []

    normalized = normalize_topic_key(topic)
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT cg.game_type
            FROM completed_games cg
            JOIN topics t ON t.id = cg.topic_id
            WHERE cg.user_id = ? AND t.user_id = ? AND t.normalized_title = ?
            ORDER BY cg.completed_at DESC
            """,
            (LOCAL_USER_ID, LOCAL_USER_ID, normalized),
        ).fetchall()

    return [row["game_type"] for row in rows]


def is_game_completed(topic, game_type):
    return game_type in completed_games_for_topic(topic)


def mark_game_completed(topic, game_type):
    if game_type not in GAME_TYPES:
        return

    topic_row = get_or_create_topic(topic)
    with db_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO completed_games (user_id, topic_id, game_type, completed_at)
            VALUES (?, ?, ?, ?)
            """,
            (LOCAL_USER_ID, topic_row["id"], game_type, now_iso()),
        )


def stored_progress(topic):
    topic = (topic or current_topic() or "").strip()
    if not topic:
        return None

    normalized = normalize_topic_key(topic)
    with db_connection() as conn:
        return conn.execute(
            """
            SELECT t.title, p.score
            FROM topics t
            LEFT JOIN progress p ON p.topic_id = t.id AND p.user_id = t.user_id
            WHERE t.user_id = ? AND t.normalized_title = ?
            """,
            (LOCAL_USER_ID, normalized),
        ).fetchone()


def profile_snapshot():
    with db_connection() as conn:
        topic_rows = conn.execute(
            """
            SELECT
                t.id,
                t.title,
                t.updated_at,
                COALESCE(p.score, 0) AS score,
                COALESCE(p.attempts, 0) AS attempts,
                COALESCE(p.correct_attempts, 0) AS correct_attempts
            FROM topics t
            LEFT JOIN progress p ON p.topic_id = t.id AND p.user_id = t.user_id
            WHERE t.user_id = ?
            ORDER BY t.updated_at DESC
            LIMIT 20
            """,
            (LOCAL_USER_ID,),
        ).fetchall()
        card_rows = conn.execute(
            """
            SELECT c.front, c.back, c.source, c.created_at, t.title AS topic
            FROM saved_cards c
            JOIN topics t ON t.id = c.topic_id
            WHERE c.user_id = ?
            ORDER BY c.created_at DESC
            LIMIT 8
            """,
            (LOCAL_USER_ID,),
        ).fetchall()

        topics = [
        {
            "title": row["title"],
            "score": int(row["score"] or 0),
            "rank": understanding_rank(row["score"]),
            "rankClass": rank_class(row["score"]),
            "attempts": int(row["attempts"] or 0),
            "correctAttempts": int(row["correct_attempts"] or 0),
            "completedGames": completed_games_for_topic(row["title"]),
        }
        for row in topic_rows
    ]
    average_score = round(sum(item["score"] for item in topics) / len(topics)) if topics else 0

    return {
        "user": {"id": LOCAL_USER_ID, "displayName": "Локальный профиль"},
        "topics": topics,
        "overall": {
            "score": average_score,
            "rank": understanding_rank(average_score),
            "rankClass": rank_class(average_score),
            "topicsCount": len(topics),
        },
        "cards": [
            {
                "topic": row["topic"],
                "front": row["front"],
                "back": row["back"],
                "source": row["source"],
            }
            for row in card_rows
        ],
    }


def deepseek_request(messages):
    missing = [
        name for name, value in {
            "DEEPSEEK_API_KEY": DEEPSEEK_API_KEY,
            "DEEPSEEK_URL": DEEPSEEK_URL,
            "DEEPSEEK_MODEL": DEEPSEEK_MODEL,
            "FLASK_SECRET_KEY": app.secret_key,
        }.items()
        if not value
    ]

    if missing:
        return None, f"Не настроены переменные окружения: {', '.join(missing)}", 500

    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json',
    }

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": model_messages(messages),
        "stream": False
    }

    try:
        resp = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=API_TIMEOUT)
    except requests.Timeout:
        app.logger.exception("DeepSeek request timed out")
        return None, (
            f"API не успел ответить за {API_TIMEOUT} секунд. "
            "Попробуй ещё раз или задай вопрос чуть короче."
        ), 504
    except requests.RequestException as exc:
        app.logger.exception("DeepSeek request failed")
        return None, f"Не удалось связаться с API: {exc}", 502

    if not resp.ok:
        try:
            details = resp.json()
        except ValueError:
            details = resp.text

        app.logger.error("DeepSeek error %s: %s", resp.status_code, details)
        return None, f"Ошибка API {resp.status_code}: {details}", 502

    try:
        data = resp.json()
        return data['choices'][0]['message']['content'], None, 200
    except (ValueError, KeyError, IndexError, TypeError):
        app.logger.exception("Unexpected DeepSeek response")
        return None, "Не удалось разобрать ответ модели. Попробуйте позже.", 502


GAME_TYPES = {
    "true_false": "Быстрый чек",
    "fill_blank": "Вставь слова",
    "sentence_order": "Собери мысль",
    "simple_choice": "Лучшее объяснение",
}

UNDERSTANDING_RANKS = [
    (0, 19, "Coal"),
    (20, 39, "Bronze"),
    (40, 59, "Silver"),
    (60, 74, "Gold"),
    (75, 89, "Ruby"),
    (90, 100, "Diamond"),
]

RANK_CLASS_BY_NAME = {
    "Coal": "coal",
    "Bronze": "bronze",
    "Silver": "silver",
    "Gold": "gold",
    "Ruby": "ruby",
    "Diamond": "diamond",
}


def normalize_topic_key(topic):
    return re.sub(r"\s+", " ", (topic or "").strip()).casefold()


def ensure_progress_store():
    if 'understanding_progress' not in session:
        session['understanding_progress'] = {}
    return session['understanding_progress']


def current_topic():
    topic = (session.get('last_answer_topic') or session.get('current_topic') or "").strip()
    if topic:
        return topic

    recent_topics = ensure_recent_topics()
    return recent_topics[0] if recent_topics else ""


def understanding_rank(score):
    score = max(0, min(100, int(score or 0)))
    for start, end, rank in UNDERSTANDING_RANKS:
        if start <= score <= end:
            return rank
    return "Coal"


def rank_class(score):
    return RANK_CLASS_BY_NAME.get(understanding_rank(score), "coal")


def topic_learning_path(topic, score=0):
    topic = (topic or current_topic() or "").strip()
    if not topic:
        return []

    normalized = normalize_topic_key(topic)
    attempts = 0
    correct_attempts = 0
    card_count = 0

    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COALESCE(p.attempts, 0) AS attempts,
                COALESCE(p.correct_attempts, 0) AS correct_attempts,
                COUNT(c.id) AS card_count
            FROM topics t
            LEFT JOIN progress p ON p.topic_id = t.id AND p.user_id = t.user_id
            LEFT JOIN saved_cards c ON c.topic_id = t.id AND c.user_id = t.user_id
            WHERE t.user_id = ? AND t.normalized_title = ?
            GROUP BY t.id, p.attempts, p.correct_attempts
            """,
            (LOCAL_USER_ID, normalized),
        ).fetchone()

    if row:
        attempts = int(row["attempts"] or 0)
        correct_attempts = int(row["correct_attempts"] or 0)
        card_count = int(row["card_count"] or 0)

    completed_games = completed_games_for_topic(topic)
    weak_spot_found = attempts > 0 and (correct_attempts < attempts or len(completed_games) > 0)

    return [
        {"key": "understood", "label": "Понял суть", "done": True},
        {"key": "checked", "label": "Проверил себя", "done": len(completed_games) > 0},
        {"key": "weak_spot", "label": "Нашёл слабое место", "done": weak_spot_found},
        {"key": "repeated", "label": "Повторил карточку", "done": card_count > 0 and int(score or 0) >= 60},
    ]


def progress_snapshot(topic=None):
    topic = (topic or current_topic() or "").strip()
    score = 0

    if topic:
        entry = stored_progress(topic)
        if entry:
            score = int(entry["score"] or 0)
            topic = entry["title"]

    return {
        "topic": topic or "Тема не выбрана",
        "score": score,
        "rank": understanding_rank(score),
        "rankClass": rank_class(score),
        "completedGames": completed_games_for_topic(topic),
        "learningPath": topic_learning_path(topic, score),
        "label": f"{topic or 'Тема не выбрана'}: {understanding_rank(score)}, {score}%",
    }

def update_understanding_progress(correct, topic=None, game_type=None, complete_game=False):
    topic = (topic or current_topic() or "").strip()
    if not topic:
        topic = "Тема не выбрана"

    if complete_game and game_type in GAME_TYPES and is_game_completed(topic, game_type):
        snapshot = progress_snapshot(topic)
        snapshot["delta"] = 0
        snapshot["completedAlready"] = True
        return snapshot

    topic_row = get_or_create_topic(topic)
    delta = randint(8, 12) if correct else randint(2, 4)
    timestamp = now_iso()

    with db_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO progress (user_id, topic_id, score, attempts, correct_attempts, updated_at)
            VALUES (?, ?, 0, 0, 0, ?)
            """,
            (LOCAL_USER_ID, topic_row["id"], timestamp),
        )
        conn.execute(
            """
            UPDATE progress
            SET score = MIN(100, score + ?),
                attempts = attempts + 1,
                correct_attempts = correct_attempts + ?,
                updated_at = ?
            WHERE user_id = ? AND topic_id = ?
            """,
            (delta, 1 if correct else 0, timestamp, LOCAL_USER_ID, topic_row["id"]),
        )
        conn.execute(
            """
            UPDATE topics
            SET updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (timestamp, topic_row["id"], LOCAL_USER_ID),
        )

    session.modified = True

    if complete_game and game_type in GAME_TYPES:
        mark_game_completed(topic_row["title"], game_type)

    snapshot = progress_snapshot(topic_row["title"])
    snapshot["delta"] = delta

    return snapshot


init_database()


def parse_json_from_model(content):
    decoder = json.JSONDecoder()
    text = (content or "").strip()

    for index, char in enumerate(text):
        if char not in "[{":
            continue

        try:
            value, _ = decoder.raw_decode(text[index:])
            return value
        except json.JSONDecodeError:
            continue

    raise ValueError("Модель вернула не JSON")


def clean_text(value, fallback="", limit=500):
    text = str(value or fallback).strip()
    return text[:limit]


def normalize_true_false(data):
    if isinstance(data, list):
        items = data
        meta = {}
    else:
        items = data.get("items", [])
        meta = data

    normalized = []

    for item in items[:3]:
        if not isinstance(item, dict):
            continue

        text = clean_text(item.get("text"), limit=280)
        if not text:
            continue

        normalized.append({
            "text": text,
            "correct": bool(item.get("correct")),
            "explanation": clean_text(item.get("explanation"), "Смотри на смысл утверждения, а не на то, как уверенно оно звучит.", 320),
            "hint": clean_text(item.get("hint"), "Проверь слова вроде «всегда», «только» и «никогда».", 180),
        })

    if len(normalized) < 2:
        raise ValueError("Не удалось собрать True/False игру")

    return {
        "type": "true_false",
        "title": clean_text(meta.get("title"), GAME_TYPES["true_false"], 80),
        "intro": clean_text(meta.get("intro"), "Отметь, где мысль верная, а где есть ловушка.", 160),
        "items": normalized,
    }


def normalize_fill_blank(data):
    text_parts = data.get("textParts") or []
    answers = data.get("answers") or []
    word_bank = data.get("wordBank") or []

    if not isinstance(text_parts, list) or not isinstance(answers, list):
        raise ValueError("Некорректная структура игры с пропусками")
    if not isinstance(word_bank, list):
        word_bank = []

    normalized_answers = []
    for variants in answers[:3]:
        if isinstance(variants, str):
            variants = [variants]
        variants = [clean_text(variant, limit=60) for variant in variants if clean_text(variant, limit=60)]
        if variants:
            normalized_answers.append(variants[:4])

    text_parts = [clean_text(part, limit=220) for part in text_parts[:len(normalized_answers) + 1]]

    if len(normalized_answers) == 0 or len(text_parts) != len(normalized_answers) + 1:
        raise ValueError("Не удалось собрать пропуски без двусмысленности")

    normalized_bank = []
    for word in word_bank:
        word = clean_text(word, limit=60)
        if word and word.lower() not in [item.lower() for item in normalized_bank]:
            normalized_bank.append(word)

    for variants in normalized_answers:
        canonical = variants[0]
        if canonical.lower() not in [item.lower() for item in normalized_bank]:
            normalized_bank.append(canonical)

    if len(normalized_bank) < len(normalized_answers):
        raise ValueError("Не хватает слов для банка")

    return {
        "type": "fill_blank",
        "title": clean_text(data.get("title"), GAME_TYPES["fill_blank"], 80),
        "intro": clean_text(data.get("intro"), "Поставь слова туда, где без них ломается смысл.", 160),
        "textParts": text_parts,
        "answers": normalized_answers,
        "wordBank": normalized_bank[:6],
        "hint": clean_text(data.get("hint"), "Выбирай слова, которые отвечают на вопрос «зачем это нужно?»", 220),
        "success": clean_text(data.get("success"), "Вот теперь смысл собрался.", 180),
        "feedback": clean_text(data.get("feedback"), "Почти. Тут важно поставить слово, без которого меняется смысл.", 220),
    }


def normalize_sentence_order(data):
    fragments = data.get("fragments") or []
    order = data.get("order") or []

    if not isinstance(fragments, list) or not isinstance(order, list):
        raise ValueError("Некорректная структура сборки предложения")

    normalized_fragments = []
    seen_ids = set()

    for index, fragment in enumerate(fragments[:8], start=1):
        if not isinstance(fragment, dict):
            continue

        fragment_id = clean_text(fragment.get("id"), f"f{index}", 24)
        text = clean_text(fragment.get("text"), limit=90)

        if not text or fragment_id in seen_ids:
            continue

        seen_ids.add(fragment_id)
        normalized_fragments.append({"id": fragment_id, "text": text})

    valid_ids = {fragment["id"] for fragment in normalized_fragments}
    normalized_order = [clean_text(item, limit=24) for item in order if clean_text(item, limit=24) in valid_ids]

    if len(normalized_fragments) < 4 or len(normalized_order) != len(normalized_fragments):
        raise ValueError("Не удалось собрать однозначный порядок фрагментов")

    return {
        "type": "sentence_order",
        "title": clean_text(data.get("title"), GAME_TYPES["sentence_order"], 80),
        "intro": clean_text(data.get("intro"), "Собери короткую мысль так, чтобы причина и смысл встали на места.", 180),
        "fragments": normalized_fragments,
        "order": normalized_order,
        "hint": clean_text(data.get("hint"), "Начни с того, о чём идёт речь, а потом добавь, зачем это нужно.", 220),
        "success": clean_text(data.get("success"), "Вот так мысль звучит яснее и по-человечески.", 180),
        "feedback": clean_text(data.get("feedback"), "Мысль почти рядом, но порядок сейчас немного ломает смысл.", 220),
    }


def normalize_simple_choice(data):
    options = data.get("options") or []
    normalized = []
    best_count = 0

    if not isinstance(options, list):
        raise ValueError("Некорректная структура вариантов")

    for index, option in enumerate(options[:4], start=1):
        if not isinstance(option, dict):
            continue

        option_id = clean_text(option.get("id"), f"o{index}", 24)
        text = clean_text(option.get("text"), limit=260)
        is_best = bool(option.get("isBest"))

        if not text:
            continue

        if is_best:
            best_count += 1

        normalized.append({
            "id": option_id,
            "text": text,
            "isBest": is_best,
            "feedback": clean_text(option.get("feedback"), "Этот вариант звучит убедительно, но проверь, не потерялся ли главный смысл.", 260),
        })

    if len(normalized) < 3 or best_count != 1:
        raise ValueError("Нужен ровно один лучший вариант объяснения")

    return {
        "type": "simple_choice",
        "title": clean_text(data.get("title"), GAME_TYPES["simple_choice"], 80),
        "intro": clean_text(data.get("intro"), "Выбери вариант, который простыми словами объясняет тему и не врёт.", 180),
        "question": clean_text(data.get("question"), "Как бы это лучше объяснить простыми словами?", 160),
        "options": normalized,
        "hint": clean_text(data.get("hint"), "Ищи вариант, где мысль понятная, но важный нюанс не потерян.", 220),
        "success": clean_text(data.get("success"), "Вот это хорошее объяснение: простое, но честное.", 180),
    }


def normalize_game(game_type, data):
    if not isinstance(data, dict) and game_type != "true_false":
        raise ValueError("Игра должна быть JSON-объектом")

    normalizers = {
        "true_false": normalize_true_false,
        "fill_blank": normalize_fill_blank,
        "sentence_order": normalize_sentence_order,
        "simple_choice": normalize_simple_choice,
    }

    return normalizers[game_type](data)


def parse_and_normalize_game(game_type, content):
    raw_game = parse_json_from_model(content)
    return normalize_game(game_type, raw_game)


def repair_game_json(game_type, content, parse_error):
    repair_messages = [
        {"role": "system", "content": "Ты исправляешь JSON для учебной мини-игры. Верни только валидный JSON без markdown и текста вокруг."},
        {
            "role": "user",
            "content": (
                f"Тип игры: {game_type}\n"
                f"Ошибка проверки: {parse_error}\n\n"
                f"Правила и схема:\n{build_game_prompt(game_type)}\n\n"
                f"Вот ответ модели, который надо исправить:\n{content}"
            )
        }
    ]

    repaired_content, error, status = deepseek_request(repair_messages)
    if error:
        raise ValueError(f"не удалось автоматически исправить JSON: {error}")

    return parse_and_normalize_game(game_type, repaired_content)


def build_game_prompt(game_type):
    common_rules = """
Общие правила:
- Используй только смысл из объяснения ниже.
- Одна игра проверяет одно микро-умение.
- Не добавляй случайные факты.
- Формулировки короткие, дружелюбные, без длинных инструкций.
- Ошибка должна вести к мягкому объяснению, без токсичного тона.
- Верни только валидный JSON без markdown и без текста вокруг.
"""

    prompts = {
        "true_false": """
Создай игру True/False из 3 утверждений.
Проверяй ключевые факты и типичные заблуждения.
Избегай двойных отрицаний и спорных исключений.

Схема:
{
  "type": "true_false",
  "title": "Быстрый чек",
  "intro": "короткая фраза",
  "items": [
    {
      "text": "одно утверждение",
      "correct": true,
      "explanation": "мягко объясни, почему так",
      "hint": "короткая подсказка"
    }
  ]
}
""",
        "fill_blank": """
Создай игру с пропусками на 1 короткое объяснение.
Сделай 2 пропуска. Скрывай только слова, без которых ломается смысл.
Не скрывай слова с большим количеством равноправных синонимов.
В wordBank добавь правильные слова и 1-2 явно лишних, но не спорных.

Схема:
{
  "type": "fill_blank",
  "title": "Вставь слова",
  "intro": "короткая фраза",
  "textParts": ["текст до первого пропуска ", ", текст между пропусками ", "."],
  "answers": [["первое слово", "допустимый вариант"], ["второе слово"]],
  "wordBank": ["первое слово", "второе слово", "лишнее"],
  "hint": "намёк",
  "success": "тёплый успех",
  "feedback": "мягкая ошибка"
}
""",
        "sentence_order": """
Создай игру "Собери мысль".
Собери одно простое предложение длиной 8-16 слов.
Разрежь его на 4-6 смысловых фрагментов, не по одному символу и не слишком мелко.
Порядок должен быть единственным очевидно правильным.

Схема:
{
  "type": "sentence_order",
  "title": "Собери мысль",
  "intro": "короткая фраза",
  "fragments": [
    {"id": "f1", "text": "первый фрагмент"},
    {"id": "f2", "text": "второй фрагмент"}
  ],
  "order": ["f1", "f2"],
  "hint": "намёк",
  "success": "тёплый успех",
  "feedback": "мягкая ошибка"
}
""",
        "simple_choice": """
Создай игру выбора лучшего простого объяснения.
Нужно 4 варианта:
1 лучший: простой и точный;
1 слишком сложный, но технически близкий;
1 слишком упрощённый и уже искажающий смысл;
1 типичное заблуждение.
Ровно один вариант должен иметь "isBest": true.

Схема:
{
  "type": "simple_choice",
  "title": "Лучшее объяснение",
  "intro": "короткая фраза",
  "question": "Как бы это лучше объяснить простыми словами?",
  "options": [
    {"id": "a", "text": "вариант", "isBest": true, "feedback": "почему этот вариант хорош или чем сбивает"}
  ],
  "hint": "намёк",
  "success": "тёплый успех"
}
""",
    }

    return f"{common_rules}\n{prompts[game_type]}"

@app.route('/', methods=['GET', 'POST'])
def index():
    messages = ensure_messages()
    recent_topics = ensure_recent_topics()
    explanation = None

    if request.method == 'POST':
        app.logger.info(f"POST to {DEEPSEEK_URL} using model {DEEPSEEK_MODEL}")
        topic = request.form.get('topic', '').strip()
        mode = request.form.get('mode', '')

        if topic:
            session['current_topic'] = topic
            get_or_create_topic(topic)
            recent_topics = add_recent_topic(topic)
            messages.append({"role": "user", "content": f"{mode_instruction(mode)}\nТема: {topic}", "display": topic, "mode": mode})
            raw_answer, error, _ = deepseek_request(build_answer_messages(topic, mode))

            if raw_answer:
                explanation = render_answer(raw_answer)
                messages.append({"role": "assistant", "content": raw_answer})
                session['last_answer'] = raw_answer
                session['last_answer_topic'] = topic
                session.pop('quiz', None)
                save_card(topic, topic, raw_answer, "answer")
            else:
                explanation = error

            session.modified = True

    return render_template(
        'index.html',
        explanation=explanation,
        messages=messages,
        recent_topics=recent_topics,
        progress=progress_snapshot(),
        profile=profile_snapshot(),
    )

@app.route('/ask', methods=['POST'])
def ask():
    messages = ensure_messages()
    data = request.get_json(silent=True) or {}
    topic = data.get('topic', '').strip()
    mode = data.get('mode', '')

    if not topic:
        return jsonify({"error": "Пустой запрос"}), 400

    session['current_topic'] = topic
    get_or_create_topic(topic)
    recent_topics = add_recent_topic(topic)
    messages.append({"role": "user", "content": f"{mode_instruction(mode)}\nТема: {topic}", "display": topic, "mode": mode})

    answer, error, status = deepseek_request(build_answer_messages(topic, mode))
    if error:
        messages.pop()
        session.modified = True
        return jsonify({"error": error}), status

    messages.append({"role": "assistant", "content": answer})
    session['last_answer'] = answer
    session['last_answer_topic'] = topic
    session.pop('quiz', None)
    save_card(topic, topic, answer, "answer")
    session.modified = True

    return jsonify({
        "answer": render_answer(answer),
        "topic": topic,
        "recentTopics": recent_topics,
        "progress": progress_snapshot(topic),
    })


@app.route('/simplify', methods=['POST'])
def simplify():
    messages = ensure_messages()
    last_answer = get_last_answer()

    if not last_answer:
        return jsonify({"error": "Сначала задай вопрос, потом упрощай ответ 🙂"}), 400

    simplify_prompt = """
Переформулируй объяснение ниже ещё проще.

Правила:
- Не добавляй новых фактов.
- Сохрани главный смысл.
- Пиши тепло, коротко и по-человечески.
- Если есть сложные термины, замени их бытовыми словами или простой аналогией.
- Ответ должен быть самостоятельным, без фразы "в предыдущем ответе".
- 4-7 коротких абзацев или пунктов, если так понятнее.
"""

    request_messages = [
        {"role": "system", "content": "Ты объясняешь сложные темы максимально простым, дружелюбным языком."},
        {"role": "user", "content": f"{simplify_prompt}\n\nИсходное объяснение:\n{last_answer}"}
    ]

    answer, error, status = deepseek_request(request_messages)
    if error:
        return jsonify({"error": error}), status

    messages.append({
        "role": "user",
        "content": "Сделай предыдущее объяснение ещё проще.",
        "display": "Ещё проще"
    })
    messages.append({"role": "assistant", "content": answer})
    session['last_answer'] = answer
    session.pop('quiz', None)
    save_card(current_topic(), "Ещё проще", answer, "simplify")
    session.modified = True

    return jsonify({"answer": render_answer(answer)})

@app.route('/game', methods=['POST'])
def game():
    data = request.get_json(silent=True) or {}
    game_type = data.get("type", "true_false")
    requested_topic = (data.get("topic") or "").strip()

    if game_type not in GAME_TYPES:
        return jsonify({"error": "Такой мини-игры пока нет"}), 400

    if 'messages' not in session:
        return jsonify({"error": "Нет истории"}), 400

    last_answer = get_last_answer()

    if not last_answer:
        return jsonify({
            "error": "Сначала задай вопрос, потом запускай игру 🙂"
        }), 400

    topic = requested_topic or current_topic()
    if is_game_completed(topic, game_type):
        return jsonify({
            "error": "Эта мини-игра по выбранной теме уже пройдена. Выбери другую игру или новую тему.",
            "completedGames": completed_games_for_topic(topic),
            "progress": progress_snapshot(topic),
        }), 409

    messages = [
        {"role": "system", "content": "Ты создаёшь учебные мини-игры, которые помогают понять смысл, а не просто угадать ответ."},
        {"role": "user", "content": f"Вот объяснение, по которому нужно сделать игру:\n{last_answer}\n\n{build_game_prompt(game_type)}"}
    ]

    content, error, status = deepseek_request(messages)
    if error:
        return jsonify({"error": error}), status

    try:
        game_data = parse_and_normalize_game(game_type, content)
    except (ValueError, TypeError, AttributeError) as exc:
        app.logger.warning("Mini-game parse failed, trying repair: %s", exc)
        try:
            game_data = repair_game_json(game_type, content, exc)
        except (ValueError, TypeError, AttributeError) as repair_exc:
            app.logger.exception("Mini-game repair failed")
            return jsonify({"error": f"Не удалось собрать игру: {repair_exc}"}), 500

    session['quiz'] = game_data
    session.modified = True
    return jsonify({"game": game_data})


@app.route('/progress', methods=['POST'])
def progress():
    data = request.get_json(silent=True) or {}
    correct = bool(data.get("correct"))
    topic = (data.get("topic") or current_topic()).strip()
    game_type = data.get("gameType")
    complete_game = bool(data.get("completeGame"))

    return jsonify({"progress": update_understanding_progress(correct, topic, game_type, complete_game)})


@app.route('/profile', methods=['GET'])
def profile():
    return jsonify(profile_snapshot())


@app.route('/reset', methods=['POST'])
def reset():
    session.pop('messages', None)
    session.pop('quiz', None)
    session.pop('last_answer', None)
    session.pop('last_answer_topic', None)
    session.pop('recent_topics', None)
    session.pop('current_topic', None)
    session.pop('understanding_progress', None)
    ensure_messages()
    ensure_recent_topics()
    session.modified = True
    return jsonify({"ok": True})

if __name__ == '__main__':
    app.run(debug=True)
