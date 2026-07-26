import json
import os

import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

CONFIG_PATH = "azkar.json"
STATE_PATH = "state.json"
CTRL_STATE_PATH = "controller_state.json"


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def tg_send(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
    )


def tg_get_updates(offset):
    r = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
        params={"offset": offset, "timeout": 0},
    )
    r.raise_for_status()
    return r.json()["result"]


def cmd_help(chat_id):
    tg_send(
        chat_id,
        (
            "<b>أوامر التحكم بالبوت:</b>\n"
            "/list — عرض كل الأذكار مرقمة\n"
            "/add نص — إضافة ذكر عام\n"
            "/addfriday نص — إضافة ذكر جمعة\n"
            "/delete رقم — حذف ذكر عام\n"
            "/deletefriday رقم — حذف ذكر جمعة\n"
            "/edit رقم نص_جديد — تعديل ذكر عام\n"
            "/editfriday رقم نص_جديد — تعديل ذكر جمعة\n"
            "/editfridayfirst نص_جديد — تعديل أول رسالة الجمعة\n"
            "/editfajr نص_جديد — تعديل رسالة الفجر\n"
            "/editasr نص_جديد — تعديل رسالة العصر\n"
            "/editsunday نص_جديد — تعديل رسالة مساء الأحد\n"
            "/editwednesday نص_جديد — تعديل رسالة مساء الأربعاء\n"
            "/test نص — إرسال رسالة تجريبية فورية للقناة\n"
            "/pause — إيقاف البوت مؤقتًا\n"
            "/resume — تشغيل البوت من جديد\n"
            "/status — حالة البوت الحالية\n"
            "/log — آخر الرسائل المرسلة"
        ),
    )


def cmd_list(chat_id, config):
    lines = ["<b>الأذكار العامة:</b>"]
    for i, item in enumerate(config["azkar"], 1):
        lines.append(f"{i}. {item.replace(chr(10), ' / ')}")
    lines.append("")
    lines.append("<b>أذكار الجمعة:</b>")
    for i, item in enumerate(config["friday_azkar"], 1):
        lines.append(f"{i}. {item.replace(chr(10), ' / ')}")
    text = "\n".join(lines)
    for start in range(0, len(text), 3500):
        tg_send(chat_id, text[start:start + 3500])


def cmd_add(chat_id, config, new_text, key="azkar"):
    if not new_text:
        tg_send(chat_id, "لازم تكتب نص الذكر بعد الأمر.")
        return False
    config[key].append(new_text)
    tg_send(chat_id, "تمت الإضافة ✅")
    return True


def cmd_delete(chat_id, config, num_str, key="azkar"):
    try:
        idx = int(num_str) - 1
        removed = config[key].pop(idx)
    except (ValueError, IndexError):
        tg_send(chat_id, "رقم غير صحيح. استخدم /list لمعرفة الأرقام.")
        return False
    tg_send(chat_id, f"تم الحذف ✅\n{removed[:150]}")
    return True


def cmd_edit(chat_id, config, rest, key="azkar"):
    parts = rest.split(" ", 1)
    if len(parts) < 2:
        tg_send(chat_id, "الصيغة: /edit رقم النص_الجديد")
        return False
    num_str, new_text = parts
    try:
        idx = int(num_str) - 1
        old = config[key][idx]
        config[key][idx] = new_text
    except (ValueError, IndexError):
        tg_send(chat_id, "رقم غير صحيح. استخدم /list لمعرفة الأرقام.")
        return False
    tg_send(chat_id, f"تم التعديل ✅\nقبل: {old[:100]}\nبعد: {new_text[:100]}")
    return True


def cmd_edit_single(chat_id, config, key, new_text):
    if not new_text:
        tg_send(chat_id, "لازم تكتب النص الجديد بعد الأمر.")
        return False
    old = config.get(key, "")
    config[key] = new_text
    tg_send(chat_id, f"تم التعديل ✅\nقبل: {old[:100]}\nبعد: {new_text[:100]}")
    return True


def cmd_test(chat_id, text):
    if not text:
        tg_send(chat_id, "لازم تكتب نص الرسالة بعد الأمر.")
        return
    tg_send(CHANNEL_ID, f"<b>{text}</b>")
    tg_send(chat_id, "تم الإرسال للقناة ✅")


def cmd_pause(chat_id, state, paused):
    state["paused"] = paused
    tg_send(chat_id, "تم إيقاف البوت مؤقتًا ⏸️" if paused else "تم تشغيل البوت ▶️")


