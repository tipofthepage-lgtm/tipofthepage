from flask import Flask, render_template, session, request, jsonify
from difflib import SequenceMatcher
import sqlite3
import hashlib
from datetime import date
import config

# -- Env --------------------------------------------------------------------

app = Flask(__name__)

# -- Config -----------------------------------------------------------------
app.secret_key = config.SECRET_KEY
DB_PATH        = config.DB_PATH


# -- Database helpers -------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                author     TEXT NOT NULL,
                year       INTEGER,
                genre      TEXT NOT NULL,
                quote      TEXT NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

# -- Fixing db problems -----------------------------------------------------
init_db()


def get_daily_book():
    """Pick a consistent quote for today by hashing the date against the quote IDs."""
    with get_db() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM quotes ORDER BY id").fetchall()]
        if not ids:
            return None
        # Deterministic pick: hash today's date, index into the id list
        day_hash  = int(hashlib.md5(str(date.today()).encode()).hexdigest(), 16)
        chosen_id = ids[day_hash % len(ids)]
        row = conn.execute(
            "SELECT id, title, author, year, genre, quote FROM quotes WHERE id = ?",
            (chosen_id,)
        ).fetchone()
    return dict(row) if row else None


def get_random_book(genre=None, exclude_ids=None):
    """Return a random quote, optionally filtered by genre and excluding already-seen IDs."""
    with get_db() as conn:
        params = []
        clauses = []
        if genre:
            clauses.append("genre = ?")
            params.append(genre)
        if exclude_ids:
            placeholders = ",".join("?" * len(exclude_ids))
            clauses.append(f"id NOT IN ({placeholders})")
            params.extend(exclude_ids)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        row = conn.execute(
            f"SELECT id, title, author, year, genre, quote FROM quotes {where} ORDER BY RANDOM() LIMIT 1",
            params
        ).fetchone()
    return dict(row) if row else None


def get_all_genres():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT genre FROM quotes ORDER BY genre"
        ).fetchall()
    return [r["genre"] for r in rows]


def get_all_live_quotes():
    with get_db() as conn:
        return [r["quote"] for r in conn.execute("SELECT quote FROM quotes").fetchall()]


