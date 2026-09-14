import sqlite3
import html
import re
import os
import sys
import threading
import urllib.parse
import http.server
import socketserver
import warnings
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Force unbuffered terminal output for instant Render logging
sys.stdout.reconfigure(line_buffering=True)
warnings.filterwarnings("ignore", category=UserWarning, module="telegram.ext")

# --- CREDENTIALS & CONSTANTS ---
BOT_TOKEN = "8732355050:AAGGg1dvD0ZAGlEUlZ5tEdVg6WreP0p9WMY"
ADMIN_IDS = [7303896375]
DEFAULT_UPI_ID = "royh4x@ybl"
ADMIN_PASSWORD = "RoyAdmin@3324*!!"

# --- RENDER PORT BINDING (LIGHTWEIGHT SOCKET SERVER) ---
class RenderHealthServer(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ROY x CHEATS Bot Online 24/7.")

    def log_message(self, format, *args):
        return  # Suppress HTTP poll noise in Render logs

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), RenderHealthServer) as httpd:
        print(f"[SERVER] Render health check bound successfully to port {port}", flush=True)
        httpd.serve_forever()

# Conversation States
(
    WAITING_UTR,
    EDIT_START_TEXT,
    EDIT_SUPPORT_TEXT,
    ADMIN_ADD_CAT,
    ADMIN_PROD_CAT,
    ADMIN_PROD_NAME,
    ADMIN_PROD_PRICE,
    ADMIN_STOCK_PROD,
    ADMIN_STOCK_KEYS,
    ADMIN_SET_QR,
    ADMIN_SET_UPI,
    ADMIN_BROADCAST,
    ADMIN_UPLOAD_FILE_TITLE,
    ADMIN_UPLOAD_FILE_DOC,
    ADMIN_PASSWORD_LOGIN,
) = range(15)

