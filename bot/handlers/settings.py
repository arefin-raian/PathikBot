from telegram import Update
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters
)
from bot.inline_keyboards import (
    get_settings_keyboard, 
    get_yes_no_keyboard,
    BACK_TO_MENU,
    to_bn_number, 
    get_edit_delete_keyboard,
    get_entries_selection_keyboard,
    get_edit_fields_keyboard,
    get_confirmation_keyboard,
    get_distributor_mgmt_keyboard,
    get_distributor_keyboard
)
from bot.text_resources import S
from bot.auth import require_auth
from core.message_store import record_message
from bot.handlers.new_entry import schedule_message_cleanup
from core.audit_logger import log_event
from core.file_data_store import (
    get_entries, 
    delete_entry, 
    update_entry,
    update_entry_and_cascade, 
    get_entry_by_id,
    get_distributors,
    add_distributor,
    remove_distributor,
    get_user_prefs,
    set_user_prefs,
)
from core.expense_calculations import calculate_petrol_cost, calculate_mobil_cost, calculate_total_entry_cost, calculate_fuel_since_refill, calc_carry_forward, PETROL_THRESHOLD_KM, MOBIL_THRESHOLD_KM, DEFAULT_PETROL_PRICE, DEFAULT_MOBIL_PRICE
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
CONFIRM_UPDATE_OLD = 11
CONFIRM_RECALC = 12

async def edit_delete_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_auth(update, context): return ConversationHandler.END
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(S('settings.edit_delete_prompt'), reply_markup=get_edit_delete_keyboard())
    await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')

async def start_edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_auth(update, context): return ConversationHandler.END
    user_id = update.effective_user.id
    query = update.callback_query
    if query:
        await query.answer()
    
    entries = await get_entries(user_id)
    if not entries:
        no_entries_text = S('settings.no_entries')
        if query:
            await query.edit_message_text(no_entries_text, reply_markup=BACK_TO_MENU)
            await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        else:
            sent_msg = await update.message.reply_text(no_entries_text)
            await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
        return ConversationHandler.END
        
    edit_prompt_msg = S('settings.edit_prompt')
    kb = get_entries_selection_keyboard(entries[-15:], "edit", show_back=bool(query))
    if query:
        await query.edit_message_text(edit_prompt_msg, reply_markup=kb)
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
    else:
        sent_msg = await update.message.reply_text(edit_prompt_msg, reply_markup=kb)
        await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
    return CHOOSING_ENTRY_TO_EDIT

async def handle_edit_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit_delete_menu":
        await edit_delete_menu_handler(update, context)
        return ConversationHandler.END
    
    if query.data.startswith("edit_"):
        entry_id = int(query.data.split("_")[1])
        context.user_data['editing_id'] = entry_id
        await query.edit_message_text(S('settings.edit_field_prompt'), reply_markup=get_edit_fields_keyboard(entry_id))
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        return CHOOSING_FIELD_TO_EDIT

async def start_field_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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
        "mobil": S('settings.prompt_edit_mobil'),
        "desig": S('settings.prompt_edit_desig'),
    }
    
    if field == "dist":
        from bot.inline_keyboards import get_distributor_keyboard
        dists = await get_distributors()
        context.user_data['selected_dist_indices'] = []
        await query.edit_message_text(S('settings.edit_field_dist_prompt'), reply_markup=get_distributor_keyboard(dists))
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        return EDITING_DISTRIBUTORS
    
    await query.edit_message_text(prompts[field])
    await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
    return ENTERING_NEW_VALUE

async def handle_edit_distributors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        return EDITING_DISTRIBUTORS
    elif query.data == "dist_done":
        names = [dists[i] for i in selected]
        entry_id = context.user_data['editing_id']
        await update_entry_and_cascade(user_id, entry_id, {'distributors_raw': names})
        await query.edit_message_text(S('settings.edit_dist_success'))
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        return await start_edit_entry(update, context)
    elif query.data == "back":
        await query.edit_message_text(S('settings.edit_field_prompt'), reply_markup=get_edit_fields_keyboard(context.user_data['editing_id']))
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        return CHOOSING_FIELD_TO_EDIT
    elif query.data == "cancel":
        await query.edit_message_text(S('common.cancelled_plain'), reply_markup=BACK_TO_MENU)
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        return ConversationHandler.END

