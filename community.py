from flask import Blueprint, request, jsonify, session
import sqlite3
from datetime import datetime
import html
import base64

community_bp = Blueprint("community", __name__, url_prefix="/community")

# ======================
# INIT DATABASE
# ======================
def init_community_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Bảng chat
    c.execute("""
        CREATE TABLE IF NOT EXISTS community (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,         
            username TEXT NOT NULL,
            avatar TEXT DEFAULT 'default-avatar.png',
            message TEXT,
            image BLOB,
            created_at TEXT NOT NULL
        )
    """)

    # Bảng reactions
    c.execute("""
        CREATE TABLE IF NOT EXISTS reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            reaction TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (message_id) REFERENCES community (id)
        )
    """)

    conn.commit()
    conn.close()


# ======================
# ADD MESSAGE
# ======================
@community_bp.route("/add", methods=["POST"])
def add_message():
    if "username" not in session:
        return jsonify({"error": "Bạn phải đăng nhập để gửi tin nhắn!"}), 401

    data = request.form
    topic = data.get("topic", "").strip()
    message = html.escape(data.get("message", "").strip())

    username = session["username"]
    avatar = session.get("avatar", "default-avatar.png")

    # Ảnh
    image_data = None
    if "image" in request.files:
        file = request.files["image"]
        if file:
            image_data = file.read()

    # Giới hạn 500 ký tự
    if message and len(message) > 500:
        return jsonify({"error": "Tin nhắn tối đa 500 ký tự!"}), 400

    # Không cho tin nhắn rỗng
    if not message and not image_data:
        return jsonify({"error": "Tin nhắn không được để trống!"}), 400

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("""
        INSERT INTO community (topic, username, avatar, message, image, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (topic, username, avatar, message, image_data, created_at))

    conn.commit()
    conn.close()

    return jsonify({"message": "Sent!"})


# ======================
# GET MESSAGES
# ======================
@community_bp.route("/get", methods=["GET"])
def get_messages():
    topic = request.args.get("topic", "food")  # default

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("""
        SELECT id, username, avatar, message, image, created_at
        FROM community
        WHERE topic = ?
        ORDER BY id DESC
        LIMIT 100
    """, (topic,))
    
    rows = c.fetchall()
    conn.close()

    messages = []
    for r in rows:
        messages.append({
            "id": r[0],
            "username": r[1],
            "avatar": r[2],
            "message": r[3],
            "image": base64.b64encode(r[4]).decode() if r[4] else None,
            "created_at": r[5],
        })

    return jsonify(messages)


# ======================
# ADD REACTION
# ======================
@community_bp.route("/react", methods=["POST"])
def add_reaction():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    message_id = data.get("message_id")
    reaction = data.get("reaction")
    username = session["username"]

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Kiểm tra user đã reaction chưa
    c.execute("""
        SELECT id FROM reactions
        WHERE message_id = ? AND username = ?
    """, (message_id, username))

    row = c.fetchone()

    if row:
        # Update lại reaction cũ
        c.execute("""
            UPDATE reactions
            SET reaction = ?, created_at = ?
            WHERE id = ?
        """, (reaction, created_at, row[0]))
    else:
        # Thêm reaction mới
        c.execute("""
            INSERT INTO reactions (message_id, username, reaction, created_at)
            VALUES (?, ?, ?, ?)
        """, (message_id, username, reaction, created_at))

    conn.commit()
    conn.close()

    return jsonify({"message": "Reaction added!"})


# ======================
# GET REACTIONS
# ======================
@community_bp.route("/reactions/<int:message_id>")
def get_reactions(message_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("""
        SELECT reaction, COUNT(*)
        FROM reactions
        WHERE message_id = ?
        GROUP BY reaction
    """, (message_id,))

    result = c.fetchall()
    conn.close()

    return jsonify(result)
