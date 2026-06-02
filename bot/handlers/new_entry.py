from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters
)
from datetime import datetime
import calendar
from core.database import add_entry, get_last_odo, get_last_day_in_month, get_distributors
from core.calculations import calculate_km, calculate_petrol_cost, calculate_mobil_cost, calculate_total_entry_cost
from bot.keyboards import (
    get_entry_type_keyboard, 
    get_yes_no_keyboard, 
    get_confirmation_keyboard,
    get_main_menu,
    get_month_selection_keyboard,
    get_all_months_keyboard,
    get_date_selection_keyboard,
    get_distributor_keyboard,
    get_back_keyboard,
    MONTHS_BN_FULL,
    to_bn_number
)

# States
(
    CHOOSING_TYPE,
    SELECT_MONTH,
    SHOW_ALL_MONTHS,
    SELECT_DATE,
    ENTER_ODO_START,
    ENTER_DISTANCE,
    CONFIRM_ODO_END,
    PETROL_QUESTION,
    ENTER_LITERS,
    MOBIL_QUESTION,
    ENTER_MOBIL_LITERS,
    DA_CONFIRM,
    MANAGER_QUESTION,
    ENTER_MANAGER,
    SELECT_DISTRIBUTORS,
    CONFIRM_ENTRY,
    ENTER_VENUE,
    ENTER_TRANSPORT_FEE,
    CONFIRM_FINAL_ENTRY
) = range(19)

# Add a history for back button
HISTORY = "step_history"

def normalize_number(text: str) -> str:
    """Convert Bengali numbers to English."""
    bn_digits = '০১২৩৪৫৬৭৮৯'
    en_digits = '0123456789'
    return text.translate(str.maketrans(bn_digits, en_digits))

async def delete_previous_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete messages to keep the chat clean."""
    msg_ids = context.user_data.get('messages_to_delete', [])
    for msg_id in msg_ids:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
        except Exception:
            pass
    context.user_data['messages_to_delete'] = []

async def add_message_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, message_id):
    if 'messages_to_delete' not in context.user_data:
        context.user_data['messages_to_delete'] = []
    context.user_data['messages_to_delete'].append(message_id)

def push_history(context, state):
    if HISTORY not in context.user_data:
        context.user_data[HISTORY] = []
    if not context.user_data[HISTORY] or context.user_data[HISTORY][-1] != state:
        context.user_data[HISTORY].append(state)

def pop_history(context):
    if HISTORY in context.user_data and len(context.user_data[HISTORY]) > 1:
        context.user_data[HISTORY].pop() # current state
        return context.user_data[HISTORY].pop() # previous state
    return None

async def start_new_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the conversation for a new entry."""
    # Keep month/year for sticky logic but clear everything else
    to_keep = ['selected_month', 'selected_year']
    kept_data = {k: context.user_data[k] for k in to_keep if k in context.user_data}
    context.user_data.clear()
    context.user_data.update(kept_data)
    
    query = update.callback_query
    msg = "এন্ট্রির ধরন নির্বাচন করুন:"
    push_history(context, CHOOSING_TYPE)
    
    if query:
        await query.answer()
        await query.edit_message_text(msg, reply_markup=get_entry_type_keyboard())
    else:
        # If started by command, track both the command and the response
        await add_message_to_delete(update, context, update.message.message_id)
        m = await update.message.reply_text(msg, reply_markup=get_entry_type_keyboard())
        await add_message_to_delete(update, context, m.message_id)
    return CHOOSING_TYPE

