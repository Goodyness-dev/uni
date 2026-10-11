import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

DB_PATH: Path = Path("backend/data/app.db")


def get_db_path() -> Path:
    override = os.getenv("TEST_DB_PATH")
    if override:
        return Path(override)
    # Ensure parent directory exists
    candidates = [
        Path("data/app.db"),
        Path("backend/data/app.db"),
        Path(__file__).resolve().parent.parent / "data" / "app.db",
    ]
    for c in candidates:
        if c.parent.is_dir():
            return c
    p = Path("backend/data/app.db")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path(), timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def now_str() -> str:
    """Returns current UTC timestamp formatted as YYYY/MM/DD HH:MM:SS."""
    return datetime.now(timezone.utc).strftime("%Y/%m/%d %H:%M:%S")


def today_date():
    """Returns current date in UTC or override date."""
    if settings.today_override:
        return datetime.strptime(settings.today_override, "%Y/%m/%d").date()
    return datetime.now(timezone.utc).date()


def init_db() -> None:
    """Initializes SQLite tables and seeds failure flags."""
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        with conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
              id TEXT PRIMARY KEY,
              source TEXT NOT NULL,
              category TEXT NOT NULL,
              text TEXT NOT NULL,
              sensitive INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS preferences (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY,
              mode TEXT NOT NULL,
              status TEXT NOT NULL,
              top_n INTEGER NOT NULL,
              live_research INTEGER NOT NULL DEFAULT 0,
              started_at TEXT NOT NULL,
              finished_at TEXT,
              metrics_json TEXT,
              trace_url TEXT
            );
            CREATE TABLE IF NOT EXISTS applications (
              id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              listing_id TEXT NOT NULL,
              status TEXT NOT NULL,
              channel TEXT NOT NULL,
              fit_score INTEGER,
              fit_reason TEXT,
              hard_rules_json TEXT,
              failed_rules_json TEXT,
              failure_reason TEXT,
              dossier_json TEXT,
              edges_json TEXT,
              tailored_json TEXT,
              verification_json TEXT,
              package_json TEXT,
              handoff_json TEXT,
              submission_json TEXT,
              metrics_json TEXT,
              trace_url TEXT,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
              event_no INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id TEXT NOT NULL,
              application_id TEXT,
              at TEXT NOT NULL,
              agent TEXT NOT NULL,
              type TEXT NOT NULL,
              message TEXT NOT NULL,
              data_json TEXT
            );
            CREATE TABLE IF NOT EXISTS notifications (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id TEXT,
              application_id TEXT,
              channel TEXT NOT NULL,
              text TEXT NOT NULL,
              sent INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS gaps (
              id TEXT PRIMARY KEY,
              application_id TEXT NOT NULL,
              criterion TEXT NOT NULL,
              question TEXT NOT NULL,
              answered INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS portal_drafts (
              draft_id TEXT PRIMARY KEY,
              listing_id TEXT NOT NULL,
              idempotency_key TEXT,
              fields_json TEXT NOT NULL,
              submitted INTEGER NOT NULL DEFAULT 0,
              confirmation_code TEXT,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS failure_flags (
              name TEXT PRIMARY KEY,
              enabled INTEGER NOT NULL DEFAULT 0,
              remaining INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS poller_state (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              last_update_id INTEGER NOT NULL DEFAULT 0
            );
            """)

            # Seed failure flags if empty
            default_flags = [
                "llm_429", "bad_json", "portal_500", "captcha_wall",
                "research_down", "smtp_fail", "injection_page"
            ]
            for flag in default_flags:
                conn.execute(
                    "INSERT OR IGNORE INTO failure_flags (name, enabled, remaining) VALUES (?, 0, 0)",
                    (flag,)
                )

            # Seed poller state
            conn.execute("INSERT OR IGNORE INTO poller_state (id, last_update_id) VALUES (1, 0)")
    finally:
        conn.close()


# --- Facts ---
def replace_facts(facts: list[dict[str, Any]]) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM facts")
            now = now_str()
            for f in facts:
                if hasattr(f, "model_dump"):
                    fd = f.model_dump()
                elif isinstance(f, dict):
                    fd = f
                else:
                    fd = dict(f)
                conn.execute(
                    "INSERT INTO facts (id, source, category, text, sensitive, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (fd["id"], fd["source"], fd["category"], fd["text"], 1 if fd.get("sensitive") else 0, now)
                )
    finally:
        conn.close()


def list_facts() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id, source, category, text, sensitive FROM facts ORDER BY id")
        return [
            {
                "id": row["id"],
                "source": row["source"],
                "category": row["category"],
                "text": row["text"],
                "sensitive": bool(row["sensitive"]),
            }
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


get_facts = list_facts


def get_fact(fact_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id, source, category, text, sensitive FROM facts WHERE id = ?", (fact_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "source": row["source"],
            "category": row["category"],
            "text": row["text"],
            "sensitive": bool(row["sensitive"]),
        }
    finally:
        conn.close()


def update_fact_text(fact_id: str, text: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        with conn:
            conn.execute("UPDATE facts SET text = ? WHERE id = ?", (text, fact_id))
        return get_fact(fact_id)
    finally:
        conn.close()


def add_vault_fact(category: str, text: str) -> dict[str, Any]:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM facts WHERE id LIKE 'P%'")
        p_ids = [row["id"] for row in cur.fetchall()]
        max_num = 0
        for pid in p_ids:
            m = re.match(r"P(\d+)", pid)
            if m:
                max_num = max(max_num, int(m.group(1)))
        new_id = f"P{max_num + 1}"
        now = now_str()
        with conn:
            conn.execute(
                "INSERT INTO facts (id, source, category, text, sensitive, created_at) VALUES (?, 'vault', ?, ?, 0, ?)",
                (new_id, category, text, now)
            )
        return {"id": new_id, "source": "vault", "category": category, "text": text, "sensitive": False}
    finally:
        conn.close()


def set_preferences(prefs: Any) -> None:
    conn = get_connection()
    try:
        dumped = prefs.model_dump() if hasattr(prefs, "model_dump") else prefs
        with conn:
            conn.execute(
                "INSERT INTO preferences (id, json) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET json = excluded.json",
                (json.dumps(dumped),)
            )
    finally:
        conn.close()


def get_preferences() -> dict[str, Any] | None:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT json FROM preferences WHERE id = 1")
        row = cur.fetchone()
        return json.loads(row["json"]) if row else None
    finally:
        conn.close()


# --- Runs ---
def create_run(mode: str, top_n: int, live_research: bool = False) -> str:
    conn = get_connection()
    try:
        today_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
        cur = conn.execute("SELECT id FROM runs WHERE id LIKE ?", (f"run_{today_prefix}_%",))
        count = len(cur.fetchall())
        run_id = f"run_{today_prefix}_{count + 1:03d}"
        now = now_str()
        with conn:
            conn.execute(
                "INSERT INTO runs (id, mode, status, top_n, live_research, started_at) VALUES (?, ?, 'running', ?, ?, ?)",
                (run_id, mode, top_n, 1 if live_research else 0, now)
            )
        return run_id
    finally:
        conn.close()


def get_run(run_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        row = cur.fetchone()
        if not row:
            return None
        cur_apps = conn.execute("SELECT id FROM applications WHERE run_id = ?", (run_id,))
        app_ids = [r["id"] for r in cur_apps.fetchall()]
        return {
            "run_id": row["id"],
            "mode": row["mode"],
            "status": row["status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "application_ids": app_ids,
            "metrics": json.loads(row["metrics_json"]) if row["metrics_json"] else None,
            "trace_url": row["trace_url"],
        }
    finally:
        conn.close()


def latest_run() -> dict[str, Any] | None:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM runs ORDER BY started_at DESC LIMIT 1")
        row = cur.fetchone()
        return get_run(row["id"]) if row else None
    finally:
        conn.close()


def finish_run(run_id: str, status: str, metrics: dict[str, Any] | None = None, trace_url: str | None = None) -> None:
    conn = get_connection()
    try:
        now = now_str()
        with conn:
            conn.execute(
                "UPDATE runs SET status = ?, finished_at = ?, metrics_json = ?, trace_url = COALESCE(?, trace_url) WHERE id = ?",
                (status, now, json.dumps(metrics) if metrics else None, trace_url, run_id)
            )
    finally:
        conn.close()


def mark_interrupted_runs() -> None:
    conn = get_connection()
    try:
        now = now_str()
        with conn:
            conn.execute("UPDATE runs SET status = 'interrupted', finished_at = ? WHERE status = 'running'", (now,))
    finally:
        conn.close()


# --- Applications & State Machine ---
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "found": {"matched", "skipped"},
    "matched": {"researched"},
    "researched": {"edges_selected"},
    "edges_selected": {"tailored"},
    "tailored": {"verified"},
    "verified": {"ready"},
    "ready": {"submitting", "prepared"},
    "submitting": {"submitted", "awaiting_user", "unconfirmed", "failed", "prepared"},
    "awaiting_user": {"submitting"},
    "unconfirmed": {"submitting"},
}


def create_application(run_id: str, listing_id: str, channel: str) -> str:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT COUNT(*) as count FROM applications")
        total = cur.fetchone()["count"]
        app_id = f"app_{total + 1}"
        now = now_str()
        with conn:
            conn.execute(
                "INSERT INTO applications (id, run_id, listing_id, status, channel, updated_at) VALUES (?, ?, ?, 'found', ?, ?)",
                (app_id, run_id, listing_id, channel, now)
            )
        return app_id
    finally:
        conn.close()


def get_application(app_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,))
        row = cur.fetchone()
        if not row:
            return None
        res = dict(row)
        for key in ["hard_rules", "failed_rules", "dossier", "edges", "tailored", "verification", "package", "handoff", "submission", "metrics"]:
            col = f"{key}_json"
            if col in res and res[col]:
                res[key] = json.loads(res[col])
            elif key not in res:
                res[key] = None
        return res
    finally:
        conn.close()


def list_applications(run_id: str | None = None) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        if run_id:
            cur = conn.execute("SELECT * FROM applications WHERE run_id = ? ORDER BY id", (run_id,))
        else:
            cur = conn.execute("SELECT * FROM applications ORDER BY id")
        rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for key in ["hard_rules", "failed_rules", "dossier", "edges", "tailored", "verification", "package", "handoff", "submission", "metrics"]:
                col = f"{key}_json"
                if col in d and d[col]:
                    d[key] = json.loads(d[col])
                elif key not in d:
                    d[key] = None
            result.append(d)
        return result
    finally:
        conn.close()


def update_application(app_id: str, **fields: Any) -> None:
    conn = get_connection()
    try:
        now = now_str()
        set_clauses = ["updated_at = ?"]
        params: list[Any] = [now]
        for k, v in fields.items():
            if k in ["hard_rules", "failed_rules", "dossier", "edges", "tailored", "verification", "package", "handoff", "submission", "metrics"]:
                set_clauses.append(f"{k}_json = ?")
                params.append(json.dumps(v) if v is not None else None)
            else:
                set_clauses.append(f"{k} = ?")
                params.append(v)
        params.append(app_id)
        sql = f"UPDATE applications SET {', '.join(set_clauses)} WHERE id = ?"
        with conn:
            conn.execute(sql, params)
    finally:
        conn.close()


def set_status(app_id: str, new_status: str, message: str, agent: str = "coordinator") -> None:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT run_id, status FROM applications WHERE id = ?", (app_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Application {app_id} does not exist")
        current_status = row["status"]
        run_id = row["run_id"]

        # Validate transition: any status to failed is allowed; otherwise must be in ALLOWED_TRANSITIONS
        if new_status != "failed" and current_status != new_status:
            allowed = ALLOWED_TRANSITIONS.get(current_status, set())
            if new_status not in allowed:
                raise ValueError(f"Illegal state transition from {current_status} to {new_status}")

        now = now_str()
        with conn:
            conn.execute("UPDATE applications SET status = ?, updated_at = ? WHERE id = ?", (new_status, now, app_id))
            conn.execute(
                "INSERT INTO events (run_id, application_id, at, agent, type, message, data_json) VALUES (?, ?, ?, ?, 'status_changed', ?, ?)",
                (run_id, app_id, now, agent, message, json.dumps({"from": current_status, "to": new_status}))
            )

        # Notify hook (lazy import)
        try:
            from app import notify
            if hasattr(notify, "on_status_change"):
                notify.on_status_change(app_id, new_status)
        except Exception:
            pass
    finally:
        conn.close()


# --- Events ---
def add_event(run_id: str, application_id: str | None, agent: str, type_: str, message: str, data: dict[str, Any] | None = None) -> int:
    conn = get_connection()
    try:
        now = now_str()
        with conn:
            cur = conn.execute(
                "INSERT INTO events (run_id, application_id, at, agent, type, message, data_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, application_id, now, agent, type_, message, json.dumps(data or {}))
            )
            return cur.lastrowid
    finally:
        conn.close()


def list_events(run_id: str, after: int = 0) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT event_no, run_id, application_id, at, agent, type, message, data_json FROM events WHERE run_id = ? AND event_no > ? ORDER BY event_no ASC",
            (run_id, after)
        )
        return [
            {
                "event_no": r["event_no"],
                "run_id": r["run_id"],
                "application_id": r["application_id"],
                "at": r["at"],
                "agent": r["agent"],
                "type": r["type"],
                "message": r["message"],
                "data": json.loads(r["data_json"]) if r["data_json"] else {},
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def list_application_events(app_id: str) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT event_no, run_id, application_id, at, agent, type, message, data_json FROM events WHERE application_id = ? ORDER BY event_no ASC",
            (app_id,)
        )
        return [
            {
                "event_no": r["event_no"],
                "run_id": r["run_id"],
                "application_id": r["application_id"],
                "at": r["at"],
                "agent": r["agent"],
                "type": r["type"],
                "message": r["message"],
                "data": json.loads(r["data_json"]) if r["data_json"] else {},
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


# --- Notifications ---
def add_notification(run_id: str | None, application_id: str | None, channel: str, text: str, sent: bool = False) -> int:
    conn = get_connection()
    try:
        now = now_str()
        with conn:
            cur = conn.execute(
                "INSERT INTO notifications (run_id, application_id, channel, text, sent, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, application_id, channel, text, 1 if sent else 0, now)
            )
            return cur.lastrowid
    finally:
        conn.close()


def list_notifications(application_id: str) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id, text, sent, created_at FROM notifications WHERE application_id = ? ORDER BY id", (application_id,))
        return [{"id": r["id"], "text": r["text"], "sent": bool(r["sent"]), "at": r["created_at"]} for r in cur.fetchall()]
    finally:
        conn.close()


def list_unsent_notifications() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id, channel, text, application_id, run_id FROM notifications WHERE sent = 0 ORDER BY id")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def mark_notification_sent(notification_id: int) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute("UPDATE notifications SET sent = 1 WHERE id = ?", (notification_id,))
    finally:
        conn.close()


# --- Gaps ---
def add_gap(application_id: str, criterion: str, question: str) -> str:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM gaps WHERE id LIKE 'G%'")
        g_ids = [row["id"] for row in cur.fetchall()]
        max_num = 0
        for gid in g_ids:
            m = re.match(r"G(\d+)", gid)
            if m:
                max_num = max(max_num, int(m.group(1)))
        gap_id = f"G{max_num + 1}"
        with conn:
            conn.execute(
                "INSERT INTO gaps (id, application_id, criterion, question, answered) VALUES (?, ?, ?, ?, 0)",
                (gap_id, application_id, criterion, question)
            )
        return gap_id
    finally:
        conn.close()


def list_gaps(run_id: str | None = None) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        if run_id:
            cur = conn.execute(
                "SELECT g.id, g.application_id, g.criterion, g.question, g.answered FROM gaps g JOIN applications a ON g.application_id = a.id WHERE a.run_id = ? ORDER BY g.id",
                (run_id,)
            )
        else:
            cur = conn.execute("SELECT id, application_id, criterion, question, answered FROM gaps ORDER BY id")
        return [{"id": r["id"], "application_id": r["application_id"], "criterion": r["criterion"], "question": r["question"], "answered": bool(r["answered"])} for r in cur.fetchall()]
    finally:
        conn.close()


def answer_gap(gap_id: str) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute("UPDATE gaps SET answered = 1 WHERE id = ?", (gap_id,))
    finally:
        conn.close()


def get_gap(gap_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id, application_id, criterion, question, answered FROM gaps WHERE id = ?", (gap_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "application_id": row["application_id"],
            "criterion": row["criterion"],
            "question": row["question"],
            "answered": bool(row["answered"]),
        }
    finally:
        conn.close()


# --- Failure Flags ---
def get_flags() -> dict[str, dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT name, enabled, remaining FROM failure_flags")
        flags: dict[str, bool] = {}
        remaining: dict[str, int] = {}
        for r in cur.fetchall():
            flags[r["name"]] = bool(r["enabled"])
            remaining[r["name"]] = r["remaining"]
        return {"flags": flags, "remaining": remaining}
    finally:
        conn.close()


def set_flag(name: str, enabled: bool, count: int = 0) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO failure_flags (name, enabled, remaining) VALUES (?, ?, ?) ON CONFLICT(name) DO UPDATE SET enabled = excluded.enabled, remaining = excluded.remaining",
                (name, 1 if enabled else 0, count)
            )
    finally:
        conn.close()


def consume_flag(name: str) -> bool:
    """Consumes one use of a flag. For counted flags, decrements remaining and disables at 0. Returns True if flag was active."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT enabled, remaining FROM failure_flags WHERE name = ?", (name,))
        row = cur.fetchone()
        if not row or not row["enabled"]:
            return False

        # Uncounted flags (stay on until toggled off)
        if name in ("captcha_wall", "injection_page", "research_down"):
            return True

        # Counted flags
        remaining = row["remaining"] - 1
        with conn:
            if remaining <= 0:
                conn.execute("UPDATE failure_flags SET enabled = 0, remaining = 0 WHERE name = ?", (name,))
            else:
                conn.execute("UPDATE failure_flags SET remaining = ? WHERE name = ?", (remaining, name))
        return True
    finally:
        conn.close()


# --- Portal Drafts & Poller ---
def create_draft(listing_id: str, idempotency_key: str | None, fields: dict[str, Any]) -> str:
    conn = get_connection()
    try:
        if idempotency_key:
            cur = conn.execute("SELECT draft_id FROM portal_drafts WHERE idempotency_key = ?", (idempotency_key,))
            existing = cur.fetchone()
            if existing:
                return existing["draft_id"]

        import secrets
        draft_id = secrets.token_hex(6)
        now = now_str()
        with conn:
            conn.execute(
                "INSERT INTO portal_drafts (draft_id, listing_id, idempotency_key, fields_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (draft_id, listing_id, idempotency_key, json.dumps(fields), now)
            )
        return draft_id
    finally:
        conn.close()


def get_draft(draft_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM portal_drafts WHERE draft_id = ?", (draft_id,))
        row = cur.fetchone()
        if not row:
            return None
        res = dict(row)
        res["fields"] = json.loads(res["fields_json"]) if res.get("fields_json") else {}
        return res
    finally:
        conn.close()


def submit_draft(draft_id: str) -> str:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT submitted, confirmation_code FROM portal_drafts WHERE draft_id = ?", (draft_id,))
        row = cur.fetchone()
        if row and row["submitted"] and row["confirmation_code"]:
            return row["confirmation_code"]

        import random
        code = f"DEMO{random.randint(1000, 9999)}"
        with conn:
            conn.execute(
                "UPDATE portal_drafts SET submitted = 1, confirmation_code = ? WHERE draft_id = ?",
                (code, draft_id)
            )
        return code
    finally:
        conn.close()


def get_last_update_id() -> int:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT last_update_id FROM poller_state WHERE id = 1")
        row = cur.fetchone()
        return row["last_update_id"] if row else 0
    finally:
        conn.close()


def set_last_update_id(last_id: int) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute("UPDATE poller_state SET last_update_id = ? WHERE id = 1", (last_id,))
    finally:
        conn.close()
