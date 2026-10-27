import sqlite3
import threading
import telebot
from telebot.types import InputPaidMediaVideo, InlineKeyboardMarkup, InlineKeyboardButton

# ==========================================
# الإعدادات الأساسية للبوت
# ==========================================
BOT_TOKEN = "8796423805:AAG8MFlxhZcc4YV4EL_aO4YgAUNyAqpt6Xs"
ADMIN_ID = 8831289833  
DB_FILE = "bot_database_new.db"  

# تفعيل المعالجة المتعددة لمنع تجميد البوت
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=4)

media_groups = {}
media_lock = threading.Lock()
db_lock = threading.Lock()

def init_db():
    """تهيئة قاعدة البيانات للبوت"""
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, join_date DATETIME DEFAULT CURRENT_TIMESTAMP)')
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('video_price', '2000')")
        conn.commit()
        conn.close()

def get_price():
    """جلب السعر الحالي للفيديو"""
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='video_price'")
        row = cursor.fetchone()
        conn.close()
        return int(row[0]) if row else 2000

def set_price(new_price):
    """تحديث سعر الفيديو"""
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET value=? WHERE key='video_price'", (str(new_price),))
        conn.commit()
        conn.close()

def register_user(user_id, username, first_name):
    """تسجيل بيانات المستخدم"""
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name) 
            VALUES (?, ?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET username=?, first_name=?
        ''', (user_id, username, first_name, username, first_name))
        conn.commit()
        conn.close()

def get_stats():
    """إحصائيات المستخدمين"""
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        row = cursor.fetchone()
        return int(row[0]) if row else 0

init_db()

def admin_keyboard():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📊 عرض الإحصائيات", callback_data="admin_stats"))
    markup.row(InlineKeyboardButton("⚙️ تغيير سعر الفيديو", callback_data="admin_set_price"))
    return markup

@bot.message_handler(commands=['admin'])
def open_admin_panel(message):
    if message.from_user.id != ADMIN_ID: 
        return
    current_price = get_price()
    bot.send_message(
        message.chat.id, 
        f"🛠 **لوحة التحكم - البوت الجديد**\n\n• السعر الحالي للفيديو: `{current_price}` نجمة ⭐️", 
        parse_mode="Markdown", 
        reply_markup=admin_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_callbacks(call):
    if call.from_user.id != ADMIN_ID: 
        return
    
    if call.data == "admin_stats":
        total_users = get_stats()
        stats_text = f"📊 إجمالي المستخدمين النشطين: `{total_users}`"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ عودة", callback_data="admin_menu"))
        bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        
    elif call.data == "admin_set_price":
        msg = bot.send_message(call.message.chat.id, "✏️ **أرسل السعر الجديد (أرقام فقط):**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, save_new_price)
        
    elif call.data == "admin_menu":
        current_price = get_price()
        bot.edit_message_text(f"🛠 **لوحة التحكم**\n\n• السعر الحالي: `{current_price}` نجمة ⭐️", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=admin_keyboard())

def save_new_price(message):
    if message.from_user.id != ADMIN_ID: 
        return
    try:
        new_price = int(message.text.strip())
        if new_price <= 0: 
            raise ValueError
        set_price(new_price)
        bot.send_message(message.chat.id, f"✅ تم تحديث السعر إلى `{new_price}` نجمة ⭐️.", parse_mode="Markdown", reply_markup=admin_keyboard())
    except:
        bot.send_message(message.chat.id, "❌ خطأ في الإدخال! أرسل رقماً موجباً صحيحاً.", parse_mode="Markdown", reply_markup=admin_keyboard())

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    register_user(user.id, user.username, user.first_name)
    current_price = get_price()
    bot.reply_to(message, f"🎬 **أهلاً بك!**\n\nالسعر الحالي للفيديوهات: `{current_price}` نجمة ⭐️.")

def delayed_send_group(group_id, current_price, caption_text):
    with media_lock:
        if group_id in media_groups:
            data = media_groups.pop(group_id)
            send_invoice(data['chat_id'], data['media_list'], data['caption'], current_price, caption_text)

@bot.message_handler(content_types=['video'])
def handle_video(message):
    user = message.from_user
    register_user(user.id, user.username, user.first_name)
    current_price = get_price()
    video_caption = message.caption if message.caption else "فيديو بدون عنوان"
    
    if message.media_group_id:
        group_id = message.media_group_id
        with media_lock:
            if group_id not in media_groups:
                media_groups[group_id] = {
                    'chat_id': message.chat.id, 
                    'media_list': [], 
                    'caption': None,
                    'timer': None
                }
                t = threading.Timer(1.5, delayed_send_group, args=[group_id, current_price, video_caption])
                media_groups[group_id]['timer'] = t
                t.start()
                
            media_groups[group_id]['media_list'].append(InputPaidMediaVideo(media=message.video.file_id))
            if message.caption and not media_groups[group_id]['caption']:
                media_groups[group_id]['caption'] = message.caption
    else:
        media_list = [InputPaidMediaVideo(media=message.video.file_id)]
        send_invoice(message.chat.id, media_list, message.caption if message.caption else "", current_price, video_caption)

def send_invoice(chat_id, media_list, caption, price, video_title):
    try:
        bot.send_paid_media(chat_id=chat_id, star_count=price, media=media_list, caption=caption if caption else "")
    except Exception as e:
        report_failed_payment(chat_id, f"فشل الإرسال: {str(e)}", video_title)

# ==========================================
# معالجة المدفوعات والطلبات والتقارير الفورية
# ==========================================

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    try:
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    except Exception as e:
        report_failed_payment(pre_checkout_query.from_user.id, f"خطأ دفع: {str(e)}", "عملية دفع معلقة")

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    user = message.from_user
    payment_info = message.successful_payment
    stars_amount = payment_info.total_amount if payment_info else "غير معروف"
    
    # تسجيل بيانات المستخدم للتأكد
    register_user(user.id, user.username, user.first_name)
    
    # تقرير فوري يصلك على حسابك عند نجاح الشراء
    report_text = (
        f"💰 **تمت عملية الشراء بنجاح!**\n\n"
        f"👤 **المشتري:** {user.first_name}\n"
        f"🆔 **الآي دي:** `{user.id}`\n"
        f"🔗 **المعرف:** @{user.username if user.username else 'لا يوجد'}\n"
        f"⭐ **المبلغ المدفوع:** `{stars_amount}` نجمة 🌟\n"
        f"📊 **الحالة:** نجحت العملية وتم بيع المحتوى للمستخدم."
    )
    try:
        bot.send_message(ADMIN_ID, report_text, parse_mode="Markdown")
    except Exception as err:
        print(f"Error sending report: {err}")

def report_failed_payment(user_id, reason, video_title="محتوى غير معروف"):
    # تقرير فوري يصلك عند فشل عملية الشراء
    fail_text = (
        f"⚠️ **فشلت عملية الشراء!**\n\n"
        f"🆔 **آي دي المستخدم:** `{user_id}`\n"
        f"❌ **السبب:** {reason}\n"
        f"🎥 **المحتوى المستهدف:** {video_title}"
    )
    try:
        bot.send_message(ADMIN_ID, fail_text, parse_mode="Markdown")
    except:
        pass

if __name__ == '__main__':
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)
