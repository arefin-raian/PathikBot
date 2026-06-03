import os
from telegram import Update
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters
)
from bot.keyboards import (
    get_settings_keyboard, 
    BACK_TO_MENU,
    to_bn_number, 
    get_edit_delete_keyboard,
    get_entries_selection_keyboard,
    get_edit_fields_keyboard,
    get_confirmation_keyboard,
    get_distributor_mgmt_keyboard,
    get_distributor_keyboard
)
from bot.strings import S
from core.database import (
    get_entries, 
    delete_entry, 
    update_entry_and_cascade, 
    get_entry_by_id,
    get_distributors,
    add_distributor,
    remove_distributor
)
from core.calculations import calculate_petrol_cost, calculate_mobil_cost, calculate_total_entry_cost
from datetime import datetime

# States for settings and edit/delete
SETTING_VALUE = 1
CHOOSING_ENTRY_TO_EDIT = 2
CHOOSING_FIELD_TO_EDIT = 3
ENTERING_NEW_VALUE = 4
CHOOSING_ENTRY_TO_DELETE = 5
CONFIRM_DELETE = 6
EDITING_DISTRIBUTORS = 7
MANAGING_DISTRIBUTORS = 8
ADDING_DISTRIBUTOR = 9
SHOWING_SETTINGS = 10

async def edit_delete_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(S('settings.edit_delete_prompt'), reply_markup=get_edit_delete_keyboard())

async def start_edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    entries = await get_entries()
    if not entries:
        msg = S('settings.no_entries')
        if query:
            await query.edit_message_text(msg, reply_markup=BACK_TO_MENU)
        else:
            await update.message.reply_text(msg)
        return ConversationHandler.END
        
    msg = S('settings.edit_prompt')
    kb = get_entries_selection_keyboard(entries[-15:], "edit", show_back=bool(query))
    if query:
        await query.edit_message_text(msg, reply_markup=kb)
    else:
        await update.message.reply_text(msg, reply_markup=kb)
    return CHOOSING_ENTRY_TO_EDIT

async def handle_edit_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit_delete_menu":
        await edit_delete_menu_handler(update, context)
        return ConversationHandler.END
    
    if query.data.startswith("edit_"):
        entry_id = int(query.data.split("_")[1])
        context.user_data['editing_id'] = entry_id
        await query.edit_message_text(S('settings.edit_field_prompt'), reply_markup=get_edit_fields_keyboard(entry_id))
        return CHOOSING_FIELD_TO_EDIT

async def start_field_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit_entry":
        return await start_edit_entry(update, context)
    
    parts = query.data.split("_")
    field = parts[2]
    entry_id = int(parts[3])
    
    context.user_data['editing_field'] = field
    
    prompts = {
        "km": S('settings.prompt_edit_km'),
        "start": S('settings.prompt_edit_start'),
        "end": S('settings.prompt_edit_end'),
        "petrol": S('settings.prompt_edit_petrol'),
        "mobil": S('settings.prompt_edit_mobil')
    }
    
    if field == "dist":
        from bot.keyboards import get_distributor_keyboard
        context.user_data['selected_dist_indices'] = []
        await query.edit_message_text(S('settings.edit_field_dist_prompt'), reply_markup=get_distributor_keyboard())
        return EDITING_DISTRIBUTORS
    
    await query.edit_message_text(prompts[field])
    return ENTERING_NEW_VALUE

async def handle_edit_distributors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
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
        return EDITING_DISTRIBUTORS
    elif query.data == "dist_done":
        names = [dists[i] for i in selected]
        entry_id = context.user_data['editing_id']
        await update_entry_and_cascade(entry_id, {'distributors_raw': names})
        await query.edit_message_text(S('settings.edit_dist_success'))
        return await start_edit_entry(update, context)
    elif query.data == "back":
        await query.edit_message_text(S('settings.edit_field_prompt'), reply_markup=get_edit_fields_keyboard(context.user_data['editing_id']))
        return CHOOSING_FIELD_TO_EDIT
    elif query.data == "cancel":
        await query.edit_message_text(S('common.cancelled_plain'), reply_markup=BACK_TO_MENU)
        return ConversationHandler.END

async def distributor_mgmt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    dists = await get_distributors()
    msg = S('settings.dist_mgmt_title')
    
    if query:
        await query.edit_message_text(msg, reply_markup=get_distributor_mgmt_keyboard(dists), parse_mode='HTML')
    else:
        await update.message.reply_text(msg, reply_markup=get_distributor_mgmt_keyboard(dists), parse_mode='HTML')
    return MANAGING_DISTRIBUTORS

