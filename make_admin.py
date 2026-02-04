import os
import sys

from eco_manager import ECO


def promote_user(username: str) -> None:
    db_path = os.environ.get("DATABASE_PATH", "eco_system.db")

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        sys.exit(1)

    eco = ECO(db_path=db_path)
    users = eco.get_all_users()
    user = next((u for u in users if u["username"] == username), None)

    if not user:
        print(f"Error: User '{username}' not found in database.")
        sys.exit(1)

    if user["is_admin"]:
        print(f"User '{username}' is already an admin.")
        return

    import sqlite3
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (username,))
        conn.commit()

    print(f"Success: User '{username}' is now an Admin.")


if __name__ == "__main__":
    print("--- ECO Manager Admin Promoter ---")
    if len(sys.argv) < 2:
        username = input("Enter username to promote: ").strip()
    else:
        username = sys.argv[1]

    if username:
        promote_user(username)
    else:
        print("Operation cancelled.")
