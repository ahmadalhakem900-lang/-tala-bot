import os, sqlite3, threading, time, telebot
from telebot.types import InputPaidMediaVideo, InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7617377624
DB_FILE = "bot_database3.db"
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=4, skip_pending=True)
media_groups, media_lock, db_lock = {}, threading.Lock(), threading.Lock()

def init_db():
    with db_lock:
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, join_date DATETIME DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, first_name TEXT, amount INTEGER, charge_id TEXT, date DATETIME DEFAULT CURRENT_TIMESTAMP)')
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('video_price', '2000')")
        conn.commit(); conn.close()

def get_price():
    with db_lock:
        conn=sqlite3.connect(DB_FILE); c=conn.cursor(); c.execute("SELECT value FROM settings WHERE key='video_price'"); row=c.fetchone(); conn.close(); return int(row[0]) if row else 2000

def get_stats():
    with db_lock:
        conn=sqlite3.connect(DB_FILE); c=conn.cursor(); c.execute("SELECT COUNT(*) FROM users"); u=c.fetchone()[0]; c.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM purchases"); co,to=c.fetchone(); c.execute("SELECT first_name, username, amount, date FROM purchases ORDER BY id DESC LIMIT 5"); last=c.fetchall(); conn.close(); return u,co,to,last

init_db()

@bot.message_handler(commands=['admin','sales'])
def open_admin(m):
    if m.from_user.id!=ADMIN_ID: return
    u,co,to,last=get_stats()
    txt=f"💰 لوحة المبيعات\n\nالمستخدمين: {u}\nالمبيعات: {co}\nمجموع النجوم: {to} ⭐️\nالسعر الحالي: {get_price()} ⭐️\n"
    if last:
        txt+="\nآخر 5:\n"
        for fn,un,am,dt in last: txt+=f"- {fn} @{un or 'بدون'} - {am}⭐️\n"
    bot.send_message(m.chat.id,txt)

@bot.message_handler(commands=['start'])
def start(m): bot.reply_to(m,f"🎬 مرحبا! الفيديوهات مقابل {get_price()} ⭐️")

def delayed_send(gid, price):
    with media_lock:
        if gid in media_groups: d=media_groups.pop(gid); send_invoice(d['chat_id'],d['media_list'],d['caption'],price)

@bot.message_handler(content_types=['video'])
def hv(m):
    pr=get_price()
    if m.media_group_id:
        gid=m.media_group_id
        with media_lock:
            if gid not in media_groups: media_groups[gid]={'chat_id':m.chat.id,'media_list':[],'caption':None}; t=threading.Timer(1.5,delayed_send,args=[gid,pr]); t.start()
            media_groups[gid]['media_list'].append(InputPaidMediaVideo(media=m.video.file_id))
            if m.caption and not media_groups[gid]['caption']: media_groups[gid]['caption']=m.caption
    else: send_invoice(m.chat.id,[InputPaidMediaVideo(media=m.video.file_id)],m.caption or "",pr)

def send_invoice(cid, media, cap, price):
    try: bot.send_paid_media(chat_id=cid, star_count=price, media=media, caption=cap)
    except Exception as e:
        try: bot.send_message(ADMIN_ID,f"⚠️ فشل دفع ID: {cid}\n{e}")
        except: pass

@bot.pre_checkout_query_handler(func=lambda q: True)
def checkout(q): bot.answer_pre_checkout_query(q.id,ok=True)

@bot.message_handler(content_types=['successful_payment'])
def paid(m):
    u=m.from_user; p=m.successful_payment
    with db_lock:
        conn=sqlite3.connect(DB_FILE); c=conn.cursor(); c.execute('INSERT INTO purchases (user_id, username, first_name, amount, charge_id) VALUES (?,?,?,?,?)',(u.id,u.username,u.first_name,p.total_amount,p.telegram_payment_charge_id)); conn.commit(); conn.close()
    try: bot.send_message(ADMIN_ID,f"💰 شراء جديد!\n• {u.first_name}\n• @{u.username or 'بدون'}\n• ID: {u.id}\n• المبلغ: {p.total_amount} ⭐️")
    except: pass

if __name__=='__main__':
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except Exception as e: print(e); time.sleep(5)
