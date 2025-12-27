import sqlite3
import sys
import os

def promote_user(username):
    db_path = "eco_system.db"
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (username,))
        if c.rowcount > 0:
            print(f"Success: User '{username}' is now an Admin.")
            conn.commit()
        else:
            print(f"Error: User '{username}' not found in database.")

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