async def handle_distributor_mgmt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "settings":
        return await settings_handler(update, context)
        
    if query.data == "add_distributor":
        await query.edit_message_text(S('settings.dist_add_prompt'))
        return ADDING_DISTRIBUTOR
        
    if query.data.startswith("remove_dist_"):
        idx = int(query.data.split("_")[2])
        dists = await get_distributors()
        if idx < 0 or idx >= len(dists):
            await query.edit_message_text(S('settings.dist_not_found'), reply_markup=get_distributor_mgmt_keyboard(dists))
            return MANAGING_DISTRIBUTORS
        name = dists[idx]
        await remove_distributor(name)
        dists = await get_distributors()
        await query.edit_message_text(S('settings.dist_removed', name=name), reply_markup=get_distributor_mgmt_keyboard(dists))
        return MANAGING_DISTRIBUTORS
        
    return MANAGING_DISTRIBUTORS

async def handle_new_distributor_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if name:
        await add_distributor(name)
        dists = await get_distributors()
        await update.message.reply_text(S('settings.dist_added', name=name), reply_markup=get_distributor_mgmt_keyboard(dists))
        return MANAGING_DISTRIBUTORS
    return ADDING_DISTRIBUTOR

async def handle_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.handlers.new_entry import normalize_number
    try:
        val = float(normalize_number(update.message.text))
        field = context.user_data['editing_field']
        entry_id = context.user_data['editing_id']
        
        entry = await get_entry_by_id(entry_id)
        if not entry:
            await update.message.reply_text(S('settings.entry_not_found'), reply_markup=BACK_TO_MENU)
            return ConversationHandler.END
            
        updates = {}
        if field == "km":
            updates['total_km'] = int(val)
        elif field == "start":
            updates['odo_start'] = int(val)
        elif field == "end":
            updates['odo_end'] = int(val)
        elif field == "petrol":
            updates['petrol_liters'] = val
            updates['petrol_cost'] = calculate_petrol_cost(val)
        elif field == "mobil":
            updates['mobil_liters'] = val
            updates['mobil_cost'] = calculate_mobil_cost(val)
            
        temp_entry = entry.copy()
        temp_entry.update(updates)
        updates['total_cost'] = calculate_total_entry_cost(
            temp_entry['entry_type'],
            temp_entry.get('petrol_liters', 0),
            temp_entry.get('mobil_liters', 0),
            temp_entry.get('da_amount'),
            temp_entry.get('transport_fee', 0)
        )
        
        await update_entry_and_cascade(entry_id, updates)
        await update.message.reply_text(S('settings.update_success'))
        return await start_edit_entry(update, context)
        
    except ValueError:
        await update.message.reply_text(S('new_entry.error_invalid_number'))
        return ENTERING_NEW_VALUE

async def start_delete_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    entries = await get_entries()
    if not entries:
        msg = S('settings.no_entries')
        if query:
            await query.edit_message_text(msg, reply_markup=BACK_TO_MENU)
        else:
            await update.message.reply_text(msg)
        return ConversationHandler.END
        
    msg = S('settings.delete_prompt')
    kb = get_entries_selection_keyboard(entries[-15:], "delete", show_back=bool(query))
    if query:
        await query.edit_message_text(msg, reply_markup=kb)
    else:
        await update.message.reply_text(msg, reply_markup=kb)
    return CHOOSING_ENTRY_TO_DELETE

async def handle_delete_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit_delete_menu":
        await edit_delete_menu_handler(update, context)
        return ConversationHandler.END
    
    entry_id = int(query.data.split("_")[1])
    context.user_data['deleting_id'] = entry_id
    
    await query.edit_message_text(S('settings.delete_confirm_prompt'), reply_markup=get_confirmation_keyboard())
    return CONFIRM_DELETE

async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        return await start_delete_entry(update, context)
    
    if query.data == "confirm_save":
        entry_id = context.user_data['deleting_id']
        await delete_entry(entry_id)
        await query.edit_message_text(S('settings.delete_success'))
        return await start_delete_entry(update, context)
    else:
        await query.edit_message_text(S('common.cancelled_plain'), reply_markup=BACK_TO_MENU)
        
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('_settings_visited', None)
    msg = S('settings.cancelled')
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=BACK_TO_MENU)
    else:
        await update.message.reply_text(msg, reply_markup=BACK_TO_MENU)
    return ConversationHandler.END

