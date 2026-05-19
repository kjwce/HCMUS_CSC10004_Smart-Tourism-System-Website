# --- START OF FILE favorites.py ---
from flask import Blueprint, request, jsonify, session
import sqlite3

favorite_bp = Blueprint('favorite', __name__, url_prefix='/auth')

# =============================
# 🔧 Tạo bảng favorites nếu chưa có
# =============================
def init_favorite_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # Lưu tên quán, địa chỉ, ảnh và tọa độ để khi click vào có thể mở lại bản đồ
    c.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            restaurant_name TEXT NOT NULL,
            address TEXT,
            image TEXT,
            lat REAL,
            lon REAL,
            UNIQUE(username, restaurant_name) 
        )
    ''')
    # UNIQUE(username, restaurant_name) để ngăn user thích 1 quán 2 lần
    conn.commit()
    conn.close()

# =============================
# 📌 CHECK STATUS (Kiểm tra user đã thích quán này chưa)
# =============================
@favorite_bp.route('/check_favorite', methods=['POST'])
def check_favorite():
    if 'username' not in session:
        return jsonify({"is_favorite": False})

    data = request.get_json()
    username = session['username']
    restaurant_name = data.get("restaurant_name")

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM favorites WHERE username = ? AND restaurant_name = ?", (username, restaurant_name))
    exists = c.fetchone()
    conn.close()

    return jsonify({"is_favorite": bool(exists)})

# =============================
# 📌 TOGGLE FAVORITE (Thêm hoặc Xóa)
# =============================
@favorite_bp.route('/toggle_favorite', methods=['POST'])
def toggle_favorite():
    if 'username' not in session:
        return jsonify({"error": "Bạn cần đăng nhập để thực hiện tính năng này!"}), 401

    data = request.get_json()
    username = session['username']
    
    name = data.get("name")
    address = data.get("address")
    image = data.get("image")
    lat = data.get("lat")
    lon = data.get("lon")

    if not name:
        return jsonify({"error": "Thiếu thông tin tên quán!"}), 400

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Kiểm tra xem đã like chưa
    c.execute("SELECT id FROM favorites WHERE username = ? AND restaurant_name = ?", (username, name))
    row = c.fetchone()

    if row:
        # Nếu đã có -> Xóa (Unlike)
        c.execute("DELETE FROM favorites WHERE id = ?", (row[0],))
        action = "removed"
    else:
        # Nếu chưa có -> Thêm (Like)
        c.execute('''
            INSERT INTO favorites (username, restaurant_name, address, image, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, name, address, image, lat, lon))
        action = "added"

    conn.commit()
    conn.close()

    return jsonify({"message": "Thành công", "action": action})

# =============================
# 📌 GET FAVORITES (Lấy danh sách cho trang User)
# =============================
@favorite_bp.route('/get_favorites', methods=['GET'])
def get_favorites():
    if 'username' not in session:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    username = session['username']

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT restaurant_name, address, image, lat, lon FROM favorites WHERE username = ? ORDER BY id DESC", (username,))
    rows = c.fetchall()
    conn.close()

    favorites = []
    for r in rows:
        favorites.append({
            "name": r[0],
            "address": r[1],
            "image": r[2],
            "lat": r[3],
            "lon": r[4]
        })

    return jsonify(favorites)