import json, os, aiofiles
from datetime import datetime

MSG_LOG_BASE = 'data/message_log'
MAX_TEMP = 300

def _ensure_dir():
    if not os.path.exists(MSG_LOG_BASE):
        os.makedirs(MSG_LOG_BASE)

def _path(user_id):
    return os.path.join(MSG_LOG_BASE, f'{user_id}.json')

async def get_log(user_id):
    _ensure_dir()
    path = _path(user_id)
    try:
        if not os.path.exists(path):
            return {'temporary': [], 'files': []}
        async with aiofiles.open(path, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content) if content.strip() else {'temporary': [], 'files': []}
    except (FileNotFoundError, json.JSONDecodeError):
        return {'temporary': [], 'files': []}

async def save_log(user_id, data):
    _ensure_dir()
    path = _path(user_id)
    async with aiofiles.open(path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=2))

async def record_message(user_id, chat_id, message_id, msg_type='temporary'):
    log = await get_log(user_id)
    entry = {'chat_id': chat_id, 'msg_id': message_id, 'type': msg_type, 'ts': datetime.now().isoformat()}
    if msg_type.startswith('file:'):
        log['files'].append(entry)
    else:
        log['temporary'].append(entry)
    if len(log['temporary']) > MAX_TEMP:
        log['temporary'] = log['temporary'][-MAX_TEMP:]
    await save_log(user_id, log)

async def record_file_message(user_id, chat_id, message_id, file_type, month, year, filename=''):
    log = await get_log(user_id)
    log['files'].append({
        'chat_id': chat_id, 'msg_id': message_id, 'type': f'file:{file_type}',
        'month': month, 'year': year, 'filename': filename,
        'ts': datetime.now().isoformat()
    })
    await save_log(user_id, log)

async def get_all_temporary(user_id):
    log = await get_log(user_id)
    return log['temporary']

async def get_all_files(user_id):
    log = await get_log(user_id)
    return log['files']

async def clear_temporary(user_id):
    log = await get_log(user_id)
    log['temporary'] = []
    await save_log(user_id, log)

async def clear_all_except_files(user_id):
    log = await get_log(user_id)
    log['temporary'] = []
    await save_log(user_id, log)