def get_edit_delete_conv_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(edit_delete_menu_handler, pattern="^edit_delete_menu$"),
            CallbackQueryHandler(start_edit_entry, pattern="^edit_entry$"),
            CallbackQueryHandler(start_delete_entry, pattern="^delete_entry$"),
            CommandHandler("editentry", start_edit_entry),
            CommandHandler("delentry", start_delete_entry)
        ],
        states={
            CHOOSING_ENTRY_TO_EDIT: [CallbackQueryHandler(handle_edit_selection, pattern="^edit_|^edit_delete_menu$")],
            CHOOSING_FIELD_TO_EDIT: [CallbackQueryHandler(start_field_edit, pattern="^edit_field_|^edit_entry$")],
            ENTERING_NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_value)],
            EDITING_DISTRIBUTORS: [CallbackQueryHandler(handle_edit_distributors, pattern="^toggle_dist_|^dist_done|^cancel$")],
            CHOOSING_ENTRY_TO_DELETE: [CallbackQueryHandler(handle_delete_selection, pattern="^delete_|^edit_delete_menu$")],
            CONFIRM_DELETE: [CallbackQueryHandler(confirm_delete_callback, pattern="^confirm_|^back$")],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    # Context-aware: initial command entry → no back_to_menu;
    # menu callback or re-entry after navigation → show back_to_menu
    first_cmd_entry = query is None and '_settings_visited' not in context.user_data
    context.user_data['_settings_visited'] = True

    petrol = os.getenv('PETROL_PRICE_PER_LITER', '140.7')
    mobil = os.getenv('MOBIL_PRICE_PER_LITER', '560.0')
    da = os.getenv('DA_AMOUNT', '200')
    transport = os.getenv('TRANSPORT_FEE', '460')
    
    text = (
        f"{S('settings.config_display_title')}\n\n"
        f"{S('settings.config_display_petrol', petrol=to_bn_number(petrol))}\n"
        f"{S('settings.config_display_mobil', mobil=to_bn_number(mobil))}\n"
        f"{S('settings.config_display_da', da=to_bn_number(da))}\n"
        f"{S('settings.config_display_transport', transport=to_bn_number(transport))}\n\n"
        f"{S('settings.config_display_action')}"
    )
    
    reply_markup = get_settings_keyboard(show_back_to_menu=not first_cmd_entry)
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    return SHOWING_SETTINGS

async def handle_settings_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return SHOWING_SETTINGS

    if query.data == "main_menu":
        context.user_data.pop('_settings_visited', None)
        from bot.handlers.start import main_menu_callback
        await main_menu_callback(update, context)
        return ConversationHandler.END

    if query.data.startswith("set_"):
        return await start_setting_change(update, context)

    if query.data == "manage_distributors":
        return await distributor_mgmt_handler(update, context)

    return SHOWING_SETTINGS

async def start_setting_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    setting_map = {
        "set_petrol_price": ("PETROL_PRICE_PER_LITER", S('settings.prompt_petrol')),
        "set_mobil_price": ("MOBIL_PRICE_PER_LITER", S('settings.prompt_mobil')),
        "set_da_rate": ("DA_AMOUNT", S('settings.prompt_da')),
        "set_transport_fee": ("TRANSPORT_FEE", S('settings.prompt_transport'))
    }
    
    env_key, prompt = setting_map[query.data]
    context.user_data['changing_setting'] = env_key
    
    await query.edit_message_text(prompt)
    return SETTING_VALUE

async def handle_setting_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text
    key = context.user_data.get('changing_setting')
    if key:
        os.environ[key] = value
    
    await update.message.reply_text(S('settings.setting_changed', value=value), parse_mode='HTML')
    return await settings_handler(update, context)

def get_settings_conv_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler("settings", settings_handler),
            CallbackQueryHandler(settings_handler, pattern="^settings$"),
            CallbackQueryHandler(start_setting_change, pattern="^set_"),
            CallbackQueryHandler(distributor_mgmt_handler, pattern="^manage_distributors$")
        ],
        states={
            SHOWING_SETTINGS: [CallbackQueryHandler(handle_settings_navigation, pattern="^set_|^manage_distributors$|^main_menu$")],
            SETTING_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_setting_value)],
            MANAGING_DISTRIBUTORS: [CallbackQueryHandler(handle_distributor_mgmt_callback)],
            ADDING_DISTRIBUTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_distributor_name)]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