def fuzzy_match(candidate, existing_quotes, threshold=0.82):
    best_ratio, best_quote = 0, None
    for q in existing_quotes:
        ratio = SequenceMatcher(None, candidate.lower(), q.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_quote = q
    return (best_quote, best_ratio) if best_ratio >= threshold else (None, best_ratio)


def record_result(quote_id, mode, outcome, guess_count=None):
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO results (quote_id, mode, outcome, guess_count)
                   VALUES (?, ?, ?, ?)""",
                (quote_id, mode, outcome, guess_count)
            )
            conn.commit()
    except Exception as e:
        app.logger.warning(f"Failed to record result: {e}")


# -- Mode select ------------------------------------------------------------

@app.route("/")
def index():
    genres = get_all_genres()
    return render_template("index.html", genres=genres)


# -- Daily mode -------------------------------------------------------------

@app.route("/daily")
def daily():
    # Only start a new daily game if the date has changed or no daily game exists
    today = str(date.today())
    if session.get("mode") != "daily" or session.get("daily_date") != today:
        book = get_daily_book()
        if book is None:
            return render_template("empty.html")
        session["book"]        = book
        session["quote_id"]    = book["id"]
        session["mode"]        = "daily"
        session["daily_date"]  = today
        session["genre_mode"]  = False
        session["clue_index"]  = 0
        session["guess_count"] = 0
        session["game_over"]   = None
        session["seen_ids"]    = []
    return render_template("game.html", **_state())


# -- Endless mode -----------------------------------------------------------

@app.route("/endless", methods=["GET"])
def endless():
    genre = request.args.get("genre", "").strip() or None
    genre_mode = genre is not None
    book = get_random_book(genre=genre)
    if book is None:
        return render_template("empty.html", genre=genre)
    session["book"]        = book
    session["quote_id"]    = book["id"]
    session["mode"]        = "endless"
    session["genre_mode"]  = genre_mode
    session["genre_filter"]= genre
    session["daily_date"]  = None
    session["clue_index"]  = 1 if genre_mode else 0   # genre already known = start one clue ahead
    session["guess_count"] = 0
    session["game_over"]   = None
    session["seen_ids"]    = [book["id"]]
    return render_template("game.html", **_state())


@app.route("/next-quote", methods=["POST"])
def next_quote():
    """Load the next quote in endless mode without resetting seen list."""
    if session.get("mode") != "endless":
        return jsonify({"error": "not in endless mode"}), 400
    genre      = session.get("genre_filter")
    seen_ids   = session.get("seen_ids", [])
    book       = get_random_book(genre=genre, exclude_ids=seen_ids)
    genre_mode = session.get("genre_mode", False)
    if book is None:
        # Exhausted all quotes in this genre/pool — reset seen and pick fresh
        session["seen_ids"] = []
        book = get_random_book(genre=genre)
    if book is None:
        return jsonify({"error": "no quotes available"}), 400
    seen_ids.append(book["id"])
    session["book"]        = book
    session["quote_id"]    = book["id"]
    session["seen_ids"]    = seen_ids
    session["clue_index"]  = 1 if genre_mode else 0
    session["guess_count"] = 0
    session["game_over"]   = None
    return jsonify(_state())


# -- Shared game routes -----------------------------------------------------

@app.route("/new-game", methods=["POST"])
def new_game():
    """Restart the current mode from scratch."""
    mode = session.get("mode", "daily")
    if mode == "daily":
        return daily()
    else:
        genre = session.get("genre_filter")
        url   = f"/endless?genre={genre}" if genre else "/endless"
        from flask import redirect
        return redirect(url)


@app.route("/guess", methods=["POST"])
def guess():
    if session.get("game_over"):
        return jsonify(_state())

    data       = request.get_json()
    guess_text = (data.get("guess") or "").strip().lower()
    book       = _current_book()
    genre_mode = session.get("genre_mode", False)
    max_guesses = 3 if genre_mode else 4

    if not guess_text:
        return jsonify({**_state(), "feedback": "Please enter a guess.", "feedback_type": "info"})

    session["guess_count"] = session.get("guess_count", 0) + 1
    guesses   = session["guess_count"]
    remaining = max_guesses - guesses

    if guess_text == book["title"].lower():
        session["game_over"] = "win"
        record_result(session["quote_id"], session.get("mode","daily"), "win", guesses)
        return jsonify({**_state(), "feedback": "Correct! Well read!", "feedback_type": "correct"})

    if guesses >= max_guesses:
        session["game_over"] = "lose"
        record_result(session["quote_id"], session.get("mode","daily"), "lose")
        return jsonify({**_state(), "feedback": f'The answer was "{book["title"]}".', "feedback_type": "wrong"})

    # Auto-advance clue, but never rewind past genre (index 1) in genre mode
    min_clue = 1 if genre_mode else 0
    if session.get("clue_index", min_clue) < (guesses + min_clue):
        session["clue_index"] = guesses + min_clue

    return jsonify({
        **_state(),
        "feedback": f"Not quite! {remaining} guess{'es' if remaining != 1 else ''} remaining.",
        "feedback_type": "wrong"
    })



@app.route("/render-state", methods=["POST"])
def render_state():
    return render_template("_game.html", **_state())


# -- Submission route -------------------------------------------------------

@app.route("/submit")
def submit_page():
    return render_template("submit.html", google_form_url=config.GOOGLE_FORM_URL)


# -- Game state helpers -----------------------------------------------------

def _new_game():
    book = get_random_book()
    if book is None:
        book = {"id": 0, "title": "No quotes yet", "author": "—",
                "year": 0, "genre": "—",
                "quote": "The database is empty. Add some quotes first!"}
    session["book"]        = book
    session["quote_id"]    = book["id"]
    session["mode"]        = "daily"
    session["genre_mode"]  = False
    session["clue_index"]  = 0
    session["guess_count"] = 0
    session["game_over"]   = None


def _current_book():
    return session.get("book", {
        "id": 0, "title": "", "author": "", "year": 0, "genre": "", "quote": ""
    })


def _state():
    book        = _current_book()
    clue_index  = session.get("clue_index",  0)
    guess_count = session.get("guess_count", 0)
    game_over   = session.get("game_over")
    mode        = session.get("mode", "daily")
    genre_mode  = session.get("genre_mode", False)
    max_guesses = 3 if genre_mode else 4

    # In genre mode the genre pill is always visible from the start
    revealed_clues = {}
    if genre_mode:
        revealed_clues["genre"] = book["genre"]
    if clue_index >= 1 and not genre_mode:
        revealed_clues["genre"]  = book["genre"]
    if clue_index >= 2:
        revealed_clues["year"]   = book["year"]
    if clue_index >= 3:
        revealed_clues["author"] = book["author"]

    if game_over == "lose":
        revealed_clues = {
            "genre":  book["genre"],
            "year":   book["year"],
            "author": book["author"],
        }

    return {
        "quote":            book["quote"],
        "clue_index":       clue_index,
        "guess_count":      guess_count,
        "max_guesses":      max_guesses,
        "game_over":        game_over,
        "revealed_clues":   revealed_clues,
        "mode":             mode,
        "genre_mode":       genre_mode,
        "genre_filter":     session.get("genre_filter"),
        "title":            book["title"]  if game_over else None,
        "author":           book["author"] if game_over else None,
        "year":             book["year"]   if game_over else None,
    }


# -- Boot -------------------------------------------------------------------

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port = int(os.environ.get("PORT", 5000)))
    # app.run(debug=True)