async def handle_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "type_regular":
        context.user_data['entry_type'] = 'REGULAR'
        push_history(context, SELECT_MONTH)
        # Sticky month logic
        if 'selected_month' in context.user_data:
            month = context.user_data['selected_month']
            year = context.user_data['selected_year']
            last_day = await get_last_day_in_month(month, year)
            await query.edit_message_text(
                f"তারিখ নির্বাচন করুন ({MONTHS_BN_FULL[month]} {to_bn_number(year)}):",
                reply_markup=get_date_selection_keyboard(year, month, last_day=last_day)
            )
            return SELECT_DATE
        else:
            await query.edit_message_text("মাস নির্বাচন করুন:", reply_markup=get_month_selection_keyboard())
            return SELECT_MONTH
    elif query.data == "type_meeting":
        context.user_data['entry_type'] = 'MONTHLY_MEETING'
        push_history(context, ENTER_VENUE)
        await query.edit_message_text("ভেন্যুর নাম লিখুন (যেমন: রংপুর সেলস সেন্টার):", reply_markup=get_back_keyboard())
        return ENTER_VENUE
    elif query.data == "cancel":
        await query.edit_message_text("বাতিল করা হয়েছে।", reply_markup=get_main_menu())
        return ConversationHandler.END

async def handle_month_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        prev = pop_history(context)
        if prev == CHOOSING_TYPE: return await start_new_entry(update, context)
        return CHOOSING_TYPE

    if query.data == "show_more_months":
        year = datetime.now().year
        await query.edit_message_text("সব মাসের তালিকা:", reply_markup=get_all_months_keyboard(year))
        return SELECT_MONTH
    elif query.data.startswith("select_month_"):
        parts = query.data.split("_")
        year, month = int(parts[2]), int(parts[3])
        context.user_data['selected_year'] = year
        context.user_data['selected_month'] = month
        
        last_day = await get_last_day_in_month(month, year)
        
        push_history(context, SELECT_DATE)
        await query.edit_message_text(
            f"তারিখ নির্বাচন করুন ({MONTHS_BN_FULL[month]}):",
            reply_markup=get_date_selection_keyboard(year, month, last_day=last_day)
        )
        return SELECT_DATE
    elif query.data == "cancel":
        await query.edit_message_text("বাতিল করা হয়েছে।", reply_markup=get_main_menu())
        return ConversationHandler.END

async def handle_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        prev = pop_history(context)
        if prev == SELECT_MONTH: return await handle_type_selection(update, context) # This will show month selection
        if prev == ENTER_VENUE: 
            context.user_data['entry_type'] = 'MONTHLY_MEETING'
            await query.edit_message_text("ভেন্যুর নাম লিখুন (যেমন: রংপুর সেলস সেন্টার):", reply_markup=get_back_keyboard())
            return ENTER_VENUE
        return CHOOSING_TYPE

    year = context.user_data['selected_year']
    month = context.user_data['selected_month']

    if query.data == "show_all_dates":
        last_day = await get_last_day_in_month(month, year)
        await query.edit_message_text("তারিখ নির্বাচন করুন (শুক্রবার বাদে):", reply_markup=get_date_selection_keyboard(year, month, last_day=last_day, show_all=True))
        return SELECT_DATE
    elif query.data.startswith("select_date_"):
        day = int(query.data.split("_")[2])
        context.user_data['date'] = f"{year}-{month:02d}-{day:02d}"
        
        if context.user_data['entry_type'] == 'REGULAR':
            last_odo = await get_last_odo()
            context.user_data['suggested_odo_start'] = last_odo
            push_history(context, ENTER_ODO_START)
            await query.edit_message_text(
                f"শুরুর ওডোমিটার কি {to_bn_number(last_odo)} হয়?",
                reply_markup=get_yes_no_keyboard('odo_start_confirm', include_back=True)
            )
            return ENTER_ODO_START
        else:
            push_history(context, ENTER_TRANSPORT_FEE)
            await query.edit_message_text("যাতায়াত ভাড়া (টাকা) লিখুন:", reply_markup=get_back_keyboard())
            return ENTER_TRANSPORT_FEE
    elif query.data == "cancel":
        await query.edit_message_text("বাতিল করা হয়েছে।", reply_markup=get_main_menu())
        return ConversationHandler.END

async def handle_odo_start_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        pop_history(context)
        return await handle_month_selection(update, context) # Shows date selection

    if query.data == "odo_start_confirm_yes":
        context.user_data['odo_start'] = context.user_data['suggested_odo_start']
        push_history(context, ENTER_DISTANCE)
        await query.edit_message_text(
            "📏 আজকের মোট দূরত্ব লিখুন:\n"
            "একটি সংখ্যা হতে পারে (যেমন: 64) অথবা যোগফল (যেমন: 14+15+16) অথবা গুণ (যেমন: 2*30+5):",
            reply_markup=get_back_keyboard()
        )
        return ENTER_DISTANCE
    else:
        await query.edit_message_text("তাহলে শুরুর সঠিক ওডোমিটার রিডিংটি লিখুন:", reply_markup=get_back_keyboard())
        return ENTER_ODO_START