def get_db():
    return sqlite3.connect("store.db")

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        referred_by INTEGER DEFAULT NULL,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        name TEXT,
        price REAL,
        FOREIGN KEY(category_id) REFERENCES categories(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        data TEXT,
        is_used INTEGER DEFAULT 0,
        FOREIGN KEY(product_id) REFERENCES products(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        utr TEXT UNIQUE,
        status TEXT DEFAULT 'PENDING'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        file_id TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS admin_auth (
        user_id INTEGER PRIMARY KEY,
        auth_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")

    default_welcome = (
        "🤖 ━━━━ **ROY x CHEATS** ━━━━ 🤖\n\n"
        "👋 Welcome back, **{name}**!\n\n"
        "Choose an option below:"
    )
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('start_text', ?)", (default_welcome,))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('support_text', '📩 Contact support: @YourAdminUsername')")
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('upi_id', ?)", (DEFAULT_UPI_ID,))
    conn.commit()
    conn.close()

def is_admin_authenticated(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM admin_auth WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row)

def build_main_menu():
    keyboard = [
        [InlineKeyboardButton("💎 Shop Now", callback_data="open_shop")],
        [
            InlineKeyboardButton("📜 My Orders", callback_data="menu_orders"),
            InlineKeyboardButton("👑 Profile", callback_data="menu_profile"),
        ],
        [
            InlineKeyboardButton("💳 Add Balance", callback_data="menu_balance"),
            InlineKeyboardButton("🤝 Referral", callback_data="menu_referral"),
        ],
        [InlineKeyboardButton("🍀 Lucky Spin", callback_data="menu_spin")],
        [InlineKeyboardButton("⚡ Reseller Dashboard", callback_data="menu_reseller")],
        [InlineKeyboardButton("📁 Download Files", callback_data="menu_files")],
        [InlineKeyboardButton("💬 Support", callback_data="menu_support")],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- USER & CUSTOMER SHOP FLOW ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    raw_name = user.first_name or user.username or "Customer"
    safe_name = html.escape(raw_name)

    conn = get_db()
    c = conn.cursor()

    referred_by = None
    if context.args and len(context.args) > 0 and context.args[0].startswith("ref_"):
        try:
            ref_id = int(context.args[0].split("_")[1])
            if ref_id != user.id:
                referred_by = ref_id
        except ValueError:
            pass

    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, first_name, referred_by) VALUES (?, ?, ?)", (user.id, raw_name, referred_by))
        conn.commit()

    c.execute("SELECT value FROM settings WHERE key = 'start_text'")
    row = c.fetchone()
    raw_template = row[0] if row else "👋 Welcome back, **{name}**!"
    conn.close()

    text = raw_template.replace("{name}", safe_name)

    try:
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=build_main_menu(), parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(text, reply_markup=build_main_menu(), parse_mode=ParseMode.HTML)
    except Exception:
        if update.message:
            await update.message.reply_text(f"👋 Welcome {safe_name}!\n\nChoose an option below:", reply_markup=build_main_menu())

async def open_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name FROM categories")
    cats = c.fetchall()
    conn.close()

    if not cats:
        await query.edit_message_text(
            "⚠️ No categories available yet.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]]),
        )
        return

    buttons = [[InlineKeyboardButton(f"📁 {name}", callback_data=f"cat_{cid}")] for cid, name in cats]
    buttons.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")])

    await query.edit_message_text(
        "📦 **Select a Category:**",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML,
    )

async def category_clicked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split("_")[1])

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, price FROM products WHERE category_id = ?", (cat_id,))
    prods = c.fetchall()

    buttons = []
    for pid, name, price in prods:
        c.execute("SELECT COUNT(*) FROM stock WHERE product_id = ? AND is_used = 0", (pid,))
        count = c.fetchone()[0]
        buttons.append([InlineKeyboardButton(f"{name} — ₹{price} (Stock: {count})", callback_data=f"prod_{pid}")])

    buttons.append([InlineKeyboardButton("⬅️ Back to Categories", callback_data="open_shop")])
    conn.close()

    if not prods:
        await query.edit_message_text(
            "No products found in this category.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="open_shop")]]),
        )
        return

    await query.edit_message_text(
        "🛒 **Choose a Product:**",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML,
    )

async def product_clicked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[1])

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, price, category_id FROM products WHERE id = ?", (prod_id,))
    prod = c.fetchone()
    c.execute("SELECT COUNT(*) FROM stock WHERE product_id = ? AND is_used = 0", (prod_id,))
    stock_count = c.fetchone()[0]
    conn.close()

    if not prod:
        await query.edit_message_text("Product not found.")
        return

    name, price, cat_id = prod
    text = (
        f"🏷️ **Item:** {name}\n"
        f"💰 **Price:** ₹{price}\n"
        f"📊 **Stock Left:** {stock_count}\n\n"
    )

    if stock_count <= 0:
        text += "❌ **Currently Out of Stock!**"
        buttons = [[InlineKeyboardButton("⬅️ Back", callback_data=f"cat_{cat_id}")]]
    else:
        buttons = [
            [InlineKeyboardButton("💳 Buy Now", callback_data=f"buy_{prod_id}")],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"cat_{cat_id}")],
        ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def buy_clicked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[1])
    context.user_data["checkout_prod_id"] = prod_id

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, price FROM products WHERE id = ?", (prod_id,))
    p_name, price = c.fetchone()
    c.execute("SELECT value FROM settings WHERE key = 'qr_file_id'")
    qr_row = c.fetchone()
    c.execute("SELECT value FROM settings WHERE key = 'upi_id'")
    upi_row = c.fetchone()
    conn.close()

    qr_file_id = qr_row[0] if qr_row else None
    upi_id = upi_row[0] if upi_row else DEFAULT_UPI_ID

    encoded_name = urllib.parse.quote("ROY x CHEATS")
    encoded_note = urllib.parse.quote(f"Buy_{p_name[:15]}")
    upi_url = f"upi://pay?pa={upi_id}&pn={encoded_name}&am={price}&cu=INR&tn={encoded_note}"

    caption = (
        f"🧾 **Order for:** {p_name}\n"
        f"💵 **Amount to Pay:** ₹{price}\n"
        f"🆔 **UPI ID:** `{upi_id}`\n\n"
        "**Instructions:**\n"
        "1. Scan the QR code or tap the **Pay via UPI App** button below.\n"
        "2. Complete the payment.\n"
        "3. Reply with your **12-digit UTR / Reference Number**.\n\n"
        "*Type /cancel anytime to abort.*"
    )

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("📲 Pay via UPI App (1-Tap)", url=upi_url)]])

    if qr_file_id:
        await query.message.reply_photo(photo=qr_file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await query.message.reply_text(f"⚠️ *[QR Code Not Uploaded]*\n\n{caption}", parse_mode=ParseMode.HTML, reply_markup=markup)

    return WAITING_UTR

async def handle_utr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    utr = update.message.text.strip()
    prod_id = context.user_data.get("checkout_prod_id")
    user = update.effective_user

    if not re.match(r"^\d{12}$", utr):
        await update.message.reply_text(
            "❌ **Invalid UTR Format!**\n\n"
            "A standard UPI UTR / Reference ID consists of **exactly 12 digits** (e.g. `412356789012`).\n"
            "Please check your UPI app and reply with the correct 12-digit number:",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_UTR

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM orders WHERE utr = ?", (utr,))
    if c.fetchone():
        conn.close()
        await update.message.reply_text(
            "⚠️ **Duplicate UTR Detected!**\n\n"
            "This Reference ID has already been registered for another order.",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_UTR

    c.execute("SELECT name, price FROM products WHERE id = ?", (prod_id,))
    p_name, price = c.fetchone()
    c.execute("INSERT INTO orders (user_id, product_id, utr) VALUES (?, ?, ?)", (user.id, prod_id, utr))
    order_id = c.lastrowid
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ **UTR #{utr} Received!**\n"
        f"Order ID: `#{order_id}`\n"
        "Your payment is under review. Your key will be sent automatically here once verified.",
        parse_mode=ParseMode.HTML,
    )

    admin_buttons = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"adm_app_{order_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"adm_rej_{order_id}"),
        ]
    ]
    admin_text = (
        f"🔔 **New Order Payment Verification!**\n\n"
        f"• **Order ID:** `#{order_id}`\n"
        f"• **User:** {user.first_name} (`{user.id}`)\n"
        f"• **Item:** {p_name}\n"
        f"• **Price:** ₹{price}\n"
        f"• **Submitted UTR:** `{utr}`"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                reply_markup=InlineKeyboardMarkup(admin_buttons),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    return ConversationHandler.END

async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id not in ADMIN_IDS:
        return

    action, order_id = query.data.split("_")[1], int(query.data.split("_")[2])
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, product_id, status FROM orders WHERE id = ?", (order_id,))
    order = c.fetchone()

    if not order or order[2] != "PENDING":
        await query.edit_message_text(f"Order #{order_id} has already been resolved.")
        conn.close()
        return

    user_id, prod_id, _ = order

    if action == "app":
        c.execute("SELECT id, data FROM stock WHERE product_id = ? AND is_used = 0 LIMIT 1", (prod_id,))
        stock_item = c.fetchone()

        if not stock_item:
            await query.edit_message_text(f"⚠️ Stock empty for Order #{order_id}! Please upload stock first.")
            conn.close()
            return

        stock_id, stock_data = stock_item
        c.execute("UPDATE stock SET is_used = 1 WHERE id = ?", (stock_id,))
        c.execute("UPDATE orders SET status = 'APPROVED' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()

        delivery_text = (
            f"🎉 **Payment Verified!**\n\n"
            f"**Order ID:** `#{order_id}`\n"
            f"**Your Account / Key Details:**\n"
            f"`{stock_data}`\n\n"
            "Thank you for shopping at **ROY x CHEATS**!"
        )
        await context.bot.send_message(chat_id=user_id, text=delivery_text, parse_mode=ParseMode.HTML)
        await query.edit_message_text(f"✅ Order #{order_id} approved and stock delivered.")

    elif action == "rej":
        c.execute("UPDATE orders SET status = 'REJECTED' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()

        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ **Payment Rejected** for Order `#{order_id}`.\nPlease check your UTR or contact support.",
            parse_mode=ParseMode.HTML,
        )
        await query.edit_message_text(f"❌ Order #{order_id} rejected.")

# --- OTHER MENU MODULES ---

async def generic_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user
    back_btn = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")]]

    if data == "menu_orders":
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT o.id, p.name, o.status FROM orders o
                     JOIN products p ON o.product_id = p.id
                     WHERE o.user_id = ? ORDER BY o.id DESC LIMIT 5""", (user.id,))
        rows = c.fetchall()
        conn.close()

        if not rows:
            text = "📜 **My Orders**\n\nYou haven't made any purchases yet."
        else:
            text = "📜 **Recent Orders:**\n\n" + "\n".join([f"• #{oid} | {pname} | **{status}**" for oid, pname, status in rows])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(back_btn), parse_mode=ParseMode.HTML)

    elif data == "menu_profile":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = 'APPROVED'", (user.id,))
        total_bought = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user.id,))
        total_refs = c.fetchone()[0]
        conn.close()

        text = (
            f"👑 **User Profile**\n\n"
            f"• **Name:** {html.escape(user.first_name or 'Customer')}\n"
            f"• **Telegram ID:** `{user.id}`\n"
            f"• **Total Purchases:** {total_bought}\n"
            f"• **Total Referrals:** {total_refs}\n"
            f"• **Wallet Balance:** ₹0.00"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(back_btn), parse_mode=ParseMode.HTML)

    elif data == "menu_referral":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user.id}"
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user.id,))
        total_refs = c.fetchone()[0]
        conn.close()

        text = (
            f"🤝 **Invite & Earn Program**\n\n"
            f"Share your referral link with friends:\n"
            f"🔗 `{ref_link}`\n\n"
            f"• **Total Friends Invited:** {total_refs}"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(back_btn), parse_mode=ParseMode.HTML)

    elif data == "menu_files":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, title FROM files")
        file_list = c.fetchall()
        conn.close()

        if not file_list:
            await query.edit_message_text(
                "📁 **Download Files**\n\nNo downloads are available right now. Check back later!",
                reply_markup=InlineKeyboardMarkup(back_btn),
                parse_mode=ParseMode.HTML,
            )
            return

        btns = [[InlineKeyboardButton(f"📥 {ftitle}", callback_data=f"dl_{fid}")] for fid, ftitle in file_list]
        btns.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_home")])
        await query.edit_message_text(
            "📁 **Select a file to download:**",
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode=ParseMode.HTML,
        )

    elif data == "menu_support":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'support_text'")
        supp = c.fetchone()[0]
        conn.close()
        await query.edit_message_text(supp, reply_markup=InlineKeyboardMarkup(back_btn), parse_mode=ParseMode.HTML)

    else:
        label = data.replace("menu_", "").capitalize()
        await query.edit_message_text(
            f"✨ **{label}**\n\nFeature currently undergoing maintenance. Stay tuned!",
            reply_markup=InlineKeyboardMarkup(back_btn),
            parse_mode=ParseMode.HTML,
        )

async def handle_file_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    file_id_db = int(query.data.split("_")[1])

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT title, file_id FROM files WHERE id = ?", (file_id_db,))
    row = c.fetchone()
    conn.close()

    if row:
        title, file_tg_id = row
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=file_tg_id,
            caption=f"📦 **{title}**\nDownloaded via **ROY x CHEATS**",
            parse_mode=ParseMode.HTML,
        )

# --- PASSWORD-BASED ADMIN GATE ---

async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        return ConversationHandler.END

    if is_admin_authenticated(user_id):
        await show_admin_dashboard(update, context)
        return ConversationHandler.END

    await update.message.reply_text(
        "🔐 **Admin Control Panel Protected**\n\n"
        "Please enter the **Admin Password** to unlock:",
        parse_mode=ParseMode.HTML,
    )
    return ADMIN_PASSWORD_LOGIN

async def handle_password_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entered_pass = update.message.text.strip()
    user_id = update.effective_user.id

    if entered_pass == ADMIN_PASSWORD:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO admin_auth (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()

        await update.message.reply_text("✅ **Access Granted!** Welcome Admin.", parse_mode=ParseMode.HTML)
        await show_admin_dashboard(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ **Incorrect Password!**\n\nPlease enter the correct Admin Password (or /cancel):",
            parse_mode=ParseMode.HTML,
        )
        return ADMIN_PASSWORD_LOGIN

async def show_admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("➕ Add Category", callback_data="adm_add_cat"), InlineKeyboardButton("🗑️ Delete Category", callback_data="adm_del_cat_list")],
        [InlineKeyboardButton("➕ Add Product", callback_data="adm_add_prod"), InlineKeyboardButton("🗑️ Delete Product", callback_data="adm_del_prod_list")],
        [InlineKeyboardButton("🔑 Add Stock / Keys", callback_data="adm_add_stock"), InlineKeyboardButton("📊 View Inventory", callback_data="adm_view_inventory")],
        [InlineKeyboardButton("🖼️ Set Payment QR", callback_data="adm_set_qr"), InlineKeyboardButton("🆔 Set UPI ID", callback_data="adm_set_upi")],
        [InlineKeyboardButton("📤 Upload Client/APK", callback_data="adm_upload_file"), InlineKeyboardButton("📢 Broadcast Message", callback_data="adm_broadcast")],
        [InlineKeyboardButton("✏️ Edit Welcome Text", callback_data="adm_edit_text"), InlineKeyboardButton("✏️ Edit Support Text", callback_data="adm_edit_support")],
    ]
    text = "⚙️ **ROY x CHEATS — Master Admin Dashboard**\n\nSelect an option to manage your store:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

# --- ADMIN ACTIONS & FLOWS ---

async def adm_add_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, price FROM products")
    prods = c.fetchall()
    conn.close()

    if not prods:
        await query.message.reply_text(
            "⚠️ **No products exist in the store yet!**\n\nPlease use **➕ Add Product** first before loading stock.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_home")]])
        )
        return ConversationHandler.END

    btns = [[InlineKeyboardButton(f"📦 {name} (₹{price})", callback_data=f"ask_{pid}")] for pid, name, price in prods]
    btns.append([InlineKeyboardButton("⬅️ Cancel", callback_data="adm_home")])

    await query.message.reply_text(
        "🔑 **Select the product you want to add stock for:**",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.HTML
    )
    return ADMIN_STOCK_PROD

async def adm_stock_prod_picked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "adm_home":
        await show_admin_dashboard(update, context)
        return ConversationHandler.END

    prod_id = int(query.data.split("_")[1])
    context.user_data["stock_prod_id"] = prod_id

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM products WHERE id = ?", (prod_id,))
    prod_row = c.fetchone()
    conn.close()

    pname = prod_row[0] if prod_row else "Selected Product"

    await query.message.reply_text(
        f"✍️ **Adding Stock for:** `{pname}`\n\n"
        "Send or paste your stock items below.\n"
        "**Note:** You can send 1 key, or multiple keys/accounts separated by new lines.\n\n"
        "*Type /cancel to abort.*",
        parse_mode=ParseMode.HTML
    )
    return ADMIN_STOCK_KEYS

async def adm_stock_keys_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()
    items = [line.strip() for line in raw_text.split("\n") if line.strip()]
    pid = context.user_data.get("stock_prod_id")

    if not pid:
        await update.message.reply_text("Session timed out. Please try adding stock again from /admin.")
        return ConversationHandler.END

    conn = get_db()
    c = conn.cursor()
    for item in items:
        c.execute("INSERT INTO stock (product_id, data) VALUES (?, ?)", (pid, item))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ **Stock Updated!**\n\nLoaded **{len(items)}** key(s)/account(s) into inventory.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_home")]])
    )
    return ConversationHandler.END

async def adm_set_qr_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📸 **Send your UPI QR Code image:**\n\n"
        "You can send it as a regular photo, screenshot, or uncompressed file image.\n"
        "*(Make sure the view-once timer icon is OFF).*\n\n"
        "*Type /cancel to abort.*",
        parse_mode=ParseMode.HTML
    )
    return ADMIN_SET_QR

async def adm_set_qr_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    fid = None

    if msg.photo:
        fid = msg.photo[-1].file_id
    elif msg.document and (msg.document.mime_type or "").startswith("image/"):
        fid = msg.document.file_id

    if not fid:
        await msg.reply_text("⚠️ That doesn't appear to be an image. Please send a valid photo or screenshot of your QR code:")
        return ADMIN_SET_QR

    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('qr_file_id', ?)", (fid,))
    conn.commit()
    conn.close()

    await msg.reply_text(
        "✅ **Payment QR Code Saved Successfully!**\n\nBuyers will now see this QR when tapping 'Buy Now'.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_home")]])
    )
    return ConversationHandler.END

async def adm_view_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT p.name, p.price, c.name,
               (SELECT COUNT(*) FROM stock s WHERE s.product_id = p.id AND s.is_used = 0) AS stock_count
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
    """)
    rows = c.fetchall()
    conn.close()

    if not rows:
        text = "📊 **Inventory Status:**\n\nNo products created yet."
    else:
        lines = ["📊 **Live Inventory Status:**\n"]
        for name, price, cat_name, stock in rows:
            warning = " ⚠️ **LOW STOCK**" if stock <= 2 else ""
            lines.append(f"• **{name}** ({cat_name or 'Uncategorized'})\n  Price: ₹{price} | **Available: {stock}**{warning}\n")
        text = "\n".join(lines)

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_home")]]),
        parse_mode=ParseMode.HTML,
    )

