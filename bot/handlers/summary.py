from telegram import Update
from telegram.ext import ContextTypes
from core.database import get_entries, get_user_prefs, set_user_prefs
from core.calculations import calculate_summary
from bot.keyboards import to_bn_number, BACK_TO_MENU, FILTER_KEYS, get_list_entries_choice_keyboard, get_filter_checkboxes_keyboard
from bot.strings import S
from datetime import datetime

def matches_filter(entry, selected):
    if not any(selected.get(k, False) for k in FILTER_KEYS):
        return False
    result = False
    if selected.get('petrol', False):
        result = result or (entry.get('petrol_liters', 0) > 0)
    if selected.get('mobil', False):
        result = result or (entry.get('mobil_liters', 0) > 0)
    if selected.get('meeting', False):
        result = result or (entry.get('entry_type') == 'MONTHLY_MEETING')
    if selected.get('manager', False):
        result = result or bool(entry.get('others_designation', ''))
    return result

async def send_entry_message(context, chat_id, i, e, first_entry=False, query=None):
    dt = datetime.strptime(e['date'], '%Y-%m-%d')
    dt_str = to_bn_number(dt.strftime('%d/%m/%y'))
    if e['entry_type'] == 'REGULAR':
        petrol_l = e.get('petrol_liters', 0)
        mobil_l = e.get('mobil_liters', 0)
        petrol_line = S('summary.entry_petrol_line', liters=to_bn_number(petrol_l), cost=to_bn_number(e['petrol_cost'])) if petrol_l else ""
        mobil_line = S('summary.entry_mobil_line', liters=to_bn_number(mobil_l), cost=to_bn_number(e['mobil_cost'])) if mobil_l else ""
        dist_block = ""
        if e.get('distributors_raw'):
            dist_block = "<blockquote expandable>"
            for dist in e['distributors_raw']:
                dist_block += S('summary.entry_distributor_line', name=dist)
            dist_block += "</blockquote>"
        text = (
            S('summary.entry_header_regular', index=to_bn_number(i), date=dt_str) + "\n" +
            S('summary.entry_body_regular',
                odo_start=to_bn_number(e['odo_start']),
                odo_end=to_bn_number(e['odo_end']),
                total_km=to_bn_number(e['total_km']),
                petrol_line=petrol_line,
                mobil_line=mobil_line,
                da_amount=to_bn_number(e['da_amount']),
                total_cost=to_bn_number(e['total_cost']),
                distributors_block=dist_block)
        )
    else:
        text = (
            S('summary.entry_header_meeting', index=to_bn_number(i), date=dt_str) + "\n" +
            S('summary.entry_body_meeting',
                odo_start=to_bn_number(e['odo_start']),
                odo_end=to_bn_number(e['odo_end']),
                total_km=to_bn_number(e['total_km']),
                da_amount=to_bn_number(e['da_amount']),
                transport_fee=to_bn_number(e.get('transport_fee', 0)),
                venue=e.get('venue', ''),
                total_cost=to_bn_number(e['total_cost']))
        )

    if first_entry and query:
        await query.edit_message_text(text, parse_mode='HTML')
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')

async def send_summary_message(context, chat_id, entries, reply_markup=None):
    summary = calculate_summary(entries)
    text = (
        f"{S('summary.summary_header')}\n"
        f"{S('summary.summary_line_total_tour', total_tour=to_bn_number(summary['total_tour']))}\n"
        f"{S('summary.summary_line_total_km', total_km=to_bn_number(summary['total_km']))}\n"
        f"{S('summary.summary_line_petrol', liters=to_bn_number(summary['total_liters_petrol']), cost=to_bn_number(summary['total_petrol_cost']))}\n"
        f"{S('summary.summary_line_mobil', liters=to_bn_number(summary['total_liters_mobil']), cost=to_bn_number(summary['total_mobil_cost']))}\n"
        f"{S('summary.summary_line_da', da=to_bn_number(summary['total_da']))}\n"
        f"{S('summary.summary_line_transport', transport=to_bn_number(summary['total_others']))}\n"
        f"{S('summary.summary_line_grand_total', grand_total=to_bn_number(summary['grand_total']))}"
    )
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode='HTML')

async def display_entries(update, context, entries, query=None):
    chat_id = update.effective_chat.id
    for i, e in enumerate(entries, 1):
        await send_entry_message(context, chat_id, i, e, first_entry=(i == 1), query=query)
    reply_markup = BACK_TO_MENU if query else None
    await send_summary_message(context, chat_id, entries, reply_markup=reply_markup)

