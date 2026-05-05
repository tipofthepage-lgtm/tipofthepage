"""
Tip of the Page — Quote Manager
PyQt6 GUI for managing book quotes in the PostgreSQL database.
Includes: Add Quote, Import Pending submissions.
"""

import sys
import os
import psycopg2
import psycopg2.extras
from difflib import SequenceMatcher
from dotenv import load_dotenv
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QFrame, QScrollArea,
    QMessageBox, QSpinBox, QComboBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

load_dotenv()


# ── Database ───────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set. Check your .env file.")
    sys.exit(1)


def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def get_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def init_db():
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id         SERIAL PRIMARY KEY,
                    title      TEXT NOT NULL,
                    author     TEXT NOT NULL,
                    year       INTEGER,
                    genre      TEXT NOT NULL,
                    quote      TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pending_quotes (
                    id              SERIAL PRIMARY KEY,
                    title           TEXT NOT NULL,
                    author          TEXT NOT NULL,
                    year            INTEGER,
                    genre           TEXT NOT NULL,
                    quote           TEXT NOT NULL,
                    submitter_email TEXT NOT NULL,
                    submitted_at    TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.commit()


def insert_quote(title, author, year, genre, quote):
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                "INSERT INTO quotes (title, author, year, genre, quote) VALUES (%s, %s, %s, %s, %s)",
                (title, author, year, genre, quote)
            )
        conn.commit()


def delete_pending(pending_id):
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute("DELETE FROM pending_quotes WHERE id = %s", (pending_id,))
        conn.commit()


def approve_pending(pending_id):
    """Move a pending quote into the live quotes table, then delete from pending."""
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute("SELECT * FROM pending_quotes WHERE id = %s", (pending_id,))
            row = cur.fetchone()
            if row is None:
                raise ValueError("Pending quote not found.")
            cur.execute(
                "INSERT INTO quotes (title, author, year, genre, quote) VALUES (%s, %s, %s, %s, %s)",
                (row["title"], row["author"], row["year"], row["genre"], row["quote"])
            )
            cur.execute("DELETE FROM pending_quotes WHERE id = %s", (pending_id,))
        conn.commit()
    return dict(row)


def get_pending_quotes():
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute("SELECT * FROM pending_quotes ORDER BY submitted_at DESC")
            return cur.fetchall()


def get_stats():
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute("SELECT COUNT(*) as count FROM quotes")
            total = cur.fetchone()["count"]
            cur.execute("SELECT COUNT(*) as count FROM pending_quotes")
            pending = cur.fetchone()["count"]
            cur.execute(
                "SELECT genre, COUNT(*) as cnt FROM quotes GROUP BY genre ORDER BY cnt DESC"
            )
            genres = cur.fetchall()
    return total, pending, genres


def get_all_quotes():
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute("SELECT quote FROM quotes")
            return cur.fetchall()


def check_duplicate_exact(quote_text):
    with get_db() as conn:
        with get_cursor(conn) as cur:
            cur.execute(
                "SELECT id FROM quotes WHERE LOWER(quote) = LOWER(%s)", (quote_text,)
            )
            return cur.fetchone()


