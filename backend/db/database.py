
import sqlite3
import json
from datetime import datetime
from threading import Lock

DB_NAME = "tasks.db"
db_lock = Lock()


def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def get_all_tasks():
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT task_id, status, result, created_at, file_hash
        FROM tasks
        ORDER BY created_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        tasks = []
        for row in rows:
            tasks.append({
                "task_id": row[0],
                "status": row[1],
                "result": json.loads(row[2]) if row[2] else None,
                "created_at": row[3],
                "file_hash": row[4] if len(row) > 4 else None,
            })

        return tasks

def init_db():
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            status TEXT,
            result TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """)

        cursor.execute("PRAGMA table_info(tasks)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        if "file_hash" not in existing_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN file_hash TEXT")

        conn.commit()
        conn.close()


# ---------------------------
# CRUD OPERATIONS
# ---------------------------

def create_task(task_id, file_hash=None):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        cursor.execute("""
        INSERT INTO tasks (task_id, status, result, created_at, updated_at, file_hash)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (task_id, "processing", None, now, now, file_hash))

        conn.commit()
        conn.close()


def update_task(task_id, status=None, result=None):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        if result is not None:
            result = json.dumps(result)

        cursor.execute("""
        UPDATE tasks
        SET status = COALESCE(?, status),
            result = COALESCE(?, result),
            updated_at = ?
        WHERE task_id = ?
        """, (status, result, now, task_id))

        conn.commit()
        conn.close()


def get_cached_result(file_hash):
    if not file_hash:
        return None

    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT result FROM tasks WHERE file_hash=? AND status='completed' ORDER BY created_at DESC LIMIT 1",
            (file_hash,)
        )

        row = cursor.fetchone()
        conn.close()

        if not row or not row[0]:
            return None

        try:
            return json.loads(row[0])
        except Exception:
            return None


def get_task(task_id):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT task_id, status, result, created_at, updated_at
        FROM tasks
        WHERE task_id = ?
        """, (task_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        task = {
            "task_id": row[0],
            "status": row[1],
            "result": json.loads(row[2]) if row[2] else None,
            "created_at": row[3],
            "updated_at": row[4]
        }

        return task


def table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def clear_task_history():
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tasks")
        deleted_tasks = cursor.rowcount if cursor.rowcount is not None else 0

        deleted_history = 0
        if table_exists(cursor, "analysis_history"):
            cursor.execute("DELETE FROM analysis_history")
            deleted_history = cursor.rowcount if cursor.rowcount is not None else 0

        conn.commit()
        conn.close()

        return {
            "deleted_tasks": deleted_tasks,
            "deleted_analysis_history": deleted_history,
        }


def delete_old_tasks(days: int = 7):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM tasks
            WHERE datetime(created_at) < datetime('now', ?)
            """,
            (f"-{days} days",),
        )

        deleted_tasks = cursor.rowcount if cursor.rowcount is not None else 0

        conn.commit()
        conn.close()

        return {
            "deleted_tasks": deleted_tasks,
            "days": days,
        }