async def adm_set_upi_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send your new UPI ID (Current default: `royh4x@ybl`):", parse_mode=ParseMode.HTML)
    return ADMIN_SET_UPI

async def adm_set_upi_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upi_id = update.message.text.strip()
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('upi_id', ?)", (upi_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ UPI ID set to: `{upi_id}`", parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def adm_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send the announcement message to broadcast to all registered bot users:")
    return ADMIN_BROADCAST

async def adm_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()

    success, failed = 0, 0
    await update.message.reply_text(f"📢 Starting broadcast to {len(users)} users...")

    for (uid,) in users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"🔔 **ANNOUNCEMENT:**\n\n{msg_text}",
                parse_mode=ParseMode.HTML,
            )
            success += 1
        except Exception:
            failed += 1

    await update.message.reply_text(f"✅ **Broadcast Completed!**\n\n• Delivered: {success}\n• Failed (Blocked): {failed}", parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def adm_upload_file_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Enter a display title for the file (e.g. `DRIP CLIENT APK MOD v2.0`):", parse_mode=ParseMode.HTML)
    return ADMIN_UPLOAD_FILE_TITLE

async def adm_upload_file_title_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["upload_title"] = update.message.text.strip()
    await update.message.reply_text("Now send the document/APK file:")
    return ADMIN_UPLOAD_FILE_DOC

async def adm_upload_file_doc_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("Please upload the file as a Document.")
        return ADMIN_UPLOAD_FILE_DOC

    file_tg_id = update.message.document.file_id
    title = context.user_data["upload_title"]

    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO files (title, file_id) VALUES (?, ?)", (title, file_tg_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ File **{title}** uploaded! Available via '📁 Download Files'.", parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def adm_del_cat_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name FROM categories")
    cats = c.fetchall()
    conn.close()

    if not cats:
        await query.edit_message_text("⚠️ No categories found to delete.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_home")]]))
        return

    buttons = [[InlineKeyboardButton(f"❌ Delete: {name}", callback_data=f"docat_{cid}")] for cid, name in cats]
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="adm_home")])
    await query.edit_message_text("Select category to delete:\n*(All products inside will be deleted)*", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def adm_delete_category_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split("_")[1])

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM stock WHERE product_id IN (SELECT id FROM products WHERE category_id = ?)", (cat_id,))
    c.execute("DELETE FROM products WHERE category_id = ?", (cat_id,))
    c.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()

    await query.edit_message_text("✅ Category and associated products deleted.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_home")]]))

