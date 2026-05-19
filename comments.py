# ==========================================
# UPDATE comment.py - Thêm API để lấy rating thực tế
# ==========================================

from flask import Blueprint, request, jsonify, session
import sqlite3
import math
from datetime import datetime
import html
import os

comment_bp = Blueprint('comment', __name__, url_prefix='/auth')

MAX_COMMENT_LENGTH = 500
UPLOAD_FOLDER = "static/comment_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_comment_db():
    """Tạo bảng comments nếu chưa có (bao gồm restaurant_id và trường image)."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_id INTEGER,            -- liên kết tới restaurants.id
            restaurant TEXT,                 -- (tuỳ bạn có giữ tên hay không)
            username TEXT NOT NULL,
            avatar TEXT DEFAULT 'default-avatar.png',
            comment TEXT,
            rating INTEGER DEFAULT 0,
            image TEXT,                      -- tên file ảnh lưu trong static/comment_images
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


# ==========================================
# 🆕 NEW ROUTE: Lấy rating thực tế từ comments
# ==========================================
@comment_bp.route('/get_restaurant_rating', methods=['GET'])
def get_restaurant_rating():
    """
    Lấy rating thực tế từ comments của restaurant
    
    Query params:
        restaurant_id: int (required)
    
    Returns:
        {
            "restaurant_id": int,
            "avg_rating": float,
            "review_count": int,
            "rating_breakdown": {
                "5": count,
                "4": count,
                "3": count,
                "2": count,
                "1": count
            }
        }
    """
    restaurant_id = request.args.get("restaurant_id")

    if not restaurant_id:
        return jsonify({"error": "restaurant_id is required"}), 400

    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        # Lấy avg rating và count
        c.execute('''
            SELECT 
                COUNT(*) as review_count,
                AVG(rating) as avg_rating
            FROM comments
            WHERE restaurant_id = ?
        ''', (restaurant_id,))
        
        row = c.fetchone()
        review_count = row[0]
        avg_rating = float(row[1]) if row[1] else 0
        
        # Lấy rating breakdown (phân bố sao)
        c.execute('''
            SELECT rating, COUNT(*) as count
            FROM comments
            WHERE restaurant_id = ?
            GROUP BY rating
        ''', (restaurant_id,))
        
        breakdown_rows = c.fetchall()
        rating_breakdown = {str(i): 0 for i in range(1, 6)}
        
        for rating, count in breakdown_rows:
            if rating >= 1 and rating <= 5:
                rating_breakdown[str(rating)] = count
        
        conn.close()
        
        return jsonify({
            "restaurant_id": int(restaurant_id),
            "avg_rating": round(avg_rating, 2),
            "review_count": review_count,
            "rating_breakdown": rating_breakdown
        })
        
    except Exception as e:
        print(f"❌ Error getting rating: {e}")
        return jsonify({"error": str(e)}), 500


@comment_bp.route('/popular_restaurants', methods=['GET'])
def popular_restaurants():
    try:
        print("🔍 Starting popular_restaurants calculation...")
        
        conn_restaurants = sqlite3.connect('restaurants.db')
        conn_comments = sqlite3.connect('users.db')
        
        c_rest = conn_restaurants.cursor()
        c_rest.execute('''
            SELECT 
                id, name, image, address, price_text, price_min, price_max, restaurant_type,
                latitude, longitude
            FROM restaurants
        ''')
        all_restaurants = c_rest.fetchall()
        
        print(f"📊 Found {len(all_restaurants)} total restaurants")
        
        # Lấy thống kê comments
        c_comments = conn_comments.cursor()
        c_comments.execute('''
            SELECT restaurant_id, COUNT(*) as review_count, AVG(rating) as avg_rating
            FROM comments 
            GROUP BY restaurant_id
        ''')
        comment_stats = c_comments.fetchall()
        
        print(f"💬 Found {len(comment_stats)} restaurants with comments")
        
        stats_dict = {}
        for rest_id, count, avg_rating in comment_stats:
            stats_dict[rest_id] = {
                'review_count': count,
                'avg_rating': float(avg_rating) if avg_rating else 0
            }
        
        conn_restaurants.close()
        conn_comments.close()
        
        restaurants_with_reviews = []
        
        for rest in all_restaurants:
            rest_id, name, image, address, price_text, price_min, price_max, restaurant_type, latitude, longitude = rest
            
            stats = stats_dict.get(rest_id, {'review_count': 0, 'avg_rating': 0})
            review_count = stats['review_count']
            avg_rating = stats['avg_rating']
            
            if review_count > 0:
                score = (avg_rating * 0.7) + (math.log(review_count + 1) * 0.3)
                
                try:
                    lat = float(latitude) if latitude else None
                    lon = float(longitude) if longitude else None
                except (TypeError, ValueError):
                    lat = None
                    lon = None
                
                restaurants_with_reviews.append({
                    "id": rest_id,
                    "name": name,
                    "image": image or "/static/images/food1.png",
                    "address": address or "Address not available",
                    # "price": price or "Price not available",
                    "price_text": price_text,         # Chuỗi gốc từ DB
                    "price_min": price_min,           # Số min
                    "price_max": price_max,           # Số max
                    "category": restaurant_type or "Category not available",
                    "review_count": review_count,
                    "avg_rating": round(avg_rating, 2),
                    "score": round(score, 2),
                    "lat": lat,
                    "latitude": lat,
                    "lon": lon,
                    "longitude": lon
                })
        
        restaurants_with_reviews.sort(key=lambda x: x['score'], reverse=True)
        top_10_restaurants = restaurants_with_reviews[:10]
        
        print(f"🏆 FINAL TOP 10 RESTAURANTS:")
        for i, rest in enumerate(top_10_restaurants, 1):
            has_coords = rest['lat'] is not None and rest['lon'] is not None
            coords_status = f"GPS: ✅ ({rest['lat']}, {rest['lon']})" if has_coords else "GPS: ❌ MISSING"
            print(f"#{i}: {rest['name']} - Score: {rest['score']} - Reviews: {rest['review_count']} - {coords_status}")
        
        return jsonify(top_10_restaurants)
        
    except Exception as e:
        print("❌ Error in popular_restaurants:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify([])


# =============================
# GET COMMENTS BY RESTAURANT ID
# =============================
@comment_bp.route('/get_comments', methods=['GET'])
def get_comments():
    restaurant_id = request.args.get("restaurant_id")

    if not restaurant_id:
        return jsonify([])

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        SELECT id, username, avatar, comment, rating, image, created_at
        FROM comments
        WHERE restaurant_id = ?
        ORDER BY id DESC
    ''', (restaurant_id,))
    rows = c.fetchall()
    conn.close()

    comments = []
    for r in rows:
        comments.append({
            "id": r[0],
            "username": r[1],
            "avatar": r[2] or "default-avatar.png",
            "comment": r[3],
            "rating": r[4],
            "image": r[5],
            "created_at": r[6],
        })

    return jsonify(comments)


# =============================
# ADD COMMENT
# =============================
@comment_bp.route('/add_comment', methods=['POST'])
def add_comment():
    if 'username' not in session:
        return jsonify({"error": "Bạn cần đăng nhập để bình luận!"}), 401

    restaurant_id = request.form.get("restaurant_id")
    comment = request.form.get("comment", "").strip()
    rating = request.form.get("rating", 0)
    image_file = request.files.get("image")

    if not restaurant_id:
        return jsonify({"error": "Thiếu restaurant_id!"}), 400

    if not comment and not image_file:
        return jsonify({"error": "Bạn phải nhập bình luận hoặc chọn ảnh!"}), 400

    if comment and len(comment) > MAX_COMMENT_LENGTH:
        return jsonify({"error": f"Tối đa {MAX_COMMENT_LENGTH} ký tự!"}), 400

    try:
        rating = int(rating)
        if rating < 0 or rating > 5:
            return jsonify({"error": "Rating phải từ 0 đến 5 sao"}), 400
    except:
        return jsonify({"error": "Rating không hợp lệ!"}), 400

    comment = html.escape(comment)
    username = session["username"]
    avatar = session.get("avatar", "default-avatar.png")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    image_filename = None
    if image_file:
        ext = image_file.filename.split(".")[-1]
        image_filename = f"{username}_{int(datetime.now().timestamp())}.{ext}"
        save_path = os.path.join(UPLOAD_FOLDER, image_filename)
        image_file.save(save_path)

    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute('''
        INSERT INTO comments (restaurant_id, username, avatar, comment, rating, image, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (restaurant_id, username, avatar, comment, rating, image_filename, created_at))
    conn.commit()
    conn.close()

    return jsonify({"message": "Bình luận đã được gửi!"})


# =============================
# DELETE COMMENT
# =============================
@comment_bp.route('/delete_comment', methods=['POST'])
def delete_comment():
    if 'username' not in session:
        return jsonify({"error": "Bạn phải đăng nhập!"}), 401

    data = request.get_json()
    comment_id = data.get("comment_id")

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("SELECT username, image FROM comments WHERE id = ?", (comment_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Không tìm thấy bình luận!"}), 404

    owner, image_file = row

    if owner != session['username']:
        conn.close()
        return jsonify({"error": "Không có quyền xoá!"}), 403

    if image_file:
        path = os.path.join(UPLOAD_FOLDER, image_file)
        if os.path.exists(path):
            os.remove(path)

    c.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Đã xoá bình luận!"})


# =============================
# EDIT COMMENT
# =============================
@comment_bp.route('/edit_comment', methods=['POST'])
def edit_comment():
    if 'username' not in session:
        return jsonify({"error": "Bạn phải đăng nhập!"}), 401

    data = request.get_json()
    comment_id = data.get("id")
    new_text = data.get("comment", "").strip()

    if not new_text:
        return jsonify({"error": "Nội dung không được trống!"}), 400

    if len(new_text) > MAX_COMMENT_LENGTH:
        return jsonify({"error": f"Tối đa {MAX_COMMENT_LENGTH} ký tự!"}), 400

    new_text = html.escape(new_text)

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("SELECT username FROM comments WHERE id = ?", (comment_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Không tìm thấy comment!"}), 404

    if row[0] != session["username"]:
        conn.close()
        return jsonify({"error": "Không có quyền sửa!"}), 403

    c.execute("UPDATE comments SET comment=? WHERE id=?", (new_text, comment_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Đã sửa bình luận!"})



