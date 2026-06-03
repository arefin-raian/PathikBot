from telegram import Update
from telegram.ext import ContextTypes
from core.database import get_entries
from core.calculations import calculate_summary
from bot.keyboards import to_bn_number, BACK_TO_MENU
from bot.strings import S
from datetime import datetime

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

async def list_entries_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    year, month = None, None
    if query:
        await query.answer()
        if query.data.startswith("list_entries_"):
            parts = query.data.split("_")
            year, month = int(parts[2]), int(parts[3])
    
    entries = await get_entries(month, year)
    if not entries:
        msg = S('summary.no_entries')
        if query:
            await query.edit_message_text(msg, reply_markup=BACK_TO_MENU)
        else:
            await update.message.reply_text(msg)
        return

    display_entries = entries if (month and year) else entries[-10:]
    chat_id = update.effective_chat.id

    for i, e in enumerate(display_entries, 1):
        await send_entry_message(context, chat_id, i, e, first_entry=(i == 1), query=query)

    # Context-aware: command → no back button; menu callback → show back button
    reply_markup = BACK_TO_MENU if query else None
    await send_summary_message(context, chat_id, display_entries, reply_markup=reply_markup)

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
