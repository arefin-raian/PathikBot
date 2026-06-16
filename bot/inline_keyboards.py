from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import calendar
from datetime import datetime
from bot.text_resources import S

MONTHS_BN_FULL = {
    1: "জানুয়ারি", 2: "ফেব্রুয়ারি", 3: "মার্চ", 4: "এপ্রিল",
    5: "মে", 6: "জুন", 7: "জুলাই", 8: "আগস্ট",
    9: "সেপ্টেম্বর", 10: "অক্টোবর", 11: "নভেম্বর", 12: "ডিসেম্বর"
}

BN_DIGITS = {'0':'০', '1':'১', '2':'২', '3':'৩', '4':'৪', '5':'৫', '6':'৬', '7':'৭', '8':'৮', '9':'৯'}

def to_bn_number(number):
    return "".join(BN_DIGITS.get(d, d) for d in str(number))

BACK_TO_MENU = InlineKeyboardMarkup([[InlineKeyboardButton(S('common.back_to_menu'), callback_data="main_menu")]])

def get_main_menu():
    b = S('keyboards.main_menu_buttons')
    keyboard = [
        [InlineKeyboardButton(b['new_entry'], callback_data="new_entry")],
        [InlineKeyboardButton(b['list_entries'], callback_data="list_entries")],
        [InlineKeyboardButton(b['summary'], callback_data="summary")],
        [InlineKeyboardButton(b['archive_menu'], callback_data="archive_menu")],
        [InlineKeyboardButton(b['edit_delete'], callback_data="edit_delete_menu")],
        [InlineKeyboardButton(b['generate_report'], callback_data="generate_report")],
        [InlineKeyboardButton(b['settings'], callback_data="settings")],
        [InlineKeyboardButton(b['help'], callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_edit_delete_keyboard():
    b = S('keyboards.edit_delete')
    keyboard = [
        [InlineKeyboardButton(b['edit'], callback_data="edit_entry")],
        [InlineKeyboardButton(b['delete'], callback_data="delete_entry")],
        [InlineKeyboardButton(b['back_to_menu'], callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_entries_selection_keyboard(entries, action_prefix, show_back=True):
    keyboard = []
    fmt = S('keyboards.entry_selection.label')
    back_btn = S('keyboards.entry_selection.back')
    for e in entries:
        dt = datetime.strptime(e['date'], '%Y-%m-%d')
        label = fmt.format(date=to_bn_number(dt.strftime('%d/%m/%y')), cost=to_bn_number(e['total_cost']))
        keyboard.append([InlineKeyboardButton(label, callback_data=f"{action_prefix}_{e['id']}")])

    if show_back:
        keyboard.append([InlineKeyboardButton(back_btn, callback_data="edit_delete_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_edit_fields_keyboard(entry_id):
    b = S('keyboards.edit_fields')
    keyboard = [
        [InlineKeyboardButton(b['km'], callback_data=f"edit_field_km_{entry_id}")],
        [InlineKeyboardButton(b['start'], callback_data=f"edit_field_start_{entry_id}")],
        [InlineKeyboardButton(b['end'], callback_data=f"edit_field_end_{entry_id}")],
        [InlineKeyboardButton(b['dist'], callback_data=f"edit_field_dist_{entry_id}")],
        [InlineKeyboardButton(b['petrol'], callback_data=f"edit_field_petrol_{entry_id}")],
        [InlineKeyboardButton(b['mobil'], callback_data=f"edit_field_mobil_{entry_id}")],
        [InlineKeyboardButton(b['desig'], callback_data=f"edit_field_desig_{entry_id}")],
        [InlineKeyboardButton(b['back'], callback_data="edit_entry")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_entry_type_keyboard():
    b = S('keyboards.entry_type')
    keyboard = [
        [InlineKeyboardButton(b['regular'], callback_data="type_regular")],
        [InlineKeyboardButton(b['meeting'], callback_data="type_meeting")],
        [InlineKeyboardButton(b['cancel'], callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_month_selection_keyboard(include_more=True):
    now = datetime.now()
    keyboard = []
    m1, y1 = now.month, now.year

    current_label = S('keyboards.month_selection.current_month', month_name=MONTHS_BN_FULL[m1], year=to_bn_number(y1))
    keyboard.append([InlineKeyboardButton(current_label, callback_data=f"select_month_{y1}_{m1}")])
    if include_more:
        more_label = S('keyboards.month_selection.more_options')
        keyboard.append([InlineKeyboardButton(more_label, callback_data="show_more_months")])

    cancel_label = S('keyboards.month_selection.cancel')
    keyboard.append([InlineKeyboardButton(cancel_label, callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def get_all_months_keyboard(year):
    keyboard = []
    row = []
    for m in range(1, 13):
        row.append(InlineKeyboardButton(MONTHS_BN_FULL[m], callback_data=f"select_month_{year}_{m}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    back_label = S('keyboards.month_selection.back')
    keyboard.append([InlineKeyboardButton(back_label, callback_data="new_entry")])
    return InlineKeyboardMarkup(keyboard)

def get_date_selection_keyboard(year, month, last_day=None, show_all=False):
    keyboard = []

    if not show_all:
        if last_day is None:
            suggest_d = 1
        else:
            suggest_d = last_day + 1

        days_in_month = calendar.monthrange(year, month)[1]
        while suggest_d <= days_in_month:
            dt = datetime(year, month, suggest_d)
            if dt.weekday() != 4:
                break
            suggest_d += 1

        if suggest_d <= days_in_month:
            suggested_label = S('keyboards.date_selection.suggested', day=to_bn_number(suggest_d), month_name=MONTHS_BN_FULL[month])
            keyboard.append([InlineKeyboardButton(suggested_label, callback_data=f"select_date_{suggest_d}")])

        show_all_label = S('keyboards.date_selection.show_all')
        keyboard.append([InlineKeyboardButton(show_all_label, callback_data="show_all_dates")])
    else:
        days_in_month = calendar.monthrange(year, month)[1]
        row = []
        for d in range(1, days_in_month + 1):
            dt = datetime(year, month, d)
            if dt.weekday() == 4:
                continue
            row.append(InlineKeyboardButton(to_bn_number(d), callback_data=f"select_date_{d}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

    back_label = S('keyboards.date_selection.back')
    keyboard.append([InlineKeyboardButton(back_label, callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def get_distributor_keyboard(distributors, selected_indices=None):
    if selected_indices is None:
        selected_indices = []
    keyboard = []

    row = []
    for i, name in enumerate(distributors):
        clean_name = name.replace("মেসার্স ", "").replace(" ট্রেডার্স", "").replace(" এন্টারপ্রাইজ", "").strip()
        prefix = "✅ " if i in selected_indices else ""
        row.append(InlineKeyboardButton(f"{prefix}{clean_name}", callback_data=f"toggle_dist_{i}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    b = S('keyboards.distributor_selection')
    footer = []
    footer.append(InlineKeyboardButton(b['back'], callback_data="back"))
    if selected_indices:
        footer.append(InlineKeyboardButton(b['done'], callback_data="dist_done"))
    keyboard.append(footer)

    return InlineKeyboardMarkup(keyboard)

def get_yes_no_keyboard(prefix, include_back=False):
    b = S('keyboards.yes_no')
    context = b.get(prefix, {})
    yes_text = context.get('yes', '✅ হ্যাঁ')
    no_text = context.get('no', '❌ না')
    keyboard = [
        [
            InlineKeyboardButton(no_text, callback_data=f"{prefix}_no"),
            InlineKeyboardButton(yes_text, callback_data=f"{prefix}_yes")
        ]
    ]
    if include_back:
        keyboard.append([InlineKeyboardButton(b['back'], callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(S('keyboards.yes_no.back'), callback_data="back")]])

def get_confirmation_keyboard(context='save'):
    b = S('keyboards.confirmation')
    c = b.get(context, b['save'])
    keyboard = [
        [
            InlineKeyboardButton(c['discard'], callback_data="confirm_discard"),
            InlineKeyboardButton(c['confirm'], callback_data="confirm_save")
        ],
        [InlineKeyboardButton(b['back'], callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

FILTER_KEYS = ['petrol', 'mobil', 'meeting', 'manager']

def get_list_entries_choice_keyboard(saved_filters=None):
    b = S('keyboards.list_entries')
    buttons = []
    buttons.append([InlineKeyboardButton(b['all_entries'], callback_data="list_entries_all")])
    if saved_filters and any(saved_filters.get(k, False) for k in FILTER_KEYS):
        names = []
        if saved_filters.get('petrol'): names.append(b['filter_petrol'])
        if saved_filters.get('mobil'): names.append(b['filter_mobil'])
        if saved_filters.get('meeting'): names.append(b['filter_meeting'])
        if saved_filters.get('manager'): names.append(b['filter_manager'])
        label = b['last_filter'] + ": " + ", ".join(names)
        buttons.append([InlineKeyboardButton(label, callback_data="list_entries_last_filter")])
    buttons.append([InlineKeyboardButton(b['filter'], callback_data="list_entries_filter")])
    return InlineKeyboardMarkup(buttons)

def get_filter_checkboxes_keyboard(selected):
    b = S('keyboards.list_entries')
    labels = [b['filter_petrol'], b['filter_mobil'], b['filter_meeting'], b['filter_manager']]
    keyboard = []
    for i, key in enumerate(FILTER_KEYS):
        checked = selected.get(key, False) if selected else False
        prefix = "✅ " if checked else ""
        keyboard.append([InlineKeyboardButton(prefix + labels[i], callback_data=f"list_entries_filter_toggle_{i}")])
    keyboard.append([
        InlineKeyboardButton(b['apply'], callback_data="list_entries_filter_apply"),
        InlineKeyboardButton(b['back'], callback_data="list_entries_filter_back")
    ])
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard(show_back_to_menu=True):
    b = S('keyboards.settings')
    keyboard = [
        [InlineKeyboardButton(b['petrol'], callback_data="set_petrol_price")],
        [InlineKeyboardButton(b['mobil'], callback_data="set_mobil_price")],
        [InlineKeyboardButton(b['da'], callback_data="set_da_rate")],
        [InlineKeyboardButton(b['transport'], callback_data="set_transport_fee")],
        [InlineKeyboardButton(b['distributors'], callback_data="manage_distributors")],
    ]
    if show_back_to_menu:
        keyboard.append([InlineKeyboardButton(b['back_to_menu'], callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_distributor_mgmt_keyboard(distributors):
    b = S('keyboards.distributor_mgmt')
    keyboard = []
    for i, d in enumerate(distributors):
        keyboard.append([
            InlineKeyboardButton(d, callback_data="ignore"),
            InlineKeyboardButton(b['remove_icon'], callback_data=f"remove_dist_{i}")
        ])

    keyboard.append([InlineKeyboardButton(b['add'], callback_data="add_distributor")])
    keyboard.append([InlineKeyboardButton(b['back'], callback_data="settings")])
    return InlineKeyboardMarkup(keyboard)
