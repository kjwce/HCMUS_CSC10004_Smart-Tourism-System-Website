import sqlite3
import unicodedata

# =================== CONFIG ===================
DATABASE_PATH = "food_v5.db"

def normalize_text(text):
    """Bỏ dấu tiếng Việt"""
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.strip()

# =================== CREATE DATABASE ===================

def create_database():
    """
    Tạo database với timestamps controlled bởi Python code
    ⭐ Python set VN time khi INSERT
    ⭐ Trigger auto-update khi UPDATE
    """
    print("🚀 Creating Multi-Dish Database with Python-controlled VN timestamps...")
    print("="*60)
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # ====== DROP OLD TABLES ======
    print("🗑️  Dropping old tables (if exist)...")
    cursor.execute("DROP TRIGGER IF EXISTS update_restaurants_timestamp")
    cursor.execute("DROP TABLE IF EXISTS search_history")
    cursor.execute("DROP TABLE IF EXISTS restaurant_tags")
    cursor.execute("DROP TABLE IF EXISTS tags")
    cursor.execute("DROP TABLE IF EXISTS restaurant_images")
    cursor.execute("DROP TABLE IF EXISTS restaurants")
    cursor.execute("DROP TABLE IF EXISTS dishes")
    
    # ====== TABLE 1: DISHES (WITHOUT description) ======
    print("\n📋 Creating table: dishes")
    cursor.execute("""
    CREATE TABLE dishes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        name_normalized TEXT NOT NULL,
        image TEXT,
        created_at TEXT NOT NULL  -- ⭐ Python will set VN time
    )
    """)
    print("   ✅ Table 'dishes' created (NO description column)")
    
    # ====== TABLE 2: RESTAURANTS (WITH updated_at) ======
    print("\n📋 Creating table: restaurants")
    cursor.execute("""
    CREATE TABLE restaurants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dish_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        address TEXT,
        opening_hours TEXT,
        price_min INTEGER,
        price_max INTEGER,
        price_text TEXT,
        image TEXT,
        restaurant_type TEXT,
        latitude REAL,
        longitude REAL,
        url TEXT,
        final_url TEXT,
        created_at TEXT NOT NULL,  -- ⭐ Python sets VN time
        updated_at TEXT NOT NULL,  -- ⭐ Python sets VN time
        
        FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE CASCADE
    )
    """)
    print("   ✅ Table 'restaurants' created with updated_at")
    
    # ⭐⭐⭐ TRIGGER: Auto-update updated_at ⭐⭐⭐
    print("\n⚡ Creating trigger: update_restaurants_timestamp")
    cursor.execute("""
    CREATE TRIGGER update_restaurants_timestamp
    AFTER UPDATE ON restaurants
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at  -- Only if not manually changed
    BEGIN
        UPDATE restaurants
        SET updated_at = datetime('now', '+7 hours')
        WHERE id = NEW.id;
    END
    """)
    print("   ✅ Trigger created (auto-updates updated_at on any UPDATE)")
    
    # ====== TABLE 3: RESTAURANT_IMAGES ======
    print("\n📋 Creating table: restaurant_images")
    cursor.execute("""
    CREATE TABLE restaurant_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        image_url TEXT NOT NULL,
        
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
    )
    """)
    print("   ✅ Table 'restaurant_images' created")
    
    # ====== TABLE 4: TAGS ======
    print("\n📋 Creating table: tags")
    cursor.execute("""
    CREATE TABLE tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        name_normalized TEXT NOT NULL UNIQUE,
        tag_type TEXT DEFAULT 'dish',
        created_at TEXT DEFAULT (datetime('now', '+7 hours')) -- ✅ Tự động
    )
    """)
    print("   ✅ Table 'tags' created")
    
    # ====== TABLE 5: RESTAURANT_TAGS ======
    print("\n📋 Creating table: restaurant_tags")
    cursor.execute("""
    CREATE TABLE restaurant_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        tag_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now', '+7 hours')),  -- ✅ Tự động
        
        FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE,
        FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
        UNIQUE(restaurant_id, tag_id)
    )
    """)
    print("   ✅ Table 'restaurant_tags' created")
    
    # ====== TABLE 6: SEARCH_HISTORY ======
    print("\n📋 Creating table: search_history")
    cursor.execute("""
    CREATE TABLE search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        dish_name TEXT NOT NULL,
        restaurant_type TEXT,
        budget INTEGER,
        max_radius REAL,
        location_text TEXT,
        latitude REAL,
        longitude REAL,
        results_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL  -- ⭐ Python sets VN time
    )
    """)
    print("   ✅ Table 'search_history' created")
    
    # ====== CREATE INDEXES ======
    print("\n⚡ Creating indexes for faster search...")
    cursor.execute("CREATE INDEX idx_dishes_name_normalized ON dishes(name_normalized)")
    cursor.execute("CREATE INDEX idx_restaurants_dish_id ON restaurants(dish_id)")
    cursor.execute("CREATE INDEX idx_restaurants_type ON restaurants(restaurant_type)")
    cursor.execute("CREATE INDEX idx_restaurants_price ON restaurants(price_min, price_max)")
    cursor.execute("CREATE INDEX idx_restaurants_location ON restaurants(latitude, longitude)")
    cursor.execute("CREATE INDEX idx_tags_normalized ON tags(name_normalized)")
    cursor.execute("CREATE INDEX idx_tags_type ON tags(tag_type)")
    cursor.execute("CREATE INDEX idx_restaurant_tags_restaurant ON restaurant_tags(restaurant_id)")
    cursor.execute("CREATE INDEX idx_restaurant_tags_tag ON restaurant_tags(tag_id)")
    cursor.execute("CREATE INDEX idx_search_history_user ON search_history(user_id)")
    cursor.execute("CREATE INDEX idx_search_history_created ON search_history(created_at DESC)")
    print("   ✅ Created 11 indexes")
    
    conn.commit()
    conn.close()
    
    # ====== VERIFY ======
    print("\n✅ Verifying database...")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"   Tables created: {len(tables)}")
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table[0]})")
        columns = cursor.fetchall()
        print(f"   - {table[0]}: {len(columns)} columns")
        
        # Show columns for dishes table
        if table[0] == 'dishes':
            print(f"     Columns: {', '.join([col[1] for col in columns])}")
    
    # Check triggers
    cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    triggers = cursor.fetchall()
    print(f"\n⚡ Triggers: {len(triggers)}")
    for trigger in triggers:
        print(f"   - {trigger[0]}")
    
    conn.close()
    
    # ====== SUMMARY ======
    print("\n" + "="*60)
    print("🎉 DATABASE CREATED SUCCESSFULLY!")
    print("="*60)
    print(f"📂 Database file: {DATABASE_PATH}")
    print(f"📊 Tables: dishes (NO description), restaurants (with updated_at),")
    print(f"           restaurant_images, tags, restaurant_tags, search_history")
    print(f"⏰ Timestamp strategy: Python code sets VN time (UTC+7)")
    print(f"⚡ Trigger: auto-updates updated_at on restaurant changes")
    print("\n💡 Next step:")
    print("   Run 'python import_dishes_no_duplicates.py' to import data")
    print("="*60)


# =================== MAIN ===================

if __name__ == "__main__":
    create_database()