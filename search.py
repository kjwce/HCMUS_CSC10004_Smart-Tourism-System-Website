from flask import Blueprint, request, jsonify
import requests
import unicodedata
import re
from math import radians, sin, cos, sqrt, atan2
import sqlite3
from datetime import datetime, timezone, timedelta
import os
import traceback  
import google.generativeai as genai

# =================== BLUEPRINT SETUP ===================
search_bp = Blueprint("search", __name__)

# =================== CONFIG ===================
DATABASE_PATH = "restaurants.db"
USERS_DB_PATH = "users.db"
# 🔥 GROQ API CONFIG 
GROQ_API_KEY = "YOUR_API_HERE"  
GROQ_API_URL = "YOUR_API_HERE"

# Test connection
if GROQ_API_KEY and GROQ_API_KEY != "gsk_YOUR_GROQ_API_KEY_HERE":
    try:
        test_response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 5
            },
            timeout=5
        )
        if test_response.status_code == 200:
            print("✅ Groq API connected successfully")
        else:
            print(f"⚠️ Groq API test failed: {test_response.status_code}")
            GROQ_API_KEY = None
    except Exception as e:
        print(f"⚠️ Groq API config error: {e}")
        GROQ_API_KEY = None
else:
    print("⚠️ GROQ_API_KEY not configured")
    GROQ_API_KEY = None


# =================== UTILITY FUNCTIONS ===================
def normalize_text(text: str) -> str:
    """Bỏ dấu tiếng Việt và chuyển về lowercase"""
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.strip()


def normalize_address(addr: str) -> str:
    """Chuẩn hóa địa chỉ để so sánh"""
    addr = normalize_text(addr)
    addr = re.sub(r'[^\w\s]', ' ', addr)
    addr = re.sub(r'\s+', ' ', addr).strip()
    return addr


# HÀM KIỂM TRA MÓN ĂN CÓ TRONG DB KHÔNG?
def check_dish_exists_in_db(dish_name: str) -> bool:
    """
    🎯 FIXED: Kiểm tra CHÍNH XÁC xem món ăn có tồn tại không
    
    Logic mới:
    1. Exact match (bánh chưng = bánh chưng) ✅
    2. Word boundary match (bánh chưng nướng starts with bánh chưng) ✅
    3. Không match substring (bánh chun ≠ bánh chưng) ❌
    """
    if not dish_name or len(dish_name.strip()) < 2:
        return False
    
    conn = get_food_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        dish_norm = normalize_text(dish_name)
        words = dish_norm.split()
        
        # 🔥 CASE 1: Single word (e.g., "pho")
        if len(words) == 1:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM dishes d
                WHERE d.name_normalized = ?           -- Exact: "pho"
                   OR d.name_normalized LIKE ?        -- Starts: "pho bo"
                   OR d.name_normalized LIKE ?        -- Contains: "banh pho"
                LIMIT 1
            """, (dish_norm, f"{dish_norm} %", f"% {dish_norm} %"))
            
            result = cursor.fetchone()
            if result and result["count"] > 0:
                conn.close()
                return True
            
            # Check tags
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM tags t
                WHERE t.tag_type = 'dish'
                AND (t.name_normalized = ? 
                     OR t.name_normalized LIKE ? 
                     OR t.name_normalized LIKE ?)
                LIMIT 1
            """, (dish_norm, f"{dish_norm} %", f"% {dish_norm} %"))
            
        # 🔥 CASE 2: Multiple words (e.g., "banh chung")
        else:
            last_word = words[-1]
            
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM dishes d
                WHERE d.name_normalized = ?                    -- Exact: "banh chung"
                   OR d.name_normalized LIKE ?                 -- Starts: "banh chung nuong"
                   OR (d.name_normalized LIKE ?                -- Ends: "... banh chung"
                       AND d.name_normalized NOT LIKE ?)       -- NOT: "... banh chung mieng"
                LIMIT 1
            """, (
                dish_norm,              # "banh chung"
                f"{dish_norm} %",       # "banh chung nuong"
                f"% {last_word}",       # ends with "chung"
                f"% {last_word}%"       # but NOT followed by more chars (e.g., "chungw")
            ))
            
            result = cursor.fetchone()
            if result and result["count"] > 0:
                conn.close()
                return True
            
            # Check tags
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM tags t
                WHERE t.tag_type = 'dish'
                AND (t.name_normalized = ?
                     OR t.name_normalized LIKE ?
                     OR (t.name_normalized LIKE ? AND t.name_normalized NOT LIKE ?))
                LIMIT 1
            """, (dish_norm, f"{dish_norm} %", f"% {last_word}", f"% {last_word}%"))
        
        result = cursor.fetchone()
        conn.close()
        
        return result and result["count"] > 0
        
    except Exception as e:
        print(f"❌ Error checking dish existence: {e}")
        if conn:
            conn.close()
        return False