async def handle_odo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_message_to_delete(update, context, update.message.message_id)
    try:
        odo = int(normalize_number(update.message.text))
        context.user_data['odo_start'] = odo
        push_history(context, ENTER_DISTANCE)
        m = await update.message.reply_text(
            "📏 আজকের মোট দূরত্ব লিখুন:\n"
            "একটি সংখ্যা হতে পারে (যেমন: 64) অথবা যোগফল (যেমন: 14+15+16) অথবা গুণ (যেমন: 2*30+5):",
            reply_markup=get_back_keyboard()
        )
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_DISTANCE
    except ValueError:
        m = await update.message.reply_text("দয়া করে সঠিক সংখ্যা লিখুন।")
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_ODO_START

async def handle_distance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_message_to_delete(update, context, update.message.message_id)
    try:
        raw_text = normalize_number(update.message.text)
        clean_text = "".join(c for c in raw_text if c in "0123456789+-*/.()")
        dist = int(eval(clean_text))
        
        context.user_data['total_km'] = dist
        context.user_data['odo_end'] = context.user_data['odo_start'] + dist
        
        push_history(context, CONFIRM_ODO_END)
        m = await update.message.reply_text(
            f"✅ দূরত্ব: {to_bn_number(dist)} কি:মি:\n"
            f"🔚 তাহলে শেষ ওডোমিটার কি {to_bn_number(context.user_data['odo_end'])} হয়?",
            reply_markup=get_yes_no_keyboard('odo_confirm', include_back=True)
        )
        await add_message_to_delete(update, context, m.message_id)
        return CONFIRM_ODO_END
    except Exception:
        m = await update.message.reply_text("দয়া করে সঠিক হিসাব বা সংখ্যা লিখুন (যেমন: 64 বা 14+15)।")
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_DISTANCE

async def handle_odo_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        pop_history(context)
        # We need to show distance entry again. But distance was a MessageHandler.
        # So we just re-send the prompt.
        await query.edit_message_text(
            "📏 আজকের মোট দূরত্ব লিখুন:\n"
            "একটি সংখ্যা হতে পারে (যেমন: 64) অথবা যোগফল (যেমন: 14+15+16) অথবা গুণ (যেমন: 2*30+5):",
            reply_markup=get_back_keyboard()
        )
        return ENTER_DISTANCE

    if query.data == "odo_confirm_yes":
        push_history(context, PETROL_QUESTION)
        await query.edit_message_text(
            "⛽ আজ কি পেট্রোল কিনেছেন?",
            reply_markup=get_yes_no_keyboard('petrol', include_back=True)
        )
        return PETROL_QUESTION
    else:
        await query.edit_message_text("তাহলে সঠিক শেষ ওডোমিটার রিডিংটি লিখুন:", reply_markup=get_back_keyboard())
        return ENTER_ODO_END # This state might need a MessageHandler too

async def handle_petrol_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        pop_history(context)
        # Show odo end confirm again
        await query.edit_message_text(
            f"✅ দূরত্ব: {to_bn_number(context.user_data['total_km'])} কি:মি:\n"
            f"🔚 তাহলে শেষ ওডোমিটার কি {to_bn_number(context.user_data['odo_end'])} হয়?",
            reply_markup=get_yes_no_keyboard('odo_confirm', include_back=True)
        )
        return CONFIRM_ODO_END

    if query.data == "petrol_yes":
        push_history(context, ENTER_LITERS)
        await query.edit_message_text("⛽ পেট্রোল লিটার লিখুন:", reply_markup=get_back_keyboard())
        return ENTER_LITERS
    else:
        context.user_data['petrol_liters'] = 0
        context.user_data['petrol_cost'] = 0
        push_history(context, MOBIL_QUESTION)
        await query.edit_message_text(
            "🛢 আজ কি মবিল কিনেছেন?",
            reply_markup=get_yes_no_keyboard('mobil', include_back=True)
        )
        return MOBIL_QUESTION

