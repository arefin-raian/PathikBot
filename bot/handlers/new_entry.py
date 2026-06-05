import asyncio
import html
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters
)
from datetime import datetime
from core.file_data_store import add_entry, get_entries, get_last_odo, get_last_day_in_month, get_distributors, get_user_prefs
from core.message_store import record_message
from core.audit_logger import log_event
from core.expense_calculations import calculate_km, calculate_petrol_cost, calculate_mobil_cost, calculate_total_entry_cost, get_petrol_status, get_mobil_status, calc_carry_forward, calculate_fuel_since_refill, PETROL_THRESHOLD_KM, MOBIL_THRESHOLD_KM, DEFAULT_PETROL_PRICE, DEFAULT_MOBIL_PRICE
from bot.inline_keyboards import (
    get_entry_type_keyboard, 
    get_yes_no_keyboard, 
    get_confirmation_keyboard,
    BACK_TO_MENU,
    get_month_selection_keyboard,
    get_all_months_keyboard,
    get_date_selection_keyboard,
    get_distributor_keyboard,
    get_back_keyboard,
    MONTHS_BN_FULL,
    to_bn_number
)
from bot.text_resources import S
from bot.auth import require_auth

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
    MANAGER_QUESTION,
    ENTER_MANAGER,
    SELECT_DISTRIBUTORS,
    CONFIRM_ENTRY,
    ENTER_VENUE,
    ENTER_TRANSPORT_FEE,
    CONFIRM_TRANSPORT_FEE,
    CONFIRM_LAST_TOUR,
    ENTER_ODO_END
) = range(20)

# Add a history for back button
HISTORY = "step_history"

def normalize_number(text: str) -> str:
    """Convert Bengali numbers to English."""
    bn_digits = '০১২৩৪৫৬৭৮৯'
    en_digits = '0123456789'
    return text.translate(str.maketrans(bn_digits, en_digits))

async def delete_previous_messages(update: Update, context: ContextTypes.DEFAULT_TYPE, exclude: int = None):
    """Delete messages to keep the chat clean."""
    msg_ids = context.user_data.get('messages_to_delete', [])
    for msg_id in msg_ids:
        if msg_id == exclude:
            continue
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
        except Exception:
            pass
    context.user_data['messages_to_delete'] = []