def correct_dish_name_with_groq(text: str) -> str:
    """
    🎯 SMART CORRECTION với logging chi tiết
    """
    if not text or len(text.strip()) < 2:
        return text
    
    # 🔍 BƯỚC 1: Kiểm tra món ăn có trong DB không
    exists = check_dish_exists_in_db(text)
    
    print(f"🔍 check_dish_exists_in_db('{text}') = {exists}")
    
    if exists:
        print(f"✅ Dish found in DB: '{text}' → No AI correction needed")
        return text
    
    # ⚠️ BƯỚC 2: Không tìm thấy → cần AI correction
    print(f"❌ Dish NOT found in DB: '{text}' → Calling Groq API for correction...")
    
    if not GROQ_API_KEY:
        print("⚠️ Groq API key not configured, returning original text")
        return text
    
    try:
        prompt = f"""Bạn là chuyên gia món ăn Việt Nam.
Nhiệm vụ: Sửa chính tả và thêm dấu tiếng Việt cho tên món ăn.

QUY TẮC BẮT BUỘC:
1. Chỉ trả về TÊN MÓN ĂN duy nhất, KHÔNG có giải thích, chú thích, ngoặc đơn
2. KHÔNG viết "(không chắc chắn)", "(gần giống nhất)", "(có thể là...)"
3. Nếu không chắc, chọn món phổ biến nhất

VÍ DỤ:
- Input: "pho bo" → Output: "Phở bò"
- Input: "bun cha" → Output: "Bún chả"  
- Input: "banh chun" → Output: "Bánh chưng"
- Input: "banh mi" → Output: "Bánh mì" 

Input: {text}
Output:"""

        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {
                        "role": "system", 
                        "content": "Bạn là chuyên gia món ăn Việt Nam. NHIỆM VỤ: Chỉ trả về TÊN MÓN ĂN đã sửa chính tả, TUYỆT ĐỐI KHÔNG giải thích, không thêm ngoặc đơn, không chú thích."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 50,
                "top_p": 1,
                "stream": False
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            corrected = data["choices"][0]["message"]["content"].strip()
            
            # Loại bỏ markdown, quotes, ngoặc đơn và chú thích
            corrected = corrected.replace("**", "").replace("*", "")
            corrected = corrected.strip('"').strip("'").strip()
            
            # 🔥 LOẠI BỎ PHẦN CHÚ THÍCH TRONG NGOẶC ĐƠN
            if '(' in corrected:
                corrected = corrected.split('(')[0].strip()
            
            # Loại bỏ các cụm từ giải thích phổ biến
            unwanted_phrases = [
                "gần giống nhất", "không chắc chắn", "có thể là",
                "hoặc", "Output:", "output:"
            ]
            for phrase in unwanted_phrases:
                if phrase in corrected.lower():
                    corrected = corrected.split(phrase)[0].strip()
                    break
            
            # Validate kết quả
            if corrected and corrected != text and len(corrected) < 100 and not any(c in corrected for c in ['(', ')']):
                print(f"🔧 Groq corrected: '{text}' → '{corrected}'")
                return corrected
            else:
                print(f"⚠️ Groq returned invalid result: '{corrected}', using original text")
                return text
        else:
            print(f"⚠️ Groq API error: {response.status_code} - {response.text}")
            return text
            
    except requests.exceptions.Timeout:
        print("⚠️ Groq API timeout")
        return text
    except Exception as e:
        print(f"⚠️ Groq API error: {e}")
        return text


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Tính khoảng cách (km) giữa 2 điểm GPS"""
    try:
        R = 6371
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
        c = 2*atan2(sqrt(a), sqrt(1-a))
        return round(R * c, 2)
    except:
        return 999.0  # Default nếu tính toán fail


def geocode_location(location_text: str) -> tuple:
    """Chuyển địa chỉ text → GPS coordinates"""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": location_text, "format": "json", "limit": 1}
        headers = {"User-Agent": "SmartFoodApp/4.0"}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        
        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            print(f"✅ Geocoded: {location_text} → ({lat}, {lon})")
            return lat, lon
        
        return None, None
    except Exception as e:
        print(f"❌ Geocode error: {e}")
        return None, None


def reverse_geocode(lat: float, lon: float) -> str:
    """Chuyển GPS coordinates → địa chỉ text"""
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"lat": lat, "lon": lon, "format": "json", "zoom": 16}
        headers = {"User-Agent": "SmartFoodApp/4.0"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        return data.get("display_name")
    except:
        return None


# =================== DATABASE FUNCTIONS ===================
def get_food_db_connection():
    """Mở kết nối tới SQLite database với WAL mode"""
    try:
        conn = sqlite3.connect(DATABASE_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"❌ Database connection error: {e}")
        return None


def get_users_db_connection():
    """Mở kết nối tới users.db (chứa comments)"""
    try:
        conn = sqlite3.connect(USERS_DB_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"❌ Users DB connection error: {e}")
        return None


def get_restaurant_rating(restaurant_id: int) -> dict:
    """Lấy rating thực tế từ bảng comments trong users.db"""
    conn = get_users_db_connection()
    if not conn:
        return {"avg_rating": 0, "review_count": 0}
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                AVG(rating) as avg_rating,
                COUNT(*) as review_count
            FROM comments
            WHERE restaurant_id = ?
        """, (restaurant_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result["review_count"] > 0:
            return {
                "avg_rating": round(result["avg_rating"], 1),
                "review_count": result["review_count"]
            }
        else:
            return {"avg_rating": 0, "review_count": 0}
            
    except sqlite3.Error as e:
        print(f"❌ Error getting rating for restaurant {restaurant_id}: {e}")
        if conn:
            conn.close()
        return {"avg_rating": 0, "review_count": 0}


def find_restaurants_in_db(
    dish_name: str, 
    restaurant_type: str, 
    price_min: int,  
    price_max: int,  
    max_radius: float,
    user_lat: float, 
    user_lon: float
) -> list:
    """
    🔍 TÌM KIẾM NHÀ HÀNG VỚI PRICE RANGE
    """
    conn = get_food_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        
        query_parts = ["""
            SELECT DISTINCT
                r.id,
                r.name,
                r.address,
                r.opening_hours,
                r.price_min,
                r.price_max,
                r.price_text,
                r.image,
                r.restaurant_type,
                r.latitude,
                r.longitude,
                r.url,
                r.final_url,
                r.created_at,
                r.updated_at,
                d.name as dish_name
            FROM restaurants r
            JOIN dishes d ON r.dish_id = d.id
            WHERE 1=1
        """]
        params = []
        
        # # FILTER 1: DISH NAME
        if dish_name and dish_name.strip():
            dish_norm = normalize_text(dish_name)
            words = dish_norm.split()
            
            # 🎯 CHIẾN LƯỢC TÌM KIẾM THÔNG MINH
            if len(words) == 1:
                # TH1: 1 từ (vd: "pho") → tìm bắt đầu hoặc chứa từ đó
                query_parts.append("""
                    AND (
                        d.name_normalized = ?
                        OR d.name_normalized LIKE ?
                        OR d.name_normalized LIKE ?
                        OR EXISTS (
                            SELECT 1 FROM restaurant_tags rt
                            JOIN tags t ON rt.tag_id = t.id
                            WHERE rt.restaurant_id = r.id
                            AND t.tag_type = 'dish'
                            AND (t.name_normalized = ? OR t.name_normalized LIKE ? OR t.name_normalized LIKE ?)
                        )
                    )
                """)
                params.extend([
                    dish_norm,           # exact: "pho"
                    f"{dish_norm} %",    # start: "pho bo"
                    f"% {dish_norm} %",  # contain: "banh pho"
                    dish_norm,           # tag exact
                    f"{dish_norm} %",    # tag start
                    f"% {dish_norm} %"   # tag contain
                ])
            else:
                # TH2: Nhiều từ (vd: "banh can") → ưu tiên exact, sau đó word boundary
                last_word = words[-1]
                query_parts.append("""
                    AND (
                        -- 1.Exact match (cao nhất)
                        d.name_normalized = ?
                        
                        -- 2.Starts with (vd: "banh can tay")
                        OR d.name_normalized LIKE ?
                        
                        -- 3.Word boundary cuối (vd: "... banh can")
                        OR (d.name_normalized LIKE ? AND d.name_normalized NOT LIKE ?)
                        
                        -- 4.Tags tương tự
                        OR EXISTS (
                            SELECT 1 FROM restaurant_tags rt
                            JOIN tags t ON rt.tag_id = t.id
                            WHERE rt.restaurant_id = r.id
                            AND t.tag_type = 'dish'
                            AND (
                                t.name_normalized = ?
                                OR t.name_normalized LIKE ?
                                OR (t.name_normalized LIKE ? AND t.name_normalized NOT LIKE ?)
                            )
                        )
                    )
                """)
                params.extend([
                    dish_norm,                    # exact: "banh can"
                    f"{dish_norm} %",             # starts: "banh can tay"
                    f"% {last_word}",             # ends: "... can"
                    f"% {last_word}%",            # NOT: "... canh" (loại "bánh canh")
                    dish_norm,                    # tag exact
                    f"{dish_norm} %",             # tag starts
                    f"% {last_word}",             # tag ends
                    f"% {last_word}%"             # tag NOT continuation
                ])

        # FILTER 2: RESTAURANT TYPE
        if restaurant_type and restaurant_type.strip() and restaurant_type != "All":
            query_parts.append("AND r.restaurant_type = ?")
            params.append(restaurant_type)
        
        # FILTER 3: PRICE RANGE (🔥 UPDATED LOGIC)
        if price_min > 0 or price_max > 0:
            if price_max == 0:
                # Chỉ có min (≤ price_min)
                query_parts.append("""
                    AND (
                        (r.price_min IS NOT NULL AND r.price_min <= ?)
                        OR (r.price_max IS NOT NULL AND r.price_max <= ?)
                    )
                """)
                params.extend([price_min, price_min])
            else:
                # Có cả min và max (trong khoảng price_min - price_max)
                query_parts.append("""
                    AND (
                        (r.price_min IS NOT NULL AND r.price_max IS NOT NULL 
                         AND ((r.price_min + r.price_max) / 2) BETWEEN ? AND ?)
                        OR (r.price_min IS NOT NULL AND r.price_min BETWEEN ? AND ?)
                        OR (r.price_max IS NOT NULL AND r.price_max BETWEEN ? AND ?)
                    )
                """)
                params.extend([price_min, price_max, price_min, price_max, price_min, price_max])
        
        # FILTER 4: LOCATION
        if user_lat and user_lon and max_radius > 0:
            lat_delta = max_radius / 111.0
            lon_delta = max_radius / (111.0 * cos(radians(user_lat)))
            
            query_parts.append("""
                AND r.latitude BETWEEN ? AND ?
                AND r.longitude BETWEEN ? AND ?
            """)
            params.extend([
                user_lat - lat_delta, user_lat + lat_delta,
                user_lon - lon_delta, user_lon + lon_delta
            ])
        
        sql = " ".join(query_parts)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        # POST-PROCESS
        results = []
        
        for row in rows:
            distance = None
            if user_lat and user_lon and row["latitude"] and row["longitude"]:
                distance = calculate_distance(user_lat, user_lon, row["latitude"], row["longitude"])
                
                if max_radius > 0 and distance > max_radius:
                    continue
            
            # Tính giá trung bình
            price_avg = None
            if row["price_min"] and row["price_max"]:
                price_avg = (row["price_min"] + row["price_max"]) // 2
            elif row["price_min"]:
                price_avg = row["price_min"]
            elif row["price_max"]:
                price_avg = row["price_max"]
            
            # 🔥 FILTER PRICE RANGE (double-check)
            if price_max > 0 and price_avg:
                if price_avg < price_min or price_avg > price_max:
                    continue
            
            cursor.execute("""
                SELECT t.name
                FROM tags t
                JOIN restaurant_tags rt ON t.id = rt.tag_id
                WHERE rt.restaurant_id = ?
                ORDER BY t.name
            """, (row["id"],))
            tags = [tag_row[0] for tag_row in cursor.fetchall()]
            
            rating_data = get_restaurant_rating(row["id"])
            
            restaurant = {
                "id": row["id"],
                "name": row["name"],
                "address": row["address"],
                "opening_hours": row["opening_hours"],
                "price": price_avg or 0,
                "price_min": row["price_min"],
                "price_max": row["price_max"],
                "price_text": row["price_text"],
                "image": row["image"],
                "restaurant_type": row["restaurant_type"],
                "lat": row["latitude"],
                "lon": row["longitude"],
                "url": row["url"],
                "final_url": row["final_url"],
                "distance": distance,
                "dish_name": row["dish_name"],
                "tags": tags,
                "avg_rating": rating_data["avg_rating"],
                "review_count": rating_data["review_count"],
                "verified": True,
                "source": "SQLite Database",
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
            results.append(restaurant)
        
        conn.close()
        
        results.sort(key=lambda x: (
            -float(x.get("avg_rating", 0)),
            x["distance"] if x["distance"] is not None else 999,
            x["price"] if x["price"] else 999999
        ))
        
        return results
        
    except Exception as e:
        print(f"❌ Database query error: {e}")
        traceback.print_exc()
        if conn:
            conn.close()
        return []


# =================== UPDATED save_search_history ===================
def save_search_history(user_id: str, search_params: dict, results_count: int):
    """Lưu lịch sử tìm kiếm với price range"""
    conn = get_food_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        vietnam_tz = timezone(timedelta(hours=7))
        current_time = datetime.now(vietnam_tz).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            INSERT INTO search_history 
            (user_id, dish_name, restaurant_type, price_min, price_max, max_radius, 
             location_text, latitude, longitude, results_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            search_params.get("dish_name"),
            search_params.get("restaurant_type"),
            search_params.get("price_min", 0),  # 🔥 NEW
            search_params.get("price_max", 0),  # 🔥 NEW
            search_params.get("max_radius", 0),
            search_params.get("location_text"),
            search_params.get("lat"),
            search_params.get("lon"),
            results_count,
            current_time
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Save history error: {e}")
        if conn:
            conn.close()


# =================== UPDATED get_search_history ===================
def get_search_history(user_id: str, limit: int = 20):
    """Lấy lịch sử tìm kiếm với price range"""
    conn = get_food_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                id, dish_name, restaurant_type, price_min, price_max, max_radius,
                location_text, latitude, longitude, results_count,
                created_at
            FROM search_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, limit))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                "id": row["id"],
                "dish_name": row["dish_name"],
                "restaurant_type": row["restaurant_type"],
                "price_min": row["price_min"],  # 🔥 NEW
                "price_max": row["price_max"],  # 🔥 NEW
                "max_radius": row["max_radius"],
                "location_text": row["location_text"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "results_count": row["results_count"],
                "created_at": row["created_at"]
            })
        
        conn.close()
        return history
    except sqlite3.Error as e:
        print(f"❌ Error getting search history: {e}")
        if conn:
            conn.close()
        return []

def delete_search_history_item(user_id: str, history_id: int):
    """Xóa 1 item trong lịch sử"""
    conn = get_food_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM search_history 
            WHERE id = ? AND user_id = ?
        """, (history_id, user_id))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted
    except sqlite3.Error as e:
        print(f"❌ Error deleting history: {e}")
        if conn:
            conn.close()
        return False

def clear_search_history(user_id: str):
    """Xóa toàn bộ lịch sử của user"""
    conn = get_food_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM search_history WHERE user_id = ?", (user_id,))
        conn.commit()
        deleted_count = cursor.rowcount
        conn.close()
        return deleted_count
    except sqlite3.Error as e:
        print(f"❌ Error clearing history: {e}")
        if conn:
            conn.close()
        return 0

# =================== AUTOCOMPLETE ===================
def get_dish_autocomplete(search_text: str, limit: int = 10) -> list:
    """Lấy danh sách gợi ý tên món từ database"""
    if not search_text or len(search_text.strip()) < 1:
        return []
    
    search_norm = normalize_text(search_text)
    conn = get_food_db_connection()
    
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT d.name
            FROM dishes d
            WHERE d.name_normalized LIKE ?
            ORDER BY d.name
            LIMIT ?
        """, (f"%{search_norm}%", limit))
        
        results = [row[0] for row in cursor.fetchall()]
        
        if len(results) < limit:
            remaining = limit - len(results)
            cursor.execute("""
                SELECT DISTINCT t.name
                FROM tags t
                WHERE t.tag_type = 'dish'
                AND t.name_normalized LIKE ?
                AND t.name NOT IN ({})
                ORDER BY t.name
                LIMIT ?
            """.format(','.join(['?'] * len(results)) if results else "SELECT 1 WHERE 0"),
                (f"%{search_norm}%", *results, remaining)
            )
            
            results.extend([row[0] for row in cursor.fetchall()])
        
        conn.close()
        return results[:limit]
        
    except Exception as e:
        print(f"❌ Autocomplete error: {e}")
        if conn:
            conn.close()
        return []


