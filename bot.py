import logging
import sqlite3
import asyncio
import sys
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
from telegram.error import Conflict, TimedOut, NetworkError

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "7844717795:AAFpJsBMsYJSoM2-rAJNXFm-mmJxaWXUzUc"
ADMIN_IDS = [8465734371]

def get_db_connection():
    # Use relative path for production environment
    conn = sqlite3.connect('home_services.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- Helper Functions ---

async def get_main_keyboard(user_id):
    keyboard = [
        ["🔍 البحث عن خدمة", "🛠️ خدماتي (لمقدمي الخدمة)"],
        ["📝 تسجيل كمقدم خدمة", "ℹ️ عن البوت"],
        ["🔗 مشاركة البوت"]
    ]
    if user_id in ADMIN_IDS:
        keyboard.append(["📊 لوحة تحكم المدير"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- Core Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data.clear() # Clear any stuck state
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)", 
                       (user.id, user.username, user.full_name))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB Error in start: {e}")

    welcome_text = (
        f"مرحباً بك {user.full_name} في بوت خدمات المنازل! 🏠\n\n"
        "هذا البوت يربط بين مقدمي الخدمات والمستخدمين الباحثين عن خدمات منزلية.\n\n"
        "يرجى اختيار ما تريد القيام به من القائمة أدناه:"
    )
    reply_markup = await get_main_keyboard(user.id)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"معرف التيليجرام الخاص بك هو: `{update.effective_user.id}`", parse_mode='Markdown')

