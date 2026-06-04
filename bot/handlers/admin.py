from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from bot.text_resources import S
from core.file_data_store import OWNER_ID, add_user, remove_user, get_all_users

# States
ADDUSER_AWAIT_ID, ADDUSER_CONFIRM, REMOVEUSER_SELECT, REMOVEUSER_CONFIRM = range(4)


async def owner_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if user and user.id == OWNER_ID:
        return True
    if update.effective_message:
        await update.effective_message.reply_text(S('admin.not_owner'))
    return False


async def start_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update, context):
        return ConversationHandler.END
    await update.effective_message.reply_text(S('admin.adduser_prompt_id'))
    return ADDUSER_AWAIT_ID


async def handle_adduser_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(S('admin.adduser_invalid_id'))
        return ADDUSER_AWAIT_ID

    users = await get_all_users()
    if str(target_id) in users:
        await update.message.reply_text(S('admin.adduser_exists', user_id=target_id))
        return ConversationHandler.END

    context.user_data['add_target_id'] = target_id
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(S('admin.confirm_add'), callback_data="admin_confirm_add")],
        [InlineKeyboardButton(S('admin.cancel_add'), callback_data="admin_cancel")]
    ])
    await update.message.reply_text(
        S('admin.adduser_confirm', user_id=target_id),
        reply_markup=kb, parse_mode='HTML'
    )
    return ADDUSER_CONFIRM


async def confirm_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "admin_confirm_add":
        target_id = context.user_data.pop('add_target_id', None)
        if target_id and await add_user(target_id):
            await query.edit_message_text(
                S('admin.adduser_success', user_id=target_id), parse_mode='HTML'
            )
        else:
            await query.edit_message_text(S('admin.adduser_failed'), parse_mode='HTML')
    else:
        await query.edit_message_text(S('admin.adduser_cancelled'), parse_mode='HTML')
    return ConversationHandler.END


async def start_removeuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update, context):
        return ConversationHandler.END

    users = await get_all_users()
    non_owner = {k: v for k, v in users.items() if int(k) != OWNER_ID}
    if not non_owner:
        await update.effective_message.reply_text(S('admin.removeuser_no_users'))
        return ConversationHandler.END

    kb = []
    for uid_str, info in non_owner.items():
        role = info.get('role', 'user')
        label = f"{uid_str} ({role})"
        kb.append([InlineKeyboardButton(label, callback_data=f"admin_remove_{uid_str}")])
    kb.append([InlineKeyboardButton(S('admin.cancel_remove'), callback_data="admin_cancel")])

    await update.effective_message.reply_text(
        S('admin.removeuser_prompt_select'),
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return REMOVEUSER_SELECT


async def select_removeuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "admin_cancel":
        await query.edit_message_text(S('admin.removeuser_cancelled'))
        return ConversationHandler.END

    target_id = int(query.data.split("_")[2])
    context.user_data['remove_target_id'] = target_id
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(S('admin.confirm_remove'), callback_data="admin_confirm_remove")],
        [InlineKeyboardButton(S('admin.back_to_list'), callback_data="admin_back_to_list")]
    ])
    await query.edit_message_text(
        S('admin.removeuser_confirm', user_id=target_id),
        reply_markup=kb, parse_mode='HTML'
    )
    return REMOVEUSER_CONFIRM


async def confirm_removeuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "admin_confirm_remove":
        target_id = context.user_data.pop('remove_target_id', None)
        if target_id and await remove_user(target_id):
            await query.edit_message_text(
                S('admin.removeuser_success', user_id=target_id), parse_mode='HTML'
            )
        else:
            await query.edit_message_text(S('admin.removeuser_failed'), parse_mode='HTML')
    elif query.data == "admin_back_to_list":
        return await start_removeuser(update, context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message:
        await update.effective_message.reply_text(S('common.cancelled'))
    return ConversationHandler.END


async def listusers_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update, context):
        return
    users = await get_all_users()
    if not users:
        await update.effective_message.reply_text(S('admin.users_empty'))
        return
    lines = [S('admin.users_title')]
    for uid_str, info in users.items():
        role = info.get('role', 'user')
        added = info.get('added_at', '?')[:10]
        lines.append(S('admin.users_line', user_id=uid_str, role=role, added_at=added))
    await update.effective_message.reply_text(''.join(lines))


def get_admin_conv_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler('adduser', start_adduser),
            CommandHandler('removeuser', start_removeuser),
        ],
        states={
            ADDUSER_AWAIT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_adduser_id)],
            ADDUSER_CONFIRM: [CallbackQueryHandler(confirm_adduser, pattern="^admin_confirm_add$|^admin_cancel$")],
            REMOVEUSER_SELECT: [CallbackQueryHandler(select_removeuser, pattern="^admin_remove_|^admin_cancel$")],
            REMOVEUSER_CONFIRM: [CallbackQueryHandler(confirm_removeuser, pattern="^admin_confirm_remove$|^admin_back_to_list$")],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