# =================== FLASK ROUTES ===================

@search_bp.route("/autocomplete/dishes", methods=["GET"])
def autocomplete_dishes():
    """API autocomplete cho tên món ăn"""
    try:
        q = request.args.get("q", "").strip()
        limit = int(request.args.get("limit", 10))
        
        if not q or len(q) < 1:
            return jsonify({"suggestions": [], "total": 0})
        
        suggestions = get_dish_autocomplete(q, limit)
        
        return jsonify({
            "query": q,
            "suggestions": suggestions,
            "total": len(suggestions)
        })
    except Exception as e:
        print(f"❌ Autocomplete API error: {e}")
        traceback.print_exc()
        return jsonify({"suggestions": [], "total": 0, "error": str(e)}), 200  # Still 200 OK

@search_bp.route("/search_restaurants", methods=["POST"])
def search_restaurants():
    """
    🔍 TÌM KIẾM NHÀ HÀNG (WITH OPTIMIZED AI CORRECTION)
    
    Flow:
    1. Parse request data
    2. Check if dish exists in DB (original input)
    3. If NOT found → Call Groq API for correction
    4. Search with corrected name
    5. Return results
    """
    try:
        # # PARSE REQUEST
        # data = request.json
        # if not data:
        #     return jsonify({"error": "No data provided", "matches": []}), 400
        
        # dish_name = data.get("dish_name") or ""
        # restaurant_type = data.get("restaurant_type") or ""
        # budget = data.get("budget", 0) or 0
        # max_radius = data.get("max_radius", 0) or 0
        
        # lat = data.get("lat")
        # lon = data.get("lon")
        # location_text = data.get("location_text") or "Ho Chi Minh City"

        # =================== PARSE REQUEST ===================
        data = request.json
        if not data:
            return jsonify({"error": "No data provided", "matches": []}), 400
        
        dish_name = data.get("dish_name") or ""
        restaurant_type = data.get("restaurant_type") or ""
        price_min = data.get("price_min", 0) or 0  # 🔥 NEW
        price_max = data.get("price_max", 0) or 0  # 🔥 NEW
        max_radius = data.get("max_radius", 0) or 0
        
        lat = data.get("lat")
        lon = data.get("lon")
        location_text = data.get("location_text") or ""
        
        # 🎯 SMART CORRECTION: Chỉ gọi AI khi cần
        original_dish = dish_name
        corrected_by_ai = False
        
        if dish_name and dish_name.strip():
            corrected_name = correct_dish_name_with_groq(dish_name)
            if corrected_name != dish_name:
                corrected_by_ai = True
                dish_name = corrected_name
        
        # DETERMINE LOCATION
        user_used_gps = False
        
        # TRƯỜNG HỢP 1: CÓ GPS
        if lat and lon:
            user_used_gps = True
            print(f"✅ Using GPS from device: ({lat}, {lon})")
            
            # Nếu không có location_text, thử reverse geocode để hiển thị
            if not location_text:
                location_text = reverse_geocode(lat, lon)
                if location_text:
                    print(f"📍 Reverse geocoded to: {location_text}")
                else:
                    # Reverse geocode fail → hiển thị tọa độ
                    location_text = f"Vị trí GPS ({lat:.4f}, {lon:.4f})"
                    print(f"⚠️ Reverse geocode failed, showing coordinates")
        
        # TRƯỜNG HỢP 2: KHÔNG CÓ GPS → BẮT BUỘC NHẬP ĐỊA CHỈ
        else:
            # Kiểm tra location_text
            if not location_text or not location_text.strip():
                return jsonify({
                    "error": "Vui lòng bật GPS hoặc nhập địa chỉ để tìm kiếm",
                    "message": "Location required - Please enable GPS or enter your address",
                    "code": "LOCATION_REQUIRED",
                    "suggestion": "Enable GPS or enter your location"
                }), 400
            
            # Geocode địa chỉ → GPS
            print(f"🔍 Geocoding user address: {location_text}")
            geocoded_lat, geocoded_lon = geocode_location(location_text)
            
            if geocoded_lat and geocoded_lon:
                # ✅ OSM thành công
                lat, lon = geocoded_lat, geocoded_lon
                print(f"✅ Geocoded successfully: ({lat}, {lon})")
            else:
                # ⚠️ OSM fail → Fallback về trường
                lat, lon = 10.7625844, 106.68169479999999
                print(f"⚠️ Geocode failed for '{location_text}'")
                print(f"⚠️ Fallback to university location: ({lat}, {lon})")
        
        print(f"\n{'='*60}")
        print(f"📍 User Location: {location_text}")
        print(f"📌 GPS: ({lat}, {lon})")
        print(f"🎯 Filters Applied:")
        print(f"   - Original Input: {original_dish}")
        if corrected_by_ai:
            print(f"   - AI Corrected: {dish_name} ✨")
        else:
            print(f"   - Search Term: {dish_name} (no correction needed)")
        print(f"   - Type: {restaurant_type or 'All'}")
        if price_min == 0 and price_max == 0:
            print(f"   - Budget: Unlimited")
        elif price_max == 0:
            print(f"   - Budget: ≤ {price_min:,}₫")
        else:
            print(f"   - Budget: {price_min:,}₫ - {price_max:,}₫")
        
        print(f"   - Max Radius: {max_radius}km" if max_radius > 0 else "   - Max Radius: Unlimited")
        print(f"{'='*60}\n")

        
        # SEARCH DATABASE
        db_results = find_restaurants_in_db(
            dish_name, restaurant_type, price_min, price_max, max_radius, lat, lon
        )
        
        # DEDUPLICATE
        seen = {}
        unique_restaurants = [] 
        
        for r in db_results:
            name_norm = normalize_text(r.get("name", ""))
            addr_norm = normalize_address(r.get("address", ""))
            lat_r = r.get("lat")
            lon_r = r.get("lon")
            gps_key = f"{lat_r:.4f},{lon_r:.4f}" if lat_r and lon_r else "no_gps"
            key = f"{name_norm}|{addr_norm}|{gps_key}"
            
            if key not in seen:
                seen[key] = r
                unique_restaurants.append(r)
        
        # SORT
        final_results = sorted(unique_restaurants, key=lambda x: (
            -float(x.get("avg_rating", 0)),
            x.get("distance", 999),
            x.get("price", 999999)
        ))
        
        print(f"✅ Final results: {len(final_results)} restaurants\n")
        
        # SAVE HISTORY
        user_id = data.get("user_id") or "anonymous"
        save_location_text = None if user_used_gps else location_text
        save_search_history(user_id, {
            "dish_name": dish_name,
            "restaurant_type": restaurant_type,
            "price_min": price_min,  # 🔥 NEW
            "price_max": price_max,  # 🔥 NEW
            "max_radius": max_radius,
            "location_text": save_location_text,
            "lat": lat,
            "lon": lon
        }, len(final_results))
        
        # RESPONSE
        response_data = {
            "total_results": len(final_results),
            "verified_count": len(final_results),
            "sources_used": ["Database", "User Comments"],
            "location": {"text": location_text, "lat": lat, "lon": lon},
            "filters": {
                "dish_name": dish_name,
                "original_dish_input": original_dish,
                "corrected_by_ai": corrected_by_ai,
                "restaurant_type": restaurant_type,
                "price_min": price_min,  # 🔥 NEW
                "price_max": price_max,  # 🔥 NEW
                "max_radius": max_radius
            },
            "matches": final_results
        }
        
        # Thêm Groq vào sources nếu đã dùng AI correction
        if corrected_by_ai:
            response_data["sources_used"].append("Groq AI")
        
        if not final_results:
            response_data["message"] = (
                f"No restaurants found for '{dish_name}'" + 
                (f" within {max_radius}km" if max_radius > 0 else "")
            )
            return jsonify(response_data), 404
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"❌❌❌ CRITICAL ERROR in search_restaurants:")
        print(traceback.format_exc())
        
        return jsonify({
            "error": f"Internal server error: {str(e)}",
            "total_results": 0,
            "matches": [],
            "message": "An error occurred during search. Please try again."
        }), 500


