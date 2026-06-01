import sqlite3

def init_db():
    conn = sqlite3.connect('home_services.db')
    cursor = conn.cursor()

    # 1. Users Table (General users, providers, and admins)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        role TEXT DEFAULT 'user', -- 'user', 'provider', 'admin'
        phone TEXT,
        city TEXT,
        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 2. Providers Table (Detailed info for companies/individuals)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS providers (
        provider_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        type TEXT, -- 'company', 'individual'
        email TEXT,
        phone TEXT,
        city TEXT,
        logo_path TEXT,
        description TEXT,
        experience_years INTEGER,
        status TEXT DEFAULT 'active', -- 'active', 'inactive', 'pending'
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')

    # 3. Categories Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        display_order INTEGER DEFAULT 0
    )
    ''')

    # 4. Services Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS services (
        service_id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id INTEGER,
        category_id INTEGER,
        name TEXT,
        description TEXT,
        city TEXT,
        price REAL,
        pricing_type TEXT, -- 'hourly', 'visit', 'fixed'
        images TEXT, -- Comma separated paths
        execution_time TEXT,
        working_hours TEXT,
        is_24h BOOLEAN DEFAULT 0,
        coverage_areas TEXT,
        contact_phone TEXT,
        whatsapp TEXT,
        social_links TEXT, -- JSON or comma separated
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY (provider_id) REFERENCES providers (provider_id),
        FOREIGN KEY (category_id) REFERENCES categories (category_id)
    )
    ''')

    # 5. Bookings/Inquiries Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bookings (
        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        service_id INTEGER,
        provider_id INTEGER,
        status TEXT DEFAULT 'pending', -- 'pending', 'confirmed', 'completed', 'cancelled'
        booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (service_id) REFERENCES services (service_id),
        FOREIGN KEY (provider_id) REFERENCES providers (provider_id)
    )
    ''')

    # Insert default categories
    default_categories = [
        ('تنظيف', 1), ('كهرباء', 2), ('سباكة', 3), 
        ('صيانة تكييف', 4), ('نقل أثاث', 5), ('دهانات', 6), 
        ('صيانة منزلية', 7), ('تركيب أجهزة', 8)
    ]
    cursor.executemany('INSERT OR IGNORE INTO categories (name, display_order) VALUES (?, ?)', default_categories)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