def check_duplicate_fuzzy(quote_text, threshold=0.85):
    all_quotes = get_all_quotes()
    best_ratio, best_quote = 0, None
    for row in all_quotes:
        ratio = SequenceMatcher(None, quote_text.lower(), row["quote"].lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_quote = row["quote"]
    return (best_quote, best_ratio) if best_ratio >= threshold else (None, best_ratio)


# ── Palette ────────────────────────────────────────────────────────────────

DARK    = "#1a1612"
SURFACE = "#252018"
CARD    = "#2e2820"
BORDER  = "#3d3528"
GOLD    = "#c9a84c"
GOLD2   = "#e8c96a"
CREAM   = "#f0e8d0"
MUTED   = "#8a7d65"
GREEN   = "#6aab6a"
RED     = "#c06060"
AMBER   = "#c89040"
BLUE    = "#5a8abf"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {DARK};
    color: {CREAM};
    font-family: 'Georgia', serif;
}}
QLabel {{ color: {CREAM}; background: transparent; }}
QLabel#section_title {{
    font-size: 11px; letter-spacing: 3px; color: {GOLD};
    font-family: 'Courier New', monospace; font-weight: bold;
}}
QLabel#field_label {{
    font-size: 12px; color: {MUTED}; font-family: 'Courier New', monospace;
}}
QLineEdit, QSpinBox, QComboBox {{
    background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: 2px;
    color: {CREAM}; padding: 8px 12px; font-size: 13px; font-family: 'Georgia', serif;
    selection-background-color: {GOLD}; selection-color: {DARK};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {GOLD}; }}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{ border: 1px solid #5a4e38; }}
QTextEdit {{
    background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: 2px;
    color: {CREAM}; padding: 10px 12px; font-size: 14px; font-family: 'Georgia', serif;
    font-style: italic; selection-background-color: {GOLD}; selection-color: {DARK};
}}
QTextEdit:focus {{ border: 1px solid {GOLD}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background-color: {CARD}; border: 1px solid {BORDER};
    color: {CREAM}; selection-background-color: {GOLD}; selection-color: {DARK};
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: {SURFACE}; width: 6px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: {GOLD}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; background: {DARK}; }}
QTabBar::tab {{
    background: {SURFACE}; color: {MUTED}; border: 1px solid {BORDER};
    padding: 10px 24px; font-family: 'Courier New', monospace;
    font-size: 11px; letter-spacing: 1px;
}}
QTabBar::tab:selected {{ background: {DARK}; color: {GOLD}; border-bottom: 2px solid {GOLD}; }}
QTabBar::tab:hover:!selected {{ color: {CREAM}; }}
QTableWidget {{
    background: {SURFACE}; border: 1px solid {BORDER};
    color: {CREAM}; gridline-color: {BORDER};
    font-family: 'Georgia', serif; font-size: 12px;
    selection-background-color: {CARD};
    selection-color: {CREAM};
}}
QTableWidget::item {{ padding: 6px 10px; border-bottom: 1px solid {BORDER}; }}
QTableWidget::item:selected {{ background: {CARD}; }}
QHeaderView::section {{
    background: {CARD}; color: {GOLD}; border: none;
    border-bottom: 1px solid {BORDER}; border-right: 1px solid {BORDER};
    padding: 8px 10px; font-family: 'Courier New', monospace;
    font-size: 10px; letter-spacing: 2px; font-weight: bold;
}}
QPushButton#submit_btn {{
    background-color: {GOLD}; color: {DARK}; border: none; border-radius: 2px;
    font-size: 13px; font-family: 'Courier New', monospace; font-weight: bold;
    letter-spacing: 2px; padding: 12px 32px;
}}
QPushButton#submit_btn:hover {{ background-color: {GOLD2}; }}
QPushButton#submit_btn:pressed {{ background-color: #a88830; }}
QPushButton#clear_btn {{
    background-color: transparent; color: {MUTED}; border: 1px solid {BORDER};
    border-radius: 2px; font-size: 12px; font-family: 'Courier New', monospace;
    letter-spacing: 1px; padding: 11px 24px;
}}
QPushButton#clear_btn:hover {{ border-color: {MUTED}; color: {CREAM}; }}
QPushButton#approve_btn {{
    background-color: {GREEN}; color: {DARK}; border: none; border-radius: 2px;
    font-size: 11px; font-family: 'Courier New', monospace; font-weight: bold;
    letter-spacing: 1px; padding: 6px 16px;
}}
QPushButton#approve_btn:hover {{ background-color: #82c982; }}
QPushButton#reject_btn {{
    background-color: transparent; color: {RED}; border: 1px solid {RED};
    border-radius: 2px; font-size: 11px; font-family: 'Courier New', monospace;
    letter-spacing: 1px; padding: 5px 14px;
}}
QPushButton#reject_btn:hover {{ background-color: rgba(192,96,96,0.15); }}
QPushButton#refresh_btn {{
    background-color: transparent; color: {MUTED}; border: 1px solid {BORDER};
    border-radius: 2px; font-size: 11px; font-family: 'Courier New', monospace;
    letter-spacing: 1px; padding: 6px 16px;
}}
QPushButton#refresh_btn:hover {{ border-color: {MUTED}; color: {CREAM}; }}
QSpinBox::up-button, QSpinBox::down-button {{ background: {BORDER}; border: none; width: 16px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {GOLD}; }}
"""


# ── Shared widgets ─────────────────────────────────────────────────────────

class Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setStyleSheet(f"color:{BORDER}; background:{BORDER}; border:none; max-height:1px;")


class StatCard(QFrame):
    def __init__(self, label, value, accent=False, parent=None):
        super().__init__(parent)
        self.setObjectName("stat_card")
        color = GOLD if accent else MUTED
        self.setStyleSheet(f"QFrame#stat_card{{background:{CARD};border:1px solid {BORDER};border-radius:2px;}}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet(f"font-size:28px;font-weight:bold;color:{color};font-family:'Courier New',monospace;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label = QLabel(label.upper())
        self.text_label.setStyleSheet(f"font-size:9px;letter-spacing:2px;color:{MUTED};font-family:'Courier New',monospace;")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)
        layout.addWidget(self.text_label)

    def update_value(self, value):
        self.value_label.setText(str(value))


class GenreRow(QWidget):
    def __init__(self, genre, count, total, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        genre_label = QLabel(genre)
        genre_label.setStyleSheet(f"font-size:12px;color:{CREAM};")
        count_label = QLabel(str(count))
        count_label.setStyleSheet(f"font-size:12px;color:{GOLD};font-family:'Courier New',monospace;font-weight:bold;")
        count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        bar_container = QFrame()
        bar_container.setFixedHeight(4)
        bar_container.setStyleSheet(f"background:{BORDER};border-radius:2px;")
        bar_fill = QFrame(bar_container)
        pct = max(4, int((count / max(total, 1)) * 120))
        bar_fill.setFixedSize(pct, 4)
        bar_fill.setStyleSheet(f"background:{GOLD};border-radius:2px;")
        layout.addWidget(genre_label, stretch=3)
        layout.addWidget(bar_container, stretch=2)
        layout.addWidget(count_label, stretch=1)


class FeedbackBanner(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide()
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text, kind="info", duration=4000):
        colors = {
            "success": (GREEN, "#1e3a1e"),
            "error":   (RED,   "#3a1e1e"),
            "warning": (AMBER, "#3a2e1a"),
            "info":    (GOLD,  "#2e2818"),
        }
        fg, bg = colors.get(kind, colors["info"])
        self.setStyleSheet(f"""
            background:{bg}; border:1px solid {fg}; border-radius:2px;
            color:{fg}; font-size:12px; font-family:'Courier New',monospace;
            padding:10px 16px; letter-spacing:0.5px;
        """)
        self.setText(text)
        self.show()
        if duration:
            self._timer.start(duration)


# ── Add Quote tab ──────────────────────────────────────────────────────────

class AddQuoteTab(QWidget):
    def __init__(self, on_added_callback, parent=None):
        super().__init__(parent)
        self.on_added = on_added_callback
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Scrollable form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background:{DARK};border:none;")
        contents = QWidget()
        contents.setStyleSheet(f"background:{DARK};")
        form = QVBoxLayout(contents)
        form.setContentsMargins(40, 32, 40, 16)
        form.setSpacing(0)

        entry_label = QLabel("NEW ENTRY")
        entry_label.setObjectName("section_title")
        form.addWidget(entry_label)
        form.addSpacing(16)

        row1 = QHBoxLayout()
        row1.setSpacing(16)
        self.title_input  = self._field(row1, "BOOK TITLE", QLineEdit(), placeholder="Guards! Guards!")
        self.author_input = self._field(row1, "AUTHOR",     QLineEdit(), placeholder="Terry Pratchett")
        form.addLayout(row1)
        form.addSpacing(12)

        row2 = QHBoxLayout()
        row2.setSpacing(16)
        year_w = QSpinBox()
        year_w.setRange(1000, 2100)
        year_w.setValue(2000)
        year_w.setFixedWidth(110)
        self.year_input = year_w
        self._field(row2, "YEAR", year_w)

        genre_w = QComboBox()
        genre_w.setEditable(True)
        genre_w.addItems([
            "Fantasy","Science Fiction","Mystery","Thriller","Romance",
            "Historical Fiction","Literary Fiction","Horror","Adventure",
            "Dystopian Fiction","Non-Fiction","Biography","Other"
        ])
        genre_w.setCurrentIndex(-1)
        genre_w.lineEdit().setPlaceholderText("Select or type genre…")
        self.genre_input = genre_w
        self._field(row2, "GENRE", genre_w)
        form.addLayout(row2)
        form.addSpacing(12)

        ql = QLabel("QUOTE")
        ql.setObjectName("field_label")
        form.addWidget(ql)
        form.addSpacing(4)
        self.quote_input = QTextEdit()
        self.quote_input.setPlaceholderText("Enter the quote here…")
        self.quote_input.setMinimumHeight(110)
        self.quote_input.setMaximumHeight(160)
        self.quote_input.textChanged.connect(self._on_quote_changed)
        form.addWidget(self.quote_input)
        form.addSpacing(6)

        self.dup_label = QLabel("")
        self.dup_label.setWordWrap(True)
        self.dup_label.setStyleSheet(f"font-size:11px;color:{AMBER};font-family:'Courier New',monospace;")
        self.dup_label.hide()
        form.addWidget(self.dup_label)
        form.addStretch()

        scroll.setWidget(contents)
        root.addWidget(scroll, stretch=1)

        # Pinned bottom bar
        bottom = QWidget()
        bottom.setStyleSheet(f"background:{DARK};border-top:1px solid {BORDER};")
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(40, 16, 40, 24)
        bl.setSpacing(10)
        self.feedback = FeedbackBanner()
        bl.addWidget(self.feedback)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.submit_btn = QPushButton("ADD QUOTE")
        self.submit_btn.setObjectName("submit_btn")
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.clicked.connect(self.submit_quote)
        self.clear_btn = QPushButton("CLEAR")
        self.clear_btn.setObjectName("clear_btn")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_form)
        btn_row.addWidget(self.submit_btn)
        btn_row.addWidget(self.clear_btn)
        bl.addLayout(btn_row)
        root.addWidget(bottom)

    def _field(self, layout, label_text, widget, placeholder=None):
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setObjectName("field_label")
        vbox.addWidget(lbl)
        if placeholder and hasattr(widget, 'setPlaceholderText'):
            widget.setPlaceholderText(placeholder)
        vbox.addWidget(widget)
        layout.addWidget(container, stretch=1)
        return widget

    def _on_quote_changed(self):
        text = self.quote_input.toPlainText().strip()
        if len(text) < 20:
            self.dup_label.hide()
            return
        if check_duplicate_exact(text):
            self.dup_label.setText("⚠  Exact duplicate found — already in database.")
            self.dup_label.show()
            return
        similar, ratio = check_duplicate_fuzzy(text, threshold=0.80)
        if similar:
            pct = int(ratio * 100)
            preview = similar[:60] + "…" if len(similar) > 60 else similar
            self.dup_label.setText(f"⚠  {pct}% similar to existing: \"{preview}\"")
            self.dup_label.show()
        else:
            self.dup_label.hide()

    def submit_quote(self):
        title  = self.title_input.text().strip()
        author = self.author_input.text().strip()
        year   = self.year_input.value()
        genre  = self.genre_input.currentText().strip()
        quote  = self.quote_input.toPlainText().strip()

        missing = [f for f, v in [("Title",title),("Author",author),("Genre",genre),("Quote",quote)] if not v]
        if missing:
            self.feedback.show_message(f"Missing fields: {', '.join(missing)}", "error")
            return
        if check_duplicate_exact(quote):
            self.feedback.show_message("This quote already exists in the database.", "error")
            return
        similar, ratio = check_duplicate_fuzzy(quote, threshold=0.80)
        if similar:
            pct = int(ratio * 100)
            reply = QMessageBox.question(
                self, "Similar Quote Found",
                f"A {pct}% similar quote already exists:\n\n\"{similar[:120]}…\"\n\nAdd anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        try:
            insert_quote(title, author, year, genre, quote)
            self.feedback.show_message(f"✓  Quote added — \"{title}\" by {author}", "success")
            self.clear_form()
            if self.on_added:
                self.on_added(title, author, quote)
        except Exception as e:
            self.feedback.show_message(f"Database error: {e}", "error")

    def clear_form(self):
        self.title_input.clear()
        self.author_input.clear()
        self.year_input.setValue(2000)
        self.genre_input.setCurrentIndex(-1)
        self.genre_input.lineEdit().setPlaceholderText("Select or type genre…")
        self.quote_input.clear()
        self.dup_label.hide()


# ── Import Pending tab ─────────────────────────────────────────────────────

class ImportPendingTab(QWidget):
    def __init__(self, on_changed_callback, parent=None):
        super().__init__(parent)
        self.on_changed = on_changed_callback
        self._build()
        self.load_pending()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        header_row = QHBoxLayout()
        title = QLabel("PENDING SUBMISSIONS")
        title.setObjectName("section_title")
        self.pending_count = QLabel("0 pending")
        self.pending_count.setStyleSheet(f"font-size:12px;color:{MUTED};font-family:'Courier New',monospace;")
        refresh_btn = QPushButton("↻  Refresh")
        refresh_btn.setObjectName("refresh_btn")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.load_pending)
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(self.pending_count)
        header_row.addSpacing(12)
        header_row.addWidget(refresh_btn)
        root.addLayout(header_row)

        info = QLabel(
            "Review quotes submitted by users via the website. "
            "Approve to move them into the live database, or reject to discard."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"font-size:12px;color:{MUTED};font-style:italic;")
        root.addWidget(info)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Title","Author","Year","Genre","Submitted","Email","Quote"])
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.table, stretch=1)

        detail_frame = QFrame()
        detail_frame.setStyleSheet(f"background:{SURFACE};border:1px solid {BORDER};border-radius:2px;")
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(20, 16, 20, 16)
        detail_layout.setSpacing(8)

        detail_header = QLabel("SELECTED QUOTE")
        detail_header.setObjectName("section_title")
        detail_layout.addWidget(detail_header)

        self.detail_text = QLabel("Select a row above to preview the full quote.")
        self.detail_text.setWordWrap(True)
        self.detail_text.setStyleSheet(f"font-size:13px;color:{CREAM};font-style:italic;line-height:1.6;font-family:'Georgia',serif;")
        self.detail_text.setMinimumHeight(60)
        detail_layout.addWidget(self.detail_text)

        self.detail_dup = QLabel("")
        self.detail_dup.setWordWrap(True)
        self.detail_dup.setStyleSheet(f"font-size:11px;color:{AMBER};font-family:'Courier New',monospace;")
        self.detail_dup.hide()
        detail_layout.addWidget(self.detail_dup)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.approve_btn = QPushButton("✓  Approve & Add to DB")
        self.approve_btn.setObjectName("approve_btn")
        self.approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.approve_btn.clicked.connect(self.approve_selected)
        self.approve_btn.setEnabled(False)
        self.reject_btn = QPushButton("✕  Reject")
        self.reject_btn.setObjectName("reject_btn")
        self.reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reject_btn.clicked.connect(self.reject_selected)
        self.reject_btn.setEnabled(False)
        btn_row.addWidget(self.approve_btn)
        btn_row.addWidget(self.reject_btn)
        btn_row.addStretch()
        detail_layout.addLayout(btn_row)

        root.addWidget(detail_frame)

        self.feedback = FeedbackBanner()
        root.addWidget(self.feedback)

        self._pending_rows = []

    def load_pending(self):
        rows = get_pending_quotes()
        self._pending_rows = [dict(r) for r in rows]
        self.table.setRowCount(len(self._pending_rows))

        for i, row in enumerate(self._pending_rows):
            # submitted_at is now a datetime object from psycopg2, not a string
            submitted = row["submitted_at"]
            date_str = submitted.strftime("%Y-%m-%d") if submitted else "—"
            vals = [
                row["title"], row["author"],
                str(row["year"]) if row["year"] else "—",
                row["genre"], date_str,
                row["submitter_email"],
                row["quote"][:80] + ("…" if len(row["quote"]) > 80 else "")
            ]
            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setForeground(QColor(CREAM))
                self.table.setItem(i, j, item)

        count = len(self._pending_rows)
        self.pending_count.setText(f"{count} pending")
        self._clear_detail()
        self.approve_btn.setEnabled(False)
        self.reject_btn.setEnabled(False)

    def _clear_detail(self):
        self.detail_text.setText("Select a row above to preview the full quote.")
        self.detail_dup.hide()

    def _on_selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self._clear_detail()
            self.approve_btn.setEnabled(False)
            self.reject_btn.setEnabled(False)
            return

        idx = rows[0].row()
        row = self._pending_rows[idx]
        self.detail_text.setText(f'"{row["quote"]}"')
        self.approve_btn.setEnabled(True)
        self.reject_btn.setEnabled(True)

        self.detail_dup.hide()
        quote = row["quote"]
        if check_duplicate_exact(quote):
            self.detail_dup.setText("⚠  Exact duplicate — this quote is already in the live database.")
            self.detail_dup.show()
            self.approve_btn.setEnabled(False)
        else:
            similar, ratio = check_duplicate_fuzzy(quote, threshold=0.80)
            if similar:
                pct = int(ratio * 100)
                preview = similar[:60] + "…" if len(similar) > 60 else similar
                self.detail_dup.setText(f"⚠  {pct}% similar to live quote: \"{preview}\"")
                self.detail_dup.show()

    def _selected_row(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None, None
        idx = rows[0].row()
        return idx, self._pending_rows[idx]

    def approve_selected(self):
        idx, row = self._selected_row()
        if row is None:
            return
        try:
            approve_pending(row["id"])
            self.feedback.show_message(f"✓  Approved — \"{row['title']}\" by {row['author']}", "success")
            self.load_pending()
            if self.on_changed:
                self.on_changed()
        except Exception as e:
            self.feedback.show_message(f"Error: {e}", "error")

    def reject_selected(self):
        idx, row = self._selected_row()
        if row is None:
            return
        reply = QMessageBox.question(
            self, "Reject Submission",
            f"Permanently discard this submission?\n\n\"{row['quote'][:120]}\"",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_pending(row["id"])
            self.feedback.show_message("Submission rejected and removed.", "warning")
            self.load_pending()
            if self.on_changed:
                self.on_changed()
        except Exception as e:
            self.feedback.show_message(f"Error: {e}", "error")


# ── Main window ────────────────────────────────────────────────────────────

class QuoteManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tip of the Page — Quote Manager")
        self.setMinimumSize(960, 680)
        self.resize(1200, 760)
        self.setStyleSheet(STYLESHEET)
        init_db()
        self._build_ui()
        self.refresh_stats()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        left = QWidget()
        left.setStyleSheet(f"background:{DARK};")
        left.setMinimumWidth(580)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        header_widget = QWidget()
        header_widget.setStyleSheet(f"background:{DARK};")
        hw = QVBoxLayout(header_widget)
        hw.setContentsMargins(40, 32, 40, 20)
        hw.setSpacing(2)
        title_lbl = QLabel("TIP OF THE PAGE")
        title_lbl.setStyleSheet(f"font-size:20px;font-weight:bold;color:{GOLD};font-family:'Courier New',monospace;letter-spacing:5px;")
        sub_lbl = QLabel("Quote Manager")
        sub_lbl.setStyleSheet(f"font-size:12px;color:{MUTED};font-family:'Georgia',serif;font-style:italic;")
        hw.addWidget(title_lbl)
        hw.addWidget(sub_lbl)
        left_layout.addWidget(header_widget)
        left_layout.addWidget(Divider())

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.add_tab = AddQuoteTab(on_added_callback=self._on_quote_added)
        self.pending_tab = ImportPendingTab(on_changed_callback=self.refresh_stats)
        self.tabs.addTab(self.add_tab, "ADD QUOTE")
        self.tabs.addTab(self.pending_tab, "IMPORT PENDING")
        left_layout.addWidget(self.tabs, stretch=1)
        root.addWidget(left, stretch=6)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color:{BORDER};background:{BORDER};border:none;max-width:1px;")
        root.addWidget(sep)

        right = QWidget()
        right.setStyleSheet(f"background:{SURFACE};")
        right.setFixedWidth(300)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(24, 32, 24, 32)
        rl.setSpacing(0)

        stats_title = QLabel("DATABASE STATS")
        stats_title.setObjectName("section_title")
        rl.addWidget(stats_title)
        rl.addSpacing(16)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self.total_card   = StatCard("Live Quotes", 0, accent=True)
        self.pending_card = StatCard("Pending", 0)
        cards_row.addWidget(self.total_card)
        cards_row.addWidget(self.pending_card)
        rl.addLayout(cards_row)
        rl.addSpacing(24)
        rl.addWidget(Divider())
        rl.addSpacing(20)

        genre_title = QLabel("BY GENRE")
        genre_title.setObjectName("section_title")
        rl.addWidget(genre_title)
        rl.addSpacing(12)

        self.genre_scroll = QScrollArea()
        self.genre_scroll.setWidgetResizable(True)
        self.genre_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.genre_scroll.setStyleSheet("background:transparent;border:none;")
        self.genre_container = QWidget()
        self.genre_container.setStyleSheet("background:transparent;")
        self.genre_layout = QVBoxLayout(self.genre_container)
        self.genre_layout.setContentsMargins(0, 0, 0, 0)
        self.genre_layout.setSpacing(0)
        self.genre_layout.addStretch()
        self.genre_scroll.setWidget(self.genre_container)
        rl.addWidget(self.genre_scroll, stretch=1)

        rl.addSpacing(16)
        rl.addWidget(Divider())
        rl.addSpacing(12)

        last_lbl = QLabel("LAST ADDED")
        last_lbl.setObjectName("section_title")
        rl.addWidget(last_lbl)
        rl.addSpacing(8)
        self.last_added = QLabel("—")
        self.last_added.setWordWrap(True)
        self.last_added.setStyleSheet(f"font-size:11px;color:{MUTED};font-family:'Georgia',serif;font-style:italic;")
        rl.addWidget(self.last_added)
        root.addWidget(right, stretch=0)

    def _on_quote_added(self, title, author, quote):
        preview = f'"{quote[:70]}…"\n— {author}' if len(quote) > 70 else f'"{quote}"\n— {author}'
        self.last_added.setText(preview)
        self.refresh_stats()

    def refresh_stats(self):
        total, pending, genres = get_stats()
        self.total_card.update_value(total)
        self.pending_card.update_value(pending)
        self.tabs.setTabText(1, f"IMPORT PENDING ({pending})" if pending else "IMPORT PENDING")

        while self.genre_layout.count() > 1:
            item = self.genre_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if genres:
            max_count = genres[0]["cnt"]
            for row in genres:
                w = GenreRow(row["genre"], row["cnt"], max_count)
                self.genre_layout.insertWidget(self.genre_layout.count() - 1, w)
        else:
            ph = QLabel("No quotes yet")
            ph.setStyleSheet(f"color:{MUTED};font-style:italic;font-size:12px;")
            self.genre_layout.insertWidget(0, ph)


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Tip of the Page — Quote Manager")
    window = QuoteManager()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()