async def distributor_mgmt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_auth(update, context): return ConversationHandler.END
    user_id = update.effective_user.id
    query = update.callback_query
    if query: await query.answer()
    
    dists = await get_distributors()
    dist_mgmt_text = S('settings.dist_mgmt_title')
    
    if query:
        await query.edit_message_text(dist_mgmt_text, reply_markup=get_distributor_mgmt_keyboard(dists), parse_mode='HTML')
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
    else:
        sent_msg = await update.message.reply_text(dist_mgmt_text, reply_markup=get_distributor_mgmt_keyboard(dists), parse_mode='HTML')
        await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
    return MANAGING_DISTRIBUTORS

async def handle_distributor_mgmt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "settings":
        return await settings_handler(update, context)
        
    if query.data == "add_distributor":
        await query.edit_message_text(S('settings.dist_add_prompt'))
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        return ADDING_DISTRIBUTOR
        
    if query.data.startswith("remove_dist_"):
        idx = int(query.data.split("_")[2])
        dists = await get_distributors()
        if idx < 0 or idx >= len(dists):
            await query.edit_message_text(S('settings.dist_not_found'), reply_markup=get_distributor_mgmt_keyboard(dists))
            await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
            return MANAGING_DISTRIBUTORS
        name = dists[idx]
        await remove_distributor(name)
        dists = await get_distributors()
        await query.edit_message_text(S('settings.dist_removed', name=name), reply_markup=get_distributor_mgmt_keyboard(dists))
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        return MANAGING_DISTRIBUTORS
        
    return MANAGING_DISTRIBUTORS

async def handle_new_distributor_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text.strip()
    if name:
        await add_distributor(name)
        dists = await get_distributors()
        sent_msg = await update.message.reply_text(S('settings.dist_added', name=name), reply_markup=get_distributor_mgmt_keyboard(dists))
        await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
        return MANAGING_DISTRIBUTORS
    return ADDING_DISTRIBUTOR

async def handle_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    field = context.user_data.get('editing_field')
    entry_id = context.user_data.get('editing_id')

    # Text-only fields (no numeric parsing, no odometer cascade prompt).
    if field == "desig":
        raw = (update.message.text or "").strip()
        new_desig = "" if raw in ("-", "—", "–") else raw
        entry = await get_entry_by_id(user_id, entry_id)
        if not entry:
            sent_msg = await update.message.reply_text(S('settings.entry_not_found'), reply_markup=BACK_TO_MENU)
            await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
            return ConversationHandler.END
        old_desig = entry.get('others_designation', '')
        await update_entry_and_cascade(user_id, entry_id, {'others_designation': new_desig})
        user = update.effective_user
        await log_event(context, 'entry_edited',
            user_id=user_id, username=user.full_name,
            details=f"Entry #{entry_id} — Designation changed",
            changes=[f"Designation: <b>{old_desig or '∅'}</b> \u2192 <b>{new_desig or '∅'}</b>"]
        )
        sent_msg = await update.message.reply_text(S('settings.edit_desig_success'))
        await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
        return await start_edit_entry(update, context)

    from bot.handlers.new_entry import normalize_number
    try:
        val = float(normalize_number(update.message.text))
        
        entry = await get_entry_by_id(user_id, entry_id)
        if not entry:
            sent_msg = await update.message.reply_text(S('settings.entry_not_found'), reply_markup=BACK_TO_MENU)
            await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
            return ConversationHandler.END
            
        prefs = await get_user_prefs(user_id)
        petrol_price = float(prefs.get('petrol_price', DEFAULT_PETROL_PRICE))
        mobil_price = float(prefs.get('mobil_price', DEFAULT_MOBIL_PRICE))
        updates = {}
        if field == "km":
            updates['total_km'] = int(val)
        elif field == "start":
            updates['odo_start'] = int(val)
        elif field == "end":
            updates['odo_end'] = int(val)
        elif field == "petrol":
            updates['petrol_liters'] = val
            updates['petrol_cost'] = calculate_petrol_cost(val, petrol_price)
        elif field == "mobil":
            updates['mobil_liters'] = val
            updates['mobil_cost'] = calculate_mobil_cost(val, mobil_price)
            
        temp_entry = entry.copy()
        temp_entry.update(updates)
        updates['total_cost'] = calculate_total_entry_cost(
            temp_entry['entry_type'],
            temp_entry.get('petrol_liters', 0),
            temp_entry.get('mobil_liters', 0),
            temp_entry.get('da_amount'),
            temp_entry.get('transport_fee', 0),
            petrol_price=petrol_price,
            mobil_price=mobil_price
        )
        
        await update_entry_and_cascade(user_id, entry_id, updates)

        user = update.effective_user
        field_key_map = {'km': 'total_km', 'start': 'odo_start', 'end': 'odo_end', 'petrol': 'petrol_liters', 'mobil': 'mobil_liters'}
        entry_key = field_key_map.get(field, field)
        old_val = entry.get(entry_key, '')
        new_val = updates.get(entry_key, '')
        field_labels = {'km': 'Distance', 'start': 'Odometer Start', 'end': 'Odometer End', 'petrol': 'Petrol Liters', 'mobil': 'Mobil Liters'}
        flabel = field_labels.get(field, field)
        await log_event(context, 'entry_edited',
            user_id=user_id, username=user.full_name,
            details=f"Entry #{entry_id} — {flabel} changed",
            changes=[f"{flabel}: <b>{old_val}</b> \u2192 <b>{new_val}</b>"]
        )
        
        # If distance-affecting field, ask about recalc
        distance_fields = {'km', 'start', 'end'}
        if field in distance_fields:
            context.user_data['_recalc_entry_id'] = entry_id
            sent_msg = await update.message.reply_text(
                S('settings.recalc_prompt'),
                reply_markup=get_yes_no_keyboard('recalc')
            )
            await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
            return CONFIRM_RECALC
        
        sent_msg = await update.message.reply_text(S('settings.update_success'))
        await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
        return await start_edit_entry(update, context)
        
    except ValueError:
        sent_msg = await update.message.reply_text(S('new_entry.error_invalid_number'))
        await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
        return ENTERING_NEW_VALUE


