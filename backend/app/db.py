import sqlite3
from contextlib import contextmanager
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  password_hash TEXT NOT NULL, salt TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user', active INTEGER NOT NULL DEFAULT 1,
  bio TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS documents(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  filename TEXT NOT NULL, stored_name TEXT NOT NULL, file_type TEXT NOT NULL,
  size INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'processing', error TEXT,
  pages INTEGER DEFAULT 0, chunk_count INTEGER DEFAULT 0, char_count INTEGER DEFAULT 0,
  title TEXT DEFAULT '', tags TEXT DEFAULT '', collection TEXT DEFAULT 'default',
  chunk_size INTEGER, chunk_overlap INTEGER,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS chunks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL, idx INTEGER NOT NULL,
  page INTEGER, section TEXT DEFAULT '', text TEXT NOT NULL, embedding BLOB NOT NULL);
CREATE INDEX IF NOT EXISTS ix_chunks_user ON chunks(user_id);
CREATE INDEX IF NOT EXISTS ix_chunks_doc ON chunks(document_id);
CREATE TABLE IF NOT EXISTS conversations(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT 'New conversation',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL, content TEXT NOT NULL,
  sources TEXT DEFAULT '[]', meta TEXT DEFAULT '{}',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS query_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, question TEXT,
  intent TEXT, top_score REAL, retrieval_ms REAL, llm_ms REAL, total_ms REAL,
  answered INTEGER, support REAL, engine TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS activity(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, detail TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as c:
        c.executescript(SCHEMA)


def log_activity(user_id, action, detail=""):
    with db() as c:
        c.execute("INSERT INTO activity(user_id,action,detail) VALUES(?,?,?)", (user_id, action, detail))
