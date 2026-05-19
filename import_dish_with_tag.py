import sqlite3
import json
import unicodedata
import os
from datetime import datetime, timezone, timedelta


# =================== CONFIG ===================
DATABASE_PATH = "restaurants.db"


def normalize_text(text):
    """Bỏ dấu tiếng Việt"""
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.strip()


def parse_price_range(price_str):
    """Parse giá từ string → (min, max)"""
    if not price_str:
        return None, None
    
    price_str = str(price_str).replace("đ", "").replace("VND", "")
    price_str = price_str.replace(".", "").replace(",", "").strip()
    
    if "-" in price_str:
        parts = price_str.split("-")
        try:
            min_price = int(parts[0].strip())
            max_price = int(parts[1].strip())
            return min_price, max_price
        except:
            return None, None
    
    try:
        price = int(price_str)
        return price, price
    except:
        return None, None


def auto_generate_tags(restaurant_data, dish_name):
    """Tự động tạo tags từ tên quán - CÓ THÊM MÓN CHAY"""
    tags = set()
    tags.add(dish_name)
    
    name = restaurant_data.get("name", "")
    name_lower = normalize_text(name)
    
    dish_keywords = [
        # Món truyền thống
        ("bun thit nuong", "Bún thịt nướng"),
        ("bun dau mam tom", "Bún đậu mắm tôm"),
        ("banh trang nuong", "Bánh tráng nướng"),
        ("bun bo hue", "Bún bò Huế"),
        ("bun rieu", "Bún riêu"),
        ("bun mam", "Bún mắm"), 
        ("bun cha", "Bún chả"),
        ("com tam", "Cơm tấm"),
        ("com chien", "Cơm chiên"),
        ("banh bot loc", "Bánh bột lọc"),
        ("banh khot", "Bánh khọt"),
        ("banh cuon", "Bánh cuốn"),
        ("banh canh", "Bánh canh"),
        ("banh chung", "Bánh chưng"),
        ("banh xeo", "Bánh xèo"),
        ("banh can", "Bánh căn"),
        ("banh beo", "Bánh bèo"),
        ("banh duc", "Bánh đúc"),
        ("banh gio", "Bánh giò"),
        ("banh pia", "Bánh pía"),
        ("banh tet", "Bánh tét"),
        ("banh mi", "Bánh mì"),
        ("banh bao", "Bánh bao"),
        ("chao long", "Cháo lòng"),
        ("ca kho to", "Cá kho tộ"),
        ("canh chua", "Canh chua"),
        ("goi cuon", "Gỏi cuốn"),
        ("cha gio", "Chả giò"),
        ("cao lau", "Cao lầu"),
        ("hu tieu", "Hủ tiếu"),
        ("mi quang", "Mì Quảng"),
        ("nem chua", "Nem chua"),
        ("xoi xeo", "Xôi xéo"),
        ("pho bo", "Phở bò"),
        ("xoi", "Xôi"),
        ("lau", "Lẩu"),
        
        # ⭐⭐⭐ MÓN CHAY MỚI ⭐⭐⭐
        ("banh mi chay", "Bánh mì chay"),
        ("com chay", "Cơm chay"),
        ("lau chay", "Lẩu chay"),
        ("pho chay", "Phở chay"),
        ("hu tieu chay", "Hủ tiếu chay"),
        ("mon an chay", "Món ăn chay"),
        ("bun chay", "Bún chay"),
    ]
    
    matched_ranges = []
    
    for keyword, dish_proper_name in dish_keywords:
        start = 0
        while True:
            pos = name_lower.find(keyword, start)
            if pos == -1:
                break
            
            end = pos + len(keyword)
            
            overlap = False
            for matched_start, matched_end in matched_ranges:
                if pos >= matched_start and end <= matched_end:
                    overlap = True
                    break
            
            if not overlap:
                is_word_boundary = (
                    (pos == 0 or name_lower[pos-1] in ' -,;')
                    and
                    (end == len(name_lower) or name_lower[end] in ' -,;')
                )
                
                if is_word_boundary:
                    tags.add(dish_proper_name)
                    matched_ranges.append((pos, end))
            
            start = pos + 1
    
    return list(tags)