async def handle_recalc_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "recalc_no":
        await query.edit_message_text(S('settings.recalc_skipped'))
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        return await start_edit_entry(update, context)
    
    if query.data == "recalc_yes":
        entry_id = context.user_data.get('_recalc_entry_id')
        affected_entries = await get_entries(user_id)
        if not affected_entries:
            await query.edit_message_text(S('settings.recalc_done'))
            await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
            return await start_edit_entry(update, context)
        
        sorted_entries = sorted(affected_entries, key=lambda e: e['date'])
        user = update.effective_user
        recalc_effects = []
        
        # Recalculate carry_forward for all entries after the edited one
        for i, e in enumerate(sorted_entries):
            if e.get('petrol_liters', 0) > 0:
                prev = sorted_entries[:i]
                new_overflow = calc_carry_forward(
                    prev, e.get('total_km', 0), 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM
                )
                old_overflow = e.get('petrol_overflow', 0)
                if old_overflow != new_overflow:
                    recalc_effects.append(f"Entry #{e['id']} petrol overflow: <b>{old_overflow}</b> \u2192 <b>{new_overflow}</b>")
                await update_entry(user_id, e['id'], {'petrol_overflow': new_overflow})
            
            if e.get('mobil_liters', 0) > 0:
                prev = sorted_entries[:i]
                new_overflow = calc_carry_forward(
                    prev, e.get('total_km', 0), 'mobil_liters', 'mobil_overflow', MOBIL_THRESHOLD_KM
                )
                old_overflow = e.get('mobil_overflow', 0)
                if old_overflow != new_overflow:
                    recalc_effects.append(f"Entry #{e['id']} mobil overflow: <b>{old_overflow}</b> \u2192 <b>{new_overflow}</b>")
                await update_entry(user_id, e['id'], {'mobil_overflow': new_overflow})
            
            if e.get('is_last_tour'):
                cur_and_prev = sorted_entries[:i+1]
                petrol_info = calculate_fuel_since_refill(cur_and_prev, 'petrol_liters', PETROL_THRESHOLD_KM)
                mobil_info = calculate_fuel_since_refill(cur_and_prev, 'mobil_liters', MOBIL_THRESHOLD_KM)
                old_p = e.get('final_petrol_consumed', 0)
                old_m = e.get('final_mobil_consumed', 0)
                if old_p != petrol_info['liters_consumed']:
                    recalc_effects.append(f"Entry #{e['id']} final petrol consumption: <b>{old_p}</b> L \u2192 <b>{petrol_info['liters_consumed']}</b> L")
                if old_m != mobil_info['liters_consumed']:
                    recalc_effects.append(f"Entry #{e['id']} final mobil consumption: <b>{old_m}</b> L \u2192 <b>{mobil_info['liters_consumed']}</b> L")
                await update_entry(user_id, e['id'], {
                    'final_petrol_consumed': petrol_info['liters_consumed'],
                    'final_mobil_consumed': mobil_info['liters_consumed']
                })
        
        if recalc_effects:
            await log_event(context, 'auto_recalc',
                user_id=user_id, username=user.full_name,
                details=f"Automatic recalculation triggered by edit of entry #{entry_id}",
                effects=recalc_effects
            )
        
        await query.edit_message_text(S('settings.recalc_done'))
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        return await start_edit_entry(update, context)
    
    return await start_edit_entry(update, context)