async def delete_stale_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete the stale prompt message from edit chain before creating a new reply message."""
    stale_id = context.user_data.pop('prompt_msg_id', None)
    if stale_id:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=stale_id)
        except Exception:
            pass

async def add_message_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, message_id):
    if 'messages_to_delete' not in context.user_data:
        context.user_data['messages_to_delete'] = []
    context.user_data['messages_to_delete'].append(message_id)
    await record_message(update.effective_user.id, update.effective_chat.id, message_id, 'temporary')

async def _delete_later(context, chat_id, msg_ids, delay=60):
    """Delete tracked messages after a delay."""
    await asyncio.sleep(delay)
    for mid in msg_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass

def schedule_message_cleanup(context, chat_id, delay=60):
    """Schedule deletion of tracked non-essential messages after delay seconds."""
    msg_ids = context.user_data.get('messages_to_delete', [])
    if msg_ids:
        context.application.create_task(_delete_later(context, chat_id, msg_ids[:], delay))

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
    if not await require_auth(update, context): return ConversationHandler.END
    context.user_data['_user_id'] = update.effective_user.id
    # Keep month/year for sticky logic but clear everything else
    to_keep = ['selected_month', 'selected_year']
    kept_data = {k: context.user_data[k] for k in to_keep if k in context.user_data}
    context.user_data.clear()
    context.user_data.update(kept_data)
    context.user_data['_user_id'] = update.effective_user.id
    
    query = update.callback_query
    msg = S('new_entry.type_prompt')
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
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "type_regular":
        context.user_data['entry_type'] = 'REGULAR'
        push_history(context, SELECT_MONTH)
        # Sticky month logic
        if 'selected_month' in context.user_data:
            month = context.user_data['selected_month']
            year = context.user_data['selected_year']
            last_day = await get_last_day_in_month(user_id, month, year)
            await query.edit_message_text(
                S('keyboards.date_selection.title_with_month', month_name=MONTHS_BN_FULL[month], year=to_bn_number(year)),
                reply_markup=get_date_selection_keyboard(year, month, last_day=last_day)
            )
            return SELECT_DATE
        else:
            await query.edit_message_text(S('new_entry.month_prompt'), reply_markup=get_month_selection_keyboard())
            return SELECT_MONTH
    elif query.data == "type_meeting":
        context.user_data['entry_type'] = 'MONTHLY_MEETING'
        context.user_data['venue'] = "রংপুর সেলস সেন্টার"
        push_history(context, SELECT_MONTH)
        if 'selected_month' in context.user_data:
            month = context.user_data['selected_month']
            year = context.user_data['selected_year']
            last_day = await get_last_day_in_month(user_id, month, year)
            await query.edit_message_text(
                S('keyboards.date_selection.title_with_month', month_name=MONTHS_BN_FULL[month], year=to_bn_number(year)),
                reply_markup=get_date_selection_keyboard(year, month, last_day=last_day)
            )
            return SELECT_DATE
        else:
            await query.edit_message_text(S('new_entry.month_prompt'), reply_markup=get_month_selection_keyboard())
            return SELECT_MONTH
    elif query.data == "cancel":
        await query.edit_message_text(S('common.cancelled_plain'), reply_markup=BACK_TO_MENU)
        return ConversationHandler.END
    return CHOOSING_TYPE

async def handle_month_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        prev = pop_history(context)
        if prev == CHOOSING_TYPE: return await start_new_entry(update, context)
        return CHOOSING_TYPE

    if query.data == "show_more_months":
        year = datetime.now().year
        await query.edit_message_text(S('keyboards.month_selection.all_months_title'), reply_markup=get_all_months_keyboard(year))
        return SELECT_MONTH
    elif query.data.startswith("select_month_"):
        parts = query.data.split("_")
        year, month = int(parts[2]), int(parts[3])
        context.user_data['selected_year'] = year
        context.user_data['selected_month'] = month
        
        last_day = await get_last_day_in_month(user_id, month, year)
        
        push_history(context, SELECT_DATE)
        await query.edit_message_text(
            S('keyboards.date_selection.title_with_month_only', month_name=MONTHS_BN_FULL[month]),
            reply_markup=get_date_selection_keyboard(year, month, last_day=last_day)
        )
        return SELECT_DATE
    elif query.data == "cancel":
        await query.edit_message_text(S('common.cancelled_plain'), reply_markup=BACK_TO_MENU)
        return ConversationHandler.END

async def handle_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        prev = pop_history(context)
        if prev == SELECT_MONTH:
            return await handle_type_selection(update, context)
        if prev == CHOOSING_TYPE:
            await query.edit_message_text(S('new_entry.what_type'), reply_markup=get_entry_type_keyboard())
            return CHOOSING_TYPE
        return CHOOSING_TYPE

    year = context.user_data['selected_year']
    month = context.user_data['selected_month']

    if query.data == "show_all_dates":
        last_day = await get_last_day_in_month(user_id, month, year)
        await query.edit_message_text(S('keyboards.date_selection.title_all_dates'), reply_markup=get_date_selection_keyboard(year, month, last_day=last_day, show_all=True))
        return SELECT_DATE
    elif query.data.startswith("select_date_"):
        day = int(query.data.split("_")[2])
        context.user_data['date'] = f"{year}-{month:02d}-{day:02d}"
        
        if context.user_data['entry_type'] == 'REGULAR':
            last_odo = await get_last_odo(user_id)
            context.user_data['suggested_odo_start'] = last_odo
            push_history(context, ENTER_ODO_START)
            await query.edit_message_text(
                S('new_entry.odo_start_confirm', last_odo=to_bn_number(last_odo)),
                reply_markup=get_yes_no_keyboard('odo_start_confirm', include_back=True),
                parse_mode='HTML'
            )
            return ENTER_ODO_START
        else:
            transport_fee = 460
            context.user_data['transport_fee'] = transport_fee
            push_history(context, CONFIRM_TRANSPORT_FEE)
            await query.edit_message_text(
                S('new_entry.transport_confirm', transport_fee=to_bn_number(transport_fee)),
                reply_markup=get_yes_no_keyboard("transport")
            )
            return CONFIRM_TRANSPORT_FEE
    elif query.data == "cancel":
        await query.edit_message_text(S('common.cancelled_plain'), reply_markup=BACK_TO_MENU)
        return ConversationHandler.END

async def handle_odo_start_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        prev = pop_history(context)
        if prev == SELECT_DATE:
            month = context.user_data['selected_month']
            year = context.user_data['selected_year']
            last_day = await get_last_day_in_month(user_id, month, year)
            await query.edit_message_text(
                S('keyboards.date_selection.title_with_month', month_name=MONTHS_BN_FULL[month], year=to_bn_number(year)),
                reply_markup=get_date_selection_keyboard(year, month, last_day=last_day)
            )
            return SELECT_DATE
        elif prev == ENTER_ODO_START:
            last_odo = context.user_data.get('suggested_odo_start', await get_last_odo(user_id))
            await query.edit_message_text(
                S('new_entry.odo_start_confirm', last_odo=to_bn_number(last_odo)),
                reply_markup=get_yes_no_keyboard('odo_start_confirm', include_back=True),
                parse_mode='HTML'
            )
            return ENTER_ODO_START
        return CHOOSING_TYPE

    if query.data == "odo_start_confirm_yes":
        context.user_data['odo_start'] = context.user_data['suggested_odo_start']
        push_history(context, ENTER_DISTANCE)
        # Track this message ID so handle_distance can delete the prompt later
        context.user_data['prompt_msg_id'] = query.message.message_id
        await query.edit_message_text(
            S('new_entry.distance_prompt'),
            reply_markup=get_back_keyboard()
        )
        return ENTER_DISTANCE
    else:
        context.user_data['prompt_msg_id'] = query.message.message_id
        await query.edit_message_text(S('new_entry.odo_start_prompt'), reply_markup=get_back_keyboard())
        return ENTER_ODO_START

async def handle_odo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(update, context)
    await add_message_to_delete(update, context, update.message.message_id)
    await delete_stale_prompt(update, context)
    try:
        odo = int(normalize_number(update.message.text))
        context.user_data['odo_start'] = odo
        push_history(context, ENTER_DISTANCE)
        m = await update.message.reply_text(
            S('new_entry.distance_prompt'),
            reply_markup=get_back_keyboard()
        )
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_DISTANCE
    except ValueError:
        m = await update.message.reply_text(S('new_entry.error_invalid_number'))
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_ODO_START

async def handle_distance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(update, context)
    await add_message_to_delete(update, context, update.message.message_id)
    
    # Delete the stale distance prompt message
    stale_id = context.user_data.pop('prompt_msg_id', None)
    if stale_id:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=stale_id)
        except Exception:
            pass
    
    try:
        raw_text = normalize_number(update.message.text)
        clean_text = "".join(c for c in raw_text if c in "0123456789+-*/.()")
        dist = int(eval(clean_text))
        
        context.user_data['total_km'] = dist
        context.user_data['odo_end'] = context.user_data['odo_start'] + dist
        
        push_history(context, CONFIRM_ODO_END)
        m = await update.message.reply_text(
            S('new_entry.distance_result', dist=to_bn_number(dist), odo_end=to_bn_number(context.user_data['odo_end'])),
            reply_markup=get_yes_no_keyboard('odo_confirm', include_back=True),
            parse_mode='HTML'
        )
        await add_message_to_delete(update, context, m.message_id)
        return CONFIRM_ODO_END
    except Exception:
        m = await update.message.reply_text(S('new_entry.error_invalid_calculation'))
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_DISTANCE

async def handle_odo_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        pop_history(context)
        await query.edit_message_text(
            S('new_entry.distance_prompt'),
            reply_markup=get_back_keyboard()
        )
        return ENTER_DISTANCE

    if query.data == "odo_confirm_yes":
        push_history(context, PETROL_QUESTION)
        all_entries = await get_entries(user_id)
        status = get_petrol_status(all_entries)
        if context.user_data.get('total_km', 0) > 0:
            status['distance_since'] += context.user_data['total_km']
            status['is_due'] = status['distance_since'] >= status['effective_threshold']
        text = S('new_entry.petrol_question')
        if status['is_due']:
            text += S('thresholds.petrol_due_reminder', km=to_bn_number(status['distance_since']))
        await query.edit_message_text(
            text,
            reply_markup=get_yes_no_keyboard('petrol', include_back=True),
            parse_mode='HTML'
        )
        return PETROL_QUESTION
    else:
        context.user_data['prompt_msg_id'] = query.message.message_id
        await query.edit_message_text(S('new_entry.odo_end_prompt'), reply_markup=get_back_keyboard())
        return ENTER_ODO_END

async def handle_odo_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await delete_previous_messages(update, context)
    await add_message_to_delete(update, context, update.message.message_id)
    await delete_stale_prompt(update, context)
    try:
        odo_end = int(normalize_number(update.message.text))
    except ValueError:
        m = await update.message.reply_text(S('new_entry.error_invalid_int'))
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_ODO_END

    context.user_data['odo_end'] = odo_end
    odo_start = context.user_data['odo_start']
    distance = calculate_km(odo_start, odo_end)
    context.user_data['total_km'] = distance

    all_entries = await get_entries(user_id)
    petrol_status = get_petrol_status(all_entries)
    if distance > 0:
        petrol_status['distance_since'] += distance
        petrol_status['is_due'] = petrol_status['distance_since'] >= petrol_status['effective_threshold']

    text = S('new_entry.distance_result', dist=to_bn_number(distance), odo_end=to_bn_number(odo_end))
    if petrol_status['is_due']:
        text += S('thresholds.petrol_due_reminder', km=to_bn_number(petrol_status['distance_since']))

    m = await update.message.reply_text(
        text,
        reply_markup=get_yes_no_keyboard('odo_confirm', include_back=True),
        parse_mode='HTML'
    )
    await add_message_to_delete(update, context, m.message_id)
    return CONFIRM_ODO_END


async def handle_odo_end_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dist = context.user_data.get('total_km', 0)
    odo_end = context.user_data.get('odo_end', 0)
    await query.edit_message_text(
        S('new_entry.distance_result', dist=to_bn_number(dist), odo_end=to_bn_number(odo_end)),
        reply_markup=get_yes_no_keyboard('odo_confirm', include_back=True),
        parse_mode='HTML'
    )
    return CONFIRM_ODO_END


async def handle_petrol_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        prev = pop_history(context)
        if prev == CONFIRM_ODO_END:
            await query.edit_message_text(
                S('new_entry.distance_result', dist=to_bn_number(context.user_data['total_km']), odo_end=to_bn_number(context.user_data['odo_end'])),
                reply_markup=get_yes_no_keyboard('odo_confirm', include_back=True),
                parse_mode='HTML'
            )
            return CONFIRM_ODO_END
        elif prev == PETROL_QUESTION:
            all_entries = await get_entries(user_id)
            status = get_petrol_status(all_entries)
            if context.user_data.get('total_km', 0) > 0:
                status['distance_since'] += context.user_data['total_km']
                status['is_due'] = status['distance_since'] >= status['effective_threshold']
            text = S('new_entry.petrol_question')
            if status['is_due']:
                text += S('thresholds.petrol_due_reminder', km=to_bn_number(status['distance_since']))
            await query.edit_message_text(
                text,
                reply_markup=get_yes_no_keyboard('petrol', include_back=True),
                parse_mode='HTML'
            )
            return PETROL_QUESTION
        return CHOOSING_TYPE

    if query.data == "petrol_yes":
        push_history(context, ENTER_LITERS)
        context.user_data['prompt_msg_id'] = query.message.message_id
        await query.edit_message_text(S('new_entry.petrol_liters_prompt'), reply_markup=get_back_keyboard())
        return ENTER_LITERS
    else:
        context.user_data['petrol_liters'] = 0
        context.user_data['petrol_cost'] = 0
        push_history(context, MOBIL_QUESTION)
        # Check mobil threshold
        all_entries = await get_entries(user_id)
        status = get_mobil_status(all_entries)
        if context.user_data.get('total_km', 0) > 0:
            status['distance_since'] += context.user_data['total_km']
            status['is_due'] = status['distance_since'] >= status['effective_threshold']
        mobil_text = S('new_entry.mobil_question')
        if status['is_due']:
            mobil_text += S('thresholds.mobil_due_reminder', km=to_bn_number(status['distance_since']))
        await query.edit_message_text(
            mobil_text,
            reply_markup=get_yes_no_keyboard('mobil', include_back=True),
            parse_mode='HTML'
        )
        return MOBIL_QUESTION

async def handle_liters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await delete_previous_messages(update, context)
    await add_message_to_delete(update, context, update.message.message_id)
    await delete_stale_prompt(update, context)
    try:
        liters = float(normalize_number(update.message.text))
        context.user_data['petrol_liters'] = liters
        prefs = await get_user_prefs(user_id)
        petrol_price = float(prefs.get('petrol_price', DEFAULT_PETROL_PRICE))
        context.user_data['petrol_cost'] = calculate_petrol_cost(liters, petrol_price)
        
        push_history(context, MOBIL_QUESTION)
        # Check mobil threshold for embedded mobil question
        all_entries = await get_entries(user_id)
        status = get_mobil_status(all_entries)
        if context.user_data.get('total_km', 0) > 0:
            status['distance_since'] += context.user_data['total_km']
            status['is_due'] = status['distance_since'] >= status['effective_threshold']
        petrol_text = S('new_entry.petrol_result', petrol_cost=to_bn_number(context.user_data['petrol_cost']))
        if status['is_due']:
            petrol_text += S('thresholds.mobil_due_reminder', km=to_bn_number(status['distance_since']))
        m = await update.message.reply_text(
            petrol_text,
            reply_markup=get_yes_no_keyboard('mobil', include_back=True),
            parse_mode='HTML'
        )
        await add_message_to_delete(update, context, m.message_id)
        return MOBIL_QUESTION
    except ValueError:
        m = await update.message.reply_text(S('new_entry.error_invalid_float'))
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_LITERS

async def handle_mobil_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        prev = pop_history(context)
        if prev == PETROL_QUESTION:
            all_entries = await get_entries(user_id)
            status = get_petrol_status(all_entries)
            if context.user_data.get('total_km', 0) > 0:
                status['distance_since'] += context.user_data['total_km']
                status['is_due'] = status['distance_since'] >= status['effective_threshold']
            text = S('new_entry.petrol_question')
            if status['is_due']:
                text += S('thresholds.petrol_due_reminder', km=to_bn_number(status['distance_since']))
            await query.edit_message_text(
                text,
                reply_markup=get_yes_no_keyboard('petrol', include_back=True),
                parse_mode='HTML'
            )
            return PETROL_QUESTION
        elif prev == MOBIL_QUESTION:
            all_entries = await get_entries(user_id)
            status = get_mobil_status(all_entries)
            if context.user_data.get('total_km', 0) > 0:
                status['distance_since'] += context.user_data['total_km']
                status['is_due'] = status['distance_since'] >= status['effective_threshold']
            mobil_text = S('new_entry.mobil_question')
            if status['is_due']:
                mobil_text += S('thresholds.mobil_due_reminder', km=to_bn_number(status['distance_since']))
            await query.edit_message_text(
                mobil_text,
                reply_markup=get_yes_no_keyboard('mobil', include_back=True),
                parse_mode='HTML'
            )
            return MOBIL_QUESTION
        return CHOOSING_TYPE

    if query.data == "mobil_yes":
        push_history(context, ENTER_MOBIL_LITERS)
        context.user_data['prompt_msg_id'] = query.message.message_id
        await query.edit_message_text(S('new_entry.mobil_liters_prompt'), reply_markup=get_back_keyboard())
        return ENTER_MOBIL_LITERS
    else:
        context.user_data['mobil_liters'] = 0
        context.user_data['mobil_cost'] = 0
        push_history(context, MANAGER_QUESTION)
        await query.edit_message_text(
            S('new_entry.manager_question'),
            reply_markup=get_yes_no_keyboard('manager', include_back=True)
        )
        return MANAGER_QUESTION

async def handle_mobil_liters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await delete_previous_messages(update, context)
    await add_message_to_delete(update, context, update.message.message_id)
    await delete_stale_prompt(update, context)
    try:
        liters = float(normalize_number(update.message.text))
        context.user_data['mobil_liters'] = liters
        prefs = await get_user_prefs(user_id)
        mobil_price = float(prefs.get('mobil_price', DEFAULT_MOBIL_PRICE))
        context.user_data['mobil_cost'] = calculate_mobil_cost(liters, mobil_price)
        
        push_history(context, MANAGER_QUESTION)
        m = await update.message.reply_text(
            S('new_entry.mobil_result', mobil_cost=to_bn_number(context.user_data['mobil_cost'])),
            reply_markup=get_yes_no_keyboard('manager', include_back=True),
            parse_mode='HTML'
        )
        await add_message_to_delete(update, context, m.message_id)
        return MANAGER_QUESTION
    except ValueError:
        m = await update.message.reply_text(S('new_entry.error_invalid_mobil_float'))
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_MOBIL_LITERS

async def handle_manager_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        prev = pop_history(context)
        if prev == ENTER_MOBIL_LITERS:
            await query.edit_message_text(S('new_entry.mobil_liters_prompt'), reply_markup=get_back_keyboard())
            return ENTER_MOBIL_LITERS
        elif prev == MOBIL_QUESTION:
            user_id = update.effective_user.id
            all_entries = await get_entries(user_id)
            status = get_mobil_status(all_entries)
            if context.user_data.get('total_km', 0) > 0:
                status['distance_since'] += context.user_data['total_km']
                status['is_due'] = status['distance_since'] >= status['effective_threshold']
            mobil_text = S('new_entry.mobil_question')
            if status['is_due']:
                mobil_text += S('thresholds.mobil_due_reminder', km=to_bn_number(status['distance_since']))
            await query.edit_message_text(mobil_text, reply_markup=get_yes_no_keyboard('mobil', include_back=True), parse_mode='HTML')
            return MOBIL_QUESTION
        return CHOOSING_TYPE
    
    if query.data == "manager_yes":
        push_history(context, ENTER_MANAGER)
        context.user_data['prompt_msg_id'] = query.message.message_id
        await query.edit_message_text(S('new_entry.manager_designation_prompt'), reply_markup=get_back_keyboard())
        return ENTER_MANAGER
    else:
        context.user_data['others_designation'] = ""
        prefs = await get_user_prefs(update.effective_user.id)
        context.user_data['da_amount'] = int(prefs.get('da_amount', 200))
        push_history(context, SELECT_DISTRIBUTORS)
        context.user_data['selected_dist_indices'] = []
        dists = await get_distributors()
        await query.edit_message_text(S('new_entry.distributor_prompt'), reply_markup=get_distributor_keyboard(dists))
        return SELECT_DISTRIBUTORS

async def handle_manager_designation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_previous_messages(update, context)
    await add_message_to_delete(update, context, update.message.message_id)
    await delete_stale_prompt(update, context)
    context.user_data['others_designation'] = update.message.text
    prefs = await get_user_prefs(update.effective_user.id)
    context.user_data['da_amount'] = prefs.get('da_amount', 200)
    push_history(context, SELECT_DISTRIBUTORS)
    context.user_data['selected_dist_indices'] = []
    dists = await get_distributors()
    m = await update.message.reply_text(S('new_entry.distributor_prompt'), reply_markup=get_distributor_keyboard(dists))
    await add_message_to_delete(update, context, m.message_id)
    return SELECT_DISTRIBUTORS

async def handle_distributor_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        prev = pop_history(context)
        if prev == ENTER_MANAGER:
            await query.edit_message_text(S('new_entry.manager_designation_prompt'), reply_markup=get_back_keyboard())
            return ENTER_MANAGER
        await query.edit_message_text(
            S('new_entry.manager_question'),
            reply_markup=get_yes_no_keyboard('manager', include_back=True)
        )
        return MANAGER_QUESTION

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
        await query.edit_message_text(S('common.cancelled_plain'), reply_markup=BACK_TO_MENU)
        return ConversationHandler.END

async def handle_venue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await delete_previous_messages(update, context)
    await add_message_to_delete(update, context, update.message.message_id)
    context.user_data['venue'] = update.message.text
    push_history(context, SELECT_MONTH)
    # Meeting month selection
    if 'selected_month' in context.user_data:
        month = context.user_data['selected_month']
        year = context.user_data['selected_year']
        last_day = await get_last_day_in_month(user_id, month, year)
        m = await update.message.reply_text(
            S('keyboards.date_selection.title_with_month', month_name=MONTHS_BN_FULL[month], year=to_bn_number(year)),
            reply_markup=get_date_selection_keyboard(year, month, last_day=last_day)
        )
        await add_message_to_delete(update, context, m.message_id)
        return SELECT_DATE
    else:
        m = await update.message.reply_text(S('new_entry.month_prompt'), reply_markup=get_month_selection_keyboard())
        await add_message_to_delete(update, context, m.message_id)
        return SELECT_MONTH

async def handle_transport_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await delete_previous_messages(update, context)
    await add_message_to_delete(update, context, update.message.message_id)
    await delete_stale_prompt(update, context)
    try:
        fee = int(normalize_number(update.message.text))
        context.user_data['transport_fee'] = fee
        
        last_odo = await get_last_odo(user_id)
        context.user_data['odo_start'] = last_odo
        context.user_data['odo_end'] = last_odo
        context.user_data['total_km'] = 0
        context.user_data['petrol_liters'] = 0
        context.user_data['petrol_cost'] = 0
        context.user_data['mobil_liters'] = 0
        context.user_data['mobil_cost'] = 0
        context.user_data['da_amount'] = 0
        context.user_data['others_designation'] = S('new_entry.da_skip')
        
        push_history(context, CONFIRM_ENTRY)
        return await show_confirmation(update, context)
    except ValueError:
        m = await update.message.reply_text(S('new_entry.error_invalid_int'))
        await add_message_to_delete(update, context, m.message_id)
        return ENTER_TRANSPORT_FEE

async def handle_transport_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()

    if query.data == "transport_yes":
        fee = context.user_data.get('transport_fee', 460)
        context.user_data['transport_fee'] = fee
        last_odo = await get_last_odo(user_id)
        context.user_data['odo_start'] = last_odo
        context.user_data['odo_end'] = last_odo
        context.user_data['total_km'] = 0
        context.user_data['petrol_liters'] = 0
        context.user_data['petrol_cost'] = 0
        context.user_data['mobil_liters'] = 0
        context.user_data['mobil_cost'] = 0
        context.user_data['da_amount'] = 0
        context.user_data['others_designation'] = S('new_entry.da_skip')
        push_history(context, CONFIRM_ENTRY)
        return await show_confirmation(update, context)

    elif query.data == "transport_no":
        context.user_data['prompt_msg_id'] = query.message.message_id
        await query.edit_message_text(S('new_entry.transport_prompt'), reply_markup=get_back_keyboard())
        return ENTER_TRANSPORT_FEE

    elif query.data == "back":
        pop_history(context)
        month = context.user_data['selected_month']
        year = context.user_data['selected_year']
        last_day = await get_last_day_in_month(user_id, month, year)
        await query.edit_message_text(
            S('keyboards.date_selection.title_with_month', month_name=MONTHS_BN_FULL[month], year=to_bn_number(year)),
            reply_markup=get_date_selection_keyboard(year, month, last_day=last_day)
        )
        return SELECT_DATE

    return CONFIRM_TRANSPORT_FEE

async def handle_back_to_confirm_transport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fee = 460
    context.user_data['transport_fee'] = fee
    await query.edit_message_text(
        S('new_entry.transport_confirm', transport_fee=to_bn_number(fee)),
        reply_markup=get_yes_no_keyboard("transport"),
        parse_mode='HTML'
    )
    return CONFIRM_TRANSPORT_FEE

async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    prefs = await get_user_prefs(update.effective_user.id)
    petrol_price = float(prefs.get('petrol_price', DEFAULT_PETROL_PRICE))
    mobil_price = float(prefs.get('mobil_price', DEFAULT_MOBIL_PRICE))
    cost = calculate_total_entry_cost(
        data['entry_type'], 
        data.get('petrol_liters', 0), 
        data.get('mobil_liters', 0), 
        data.get('da_amount'),
        data.get('transport_fee', 0),
        petrol_price=petrol_price,
        mobil_price=mobil_price
    )
    data['total_cost'] = cost
    
    dt = datetime.strptime(data['date'], '%Y-%m-%d')
    date_bn = to_bn_number(dt.strftime('%d/%m/%y'))

    if data['entry_type'] == 'REGULAR':
        petrol_l = data.get('petrol_liters', 0)
        mobil_l = data.get('mobil_liters', 0)
        petrol_line = S('summary.entry_petrol_line', liters=to_bn_number(petrol_l), cost=to_bn_number(data.get('petrol_cost', 0))) if petrol_l else ""
        mobil_line = S('summary.entry_mobil_line', liters=to_bn_number(mobil_l), cost=to_bn_number(data.get('mobil_cost', 0))) if mobil_l else ""
        dist_block = ""
        if data.get('distributors_raw'):
            dist_block = "<blockquote expandable>"
            for name in data['distributors_raw']:
                dist_block += S('summary.entry_distributor_line', name=html.escape(name))
            dist_block += "</blockquote>"
        summary = (
            S('summary.entry_header_regular', index="", date=date_bn) + "\n" +
            S('summary.entry_body_regular',
                odo_start=to_bn_number(data['odo_start']),
                odo_end=to_bn_number(data['odo_end']),
                total_km=to_bn_number(data['total_km']),
                petrol_line=petrol_line,
                mobil_line=mobil_line,
                da_amount=to_bn_number(data['da_amount']),
                total_cost=to_bn_number(cost),
                distributors_block=dist_block)
        )
    else:
        summary = (
            S('summary.entry_header_meeting', index="", date=date_bn) + "\n" +
            S('summary.entry_body_meeting',
                odo_start=to_bn_number(data['odo_start']),
                odo_end=to_bn_number(data['odo_end']),
                total_km=to_bn_number(data['total_km']),
                da_amount=to_bn_number(data['da_amount']),
                transport_fee=to_bn_number(data.get('transport_fee', 0)),
                venue=data.get('venue', ''),
                total_cost=to_bn_number(cost))
        )

    msg = summary + '\n\n' + S('new_entry.entry_preview')
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=get_confirmation_keyboard(), parse_mode='HTML')
    else:
        m = await update.message.reply_text(msg, reply_markup=get_confirmation_keyboard(), parse_mode='HTML')
        await add_message_to_delete(update, context, m.message_id)
    return CONFIRM_ENTRY

async def save_entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        prev = pop_history(context)
        if prev == SELECT_DISTRIBUTORS:
            dists = await get_distributors()
            await query.edit_message_text(S('new_entry.distributor_prompt'), reply_markup=get_distributor_keyboard(dists))
            return SELECT_DISTRIBUTORS
        elif prev == CONFIRM_TRANSPORT_FEE:
            transport_fee = context.user_data.get('transport_fee', 460)
            await query.edit_message_text(
                S('new_entry.transport_confirm', transport_fee=to_bn_number(transport_fee)),
                reply_markup=get_yes_no_keyboard("transport"),
                parse_mode='HTML'
            )
            return CONFIRM_TRANSPORT_FEE
        return CHOOSING_TYPE

    if query.data == "confirm_save":
        await delete_previous_messages(update, context, exclude=query.message.message_id)

        # Compute carry-forward for petrol/mobil refills
        all_entries = await get_entries(user_id)
        petrol_liters = context.user_data.get('petrol_liters', 0)
        mobil_liters = context.user_data.get('mobil_liters', 0)
        total_km = context.user_data.get('total_km', 0)
        if petrol_liters > 0:
            overflow = calc_carry_forward(all_entries, total_km, 'petrol_liters', 'petrol_overflow', 480)
            context.user_data['petrol_overflow'] = overflow
        if mobil_liters > 0:
            overflow = calc_carry_forward(all_entries, total_km, 'mobil_liters', 'mobil_overflow', 1000)
            context.user_data['mobil_overflow'] = overflow

        entry_id = await add_entry(user_id, {
            'entry_type': context.user_data.get('entry_type'),
            'date': context.user_data.get('date'),
            'odo_start': context.user_data.get('odo_start', 0),
            'odo_end': context.user_data.get('odo_end', 0),
            'total_km': context.user_data.get('total_km', 0),
            'petrol_liters': context.user_data.get('petrol_liters', 0),
            'petrol_cost': context.user_data.get('petrol_cost', 0),
            'mobil_liters': context.user_data.get('mobil_liters', 0),
            'mobil_cost': context.user_data.get('mobil_cost', 0),
            'da_amount': context.user_data.get('da_amount', 0),
            'others_designation': context.user_data.get('others_designation', ''),
            'transport_fee': context.user_data.get('transport_fee', 0),
            'venue': context.user_data.get('venue', ''),
            'distributors_raw': context.user_data.get('distributors_raw', []),
            'total_cost': context.user_data.get('total_cost', 0),
        })
        
        dt = datetime.strptime(context.user_data['date'], '%Y-%m-%d')
        
        await query.edit_message_text(
            S('new_entry.save_success', entry_id=to_bn_number(entry_id)),
            parse_mode='HTML'
        )
        
        from bot.handlers.summary import send_summary_message
        month_entries = await get_entries(user_id, dt.month, dt.year)
        await send_summary_message(context, update.effective_chat.id, user_id, month_entries)

        user = update.effective_user
        entry_type = context.user_data.get('entry_type', '')
        total_km = context.user_data.get('total_km', 0)
        petrol_l = context.user_data.get('petrol_liters', 0)
        mobil_l = context.user_data.get('mobil_liters', 0)
        changes = []
        changes.append(f"Type: <b>{entry_type}</b>")
        changes.append(f"Date: <b>{context.user_data.get('date', '')}</b>")
        changes.append(f"Distance: <b>{total_km}</b> km")
        if petrol_l:
            changes.append(f"Petrol: <b>{petrol_l}</b> L (cost: {context.user_data.get('petrol_cost', 0)}/-)")
        if mobil_l:
            changes.append(f"Mobil: <b>{mobil_l}</b> L (cost: {context.user_data.get('mobil_cost', 0)}/-)")
        changes.append(f"Total Cost: <b>{context.user_data.get('total_cost', 0)}</b>/-")
        await log_event(context, 'entry_created',
            user_id=user_id, username=user.full_name,
            details=f"Entry #{entry_id} created",
            changes=changes
        )

        # Count REGULAR tour entries for the month (excluding meetings)
        tour_count = sum(1 for e in month_entries if e.get('entry_type') == 'REGULAR')
        
        if tour_count >= 16:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=S('new_entry.last_tour_prompt'),
                reply_markup=get_yes_no_keyboard('last_tour')
            )
            return CONFIRM_LAST_TOUR
        else:
            schedule_message_cleanup(context, update.effective_chat.id)
            menu_kb = InlineKeyboardMarkup([[InlineKeyboardButton(S('common.back_to_menu'), callback_data="main_menu")]])
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=S('new_entry.back_to_menu_prompt'),
                reply_markup=menu_kb
            )
            to_keep = ['selected_month', 'selected_year']
            kept_data = {k: context.user_data[k] for k in to_keep if k in context.user_data}
            context.user_data.clear()
            context.user_data.update(kept_data)
            return ConversationHandler.END
    else:
        await delete_previous_messages(update, context, exclude=query.message.message_id)
        schedule_message_cleanup(context, update.effective_chat.id)
        await query.edit_message_text(S('new_entry.save_discarded'), reply_markup=BACK_TO_MENU)
        to_keep = ['selected_month', 'selected_year']
        kept_data = {k: context.user_data[k] for k in to_keep if k in context.user_data}
        context.user_data.clear()
        context.user_data.update(kept_data)
        return ConversationHandler.END

async def handle_last_tour_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    await delete_previous_messages(update, context, exclude=query.message.message_id)
    dt = datetime.strptime(context.user_data['date'], '%Y-%m-%d')
    
    if query.data == "last_tour_yes":
        month_entries = await get_entries(user_id, dt.month, dt.year)
        entry_id = max(e['id'] for e in month_entries)
        
        petrol_info = calculate_fuel_since_refill(month_entries, 'petrol_liters', PETROL_THRESHOLD_KM)
        mobil_info = calculate_fuel_since_refill(month_entries, 'mobil_liters', MOBIL_THRESHOLD_KM)
        
        from core.file_data_store import update_entry
        await update_entry(user_id, entry_id, {
            'is_last_tour': True,
            'final_petrol_consumed': petrol_info['liters_consumed'],
            'final_mobil_consumed': mobil_info['liters_consumed']
        })

        user = update.effective_user
        effects = []
        if petrol_info['liters_consumed'] > 0:
            effects.append(f"Auto-calculated petrol consumption: <b>{petrol_info['liters_consumed']}</b> L over <b>{petrol_info['distance_since_refill']}</b> km since last refill")
        if mobil_info['liters_consumed'] > 0:
            effects.append(f"Auto-calculated mobil consumption: <b>{mobil_info['liters_consumed']}</b> L over <b>{mobil_info['distance_since_refill']}</b> km since last refill")
        await log_event(context, 'entry_edited',
            user_id=user_id, username=user.full_name,
            details=f"Entry #{entry_id} marked as last tour of the month",
            changes=[
                f"<code>is_last_tour</code> → <b>True</b>",
                f"<code>final_petrol_consumed</code> → <b>{petrol_info['liters_consumed']}</b> L",
                f"<code>final_mobil_consumed</code> → <b>{mobil_info['liters_consumed']}</b> L",
            ],
            effects=effects
        )
        
        consumption_text = ""
        if petrol_info['liters_consumed'] > 0:
            consumption_text += S('thresholds.final_petrol_consumed',
                liters=to_bn_number(petrol_info['liters_consumed']),
                km=to_bn_number(petrol_info['distance_since_refill']))
        if mobil_info['liters_consumed'] > 0:
            consumption_text += S('thresholds.final_mobil_consumed',
                liters=to_bn_number(mobil_info['liters_consumed']),
                km=to_bn_number(mobil_info['distance_since_refill']))
        
        msg = S('new_entry.last_tour_done') + consumption_text
        await query.edit_message_text(msg, parse_mode='HTML')
        schedule_message_cleanup(context, update.effective_chat.id)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=S('new_entry.back_to_menu_prompt'),
            reply_markup=BACK_TO_MENU
        )
    else:
        await query.edit_message_text(S('new_entry.last_tour_skipped'))
        schedule_message_cleanup(context, update.effective_chat.id)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=S('new_entry.back_to_menu_prompt'),
            reply_markup=BACK_TO_MENU
        )
        
    to_keep = ['selected_month', 'selected_year']
    kept_data = {k: context.user_data[k] for k in to_keep if k in context.user_data}
    context.user_data.clear()
    context.user_data.update(kept_data)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation."""
    exclude_id = update.callback_query.message.message_id if update.callback_query else None
    await delete_previous_messages(update, context, exclude=exclude_id)
    schedule_message_cleanup(context, update.effective_chat.id)
    msg = S('new_entry.cancelled')
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=BACK_TO_MENU)
    else:
        await update.message.reply_text(msg, reply_markup=BACK_TO_MENU)
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
            ENTER_ODO_END: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_odo_end),
                CallbackQueryHandler(handle_odo_end_back, pattern="^back$")
            ],
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
            SELECT_DISTRIBUTORS: [CallbackQueryHandler(handle_distributor_selection, pattern="^toggle_dist_|^dist_done|^cancel$|^back$")],
            CONFIRM_TRANSPORT_FEE: [CallbackQueryHandler(handle_transport_confirm, pattern="^transport_|^back$")],
            CONFIRM_ENTRY: [CallbackQueryHandler(save_entry_callback, pattern="^confirm_|^back$")],
            CONFIRM_LAST_TOUR: [CallbackQueryHandler(handle_last_tour_confirm, pattern="^last_tour_")],
            ENTER_VENUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_venue),
                CallbackQueryHandler(handle_type_selection, pattern="^back$")
            ],
            ENTER_TRANSPORT_FEE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_transport_fee),
                CallbackQueryHandler(handle_back_to_confirm_transport, pattern="^back$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(cancel, pattern="^cancel$")]
    )