def insert_or_get_tag(cursor, tag_name, tag_type="dish"):
    """Insert tag hoặc lấy ID nếu đã tồn tại"""
    tag_name_norm = normalize_text(tag_name)
    
    cursor.execute("SELECT id FROM tags WHERE name_normalized = ?", (tag_name_norm,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    
    try:
        cursor.execute("""
            INSERT INTO tags (name, name_normalized, tag_type)
            VALUES (?, ?, ?)
        """, (tag_name, tag_name_norm, tag_type))
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        cursor.execute("SELECT id FROM tags WHERE name_normalized = ?", (tag_name_norm,))
        result = cursor.fetchone()
        if result:
            return result[0]
        print(f"⚠️  ERROR: Cannot find or insert tag: {tag_name}")
        return None


def link_restaurant_tag(cursor, restaurant_id, tag_id):
    """Liên kết restaurant ↔ tag"""
    cursor.execute("""
        INSERT OR IGNORE INTO restaurant_tags (restaurant_id, tag_id)
        VALUES (?, ?)
    """, (restaurant_id, tag_id))


def check_restaurant_exists(cursor, dish_id, name, address):
    """⭐ KIỂM TRA RESTAURANT ĐÃ TỒN TẠI CHƯA"""
    name_norm = normalize_text(name)
    address_norm = normalize_text(address) if address else ""
    
    # Kiểm tra theo dish_id + tên + địa chỉ
    cursor.execute("""
        SELECT id FROM restaurants
        WHERE dish_id = ?
        AND LOWER(name) = ?
        AND (address IS NULL OR LOWER(address) = ?)
        LIMIT 1
    """, (dish_id, name_norm, address_norm))
    
    result = cursor.fetchone()
    return result[0] if result else None


def import_multiple_json_files():
    """Import từ nhiều file JSON với auto-tags VÀ KHÔNG TRÙNG LẶP"""
    
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()
    
    # ⭐⭐⭐ VIETNAM TIME ⭐⭐⭐
    vietnam_tz = timezone(timedelta(hours=7))
    current_time = datetime.now(vietnam_tz).strftime('%Y-%m-%d %H:%M:%S')
    
    print("\n🚀 Starting Import Process (NO DUPLICATES)...")
    print(f"⏰ Vietnam Time: {current_time}")
    print("="*60)


    FOLDER = "CRAWL_FOODY"
    
    dishes_config = [
        # Món truyền thống
        {"file": "bánh bèo.json", "dish_name": "Bánh bèo"},
        {"file": "bánh bột lọc.json", "dish_name": "Bánh bột lọc"},
        {"file": "bánh căn.json", "dish_name": "Bánh căn"},
        {"file": "bánh canh.json", "dish_name": "Bánh canh"},
        {"file": "bánh chưng.json", "dish_name": "Bánh chưng"},
        {"file": "bánh cuốn.json", "dish_name": "Bánh cuốn"},
        {"file": "bánh đúc.json", "dish_name": "Bánh đúc"},
        {"file": "bánh giò.json", "dish_name": "Bánh giò"},
        {"file": "bánh khọt.json", "dish_name": "Bánh khọt"},
        {"file": "bánh pía.json", "dish_name": "Bánh pía"},
        {"file": "bánh tét.json", "dish_name": "Bánh tét"},
        {"file": "bánh tráng nướng.json", "dish_name": "Bánh tráng nướng"},
        {"file": "bánh xèo.json", "dish_name": "Bánh xèo"},
        {"file": "bún bò huế.json", "dish_name": "Bún bò Huế"},
        {"file": "bún đậu mắm tôm.json", "dish_name": "Bún đậu mắm tôm"},
        {"file": "bún mắm.json", "dish_name": "Bún mắm"},
        {"file": "bún riêu.json", "dish_name": "Bún riêu"},
        {"file": "bún thịt nướng.json", "dish_name": "Bún thịt nướng"},
        {"file": "cá kho tộ.json", "dish_name": "Cá kho tộ"},
        {"file": "canh chua.json", "dish_name": "Canh chua"},
        {"file": "cao lầu.json", "dish_name": "Cao lầu"},
        {"file": "cháo lòng.json", "dish_name": "Cháo lòng"},
        {"file": "đồ uống.json", "dish_name": "Đồ uống"},
        {"file": "gỏi cuốn.json", "dish_name": "Gỏi cuốn"},
        {"file": "mì quảng.json", "dish_name": "Mì quảng"},
        {"file": "nem chua.json", "dish_name": "Nem chua"},
        {"file": "tráng miệng.json", "dish_name": "Tráng miệng"},
        {"file": "xôi xéo.json", "dish_name": "Xôi xéo"},
        
        # ⭐⭐⭐ MÓN CHAY MỚI ⭐⭐⭐
        {"file": "bánh mì chay.json", "dish_name": "Bánh mì chay"},
        {"file": "cơm chay.json", "dish_name": "Cơm chay"},
        {"file": "lẩu chay.json", "dish_name": "Lẩu chay"},
        {"file": "phở chay.json", "dish_name": "Phở chay"},
        {"file": "hủ tiếu chay.json", "dish_name": "Hủ tiếu chay"},
        {"file": "món ăn chay.json", "dish_name": "Món ăn chay"},
        {"file": "bún chay.json", "dish_name": "Bún chay"},
    ]
    
    total_dishes = 0
    total_restaurants = 0
    total_skipped = 0
    total_tags_created = 0
    total_links_created = 0
    
    for config in dishes_config:
        file_path = os.path.join(FOLDER, config["file"])
        
        if not os.path.exists(file_path):
            print(f"\n⚠️  File not found: {file_path} - SKIPPING")
            continue
        
        try:
            print(f"\n📂 Processing: {file_path}")
            print("-" * 60)
            
            with open(file_path, "r", encoding="utf-8") as f:
                restaurants = json.load(f)
            
            print(f"   Loaded: {len(restaurants)} restaurants")
            
            # INSERT DISH (OR GET EXISTING)
            dish_name = config["dish_name"]
            dish_name_norm = normalize_text(dish_name)
            
            cursor.execute("""
                INSERT OR IGNORE INTO dishes (name, name_normalized, created_at)
                VALUES (?, ?, ?)
            """, (dish_name, dish_name_norm, current_time))
            
            cursor.execute("SELECT id FROM dishes WHERE name = ?", (dish_name,))
            dish_id = cursor.fetchone()[0]
            total_dishes += 1
            
            print(f"   ✅ Dish ID {dish_id}: {dish_name}")
            
            # ⭐⭐⭐ INSERT RESTAURANTS (KIỂM TRA TRÙNG) ⭐⭐⭐
            inserted_count = 0
            skipped_count = 0
            
            for rest in restaurants:
                rest_name = rest.get("name")
                rest_address = rest.get("address")
                
                # ⭐ KIỂM TRA ĐÃ TỒN TẠI
                existing_id = check_restaurant_exists(cursor, dish_id, rest_name, rest_address)
                
                if existing_id:
                    skipped_count += 1
                    total_skipped += 1
                    # Vẫn cập nhật tags cho restaurant cũ
                    restaurant_id = existing_id
                else:
                    # INSERT MỚI
                    price_min, price_max = parse_price_range(rest.get("price"))
                    
                    cursor.execute("""
                        INSERT INTO restaurants 
                        (dish_id, name, address, opening_hours, 
                         price_min, price_max, price_text, image, restaurant_type,
                         latitude, longitude, url, final_url, 
                         created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        dish_id,
                        rest_name,
                        rest_address,
                        rest.get("opening_hours"),
                        price_min,
                        price_max,
                        rest.get("price"),
                        rest.get("image"),              # 1 ảnh duy nhất / nhà hàng
                        rest.get("category", "Quán ăn"),
                        rest.get("latitude"),
                        rest.get("longitude"),
                        rest.get("url"),
                        rest.get("final_url"),
                        current_time,
                        current_time
                    ))
                    
                    restaurant_id = cursor.lastrowid
                    total_restaurants += 1
                    inserted_count += 1
                
                # AUTO-GENERATE TAGS (cho cả restaurant mới và cũ)
                tags = auto_generate_tags(rest, dish_name)
                
                for tag_name in tags:
                    tag_id = insert_or_get_tag(cursor, tag_name, "dish")
                    
                    if tag_id:
                        link_restaurant_tag(cursor, restaurant_id, tag_id)
                        total_links_created += 1
            
            print(f"   ✅ Inserted: {inserted_count} restaurants")
            print(f"   ⏭️  Skipped: {skipped_count} duplicates")
            
            cursor.execute("""
                SELECT DISTINCT t.name
                FROM tags t
                JOIN restaurant_tags rt ON t.id = rt.tag_id
                JOIN restaurants r ON rt.restaurant_id = r.id
                WHERE r.dish_id = ?
                LIMIT 5
            """, (dish_id,))
            sample_tags = [row[0] for row in cursor.fetchall()]
            print(f"   🏷️  Sample tags: {', '.join(sample_tags)}")
            
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON Error in {file_path}: {e}")
        except Exception as e:
            print(f"   ❌ Error processing {file_path}: {e}")
            import traceback
            traceback.print_exc()
    
    conn.commit()
    
    # VERIFY DATA
    print("\n" + "="*60)
    print("✅ Verifying imported data...")
    print("="*60)
    
    cursor.execute("SELECT COUNT(*) FROM dishes")
    db_dishes = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM restaurants")
    db_restaurants = cursor.fetchone()[0]
    
    # ❌ BỎ restaurant_images
    # cursor.execute("SELECT COUNT(*) FROM restaurant_images")
    # db_images = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tags")
    db_tags = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM restaurant_tags")
    db_links = cursor.fetchone()[0]
    
    # Show dishes breakdown
    cursor.execute("""
        SELECT d.name, COUNT(r.id) as restaurant_count
        FROM dishes d
        LEFT JOIN restaurants r ON d.id = r.dish_id
        GROUP BY d.id
        ORDER BY d.name
    """)
    dishes_breakdown = cursor.fetchall()
    
    print(f"\n📊 Dishes in database:")
    for dish_name, count in dishes_breakdown:
        print(f"   - {dish_name}: {count} restaurants")
    
    # Show top tags
    cursor.execute("""
        SELECT t.name, COUNT(rt.restaurant_id) as restaurant_count
        FROM tags t
        LEFT JOIN restaurant_tags rt ON t.id = rt.tag_id
        GROUP BY t.id
        ORDER BY restaurant_count DESC
        LIMIT 10
    """)
    top_tags = cursor.fetchall()
    
    print(f"\n🏷️  Top 10 Tags:")
    for tag_name, count in top_tags:
        print(f"   - {tag_name}: {count} restaurants")
    
    conn.close()
    
    # SUMMARY
    print("\n" + "="*60)
    print("🎉 IMPORT COMPLETE (NO DUPLICATES)!")
    print("="*60)
    print(f"⏰ Completed at: {current_time} (Vietnam Time)")
    print(f"✅ Total dishes imported: {total_dishes}")
    print(f"✅ Total NEW restaurants: {total_restaurants}")
    print(f"⏭️  Total SKIPPED duplicates: {total_skipped}")
    print(f"✅ Total tags in DB: {db_tags}")
    print(f"✅ Total restaurant-tag links: {db_links}")
    print(f"\n📂 Database file: {DATABASE_PATH}")
    print(f"📊 Current database:")
    print(f"   - Dishes: {db_dishes}")
    print(f"   - Restaurants: {db_restaurants}")
    print(f"   - Tags: {db_tags}")
    print(f"   - Restaurant-Tag Links: {db_links}")
    print("="*60)
    print("\n💡 Next step:")
    print("   Run your Flask API: python app.py")
    print("="*60)


if __name__ == "__main__":
    print("🚀 Import Dishes with NO DUPLICATES")
    print("="*60)
    import_multiple_json_files()
