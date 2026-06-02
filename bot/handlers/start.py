from telegram import Update
from telegram.ext import ContextTypes
from bot.keyboards import get_main_menu

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user = update.effective_user
    welcome_text = (
        f"স্বাগতম {user.first_name}! 👋\n\n"
        "**পথিকবট** মোটর সাইকেল লগশীট অটোমেশন সিস্টেমে আপনাকে স্বাগতম।\n"
        "আমি আপনাকে আপনার দৈনন্দিন ভিজিট ট্র্যাক করতে এবং মাসিক রিপোর্ট তৈরি করতে সাহায্য করব।\n\n"
        "আজ আপনি কী করতে চান?"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu(), parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command with detailed Bangla explanations."""
    help_text = (
        "📚 **কমান্ডগুলোর বিস্তারিত ব্যাখ্যা**\n\n"
        "• /start\n"
        "বট চালু করার পর প্রথমে এই কমান্ডটি দিন। এটি একটি স্বাগত বার্তা দেখাবে যেখানে সব কমান্ডের একটি তালিকা পাবেন।\n\n"
        "• /newentry (বা নতুন এন্ট্রি বাটন)\n"
        "নতুন কোনো এন্ট্রি যোগ করতে এটি ব্যবহার করুন। বট আপনাকে ধাপে ধাপে প্রশ্ন করবে:\n"
        "  – এন্ট্রির ধরন (ফিল্ড ট্যুর নাকি মাসিক মিটিং)\n"
        "  – তারিখ ও মাস\n"
        "  – মিটার রিডিং ও দূরত্ব (আপনি এখানে যোগ/গুণ করতে পারেন, যেমন: 14+15)\n"
        "  – পেট্রোল ও মোবাইল রিচার্জের তথ্য\n"
        "বট নিজেই সব তথ্য গুছিয়ে সংরক্ষণ করবে।\n\n"
        "• /editentry\n"
        "পুরানো কোনো এন্ট্রি এডিট করতে এটি ব্যবহার করুন।\n\n"
        "• /delentry\n"
        "ভুল করে কোনো এন্ট্রি যোগ করলে তা ডিলিট করতে এটি ব্যবহার করুন।\n\n"
        "• /cancel\n"
        "যদি কাজ চলাকালীন মাঝপথে থামতে চান, তবে এই কমান্ডটি দিন।\n\n"
        "• /listentries (বা এন্ট্রি তালিকা বাটন)\n"
        "সাম্প্রতিক এন্ট্রিগুলো দেখতে এটি ব্যবহার করুন।\n\n"
        "• /summary (বা সারসংক্ষেপ বাটন)\n"
        "চলতি মাসের মোট খরচ ও দূরত্বের হিসাব দেখতে এটি ব্যবহার করুন।\n\n"
        "• /settings (বা সেটিংস বাটন)\n"
        "বর্তমানে সেট করা তেলের দাম, DA রেট ইত্যাদি দেখতে এটি ব্যবহার করুন।\n\n"
        "• /generate (বা রিপোর্ট তৈরি বাটন)\n"
        "মাস শেষে অফিসের জন্য DOCX রিপোর্ট তৈরি করতে এটি ব্যবহার করুন।"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(help_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(help_text, parse_mode='Markdown')

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu button clicks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "main_menu":
        await query.edit_message_text(
            "মূল মেনু:\nআপনি কী করতে চান?",
            reply_markup=get_main_menu()
        )