async def handle_liters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_message_to_delete(update, context, update.message.message_id)
    try:
        liters = float(normalize_number(update.message.text))
        context.user_data['petrol_liters'] = liters
        context.user_data['petrol_cost'] = calculate_petrol_cost(liters)
        
        push_history(context, MOBIL_QUESTION)
        m = await update.message.reply_text(
            f"✅ পেট্রোল খরচ: {to_bn_number(context.user_data['petrol_cost'])}/-\n"
            "🛢 আজ কি মবিল কিনেছেন?",
            reply_markup=get_yes_no_keyboard('mobil', include_back=True)
        )
        await add_message_to_delete(update, context, m.message_id)
        return MOBIL_QUESTION
    except ValueError:
        m = await update.message.reply_text("দয়া করে সঠিক সংখ্যা লিখুন (যেমন: ১০ বা ১০.৫)।")
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_LITERS

async def handle_mobil_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        pop_history(context)
        await query.edit_message_text(
            "⛽ আজ কি পেট্রোল কিনেছেন?",
            reply_markup=get_yes_no_keyboard('petrol', include_back=True)
        )
        return PETROL_QUESTION

    if query.data == "mobil_yes":
        push_history(context, ENTER_MOBIL_LITERS)
        await query.edit_message_text("🛢 মবিল লিটার লিখুন:", reply_markup=get_back_keyboard())
        return ENTER_MOBIL_LITERS
    else:
        context.user_data['mobil_liters'] = 0
        context.user_data['mobil_cost'] = 0
        push_history(context, MANAGER_QUESTION)
        await query.edit_message_text(
            "💰 আপনার সাথে কি ম্যানেজার বা অন্য কেউ ছিলেন?",
            reply_markup=get_yes_no_keyboard('manager', include_back=True)
        )
        return MANAGER_QUESTION

async def handle_mobil_liters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_message_to_delete(update, context, update.message.message_id)
    try:
        liters = float(normalize_number(update.message.text))
        context.user_data['mobil_liters'] = liters
        context.user_data['mobil_cost'] = calculate_mobil_cost(liters)
        
        push_history(context, MANAGER_QUESTION)
        m = await update.message.reply_text(
            f"✅ মবিল খরচ: {to_bn_number(context.user_data['mobil_cost'])}/-\n"
            "💰 আপনার সাথে কি ম্যানেজার বা অন্য কেউ ছিলেন?",
            reply_markup=get_yes_no_keyboard('manager', include_back=True)
        )
        await add_message_to_delete(update, context, m.message_id)
        return MANAGER_QUESTION
    except ValueError:
        m = await update.message.reply_text("দয়া করে সঠিক সংখ্যা লিখুন (যেমন: ১ বা ০.৫)।")
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_MOBIL_LITERS

async def handle_manager_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        pop_history(context)
        await query.edit_message_text(
            "🛢 আজ কি মবিল কিনেছেন?",
            reply_markup=get_yes_no_keyboard('mobil', include_back=True)
        )
        return MOBIL_QUESTION

    if query.data == "manager_yes":
        push_history(context, ENTER_MANAGER)
        await query.edit_message_text("তার পদবী লিখুন (যেমন: ম্যানেজার সাহেব):", reply_markup=get_back_keyboard())
        return ENTER_MANAGER
    else:
        context.user_data['others_designation'] = ""
        push_history(context, DA_CONFIRM)
        await query.edit_message_text(
            "💰 সাধারণ DA ২০০/- টাকা। এটি কি সঠিক?",
            reply_markup=get_yes_no_keyboard('da', include_back=True)
        )
        return DA_CONFIRM

async def handle_manager_designation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_message_to_delete(update, context, update.message.message_id)
    context.user_data['others_designation'] = update.message.text
    push_history(context, DA_CONFIRM)
    m = await update.message.reply_text(
        "💰 সাধারণ DA ২০০/- টাকা। এটি কি সঠিক?",
        reply_markup=get_yes_no_keyboard('da', include_back=True)
    )
    await add_message_to_delete(update, context, m.message_id)
    return DA_CONFIRM