async def adm_del_prod_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, price FROM products")
    prods = c.fetchall()
    conn.close()

    if not prods:
        await query.edit_message_text("⚠️ No products found to delete.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_home")]]))
        return

    buttons = [[InlineKeyboardButton(f"❌ Delete: {name} (₹{price})", callback_data=f"doprod_{pid}")] for pid, name in prods]
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="adm_home")])
    await query.edit_message_text("Select product to delete:", reply_markup=InlineKeyboardMarkup(buttons))

async def adm_delete_product_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[1])

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM stock WHERE product_id = ?", (prod_id,))
    c.execute("DELETE FROM products WHERE id = ?", (prod_id,))
    conn.commit()
    conn.close()

    await query.edit_message_text("✅ Product and remaining stock deleted.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin", callback_data="adm_home")]]))

async def adm_edit_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send the new Welcome Message (Use `{name}` for buyer name):", parse_mode=ParseMode.HTML)
    return EDIT_START_TEXT

async def adm_edit_text_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_text = update.message.text
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('start_text', ?)", (new_text,))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Welcome message saved! Run /start to preview.", parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def adm_edit_support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send the new support info or contact link:")
    return EDIT_SUPPORT_TEXT

async def adm_edit_support_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_text = update.message.text
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('support_text', ?)", (new_text,))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Support message saved.", parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def adm_add_cat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Send category name:")
    return ADMIN_ADD_CAT

