from telegram import Update
from telegram.ext import ContextTypes
from bot.keyboards import get_main_menu, MONTHS_BN_FULL, to_bn_number
from datetime import datetime

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user = update.effective_user
    now = datetime.now()
    month_name = MONTHS_BN_FULL[now.month]
    year = to_bn_number(now.year)
    today = to_bn_number(now.strftime('%d/%m/%y'))
    welcome_text = (
        f"স্বাগতম {user.first_name}! 👋\n\n"
        f"<b>পথিকবট</b> — মোটরসাইকেল লগশীট অটোমেশন সিস্টেম\n\n"
        f"চলতি মাস: <b>{month_name} {year}</b>\n"
        f"আজকের তারিখ: <b>{today}</b>\n\n"
        f"আপনার দৈনন্দিন ফিল্ড ট্যুর ও খরচ ট্র্যাক করুন এবং মাসিক রিপোর্ট তৈরি করুন।\n"
        f"নিচের মেনু থেকে আপনার পছন্দের অপশনটি নির্বাচন করুন:"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu(), parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command with detailed Bangla explanations."""
    help_text = (
        "📚 <b>কমান্ডগুলোর বিস্তারিত ব্যাখ্যা</b>\n\n"
        "• /start\n"
        "বট চালু করার পর প্রথমে এই কমান্ডটি দিন। এটি একটি স্বাগত বার্তা দেখাবে।\n\n"
        "• /newentry (➕ নতুন এন্ট্রি)\n"
        "নতুন কোনো এন্ট্রি যোগ করতে এটি ব্যবহার করুন। বট আপনাকে ধাপে ধাপে প্রশ্ন করবে:\n"
        "  – এন্ট্রির ধরন (ফিল্ড ট্যুর নাকি মাসিক মিটিং)\n"
        "  – তারিখ ও মাস\n"
        "  – মিটার রিডিং ও দূরত্ব (যোগ/গুণ করা যাবে, যেমন: <b>14+15</b>)\n"
        "  – পেট্রোল ও মোবাইল রিচার্জের তথ্য\n\n"
        "• /editentry (📝 এডিট)\n"
        "পুরানো কোনো এন্ট্রি এডিট করতে এটি ব্যবহার করুন।\n\n"
        "• /delentry (🗑 ডিলিট)\n"
        "ভুল করে কোনো এন্ট্রি যোগ করলে তা ডিলিট করতে এটি ব্যবহার করুন।\n\n"
        "• /cancel\n"
        "মাঝপথে কোনো কাজ বাতিল করতে এই কমান্ডটি দিন।\n\n"
        "• /listentries (📋 এন্ট্রি তালিকা)\n"
        "চলতি মাসের সব এন্ট্রি বিস্তারিত দেখতে এটি ব্যবহার করুন।\n\n"
        "• /summary (📊 সারসংক্ষেপ)\n"
        "চলতি মাসের মোট খরচ ও দূরত্বের হিসাব দেখতে এটি ব্যবহার করুন।\n\n"
        "• /months (📁 পুরানো মাস)\n"
        "পুরানো মাসের এন্ট্রি ও সারসংক্ষেপ দেখতে এটি ব্যবহার করুন।\n\n"
        "• /settings (⚙️ সেটিংস)\n"
        "পেট্রোলের দাম, DA রেট, মোবাইল খরচ — সব কনফিগারেশন দেখতে ও পরিবর্তন করতে এটি ব্যবহার করুন।\n\n"
        "• /generate (📄 রিপোর্ট তৈরি)\n"
        "চলতি মাসের জন্য অফিসিয়াল DOCX লগশীট রিপোর্ট তৈরি করতে এটি ব্যবহার করুন।"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(help_text, reply_markup=get_main_menu(), parse_mode='HTML')
    else:
        await update.message.reply_text(help_text, reply_markup=get_main_menu(), parse_mode='HTML')

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu button clicks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "main_menu":
        now = datetime.now()
        month_name = MONTHS_BN_FULL[now.month]
        year = to_bn_number(now.year)
        await query.edit_message_text(
            f"<b>মূল মেনু</b>\n"
            f"চলতি মাস: <b>{month_name} {year}</b>\n\n"
            f"আপনার পছন্দের অপশনটি নির্বাচন করুন:",
            reply_markup=get_main_menu(),
            parse_mode='HTML'
        )
