import sqlite3
import threading
import telebot
from telebot.types import InputPaidMediaVideo, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request

BOT_TOKEN = "8796423805:AAG8MFlxhZcc4YV4EL_aO4YgAUNyAqpt6Xs"
ADMIN_ID = 8831289833  
DB_FILE = "/tmp/database.db"  

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, join_date DATETIME DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('video_price', '2000')")
    conn.commit()
    conn.close()

def get_price():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='video_price'")
        row = cursor.fetchone()
        conn.close()
        return int(row[0]) if row else 2000
    except:
        return 2000

init_db()

@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@bot.message_handler(func=lambda message: message.from_user.id != ADMIN_ID, commands=['start'])
def block_public_users(message):
    bot.send_message(message.chat.id, "❌ عذراً، هذا البوت خاص ومغلق للعمليات الخلفية فقط.")

@bot.message_handler(commands=['admin'])
def open_admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    current_price = get_price()
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("⚙️ تغيير سعر الفيديو", callback_data="admin_set_price"))
    bot.send_message(message.chat.id, f"🛠 **لوحة التحكم**\n\n• السعر الحالي: `{current_price}` نجمة ⭐️", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(content_types=['video'])
def handle_video(message):
    if message.from_user.id != ADMIN_ID: return
    current_price = get_price()
    media_list = [InputPaidMediaVideo(media=message.video.file_id)]
    try:
        bot.send_paid_media(chat_id=message.chat.id, star_count=current_price, media=media_list, caption=message.caption if message.caption else "")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"⚠️ فشل التشفير: {str(e)}")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    user = message.from_user
    payment_info = message.successful_payment
    report_text = (
        f"💰 **تقرير مبيعات فوري ناجح**\n\n"
        f"• **المشتري:** {user.first_name}\n"
        f"• **المستخدم:** @{user.username if user.username else 'لا يوجد'}\n"
        f"• **المبلغ:** `{payment_info.total_amount}` نجمة ⭐️\n"
        f"✅ تمت العملية بنجاح."
    )
    bot.send_message(ADMIN_ID, report_text, parse_mode="Markdown")

@app.route('/')
def index():
    return "Bot is Running Successfully!", 200