async def handle_da_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        pop_history(context)
        await query.edit_message_text(
            "💰 আপনার সাথে কি ম্যানেজার বা অন্য কেউ ছিলেন?",
            reply_markup=get_yes_no_keyboard('manager', include_back=True)
        )
        return MANAGER_QUESTION

    if query.data == "da_yes":
        context.user_data['da_amount'] = 200
    else:
        context.user_data['da_amount'] = 0
    
    push_history(context, SELECT_DISTRIBUTORS)
    context.user_data['selected_dist_indices'] = []
    dists = await get_distributors()
    await query.edit_message_text("পরিবেশক নির্বাচন করুন (একাধিক হতে পারে):", reply_markup=get_distributor_keyboard(dists))
    return SELECT_DISTRIBUTORS

async def handle_distributor_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        pop_history(context)
        await query.edit_message_text(
            "💰 সাধারণ DA ২০০/- টাকা। এটি কি সঠিক?",
            reply_markup=get_yes_no_keyboard('da', include_back=True)
        )
        return DA_CONFIRM

    selected = context.user_data.get('selected_dist_indices', [])
    dists = await get_distributors()
    
    if query.data.startswith("toggle_dist_"):
        idx = int(query.data.split("_")[2])
        if idx in selected:
            selected.remove(idx)
        else:
            selected.append(idx)
        context.user_data['selected_dist_indices'] = selected
        await query.edit_message_reply_markup(reply_markup=get_distributor_keyboard(dists, selected))
        return SELECT_DISTRIBUTORS
    elif query.data == "dist_done":
        names = [dists[i] for i in selected]
        context.user_data['distributors_raw'] = names
        push_history(context, CONFIRM_ENTRY)
        return await show_confirmation(update, context)
    elif query.data == "cancel":
        await query.edit_message_text("বাতিল করা হয়েছে।", reply_markup=get_main_menu())
        return ConversationHandler.END

async def handle_venue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_message_to_delete(update, context, update.message.message_id)
    context.user_data['venue'] = update.message.text
    push_history(context, SELECT_MONTH)
    # Meeting month selection
    if 'selected_month' in context.user_data:
        month = context.user_data['selected_month']
        year = context.user_data['selected_year']
        last_day = await get_last_day_in_month(month, year)
        m = await update.message.reply_text(
            f"তারিখ নির্বাচন করুন ({MONTHS_BN_FULL[month]} {to_bn_number(year)}):",
            reply_markup=get_date_selection_keyboard(year, month, last_day=last_day)
        )
        await add_message_to_delete(update, context, m.message_id)
        return SELECT_DATE
    else:
        m = await update.message.reply_text("মাস নির্বাচন করুন:", reply_markup=get_month_selection_keyboard())
        await add_message_to_delete(update, context, m.message_id)
        return SELECT_MONTH

async def handle_transport_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_message_to_delete(update, context, update.message.message_id)
    try:
        fee = int(normalize_number(update.message.text))
        context.user_data['transport_fee'] = fee
        
        last_odo = await get_last_odo()
        context.user_data['odo_start'] = last_odo
        context.user_data['odo_end'] = last_odo
        context.user_data['total_km'] = 0
        context.user_data['petrol_liters'] = 0
        context.user_data['petrol_cost'] = 0
        context.user_data['mobil_liters'] = 0
        context.user_data['mobil_cost'] = 0
        context.user_data['da_amount'] = 0
        context.user_data['others_designation'] = "মাসিক মিটিং"
        
        push_history(context, CONFIRM_ENTRY)
        return await show_confirmation(update, context)
    except ValueError:
        m = await update.message.reply_text("দয়া করে সঠিক পূর্ণসংখ্যা লিখুন।")
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_TRANSPORT_FEE