def cmd_status(chat_id, config, state):
    paused = state.get("paused", False)
    tg_send(
        chat_id,
        (
            f"<b>حالة البوت:</b> {'متوقف ⏸️' if paused else 'شغال ▶️'}\n"
            f"عدد الأذكار العامة: {len(config['azkar'])}\n"
            f"عدد أذكار الجمعة: {len(config['friday_azkar'])}"
        ),
    )


def cmd_log(chat_id, state):
    log = state.get("log", [])
    if not log:
        tg_send(chat_id, "ما في سجل بعد.")
        return
    lines = ["<b>آخر الرسائل المرسلة:</b>"]
    for entry in log[-15:][::-1]:
        preview = entry.get("preview", "").replace("\n", " / ")
        kind = entry.get("kind", "")
        lines.append(f"{entry['time']} [{kind}] — {preview}")
    tg_send(chat_id, "\n".join(lines))


def handle_command(chat_id, text, config, state):
    config_changed = False
    state_changed = False

    if text.startswith("/list"):
        cmd_list(chat_id, config)
    elif text.startswith("/editfriday "):
        config_changed = cmd_edit(chat_id, config, text[len("/editfriday "):].strip(), "friday_azkar")
    elif text.startswith("/edit "):
        config_changed = cmd_edit(chat_id, config, text[len("/edit "):].strip())
    elif text.startswith("/editfridayfirst "):
        config_changed = cmd_edit_single(chat_id, config, "friday_first_message", text[len("/editfridayfirst "):].strip())
    elif text.startswith("/editfajr "):
        config_changed = cmd_edit_single(chat_id, config, "fajr_message", text[len("/editfajr "):].strip())
    elif text.startswith("/editasr "):
        config_changed = cmd_edit_single(chat_id, config, "asr_message", text[len("/editasr "):].strip())
    elif text.startswith("/editsunday "):
        config_changed = cmd_edit_single(chat_id, config, "sunday_evening_message", text[len("/editsunday "):].strip())
    elif text.startswith("/editwednesday "):
        config_changed = cmd_edit_single(chat_id, config, "wednesday_evening_message", text[len("/editwednesday "):].strip())
    elif text.startswith("/addfriday "):
        config_changed = cmd_add(chat_id, config, text[len("/addfriday "):].strip(), "friday_azkar")
    elif text.startswith("/add "):
        config_changed = cmd_add(chat_id, config, text[len("/add "):].strip())
    elif text.startswith("/deletefriday "):
        config_changed = cmd_delete(chat_id, config, text[len("/deletefriday "):].strip(), "friday_azkar")
    elif text.startswith("/delete "):
        config_changed = cmd_delete(chat_id, config, text[len("/delete "):].strip())
    elif text.startswith("/test "):
        cmd_test(chat_id, text[len("/test "):].strip())
    elif text.startswith("/pause"):
        cmd_pause(chat_id, state, True)
        state_changed = True
    elif text.startswith("/resume"):
        cmd_pause(chat_id, state, False)
        state_changed = True
    elif text.startswith("/status"):
        cmd_status(chat_id, config, state)
    elif text.startswith("/log"):
        cmd_log(chat_id, state)
    elif text.startswith("/help") or text.startswith("/start"):
        cmd_help(chat_id)
    else:
        tg_send(chat_id, "أمر غير معروف. اكتب /help لعرض الأوامر.")

    return config_changed, state_changed


def main():
    ctrl_state = load_json(CTRL_STATE_PATH, {"last_update_id": 0})
    updates = tg_get_updates(ctrl_state["last_update_id"] + 1)

    if not updates:
        return

    config = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {})

    config_changed = False
    state_changed = False

    for update in updates:
        ctrl_state["last_update_id"] = update["update_id"]
        msg = update.get("message")
        if not msg:
            continue
        from_id = msg.get("from", {}).get("id")
        if from_id != ADMIN_ID:
            continue
        chat_id = msg["chat"]["id"]
        text = (msg.get("text") or "").strip()
        if not text:
            continue

        c_changed, s_changed = handle_command(chat_id, text, config, state)
        config_changed = config_changed or c_changed
        state_changed = state_changed or s_changed

    save_json(CTRL_STATE_PATH, ctrl_state)
    if config_changed:
        save_json(CONFIG_PATH, config)
    if state_changed:
        save_json(STATE_PATH, state)


if __name__ == "__main__":
    main()