# =================== SEARCH HISTORY ROUTES ===================

@search_bp.route("/history", methods=["GET"])
def get_history():
    """Lấy lịch sử tìm kiếm của user"""
    user_id = request.args.get("user_id", "anonymous")
    limit = int(request.args.get("limit", 20))
    
    history = get_search_history(user_id, limit)
    
    return jsonify({
        "user_id": user_id,
        "total": len(history),
        "history": history
    })


@search_bp.route("/history/<int:history_id>", methods=["DELETE"])
def delete_history_item(history_id):
    """Xóa 1 item trong lịch sử"""
    user_id = request.args.get("user_id", "anonymous")
    success = delete_search_history_item(user_id, history_id)
    
    if success:
        return jsonify({"message": "History item deleted", "id": history_id})
    else:
        return jsonify({"error": "Failed to delete or not found"}), 404


@search_bp.route("/history/clear", methods=["DELETE"])
def clear_history():
    """Xóa toàn bộ lịch sử"""
    user_id = request.args.get("user_id", "anonymous")
    deleted_count = clear_search_history(user_id)
    
    return jsonify({
        "message": f"Cleared {deleted_count} history items",
        "deleted_count": deleted_count
    })


# =================== UPDATED get_history_detail ROUTE ===================
@search_bp.route("/history/<int:history_id>", methods=["GET"])
def get_history_detail(history_id):
    """Lấy chi tiết 1 lịch sử tìm kiếm với price range"""
    user_id = request.args.get("user_id", "anonymous")
    
    conn = get_food_db_connection()
    if not conn:
        return jsonify({"error": "Database error"}), 500
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            id, dish_name, restaurant_type, price_min, price_max, max_radius,
            location_text, latitude, longitude, results_count, created_at
        FROM search_history
        WHERE id = ? AND user_id = ?
    """, (history_id, user_id))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "History not found"}), 404
    
    return jsonify({
        "id": row["id"],
        "dish_name": row["dish_name"],
        "restaurant_type": row["restaurant_type"] or "",
        "price_min": row["price_min"] or 0,  # 🔥 NEW
        "price_max": row["price_max"] or 0,  # 🔥 NEW
        "max_radius": row["max_radius"] or 0,
        "location_text": row["location_text"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "results_count": row["results_count"],
        "created_at": row["created_at"]
    })

# XỬ LÝ BIẾN ĐỊA CHỈ NGƯỜI DÙNG NHẬP THÀNH LAT,LON ĐỂ CHỈ ĐƯỜNG
@search_bp.route("/geocode", methods=["POST"])
def geocode_api():
    """
    Nhận location_text (địa chỉ người dùng gõ),
    trả về lat, lon hoặc báo lỗi.
    """
    try:
        data = request.get_json(silent=True) or {}
        location_text = (data.get("location_text") or "").strip()

        if not location_text:
            return jsonify({
                "success": False,
                "error": "location_text is required"
            }), 400

        lat, lon = geocode_location(location_text)

        if lat is None or lon is None:
            return jsonify({
                "success": False,
                "error": "Cannot geocode this address",
                "location_text": location_text
            }), 200   # vẫn 200 nhưng success=False

        return jsonify({
            "success": True,
            "location_text": location_text,
            "lat": lat,
            "lon": lon
        }), 200

    except Exception as e:
        print("❌ Geocode API error:", e)
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Internal geocode error: {str(e)}"
        }), 500


@search_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_food_db_connection()
        db_ok = conn is not None
        groq_ok = GROQ_API_KEY is not None
        
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM restaurants")
            restaurant_count = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) as count FROM dishes")
            dish_count = cursor.fetchone()["count"]
            conn.close()
        else:
            restaurant_count = 0
            dish_count = 0
        
        return jsonify({
            "status": "healthy" if db_ok else "degraded",
            "api_version": "7.1-STABLE",
            "database_ok": db_ok,
            "groq_api_ok": groq_ok,
            "statistics": {
                "total_dishes": dish_count,
                "total_restaurants": restaurant_count
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500