# --- Simplified State Management ---

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    state = context.user_data.get('state')

    # Global Exit/Cancel
    if text == "إلغاء ❌" or text == "🔙 العودة للقائمة الرئيسية":
        context.user_data.clear()
        return await start(update, context)

    # Main Menu Routing
    if not state or text in ["🔍 البحث عن خدمة", "🛠️ خدماتي (لمقدمي الخدمة)", "📝 تسجيل كمقدم خدمة", "ℹ️ عن البوت", "🔗 مشاركة البوت", "📊 لوحة تحكم المدير"]:
        context.user_data.clear() # Reset state on any main button click
        
        if text == "🔍 البحث عن خدمة":
            return await show_categories(update, context)
        elif text == "🛠️ خدماتي (لمقدمي الخدمة)":
            return await provider_dashboard(update, context)
        elif text == "📝 تسجيل كمقدم خدمة":
            return await start_registration(update, context)
        elif text == "ℹ️ عن البوت":
            return await update.message.reply_text("🏠 *بوت خدمات المنازل*\n\nمنصة لربط مقدمي الخدمات بالمستخدمين.", parse_mode='Markdown')
        elif text == "🔗 مشاركة البوت":
            bot = await context.bot.get_me()
            url = f"https://t.me/share/url?url=https://t.me/{bot.username}&text=جرب بوت خدمات المنازل! 🏠"
            return await update.message.reply_text("شارك البوت:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 مشاركة", url=url)]]))
        elif text == "📊 لوحة تحكم المدير":
            return await admin_dashboard(update, context)
        elif text == "➕ إضافة خدمة جديدة":
            return await start_add_service(update, context)
        elif text == "📋 عرض خدماتي":
            return await show_my_services(update, context)
        elif text == "📢 إرسال إعلان عام":
            return await start_broadcast(update, context)

    # Handle States
    if state == "REG_TYPE":
        context.user_data['reg_type'] = 'company' if "شركة" in text else 'individual'
        context.user_data['state'] = "REG_NAME"
        return await update.message.reply_text("يرجى إدخال اسمك أو اسم الشركة:", reply_markup=ReplyKeyboardRemove())
    elif state == "REG_NAME":
        context.user_data['reg_name'] = text
        context.user_data['state'] = "REG_EMAIL"
        return await update.message.reply_text("يرجى إدخال البريد الإلكتروني للتواصل:")
    elif state == "REG_EMAIL":
        context.user_data['reg_email'] = text
        context.user_data['state'] = "REG_PHONE"
        return await update.message.reply_text("يرجى إدخال رقم الهاتف:")
    elif state == "REG_PHONE":
        context.user_data['reg_phone'] = text
        context.user_data['state'] = "REG_CITY"
        return await update.message.reply_text("يرجى إدخال المدينة:")
    elif state == "REG_CITY":
        context.user_data['reg_city'] = text
        context.user_data['state'] = "REG_DESC"
        return await update.message.reply_text("يرجى إدخال وصف مختصر لخدماتك:")
    elif state == "REG_DESC":
        return await complete_registration(update, context)
    
    elif state == "ADD_SERVICE_NAME":
        context.user_data['s_name'] = text
        context.user_data['state'] = "ADD_SERVICE_DESC"
        return await update.message.reply_text("يرجى إدخال وصف الخدمة:")
    elif state == "ADD_SERVICE_DESC":
        context.user_data['s_desc'] = text
        context.user_data['state'] = "ADD_SERVICE_PRICE"
        return await update.message.reply_text("يرجى إدخال السعر (رقم):")
    elif state == "ADD_SERVICE_PRICE":
        try: context.user_data['s_price'] = float(text)
        except: return await update.message.reply_text("يرجى إدخال رقم صحيح.")
        context.user_data['state'] = "ADD_SERVICE_PRICING"
        kb = [["بالساعة", "بالزيارة"], ["سعر ثابت", "حسب الاتفاق"]]
        return await update.message.reply_text("طريقة التسعير:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    elif state == "ADD_SERVICE_PRICING":
        context.user_data['s_pricing'] = text
        context.user_data['state'] = "ADD_SERVICE_PHONE"
        return await update.message.reply_text("رقم التواصل:", reply_markup=ReplyKeyboardRemove())
    elif state == "ADD_SERVICE_PHONE":
        context.user_data['s_phone'] = text
        context.user_data['state'] = "ADD_SERVICE_WA"
        return await update.message.reply_text("رقم الواتساب (مثال: 966500000000):")
    elif state == "ADD_SERVICE_CAT":
        conn = get_db_connection()
        cat = conn.execute("SELECT category_id FROM categories WHERE name = ?", (text,)).fetchone()
        conn.close()
        if not cat:
            return await update.message.reply_text("يرجى اختيار تصنيف من القائمة.")
        context.user_data['cat_id'] = cat['category_id']
        context.user_data['state'] = "ADD_SERVICE_NAME"
        return await update.message.reply_text(f"تم اختيار: {text}\n\nيرجى إدخال اسم الخدمة (مثال: تنظيف منازل):", reply_markup=ReplyKeyboardRemove())
    elif state == "ADD_SERVICE_WA":
        return await complete_add_service(update, context)
    
    elif state == "BROADCAST":
        return await complete_broadcast(update, context)
    
    elif state == "BOOKING":
        return await complete_booking(update, context)

# --- Logic Implementations ---

async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    p = conn.execute("SELECT * FROM providers WHERE user_id = ?", (update.effective_user.id,)).fetchone()
    conn.close()
    if p: return await update.message.reply_text("أنت مسجل بالفعل.")
    context.user_data['state'] = "REG_TYPE"
    kb = [["شركة 🏢", "فرد 👤"], ["إلغاء ❌"]]
    await update.message.reply_text("اختر نوع الحساب:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def complete_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data
    user_id = update.effective_user.id
    try:
        conn = get_db_connection()
        conn.execute("UPDATE users SET role = 'provider' WHERE user_id = ?", (user_id,))
        conn.execute("INSERT INTO providers (user_id, name, type, email, phone, city, description) VALUES (?,?,?,?,?,?,?)",
                     (user_id, d['reg_name'], d.get('reg_type', 'individual'), d['reg_email'], d['reg_phone'], d['reg_city'], update.message.text))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ تم التسجيل!", reply_markup=await get_main_keyboard(user_id))
    except Exception as e:
        logger.error(f"Reg Error: {e}")
        await update.message.reply_text("خطأ في التسجيل.")
    context.user_data.clear()

async def provider_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    p = conn.execute("SELECT * FROM providers WHERE user_id = ?", (update.effective_user.id,)).fetchone()
    conn.close()
    if not p: return await update.message.reply_text("يرجى التسجيل أولاً.")
    kb = [["➕ إضافة خدمة جديدة", "📋 عرض خدماتي"], ["🔙 العودة للقائمة الرئيسية"]]
    await update.message.reply_text(f"لوحة تحكم {p['name']}:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def start_add_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    cats = conn.execute("SELECT * FROM categories ORDER BY display_order").fetchall()
    conn.close()
    kb = [[c['name']] for c in cats] + [["إلغاء ❌"]]
    context.user_data['state'] = "ADD_SERVICE_CAT"
    await update.message.reply_text("اختر التصنيف:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def complete_add_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data
    try:
        conn = get_db_connection()
        p_id = conn.execute("SELECT provider_id FROM providers WHERE user_id = ?", (update.effective_user.id,)).fetchone()[0]
        conn.execute("INSERT INTO services (provider_id, category_id, name, description, price, pricing_type, contact_phone, whatsapp) VALUES (?,?,?,?,?,?,?,?)",
                     (p_id, d['cat_id'], d['s_name'], d['s_desc'], d['s_price'], d['s_pricing'], d['s_phone'], update.message.text))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ تم الإضافة!", reply_markup=await get_main_keyboard(update.effective_user.id))
    except Exception as e:
        logger.error(f"Add Service Error: {e}")
        await update.message.reply_text("خطأ.")
    context.user_data.clear()

async def show_my_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    ss = conn.execute("SELECT s.* FROM services s JOIN providers p ON s.provider_id = p.provider_id WHERE p.user_id = ?", (update.effective_user.id,)).fetchall()
    conn.close()
    if not ss: return await update.message.reply_text("لا توجد خدمات.")
    msg = "📋 خدماتك:\n\n" + "\n".join([f"🔹 {s['name']}" for s in ss])
    await update.message.reply_text(msg)

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    cats = conn.execute("SELECT * FROM categories ORDER BY display_order").fetchall()
    conn.close()
    kb = []
    for i in range(0, len(cats), 2):
        row = [InlineKeyboardButton(cats[i]['name'], callback_data=f"cat_{cats[i]['category_id']}")]
        if i+1 < len(cats): row.append(InlineKeyboardButton(cats[i+1]['name'], callback_data=f"cat_{cats[i+1]['category_id']}"))
        kb.append(row)
    await update.message.reply_text("اختر التصنيف: 🔍", reply_markup=InlineKeyboardMarkup(kb))

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    conn = get_db_connection()
    u = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    p = conn.execute("SELECT COUNT(*) FROM providers").fetchone()[0]
    s = conn.execute("SELECT COUNT(*) FROM services").fetchone()[0]
    conn.close()
    text = f"📊 *لوحة المدير*\n\n👥 مستخدمين: {u}\n🏢 مقدمين: {p}\n🛠️ خدمات: {s}"
    kb = [["📢 إرسال إعلان عام"], ["🔙 العودة للقائمة الرئيسية"]]
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    context.user_data['state'] = "BROADCAST"
    await update.message.reply_text("اكتب نص الإعلان:", reply_markup=ReplyKeyboardMarkup([["إلغاء ❌"]], resize_keyboard=True))

async def complete_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    conn = get_db_connection()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    count = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u['user_id'], text=f"📢 *إعلان:*\n\n{text}", parse_mode='Markdown')
            count += 1
            await asyncio.sleep(0.05)
        except: continue
    await update.message.reply_text(f"✅ تم الإرسال لـ {count} مستخدم.")
    context.user_data.clear()
    return await admin_dashboard(update, context)

# --- Callbacks ---

async def query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "back_to_cats":
        return await back_to_cats(update, context)
    
    if data.startswith("cat_"):
        cat_id = data.split('_')[1]
        conn = get_db_connection()
        ss = conn.execute("SELECT s.*, p.name as p_name FROM services s JOIN providers p ON s.provider_id = p.provider_id WHERE s.category_id = ? AND s.is_active = 1", (cat_id,)).fetchall()
        conn.close()
        if not ss: return await query.edit_message_text("لا توجد خدمات.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="back_to_cats")]]))
        kb = [[InlineKeyboardButton(f"{s['name']} - {s['p_name']}", callback_data=f"ser_{s['service_id']}")] for s in ss]
        kb.append([InlineKeyboardButton("🔙 عودة", callback_data="back_to_cats")])
        await query.edit_message_text("الخدمات المتاحة:", reply_markup=InlineKeyboardMarkup(kb))
        
    elif data.startswith("ser_"):
        ser_id = data.split('_')[1]
        conn = get_db_connection()
        s = conn.execute("SELECT s.*, p.name as p_name, p.city as p_city, p.phone as p_phone, p.whatsapp as p_wa FROM services s JOIN providers p ON s.provider_id = p.provider_id WHERE s.service_id = ?", (ser_id,)).fetchone()
        conn.close()
        text = f"🛠️ *{s['name']}*\n👤 مقدم الخدمة: {s['p_name']}\n📍 المدينة: {s['p_city']}\n💰 السعر: {s['price']} - {s['pricing_type']}\n\n📝 {s['description']}"
        kb = [[InlineKeyboardButton("📞 اتصال", url=f"tel:{s['p_phone']}"), InlineKeyboardButton("💬 واتساب", url=f"https://wa.me/{s['p_wa']}")],
              [InlineKeyboardButton("📅 طلب حجز", callback_data=f"book_{s['service_id']}")],
              [InlineKeyboardButton("🔙 عودة", callback_data=f"cat_{s['category_id']}")]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
        
    elif data.startswith("book_"):
        context.user_data['booking_service_id'] = data.split('_')[1]
        context.user_data['state'] = "BOOKING"
        await query.message.reply_text("اكتب تفاصيل طلبك:", reply_markup=ReplyKeyboardMarkup([["إلغاء ❌"]], resize_keyboard=True))

async def complete_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    ser_id = context.user_data['booking_service_id']
    conn = get_db_connection()
    s = conn.execute("SELECT s.*, p.user_id as p_tid FROM services s JOIN providers p ON s.provider_id = p.provider_id WHERE s.service_id = ?", (ser_id,)).fetchone()
    if s:
        try: await context.bot.send_message(chat_id=s['p_tid'], text=f"🔔 *طلب جديد!*\n\n👤 العميل: {update.effective_user.full_name}\n🛠️ الخدمة: {s['name']}\n📝 الرسالة: {text}", parse_mode='Markdown')
        except: pass
        await update.message.reply_text("✅ تم إرسال طلبك!", reply_markup=await get_main_keyboard(update.effective_user.id))
    conn.close()
    context.user_data.clear()

async def back_to_cats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    cats = conn.execute("SELECT * FROM categories ORDER BY display_order").fetchall()
    conn.close()
    kb = []
    for i in range(0, len(cats), 2):
        row = [InlineKeyboardButton(cats[i]['name'], callback_data=f"cat_{cats[i]['category_id']}")]
        if i+1 < len(cats): row.append(InlineKeyboardButton(cats[i+1]['name'], callback_data=f"cat_{cats[i+1]['category_id']}"))
        kb.append(row)
    await update.callback_query.edit_message_text("اختر التصنيف: 🔍", reply_markup=InlineKeyboardMarkup(kb))

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('id', get_user_id))
    app.add_handler(CallbackQueryHandler(query_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    
    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)