async def show_filter_choice(update, context, query=None):
    user_id = update.effective_user.id
    prefs = await get_user_prefs(user_id)
    saved = prefs.get('list_filters', {})
    has_saved = any(saved.get(k, False) for k in FILTER_KEYS)
    text = S('list_entries.choose_option')
    if has_saved:
        names = []
        if saved.get('petrol'): names.append(S('keyboards.list_entries.filter_petrol'))
        if saved.get('mobil'): names.append(S('keyboards.list_entries.filter_mobil'))
        if saved.get('meeting'): names.append(S('keyboards.list_entries.filter_meeting'))
        if saved.get('manager'): names.append(S('keyboards.list_entries.filter_manager'))
        text += "\n\n" + S('list_entries.last_filter_hint', filter_names=", ".join(names))
    if query:
        await query.edit_message_text(text, reply_markup=get_list_entries_choice_keyboard(saved))
    else:
        await update.message.reply_text(text, reply_markup=get_list_entries_choice_keyboard(saved))

async def list_entries_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        data = query.data
        parts = data.split("_")

        # 1. Archive month: list_entries_2026_6 — show entries directly
        if len(parts) >= 4 and parts[2].isdigit() and parts[3].isdigit():
            year, month = int(parts[2]), int(parts[3])
            entries = await get_entries(month, year)
            if not entries:
                await query.edit_message_text(S('summary.no_entries'), reply_markup=BACK_TO_MENU)
                return
            await display_entries(update, context, entries, query)
            return

        # 2. Main menu → show filter choice
        if data == "list_entries":
            await show_filter_choice(update, context, query)
            return

        # 3. All entries
        if data == "list_entries_all":
            entries = await get_entries()
            if not entries:
                await query.edit_message_text(S('summary.no_entries'), reply_markup=BACK_TO_MENU)
                return
            await display_entries(update, context, entries, query)
            return

        # 4. Use last saved filter
        if data == "list_entries_last_filter":
            prefs = await get_user_prefs(update.effective_user.id)
            filters = prefs.get('list_filters', {})
            entries = await get_entries()
            filtered = [e for e in entries if matches_filter(e, filters)]
            if not filtered:
                await query.edit_message_text(S('list_entries.no_matches'), reply_markup=BACK_TO_MENU)
                return
            await display_entries(update, context, filtered, query)
            return

        # 5. Show filter checkboxes
        if data == "list_entries_filter":
            prefs = await get_user_prefs(update.effective_user.id)
            saved = prefs.get('list_filters', {})
            context.user_data['list_filter_state'] = dict(saved)
            await query.edit_message_text(S('list_entries.filter_title'), reply_markup=get_filter_checkboxes_keyboard(saved))
            return

        # 6. Toggle a filter checkbox
        if data.startswith("list_entries_filter_toggle_"):
            idx = int(data.split("_")[-1])
            key = FILTER_KEYS[idx]
            state = context.user_data.get('list_filter_state', {})
            state[key] = not state.get(key, False)
            context.user_data['list_filter_state'] = state
            await query.edit_message_text(S('list_entries.filter_title'), reply_markup=get_filter_checkboxes_keyboard(state))
            return

        # 7. Apply filter
        if data == "list_entries_filter_apply":
            state = context.user_data.get('list_filter_state', {})
            prefs = await get_user_prefs(update.effective_user.id)
            prefs['list_filters'] = state
            await set_user_prefs(update.effective_user.id, prefs)
            entries = await get_entries()
            filtered = [e for e in entries if matches_filter(e, state)]
            if not filtered:
                await query.edit_message_text(S('list_entries.no_matches'), reply_markup=BACK_TO_MENU)
                return
            await display_entries(update, context, filtered, query)
            return

        # 8. Back from filter checkboxes
        if data == "list_entries_filter_back":
            await show_filter_choice(update, context, query)
            return

    else:
        # Slash command: /listentries
        entries = await get_entries()
        if not entries:
            await update.message.reply_text(S('summary.no_entries'))
            return
        await show_filter_choice(update, context)

async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    year, month = None, None
    if query:
        await query.answer()
        if query.data.startswith("summary_"):
            parts = query.data.split("_")
            year, month = int(parts[1]), int(parts[2])
    
    entries = await get_entries(month, year)
    if not entries:
        msg = S('summary.no_entries')
        if query:
            await query.edit_message_text(msg, reply_markup=BACK_TO_MENU)
        else:
            await update.message.reply_text(msg)
        return

    summary = calculate_summary(entries)
    text = (
        f"{S('summary.summary_header')}\n"
        f"{S('summary.summary_line_total_tour', total_tour=to_bn_number(summary['total_tour']))}\n"
        f"{S('summary.summary_line_total_km', total_km=to_bn_number(summary['total_km']))}\n"
        f"{S('summary.summary_line_petrol', liters=to_bn_number(summary['total_liters_petrol']), cost=to_bn_number(summary['total_petrol_cost']))}\n"
        f"{S('summary.summary_line_mobil', liters=to_bn_number(summary['total_liters_mobil']), cost=to_bn_number(summary['total_mobil_cost']))}\n"
        f"{S('summary.summary_line_da', da=to_bn_number(summary['total_da']))}\n"
        f"{S('summary.summary_line_transport', transport=to_bn_number(summary['total_others']))}\n"
        f"{S('summary.summary_line_grand_total', grand_total=to_bn_number(summary['grand_total']))}"
    )
    reply_markup = BACK_TO_MENU if query else None
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