async def start_delete_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_auth(update, context): return ConversationHandler.END
    user_id = update.effective_user.id
    query = update.callback_query
    if query:
        await query.answer()
    
    entries = await get_entries(user_id)
    if not entries:
        no_entries_text = S('settings.no_entries')
        if query:
            await query.edit_message_text(no_entries_text, reply_markup=BACK_TO_MENU)
            await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        else:
            sent_msg = await update.message.reply_text(no_entries_text)
            await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
        return ConversationHandler.END
        
    delete_prompt_text = S('settings.delete_prompt')
    kb = get_entries_selection_keyboard(entries[-15:], "delete", show_back=bool(query))
    if query:
        await query.edit_message_text(delete_prompt_text, reply_markup=kb)
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
    else:
        sent_msg = await update.message.reply_text(delete_prompt_text, reply_markup=kb)
        await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
    return CHOOSING_ENTRY_TO_DELETE

async def handle_delete_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit_delete_menu":
        await edit_delete_menu_handler(update, context)
        return ConversationHandler.END
    
    entry_id = int(query.data.split("_")[1])
    context.user_data['deleting_id'] = entry_id
    
    await query.edit_message_text(S('settings.delete_confirm_prompt'), reply_markup=get_confirmation_keyboard('delete'))
    await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
    return CONFIRM_DELETE

