from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import calendar
from datetime import datetime

MONTHS_BN_FULL = {
    1: "জানুয়ারি", 2: "ফেব্রুয়ারি", 3: "মার্চ", 4: "এপ্রিল",
    5: "মে", 6: "জুন", 7: "জুলাই", 8: "আগস্ট",
    9: "সেপ্টেম্বর", 10: "অক্টোবর", 11: "নভেম্বর", 12: "ডিসেম্বর"
}

BN_DIGITS = {'0':'০', '1':'১', '2':'২', '3':'৩', '4':'৪', '5':'৫', '6':'৬', '7':'৭', '8':'৮', '9':'৯'}

def to_bn_number(number):
    return "".join(BN_DIGITS.get(d, d) for d in str(number))

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("➕ নতুন এন্ট্রি", callback_data="new_entry")],
        [InlineKeyboardButton("📋 এন্ট্রি তালিকা", callback_data="list_entries")],
        [InlineKeyboardButton("📊 সারসংক্ষেপ", callback_data="summary")],
        [InlineKeyboardButton("📁 পুরানো মাস", callback_data="archive_menu")],
        [InlineKeyboardButton("📝 এডিট / 🗑 ডিলিট", callback_data="edit_delete_menu")],
        [InlineKeyboardButton("📄 রিপোর্ট তৈরি করুন", callback_data="generate_report")],
        [InlineKeyboardButton("⚙️ সেটিংস", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_edit_delete_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 এন্ট্রি এডিট করুন", callback_data="edit_entry")],
        [InlineKeyboardButton("🗑 এন্ট্রি ডিলিট করুন", callback_data="delete_entry")],
        [InlineKeyboardButton("🔙 মূল মেনু", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_entries_selection_keyboard(entries, action_prefix):
    """Create a keyboard with dates to select an entry for edit/delete."""
    keyboard = []
    for e in entries:
        dt = datetime.strptime(e['date'], '%Y-%m-%d')
        label = f"{to_bn_number(dt.strftime('%d/%m/%y'))} — {to_bn_number(e['total_cost'])}/-"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"{action_prefix}_{e['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="edit_delete_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_edit_fields_keyboard(entry_id):
    keyboard = [
        [InlineKeyboardButton("📏 দূরত্ব (কিমি)", callback_data=f"edit_field_km_{entry_id}")],
        [InlineKeyboardButton("🔢 শুরুর ওডোমিটার", callback_data=f"edit_field_start_{entry_id}")],
        [InlineKeyboardButton("🔢 শেষ ওডোমিটার", callback_data=f"edit_field_end_{entry_id}")],
        [InlineKeyboardButton("🤝 পরিবেশক পরিবর্তন", callback_data=f"edit_field_dist_{entry_id}")],
        [InlineKeyboardButton("⛽ পেট্রোল (লিটার)", callback_data=f"edit_field_petrol_{entry_id}")],
        [InlineKeyboardButton("🛢 মবিল (লিটার)", callback_data=f"edit_field_mobil_{entry_id}")],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data="edit_entry")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_entry_type_keyboard():
    keyboard = [
        [InlineKeyboardButton("🛵 সাধারণ ট্যুর", callback_data="type_regular")],
        [InlineKeyboardButton("🏢 মাসিক মিটিং", callback_data="type_meeting")],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_month_selection_keyboard(include_more=True):
    now = datetime.now()
    keyboard = []
    # Current month
    m1, y1 = now.month, now.year
    
    keyboard.append([InlineKeyboardButton(f"চলতি মাস ({MONTHS_BN_FULL[m1]} {to_bn_number(y1)})", callback_data=f"select_month_{y1}_{m1}")])
    if include_more:
        keyboard.append([InlineKeyboardButton("📅 আরও অপশন", callback_data="show_more_months")])
    
    keyboard.append([InlineKeyboardButton("🔙 বাতিল", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def get_all_months_keyboard(year):
    keyboard = []
    row = []
    for m in range(1, 13):
        row.append(InlineKeyboardButton(MONTHS_BN_FULL[m], callback_data=f"select_month_{year}_{m}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    keyboard.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="new_entry")])
    return InlineKeyboardMarkup(keyboard)

def get_date_selection_keyboard(year, month, last_day=None, show_all=False):
    keyboard = []
    
    if not show_all:
        # Suggest only ONE date
        if last_day is None:
            # First entry of the month
            suggest_d = 1
        else:
            suggest_d = last_day + 1
            
        # Check if Friday
        days_in_month = calendar.monthrange(year, month)[1]
        while suggest_d <= days_in_month:
            dt = datetime(year, month, suggest_d)
            if dt.weekday() != 4: # Not Friday
                break
            suggest_d += 1
            
        if suggest_d <= days_in_month:
            keyboard.append([InlineKeyboardButton(f"সাজেস্টেড তারিখ: {to_bn_number(suggest_d)} {MONTHS_BN_FULL[month]}", callback_data=f"select_date_{suggest_d}")])
        
        keyboard.append([InlineKeyboardButton("📅 আরও তারিখ দেখুন", callback_data="show_all_dates")])
    else:
        # Show all dates in 5 columns, SKIP Fridays
        days_in_month = calendar.monthrange(year, month)[1]
        row = []
        for d in range(1, days_in_month + 1):
            dt = datetime(year, month, d)
            if dt.weekday() == 4: continue # Skip Friday
            
            row.append(InlineKeyboardButton(to_bn_number(d), callback_data=f"select_date_{d}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        if row: keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def get_distributor_keyboard(distributors, selected_indices=None):
    if selected_indices is None: selected_indices = []
    keyboard = []
    
    # 2 columns, remove "মেসার্স", "ট্রেডার্স", "এন্টারপ্রাইজ" from labels
    row = []
    for i, name in enumerate(distributors):
        clean_name = name.replace("মেসার্স ", "").replace(" ট্রেডার্স", "").replace(" এন্টারপ্রাইজ", "").strip()
        prefix = "✅ " if i in selected_indices else ""
        row.append(InlineKeyboardButton(f"{prefix}{clean_name}", callback_data=f"toggle_dist_{i}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    
    # Done and Cancel in the same row
    footer = []
    if selected_indices:
        footer.append(InlineKeyboardButton("🆗 সম্পন্ন", callback_data="dist_done"))
    footer.append(InlineKeyboardButton("🔙 ফিরে যান", callback_data="back"))
    keyboard.append(footer)
    
    return InlineKeyboardMarkup(keyboard)

def get_yes_no_keyboard(prefix, include_back=False):
    keyboard = [
        [
            InlineKeyboardButton("✅ হ্যাঁ", callback_data=f"{prefix}_yes"),
            InlineKeyboardButton("❌ না", callback_data=f"{prefix}_no")
        ]
    ]
    if include_back:
        keyboard.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে যান", callback_data="back")]])

def get_confirmation_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("✅ নিশ্চিত করুন", callback_data="confirm_save"),
            InlineKeyboardButton("❌ বাতিল করুন", callback_data="confirm_discard")
        ],
        [InlineKeyboardButton("🔙 ফিরে যান", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard():
    keyboard = [
        [InlineKeyboardButton("⛽ পেট্রোল মূল্য", callback_data="set_petrol_price")],
        [InlineKeyboardButton("🛢 মবিল মূল্য", callback_data="set_mobil_price")],
        [InlineKeyboardButton("💰 DA রেট", callback_data="set_da_rate")],
        [InlineKeyboardButton("🚌 পরিবহন ভাড়া", callback_data="set_transport_fee")],
        [InlineKeyboardButton("🤝 পরিবেশক ম্যানেজমেন্ট", callback_data="manage_distributors")],
        [InlineKeyboardButton("🔙 মূল মেনু", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_distributor_mgmt_keyboard(distributors):
    keyboard = []
    # List all with a delete icon
    for i, d in enumerate(distributors):
        keyboard.append([
            InlineKeyboardButton(d, callback_data="ignore"),
            InlineKeyboardButton("❌", callback_data=f"remove_dist_{i}")
        ])
    
    keyboard.append([InlineKeyboardButton("➕ নতুন পরিবেশক যোগ করুন", callback_data="add_distributor")])
    keyboard.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="settings")])
    return InlineKeyboardMarkup(keyboard)