async def adm_add_cat_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        await update.message.reply_text(f"✅ Category **{name}** added!", parse_mode=ParseMode.HTML)
    except sqlite3.IntegrityError:
        await update.message.reply_text("⚠️ That category already exists.")
    finally:
        conn.close()
    return ConversationHandler.END

async def adm_add_prod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name FROM categories")
    cats = c.fetchall()
    conn.close()

    if not cats:
        await query.message.reply_text("Please create at least one category first.")
        return ConversationHandler.END

    btns = [[InlineKeyboardButton(name, callback_data=f"apc_{cid}")] for cid, name in cats]
    await query.message.reply_text("Select category:", reply_markup=InlineKeyboardMarkup(btns))
    return ADMIN_PROD_CAT

async def adm_prod_cat_picked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["new_prod_cat"] = int(query.data.split("_")[1])
    await query.message.reply_text("Send product title:")
    return ADMIN_PROD_NAME

async def adm_prod_name_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_prod_name"] = update.message.text.strip()
    await update.message.reply_text("Send price in ₹ (e.g. 199):")
    return ADMIN_PROD_PRICE

async def adm_prod_price_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Invalid numerical value. Send price again:")
        return ADMIN_PROD_PRICE

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO products (category_id, name, price) VALUES (?, ?, ?)",
        (context.user_data["new_prod_cat"], context.user_data["new_prod_name"], price),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Product added successfully!", parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation canceled.")
    return ConversationHandler.END