async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        return await start_delete_entry(update, context)
    
    if query.data == "confirm_save":
        entry_id = context.user_data['deleting_id']
        entry_info = await get_entry_by_id(user_id, entry_id)
        await delete_entry(user_id, entry_id)
        user = update.effective_user
        await log_event(context, 'entry_deleted',
            user_id=user_id, username=user.full_name,
            details=f"Entry #{entry_id} deleted",
            changes=[
                f"Type: <b>{entry_info.get('entry_type', '?') if entry_info else '?'}</b>",
                f"Date: <b>{entry_info.get('date', '?') if entry_info else '?'}</b>",
                f"Distance: <b>{entry_info.get('total_km', '?') if entry_info else '?'}</b> km",
            ]
        )
        await query.edit_message_text(S('settings.delete_success'))
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        return await start_delete_entry(update, context)
    else:
        await query.edit_message_text(S('common.cancelled_plain'), reply_markup=BACK_TO_MENU)
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
        
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.pop('_settings_visited', None)
    schedule_message_cleanup(context, update.effective_chat.id)
    cancel_text = S('settings.cancelled')
    if update.callback_query:
        await update.callback_query.edit_message_text(cancel_text, reply_markup=BACK_TO_MENU)
        await record_message(user_id, update.callback_query.message.chat_id, update.callback_query.message.message_id, 'temporary')
    else:
        sent_msg = await update.message.reply_text(cancel_text, reply_markup=BACK_TO_MENU)
        await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
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
            EDITING_DISTRIBUTORS: [CallbackQueryHandler(handle_edit_distributors, pattern="^toggle_dist_|^dist_done|^cancel$|^back$")],
            CHOOSING_ENTRY_TO_DELETE: [CallbackQueryHandler(handle_delete_selection, pattern="^delete_|^edit_delete_menu$")],
            CONFIRM_DELETE: [CallbackQueryHandler(confirm_delete_callback, pattern="^confirm_|^back$")],
            CONFIRM_RECALC: [CallbackQueryHandler(handle_recalc_confirm, pattern="^recalc_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_auth(update, context): return ConversationHandler.END
    query = update.callback_query
    if query: await query.answer()
    
    # Context-aware: initial command entry → no back_to_menu;
    # menu callback or re-entry after navigation → show back_to_menu
    first_cmd_entry = query is None and '_settings_visited' not in context.user_data
    context.user_data['_settings_visited'] = True

    user_id = update.effective_user.id
    prefs = await get_user_prefs(user_id)
    petrol = prefs.get('petrol_price', '140.7')
    mobil = prefs.get('mobil_price', '560.0')
    da = prefs.get('da_amount', '200')
    transport = prefs.get('transport_fee', '460')
    pth = prefs.get('petrol_threshold', PETROL_THRESHOLD_KM)
    mth = prefs.get('mobil_threshold', MOBIL_THRESHOLD_KM)
    unset = S('settings.config_display_header_unset')
    h_company = prefs.get('header_company') or unset
    h_depot = prefs.get('header_depot') or unset
    h_moto = prefs.get('header_motorcycle') or unset
    h_name = prefs.get('header_name') or unset
    h_desig = prefs.get('header_designation') or unset

    text = (
        f"{S('settings.config_display_title')}\n\n"
        f"{S('settings.config_display_petrol', petrol=to_bn_number(petrol))}\n"
        f"{S('settings.config_display_mobil', mobil=to_bn_number(mobil))}\n"
        f"{S('settings.config_display_da', da=to_bn_number(da))}\n"
        f"{S('settings.config_display_transport', transport=to_bn_number(transport))}\n\n"
        f"{S('settings.config_display_petrol_th', v=to_bn_number(pth))}\n"
        f"{S('settings.config_display_mobil_th', v=to_bn_number(mth))}\n\n"
        f"{S('settings.config_display_header_company', v=h_company)}\n"
        f"{S('settings.config_display_header_depot', v=h_depot)}\n"
        f"{S('settings.config_display_header_motorcycle', v=h_moto)}\n"
        f"{S('settings.config_display_header_name', v=h_name)}\n"
        f"{S('settings.config_display_header_designation', v=h_desig)}\n\n"
        f"{S('settings.config_display_action')}"
    )
    
    reply_markup = get_settings_keyboard(show_back_to_menu=not first_cmd_entry)
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
    else:
        sent_msg = await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
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
    if not await require_auth(update, context): return ConversationHandler.END
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    setting_map = {
        "set_petrol_price": ("petrol_price", S('settings.prompt_petrol')),
        "set_mobil_price": ("mobil_price", S('settings.prompt_mobil')),
        "set_da_rate": ("da_amount", S('settings.prompt_da')),
        "set_transport_fee": ("transport_fee", S('settings.prompt_transport')),
        "set_petrol_threshold": ("petrol_threshold", S('settings.prompt_petrol_threshold')),
        "set_mobil_threshold": ("mobil_threshold", S('settings.prompt_mobil_threshold')),
        "set_header_company": ("header_company", S('settings.prompt_header_company')),
        "set_header_depot": ("header_depot", S('settings.prompt_header_depot')),
        "set_header_motorcycle": ("header_motorcycle", S('settings.prompt_header_motorcycle')),
        "set_header_name": ("header_name", S('settings.prompt_header_name')),
        "set_header_designation": ("header_designation", S('settings.prompt_header_designation')),
    }
    
    prefs_key, prompt = setting_map[query.data]
    context.user_data['changing_setting'] = prefs_key
    
    await query.edit_message_text(prompt)
    await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
    return SETTING_VALUE

async def handle_setting_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    value = update.message.text
    key = context.user_data.get('changing_setting')
    if not key:
        return await settings_handler(update, context)
    
    user = update.effective_user
    prefs_before = await get_user_prefs(user_id)
    old_val = prefs_before.get(key, '')
    TEXT_KEYS = {'header_company', 'header_depot', 'header_motorcycle', 'header_name', 'header_designation'}
    if key in TEXT_KEYS:
        value = (value or '').strip()
    else:
        try:
            if key in ('da_amount', 'transport_fee', 'petrol_threshold', 'mobil_threshold'):
                value = int(value)
            elif key in ('petrol_price', 'mobil_price'):
                value = float(value)
        except ValueError:
            sent_msg = await update.message.reply_text(S('settings.error_invalid_number'))
            await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
            return SETTING_VALUE
    prefs_before[key] = value
    await set_user_prefs(user_id, prefs_before)
    setting_labels = {
        'petrol_price': 'Petrol Price', 'mobil_price': 'Mobil Price',
        'da_amount': 'DA Amount', 'transport_fee': 'Transport Fee',
        'petrol_threshold': 'Petrol Threshold (km)', 'mobil_threshold': 'Mobil Threshold (km)',
        'header_company': 'Header Company', 'header_depot': 'Header Depot',
        'header_motorcycle': 'Header Motorcycle', 'header_name': 'Header Officer Name',
        'header_designation': 'Header Designation',
    }
    await log_event(context, 'settings_changed',
        user_id=user_id, username=user.full_name,
        details=f"{setting_labels.get(key, key)} changed",
        changes=[f"<b>{old_val}</b> \u2192 <b>{value}</b>"]
    )
    sent_msg = await update.message.reply_text(S('settings.setting_changed', value=value), parse_mode='HTML')
    await record_message(user_id, sent_msg.chat_id, sent_msg.message_id, 'temporary')
    
    if key in ('petrol_price', 'mobil_price'):
        context.user_data['_price_key'] = key
        context.user_data['_price_value'] = value
        sent_msg2 = await update.message.reply_text(
            S('settings.update_old_prompt'),
            reply_markup=get_yes_no_keyboard('update_old'),
            parse_mode='HTML'
        )
        await record_message(user_id, sent_msg2.chat_id, sent_msg2.message_id, 'temporary')
        return CONFIRM_UPDATE_OLD
    
    return await settings_handler(update, context)

async def handle_update_old_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    if query.data == "update_old_no":
        return await settings_handler(update, context)
    
    if query.data == "update_old_yes":
        key = context.user_data.get('_price_key')
        value = context.user_data.get('_price_value')
        try:
            value_float = float(value)
        except (ValueError, TypeError):
            return await settings_handler(update, context)
        
        cost_field = 'petrol_cost' if key == 'petrol_price' else 'mobil_cost'
        liters_field = 'petrol_liters' if key == 'petrol_price' else 'mobil_liters'
        
        now = datetime.now()
        entries = await get_entries(user_id, now.month, now.year)
        updated_count = 0
        for entry in entries:
            liters = entry.get(liters_field, 0)
            if liters > 0:
                if key == 'petrol_price':
                    new_cost = calculate_petrol_cost(liters, value_float)
                else:
                    new_cost = calculate_mobil_cost(liters, value_float)
                
                old_total = entry.get('total_cost', 0)
                old_cost = entry.get(cost_field, 0)
                delta = new_cost - old_cost
                
                await update_entry_and_cascade(user_id, entry['id'], {
                    cost_field: new_cost,
                    'total_cost': old_total + delta
                })
                updated_count += 1
        
        user = update.effective_user
        await log_event(context, 'auto_recalc',
            user_id=user_id, username=user.full_name,
            details=f"Price change propagated to {updated_count} existing entries this month",
            effects=[
                f"<b>{updated_count}</b> entries had their {cost_field} recalculated with new price <b>{value}</b>"
            ]
        )
        
        await query.edit_message_text(S('settings.update_old_updated'), parse_mode='HTML')
        await record_message(user_id, query.message.chat_id, query.message.message_id, 'temporary')
    
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
            CONFIRM_UPDATE_OLD: [CallbackQueryHandler(handle_update_old_confirm, pattern="^update_old_|^back$")],
            MANAGING_DISTRIBUTORS: [CallbackQueryHandler(handle_distributor_mgmt_callback)],
            ADDING_DISTRIBUTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_distributor_name)]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
