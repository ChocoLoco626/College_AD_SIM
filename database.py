import hashlib, hmac, os, sqlite3, json
from pathlib import Path

DB_PATH = Path("college_ad_sim_v5.db")

def conn():
    c = sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS saves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        data TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, name)
    )""")
    c.commit()
    return c

def init_db():
    c = conn(); c.close()

def _hash(password, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180_000)
    return salt.hex() + "$" + digest.hex()

def _check(password, stored):
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        got = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180_000).hex()
        return hmac.compare_digest(got, digest_hex)
    except Exception:
        return False

def create_user(username, password):
    c = conn()
    try:
        c.execute("INSERT INTO users(username,password_hash) VALUES(?,?)",
                  (username.strip(), _hash(password)))
        c.commit()
        return True, "Account created."
    except sqlite3.IntegrityError:
        return False, "That username already exists."
    finally:
        c.close()

def authenticate_user(username, password):
    c = conn()
    row = c.execute("SELECT id,password_hash FROM users WHERE username=?",
                    (username.strip(),)).fetchone()
    c.close()
    if row and _check(password, row[1]):
        return row[0]
    return None

def list_saves(user_id):
    c = conn()
    rows = c.execute("SELECT name,updated_at FROM saves WHERE user_id=? ORDER BY updated_at DESC",
                     (user_id,)).fetchall()
    c.close()
    return rows

def save_game(user_id, name, data):
    payload = json.dumps(data)
    c = conn()
    c.execute("""INSERT INTO saves(user_id,name,data) VALUES(?,?,?)
                 ON CONFLICT(user_id,name) DO UPDATE SET data=excluded.data,
                 updated_at=CURRENT_TIMESTAMP""", (user_id, name, payload))
    c.commit(); c.close()

def load_game(user_id, name):
    c = conn()
    row = c.execute("SELECT data FROM saves WHERE user_id=? AND name=?",
                    (user_id, name)).fetchone()
    c.close()
    return json.loads(row[0]) if row else None