async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    cost = calculate_total_entry_cost(
        data['entry_type'], 
        data.get('petrol_liters', 0), 
        data.get('mobil_liters', 0), 
        data.get('da_amount'),
        data.get('transport_fee', 0)
    )
    data['total_cost'] = cost
    
    # Format date for summary
    dt = datetime.strptime(data['date'], '%Y-%m-%d')
    date_bn = dt.strftime('%d/%m/%y')
    
    summary = f"📋 **এন্ট্রি সংক্ষিপ্ত বিবরণ:**\n\n"
    summary += f"  ধরন: {'ফিল্ড ট্যুর' if data['entry_type'] == 'REGULAR' else 'মাসিক মিটিং'}\n"
    summary += f"  তারিখ: {to_bn_number(date_bn)}\n"
    summary += f"  মিটার শুরু: {to_bn_number(data['odo_start'])}\n"
    summary += f"  মিটার শেষ: {to_bn_number(data['odo_end'])}\n"
    summary += f"  দূরত্ব: {to_bn_number(data['total_km'])} কিমি\n"
    
    if data.get('petrol_liters'):
        summary += f"  পেট্রোল: {to_bn_number(data['petrol_liters'])} লি = {to_bn_number(data['petrol_cost'])} টাকা\n"
    
    if data.get('mobil_liters'):
        summary += f"  মবিল: {to_bn_number(data['mobil_liters'])} লি = {to_bn_number(data['mobil_cost'])} টাকা\n"
        
    summary += f"  DA বিল: {to_bn_number(data['da_amount'])} টাকা\n"
    
    if data['entry_type'] == 'MONTHLY_MEETING':
        summary += f"  যাতায়াত ভাড়া: {to_bn_number(data['transport_fee'])} টাকা\n"
        summary += f"  বিবরণ: {data['venue']}\n"
    
    summary += f"  মোট খরচ: {to_bn_number(cost)} টাকা\n"
    
    if data['entry_type'] == 'REGULAR':
        summary += f"\n  পরিবেশকবৃন্দ:\n"
        for name in data['distributors_raw']:
            summary += f"  – {name}\n"
        
    msg = summary + "\nআপনি কি এটি সংরক্ষণ করতে চান?"
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=get_confirmation_keyboard(), parse_mode='Markdown')
    else:
        m = await update.message.reply_text(msg, reply_markup=get_confirmation_keyboard(), parse_mode='Markdown')
        await add_message_to_delete(update, context, m.message_id)
    return CONFIRM_ENTRY

async def save_entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        pop_history(context)
        if context.user_data['entry_type'] == 'REGULAR':
            return await handle_da_confirm(update, context) # shows distributor selection
        else:
            await query.edit_message_text("যাতায়াত ভাড়া (টাকা) লিখুন:", reply_markup=get_back_keyboard())
            return ENTER_TRANSPORT_FEE

    if query.data == "confirm_save":
        await delete_previous_messages(update, context)
        entry_id = await add_entry(context.user_data.copy())
        
        # Check if it's the last 3 days of the month
        dt = datetime.strptime(context.user_data['date'], '%Y-%m-%d')
        days_in_month = calendar.monthrange(dt.year, dt.month)[1]
        
        if dt.day >= days_in_month - 2:
            # Within last 3 days
            await query.edit_message_text(
                f"✅ এন্ট্রি সফলভাবে সংরক্ষণ করা হয়েছে! (ID: {to_bn_number(entry_id)})\n\n"
                "❓ এটি কি এই মাসের শেষ এন্ট্রি?",
                reply_markup=get_yes_no_keyboard('final_entry')
            )
            return CONFIRM_FINAL_ENTRY
        else:
            await query.edit_message_text(f"✅ এন্ট্রি সফলভাবে সংরক্ষণ করা হয়েছে! (ID: {to_bn_number(entry_id)})", reply_markup=get_main_menu())
            # Final Aggressive Cleanup: If this message was a reply to a command, we might want to delete it too
            # and send a fresh start menu? But for now, editing it to main menu is standard.
            
            # Keep month/year for sticky logic
            to_keep = ['selected_month', 'selected_year']
            kept_data = {k: context.user_data[k] for k in to_keep if k in context.user_data}
            context.user_data.clear()
            context.user_data.update(kept_data)
            return ConversationHandler.END
    else:
        await delete_previous_messages(update, context)
        await query.edit_message_text("❌ এন্ট্রি বাতিল করা হয়েছে।", reply_markup=get_main_menu())
        # Keep month/year for sticky logic
        to_keep = ['selected_month', 'selected_year']
        kept_data = {k: context.user_data[k] for k in to_keep if k in context.user_data}
        context.user_data.clear()
        context.user_data.update(kept_data)
        return ConversationHandler.END

