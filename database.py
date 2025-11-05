import sqlite3
import os

DB_FILE = "learning_app.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    );""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        topic TEXT,
        mode TEXT,
        content_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );""")
    conn.commit()
    conn.close()

def create_user(email, password_hash):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (email, password_hash) VALUES (?,?)", (email, password_hash))
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id

def get_user_by_email(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cur.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user

def save_generation(user_id, topic, mode, content_json):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO generations (user_id, topic, mode, content_json) VALUES (?,?,?,?)",
                (user_id, topic, mode, content_json))
    conn.commit()
    gen_id = cur.lastrowid
    conn.close()
    return gen_id

def get_generations_by_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, topic, mode, content_json, created_at, user_id FROM generations WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_generation_by_id(gen_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM generations WHERE id = ?", (gen_id,))
    row = cur.fetchone()
    conn.close()
    return row

def delete_generation(gen_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM generations WHERE id = ?", (gen_id,))
    conn.commit()
    conn.close()