def main():
    print("[INIT] Setting up local database...", flush=True)
    init_db()

    # Launch daemon socket server for Render port checks
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    print("[INIT] Initializing Telegram Application...", flush=True)
    app = Application.builder().token(BOT_TOKEN).build()

    # 1. Admin Password Login Flow
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("admin", admin_entry)],
        states={
            ADMIN_PASSWORD_LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password_login)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # 2. Add Stock Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_add_stock_start, pattern="^adm_add_stock$")],
        states={
            ADMIN_STOCK_PROD: [CallbackQueryHandler(adm_stock_prod_picked, pattern=r"^(ask_\d+|adm_home)$")],
            ADMIN_STOCK_KEYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_stock_keys_entered)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # 3. Set QR Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_set_qr_start, pattern="^adm_set_qr$")],
        states={
            ADMIN_SET_QR: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, adm_set_qr_save)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # 4. Customer Checkout Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_clicked, pattern=r"^buy_\d+$")],
        states={WAITING_UTR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_utr)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # 5. Set UPI ID Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_set_upi_start, pattern="^adm_set_upi$")],
        states={ADMIN_SET_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_set_upi_save)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # 6. Broadcast Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_broadcast_start, pattern="^adm_broadcast$")],
        states={ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_broadcast_send)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # 7. Upload File Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_upload_file_start, pattern="^adm_upload_file$")],
        states={
            ADMIN_UPLOAD_FILE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_upload_file_title_entered)],
            ADMIN_UPLOAD_FILE_DOC: [MessageHandler(filters.Document.ALL, adm_upload_file_doc_entered)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # 8. Edit Welcome Text Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_edit_text_start, pattern="^adm_edit_text$")],
        states={EDIT_START_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_edit_text_save)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # 9. Edit Support Text Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_edit_support_start, pattern="^adm_edit_support$")],
        states={EDIT_SUPPORT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_edit_support_save)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # 10. Add Category Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_add_cat_start, pattern="^adm_add_cat$")],
        states={ADMIN_ADD_CAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_cat_save)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # 11. Add Product Flow
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_add_prod_start, pattern="^adm_add_prod$")],
        states={
            ADMIN_PROD_CAT: [CallbackQueryHandler(adm_prod_cat_picked, pattern=r"^apc_\d+$")],
            ADMIN_PROD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_prod_name_entered)],
            ADMIN_PROD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_prod_price_entered)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # Navigation & Core Action Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_admin_dashboard, pattern="^adm_home$"))
    app.add_handler(CallbackQueryHandler(adm_view_inventory, pattern="^adm_view_inventory$"))
    app.add_handler(CallbackQueryHandler(adm_del_cat_list, pattern="^adm_del_cat_list$"))
    app.add_handler(CallbackQueryHandler(adm_delete_category_action, pattern=r"^docat_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_del_prod_list, pattern="^adm_del_prod_list$"))
    app.add_handler(CallbackQueryHandler(adm_delete_product_action, pattern=r"^doprod_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_file_download, pattern=r"^dl_\d+$"))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(open_shop, pattern="^open_shop$"))
    app.add_handler(CallbackQueryHandler(category_clicked, pattern=r"^cat_\d+$"))
    app.add_handler(CallbackQueryHandler(product_clicked, pattern=r"^prod_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_admin_action, pattern=r"^adm_(app|rej)_\d+$"))
    app.add_handler(CallbackQueryHandler(generic_menu_handler, pattern=r"^menu_"))

    print("[SUCCESS] Bot polling started for ROY x CHEATS under Password Protection!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()