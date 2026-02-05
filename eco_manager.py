import sqlite3
import datetime
import logging
import mimetypes
import os
import shutil
from typing import List, Optional, Tuple
from pathlib import Path
import secrets
import bcrypt

logger = logging.getLogger(__name__)

# Status constants
STATUS_DRAFT = "DRAFT"
STATUS_SUBMITTED = "SUBMITTED"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"

MIN_PASSWORD_LENGTH = 8


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
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT,
                    is_admin INTEGER DEFAULT 0,
                    first_name TEXT,
                    last_name TEXT,
                    email TEXT
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

                CREATE TABLE IF NOT EXISTS api_tokens (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_ecos_status ON ecos(status);
                CREATE INDEX IF NOT EXISTS idx_ecos_created_by ON ecos(created_by);
                CREATE INDEX IF NOT EXISTS idx_eco_history_eco_id ON eco_history(eco_id);
                CREATE INDEX IF NOT EXISTS idx_attachments_eco_id ON attachments(eco_id);
                CREATE INDEX IF NOT EXISTS idx_api_tokens_user_id ON api_tokens(user_id);
            """)
            for column, definition in [
                ("password_hash", "TEXT"),
                ("is_admin", "INTEGER DEFAULT 0"),
                ("first_name", "TEXT"),
                ("last_name", "TEXT"),
                ("email", "TEXT"),
            ]:
                try:
                    c.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            conn.commit()

    def get_or_create_user(self, username: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if row:
                return row[0]
            # Regular users created implicitly are not admins
            c.execute("INSERT INTO users (username, is_admin) VALUES (?, 0)", (username,))
            conn.commit()
            return c.lastrowid

    def check_health(self) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def register_user(self, username: str, password: str, first_name: str = None, last_name: str = None, email: str = None) -> bool:
        if len(password) < MIN_PASSWORD_LENGTH:
            return False
        # bcrypt.hashpw returns bytes, we decode to store as text
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                # Check if this is the first user
                c.execute("SELECT COUNT(*) FROM users")
                count = c.fetchone()[0]
                is_admin = 1 if count == 0 else 0
                
                c.execute("""
                    INSERT INTO users (username, password_hash, is_admin, first_name, last_name, email)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (username, password_hash, is_admin, first_name, last_name, email))
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def verify_password(self, username: str, password: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if not row or not row[0]:
                return False
            # row[0] is str, we need bytes for checkpw
            stored_hash = row[0].encode('utf-8')
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash)

    def generate_token(self, username: str, password: str) -> Optional[str]:
        if not self.verify_password(username, password):
            logger.warning("Failed login attempt for user '%s'", username)
            return None
            
        # User exists and password correct, get ID
        user_id = self.get_or_create_user(username) 
        token = secrets.token_hex(32)
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO api_tokens (token, user_id, created_at) VALUES (?, ?, ?)", (token, user_id, now))
            conn.commit()
        return token

    def get_user_from_token(self, token: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("""
                SELECT u.id, u.username, u.is_admin 
                FROM api_tokens t 
                JOIN users u ON t.user_id = u.id 
                WHERE t.token = ?
            """, (token,))
            row = c.fetchone()
            return dict(row) if row else None

    def revoke_token(self, token: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM api_tokens WHERE token = ?", (token,))
            conn.commit()
            return c.rowcount > 0

    def get_all_users(self) -> List[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT id, username, is_admin, first_name, last_name, email FROM users")
            return [dict(row) for row in c.fetchall()]

    def delete_user(self, user_id: int) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                # Check if user is the last admin
                c.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
                row = c.fetchone()
                if not row:
                    return False
                if row[0]:
                    c.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
                    admin_count = c.fetchone()[0]
                    if admin_count <= 1:
                        logger.warning("Attempted to delete the last admin user (id=%d)", user_id)
                        return False
                # Clean up user's API tokens
                c.execute("DELETE FROM api_tokens WHERE user_id = ?", (user_id,))
                c.execute("DELETE FROM users WHERE id = ?", (user_id,))
                logger.info("Deleted user id=%d", user_id)
                return c.rowcount > 0
        except sqlite3.Error:
            logger.exception("Failed to delete user id=%d", user_id)
            return False

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

    def update_eco(self, eco_id: int, title: str, description: str, username: str) -> bool:
        user_id = self.get_or_create_user(username)
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM ecos WHERE id = ?", (eco_id,))
            if not c.fetchone():
                return False
            c.execute(
                "UPDATE ecos SET title = ?, description = ?, updated_at = ? WHERE id = ?",
                (title, description, now, eco_id),
            )
            c.execute("""
                INSERT INTO eco_history (eco_id, action, comment, performed_by, performed_at)
                VALUES (?, 'EDITED', ?, ?, ?)
            """, (eco_id, f"Title: {title}", user_id, now))
            conn.commit()
            return True

    def delete_eco(self, eco_id: int) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT id FROM ecos WHERE id = ?", (eco_id,))
                if not c.fetchone():
                    return False
                c.execute("DELETE FROM eco_history WHERE eco_id = ?", (eco_id,))
                c.execute("DELETE FROM attachments WHERE eco_id = ?", (eco_id,))
                c.execute("DELETE FROM ecos WHERE id = ?", (eco_id,))
                conn.commit()
                logger.info("Deleted ECO id=%d", eco_id)
                return True
        except sqlite3.Error:
            logger.exception("Failed to delete ECO id=%d", eco_id)
            return False

    def submit_eco(self, eco_id: int, username: str, comment: Optional[str] = None) -> bool:
        user_id = self.get_or_create_user(username)
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT status FROM ecos WHERE id = ?", (eco_id,))
            row = c.fetchone()
            if not row or row[0] != STATUS_DRAFT:
                return False
            c.execute("UPDATE ecos SET status = ?, updated_at = ? WHERE id = ?", (STATUS_SUBMITTED, now, eco_id))
            c.execute("""
                INSERT INTO eco_history (eco_id, action, comment, performed_by, performed_at)
                VALUES (?, ?, ?, ?, ?)
            """, (eco_id, STATUS_SUBMITTED, comment, user_id, now))
            conn.commit()
            return True

    def approve_eco(self, eco_id: int, username: str, comment: Optional[str] = None) -> bool:
        user_id = self.get_or_create_user(username)
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT status FROM ecos WHERE id = ?", (eco_id,))
            row = c.fetchone()
            if not row or row[0] != STATUS_SUBMITTED:
                return False
            c.execute("UPDATE ecos SET status = ?, updated_at = ? WHERE id = ?", (STATUS_APPROVED, now, eco_id))
            c.execute("""
                INSERT INTO eco_history (eco_id, action, comment, performed_by, performed_at)
                VALUES (?, ?, ?, ?, ?)
            """, (eco_id, STATUS_APPROVED, comment, user_id, now))
            conn.commit()
            return True

    def reject_eco(self, eco_id: int, username: str, comment: str) -> bool:
        user_id = self.get_or_create_user(username)
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT status FROM ecos WHERE id = ?", (eco_id,))
            row = c.fetchone()
            if not row or row[0] != STATUS_SUBMITTED:
                return False
            c.execute("UPDATE ecos SET status = ?, updated_at = ? WHERE id = ?", (STATUS_REJECTED, now, eco_id))
            c.execute("""
                INSERT INTO eco_history (eco_id, action, comment, performed_by, performed_at)
                VALUES (?, ?, ?, ?, ?)
            """, (eco_id, STATUS_REJECTED, comment, user_id, now))
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
            safe_filename = Path(filename).name
            dest_path = self.attachments_dir / f"{eco_id}_{safe_filename}"
            shutil.copy2(src_path, dest_path)

            file_size = dest_path.stat().st_size
            mime_type = mimetypes.guess_type(safe_filename)[0] or "application/octet-stream"

            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO attachments (eco_id, filename, mime_type, file_path, file_size, uploaded_by, uploaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (eco_id, safe_filename, mime_type, str(dest_path), file_size, user_id, now))
                conn.commit()
            return True
        except (OSError, sqlite3.Error):
            logger.exception("Failed to add attachment '%s' to ECO %d", filename, eco_id)
            return False

    def get_attachment_path(self, eco_id: int, filename: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT file_path FROM attachments WHERE eco_id = ? AND filename = ?", (eco_id, filename))
            row = c.fetchone()
            return row[0] if row else None

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
                SELECT a.id, filename, mime_type, file_path, file_size, uploaded_at, u.username AS uploaded_by
                FROM attachments a JOIN users u ON a.uploaded_by = u.id
                WHERE a.eco_id = ?
            """, (eco_id,))
            eco['attachments'] = [dict(r) for r in c.fetchall()]
            return eco

    def list_ecos(
        self,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Tuple[int, str, str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            query = "SELECT e.id, e.title, e.status, e.created_at, u.username AS created_by FROM ecos e JOIN users u ON e.created_by = u.id"
            conditions = []
            params: list = []
            if search:
                conditions.append("(title LIKE ? OR description LIKE ?)")
                pattern = f"%{search}%"
                params.extend([pattern, pattern])
            if status:
                conditions.append("status = ?")
                params.append(status)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            c.execute(query, params)
            return c.fetchall()

    def generate_report(self, eco_id: int, output_file: str) -> bool:
        data = self.get_eco_details(eco_id)
        if not data:
            return False
            
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# ECO Report: {data['title']}\n\n")
                f.write(f"**ID:** {data['id']}  \n")
                f.write(f"**Status:** {data['status']}  \n")
                f.write(f"**Created By:** {data['created_by']} on {data['created_at']}  \n")
                f.write(f"**Last Updated:** {data['updated_at']}  \n\n")
                
                f.write("## Description\n\n")
                f.write(f"{data['description']}\n\n")
                
                f.write("## Attachments\n\n")
                if data['attachments']:
                    f.write("| Filename | Uploaded By | Date |\n")
                    f.write("| --- | --- | --- |\n")
                    for att in data['attachments']:
                        f.write(f"| {att['filename']} | {att['uploaded_by']} | {att['uploaded_at']} |\n")
                else:
                    f.write("No attachments.\n")
                f.write("\n")

                f.write("## History\n\n")
                if data['history']:
                    f.write("| Action | User | Date | Comment |\n")
                    f.write("| --- | --- | --- | --- |\n")
                    for h in data['history']:
                        comment = h['comment'] if h['comment'] else ""
                        f.write(f"| {h['action']} | {h['username']} | {h['performed_at']} | {comment} |\n")
                else:
                    f.write("No history.\n")
            return True
        except IOError:
            return False

# Example
if __name__ == "__main__":  # pragma: no cover
    eco = ECO()
    eco_id = eco.create_eco("Test ECO", "Description", "alice")
    eco.add_attachment(eco_id, "test.pdf", "example.pdf", "alice")  # assumes example.pdf exists
    print(eco.get_eco_details(eco_id))