async def handle_final_entry_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await delete_previous_messages(update, context)
    
    if query.data == "final_entry_yes":
        # Clear sticky month
        context.user_data.clear()
        await query.edit_message_text("ধন্যবাদ। এই মাসের কাজ শেষ করা হয়েছে।", reply_markup=get_main_menu())
    else:
        # Keep sticky month
        to_keep = ['selected_month', 'selected_year']
        kept_data = {k: context.user_data[k] for k in to_keep if k in context.user_data}
        context.user_data.clear()
        context.user_data.update(kept_data)
        await query.edit_message_text("ঠিক আছে, আপনি আরও এন্ট্রি যোগ করতে পারবেন।", reply_markup=get_main_menu())
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation."""
    await delete_previous_messages(update, context)
    msg = "❌ কার্যক্রম বাতিল করা হয়েছে।"
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=get_main_menu())
    else:
        await update.message.reply_text(msg, reply_markup=get_main_menu())
    return ConversationHandler.END

def get_new_entry_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_new_entry, pattern="^new_entry$"), 
            CommandHandler("newentry", start_new_entry),
            CommandHandler("new", start_new_entry)
        ],
        states={
            CHOOSING_TYPE: [CallbackQueryHandler(handle_type_selection)],
            SELECT_MONTH: [CallbackQueryHandler(handle_month_selection, pattern="^select_month_|^show_more_months|^cancel$|^back$")],
            SELECT_DATE: [CallbackQueryHandler(handle_date_selection, pattern="^select_date_|^show_all_dates|^cancel$|^back$")],
            ENTER_ODO_START: [
                CallbackQueryHandler(handle_odo_start_confirm, pattern="^odo_start_confirm_|^back$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_odo_start)
            ],
            ENTER_DISTANCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_distance),
                CallbackQueryHandler(handle_odo_start_confirm, pattern="^back$") # Reuse back logic
            ],
            CONFIRM_ODO_END: [CallbackQueryHandler(handle_odo_confirm, pattern="^odo_confirm_|^back$")],
            PETROL_QUESTION: [CallbackQueryHandler(handle_petrol_question, pattern="^petrol_|^back$")],
            ENTER_LITERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_liters),
                CallbackQueryHandler(handle_petrol_question, pattern="^back$")
            ],
            MOBIL_QUESTION: [CallbackQueryHandler(handle_mobil_question, pattern="^mobil_|^back$")],
            ENTER_MOBIL_LITERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mobil_liters),
                CallbackQueryHandler(handle_mobil_question, pattern="^back$")
            ],
            MANAGER_QUESTION: [CallbackQueryHandler(handle_manager_question, pattern="^manager_|^back$")],
            ENTER_MANAGER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manager_designation),
                CallbackQueryHandler(handle_manager_question, pattern="^back$")
            ],
            DA_CONFIRM: [CallbackQueryHandler(handle_da_confirm, pattern="^da_|^back$")],
            SELECT_DISTRIBUTORS: [CallbackQueryHandler(handle_distributor_selection, pattern="^toggle_dist_|^dist_done|^cancel$|^back$")],
            CONFIRM_ENTRY: [CallbackQueryHandler(save_entry_callback, pattern="^confirm_|^back$")],
            CONFIRM_FINAL_ENTRY: [CallbackQueryHandler(handle_final_entry_confirm, pattern="^final_entry_")],
            ENTER_VENUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_venue),
                CallbackQueryHandler(handle_type_selection, pattern="^back$")
            ],
            ENTER_TRANSPORT_FEE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_transport_fee),
                CallbackQueryHandler(handle_date_selection, pattern="^back$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(cancel, pattern="^cancel$")]
    )

