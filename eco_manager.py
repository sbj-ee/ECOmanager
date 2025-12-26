import sqlite3
import datetime
import os
import shutil
from typing import List, Optional, Tuple
from pathlib import Path

class ECO:
    def __init__(self, db_path: str = "eco_system.db", attachments_dir: str = "attachments"):
        self.db_path = db_path
        self.attachments_dir = Path(attachments_dir).resolve()
        self.attachments_dir.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ecos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'DRAFT',
                    created_by INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (created_by) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS eco_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    eco_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    comment TEXT,
                    performed_by INTEGER NOT NULL,
                    performed_at TEXT NOT NULL,
                    FOREIGN KEY (eco_id) REFERENCES ecos(id),
                    FOREIGN KEY (performed_by) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    eco_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    uploaded_by INTEGER NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    FOREIGN KEY (eco_id) REFERENCES ecos(id),
                    FOREIGN KEY (uploaded_by) REFERENCES users(id)
                );
            """)
            conn.commit()

    def get_or_create_user(self, username: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if row:
                return row[0]
            c.execute("INSERT INTO users (username) VALUES (?)", (username,))
            conn.commit()
            return c.lastrowid

    def create_eco(self, title: str, description: str, username: str) -> int:
        user_id = self.get_or_create_user(username)
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO ecos (title, description, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (title, description, user_id, now, now))
            eco_id = c.lastrowid
            c.execute("""
                INSERT INTO eco_history (eco_id, action, performed_by, performed_at)
                VALUES (?, 'CREATED', ?, ?)
            """, (eco_id, user_id, now))
            conn.commit()
            return eco_id

    def submit_eco(self, eco_id: int, username: str, comment: Optional[str] = None) -> bool:
        user_id = self.get_or_create_user(username)
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM ecos WHERE id = ?", (eco_id,))
            if not c.fetchone():
                return False
            c.execute("UPDATE ecos SET status = 'SUBMITTED', updated_at = ? WHERE id = ?", (now, eco_id))
            c.execute("""
                INSERT INTO eco_history (eco_id, action, comment, performed_by, performed_at)
                VALUES (?, 'SUBMITTED', ?, ?, ?)
            """, (eco_id, comment, user_id, now))
            conn.commit()
            return True

    def approve_eco(self, eco_id: int, username: str, comment: Optional[str] = None) -> bool:
        user_id = self.get_or_create_user(username)
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT status FROM ecos WHERE id = ?", (eco_id,))
            row = c.fetchone()
            if not row or row[0] != 'SUBMITTED':
                return False
            c.execute("UPDATE ecos SET status = 'APPROVED', updated_at = ? WHERE id = ?", (now, eco_id))
            c.execute("""
                INSERT INTO eco_history (eco_id, action, comment, performed_by, performed_at)
                VALUES (?, 'APPROVED', ?, ?, ?)
            """, (eco_id, comment, user_id, now))
            conn.commit()
            return True

    def reject_eco(self, eco_id: int, username: str, comment: str) -> bool:
        user_id = self.get_or_create_user(username)
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT status FROM ecos WHERE id = ?", (eco_id,))
            row = c.fetchone()
            if not row or row[0] != 'SUBMITTED':
                return False
            c.execute("UPDATE ecos SET status = 'REJECTED', updated_at = ? WHERE id = ?", (now, eco_id))
            c.execute("""
                INSERT INTO eco_history (eco_id, action, comment, performed_by, performed_at)
                VALUES (?, 'REJECTED', ?, ?, ?)
            """, (eco_id, comment, user_id, now))
            conn.commit()
            return True

    def add_attachment(self, eco_id: int, filename: str, file_path: str, username: str) -> bool:
        user_id = self.get_or_create_user(username)
        now = datetime.datetime.now().isoformat()
        try:
            src_path = Path(file_path).resolve()
            if not src_path.exists():
                return False

            # Create unique filename
            safe_filename = src_path.name
            dest_path = self.attachments_dir / f"{eco_id}_{safe_filename}"
            shutil.copy2(src_path, dest_path)

            file_size = dest_path.stat().st_size
            mime_type = "application/octet-stream"  # improve with mimetypes if needed

            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO attachments (eco_id, filename, mime_type, file_path, file_size, uploaded_by, uploaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (eco_id, safe_filename, mime_type, str(dest_path), file_size, user_id, now))
                conn.commit()
            return True
        except Exception:
            return False

    def get_eco_details(self, eco_id: int) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("""
                SELECT e.id, e.title, e.description, e.status, e.created_at, e.updated_at,
                       u.username AS created_by
                FROM ecos e JOIN users u ON e.created_by = u.id
                WHERE e.id = ?
            """, (eco_id,))
            row = c.fetchone()
            if not row:
                return None
            eco = dict(row)

            c.execute("""
                SELECT h.action, h.comment, h.performed_at, u.username
                FROM eco_history h JOIN users u ON h.performed_by = u.id
                WHERE h.eco_id = ?
                ORDER BY h.performed_at
            """, (eco_id,))
            eco['history'] = [dict(r) for r in c.fetchall()]

            c.execute("""
                SELECT a.id, filename, mime_type, file_path, file_size, uploaded_at, u.username
                FROM attachments a JOIN users u ON a.uploaded_by = u.id
                WHERE a.eco_id = ?
            """, (eco_id,))
            eco['attachments'] = [dict(r) for r in c.fetchall()]
            return eco

    def list_ecos(self) -> List[Tuple[int, str, str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id, title, status, created_at FROM ecos ORDER BY created_at DESC")
            return c.fetchall()

# Example
if __name__ == "__main__":  # pragma: no cover
    eco = ECO()
    eco_id = eco.create_eco("Test ECO", "Description", "alice")
    eco.add_attachment(eco_id, "test.pdf", "example.pdf", "alice")  # assumes example.pdf exists
    print(eco.get_eco_details(eco_id))

