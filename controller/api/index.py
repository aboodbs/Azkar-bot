import base64
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TZ = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Amman"))
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO = os.environ["GITHUB_REPO"]  # e.g. "aboodbs/azkar-bot"
ADMIN_ID = int(os.environ["ADMIN_ID"])
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/contents"


def gh_get(path):
    r = requests.get(
        f"{GITHUB_API}/{path}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
    )
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(content), data["sha"]


def gh_put(path, obj, sha, message):
    content = json.dumps(obj, ensure_ascii=False, indent=2)
    b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    r = requests.put(
        f"{GITHUB_API}/{path}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json={"message": message, "content": b64, "sha": sha},
    )
    r.raise_for_status()


def tg_send(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
    )


@app.route("/webhook", methods=["POST"])
def webhook():
    if WEBHOOK_SECRET:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
            return jsonify({"ok": False}), 403

    update = request.get_json(force=True, silent=True) or {}
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return jsonify({"ok": True})

    from_id = msg.get("from", {}).get("id")
    if from_id != ADMIN_ID:
        return jsonify({"ok": True})

    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    try:
        handle_command(chat_id, text)
    except Exception as e:
        tg_send(chat_id, f"صار خطأ: {e}")

    return jsonify({"ok": True})


def handle_command(chat_id, text):
    if text.startswith("/list"):
        cmd_list(chat_id)
    elif text.startswith("/addfriday "):
        cmd_add(chat_id, text[len("/addfriday "):].strip(), key="friday_azkar")
    elif text.startswith("/add "):
        cmd_add(chat_id, text[len("/add "):].strip())
    elif text.startswith("/deletefriday "):
        cmd_delete(chat_id, text[len("/deletefriday "):].strip(), key="friday_azkar")
    elif text.startswith("/delete "):
        cmd_delete(chat_id, text[len("/delete "):].strip())
    elif text.startswith("/test "):
        cmd_test(chat_id, text[len("/test "):].strip())
    elif text.startswith("/pause"):
        cmd_pause(chat_id, True)
    elif text.startswith("/resume"):
        cmd_pause(chat_id, False)
    elif text.startswith("/status"):
        cmd_status(chat_id)
    elif text.startswith("/log"):
        cmd_log(chat_id)
    elif text.startswith("/help") or text.startswith("/start"):
        cmd_help(chat_id)
    else:
        tg_send(chat_id, "أمر غير معروف. اكتب /help لعرض الأوامر.")


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
            "/test نص — إرسال رسالة تجريبية فورية للقناة\n"
            "/pause — إيقاف البوت مؤقتًا\n"
            "/resume — تشغيل البوت من جديد\n"
            "/status — حالة البوت الحالية\n"
            "/log — آخر الرسائل المرسلة"
        ),
    )


def cmd_list(chat_id):
    config, _ = gh_get("azkar.json")

    lines = ["<b>الأذكار العامة:</b>"]
    for i, item in enumerate(config["azkar"], 1):
        preview = item.replace("\n", " / ")
        lines.append(f"{i}. {preview}")

    lines.append("")
    lines.append("<b>أذكار الجمعة:</b>")
    for i, item in enumerate(config["friday_azkar"], 1):
        preview = item.replace("\n", " / ")
        lines.append(f"{i}. {preview}")

    text = "\n".join(lines)
    for start in range(0, len(text), 3500):
        tg_send(chat_id, text[start:start + 3500])


def cmd_add(chat_id, new_text, key="azkar"):
    if not new_text:
        tg_send(chat_id, "لازم تكتب نص الذكر بعد الأمر.")
        return
    config, sha = gh_get("azkar.json")
    config[key].append(new_text)
    gh_put("azkar.json", config, sha, f"add {key} item via control bot")
    tg_send(chat_id, "تمت الإضافة ✅")


def cmd_delete(chat_id, num_str, key="azkar"):
    config, sha = gh_get("azkar.json")
    try:
        idx = int(num_str) - 1
        removed = config[key].pop(idx)
    except (ValueError, IndexError):
        tg_send(chat_id, "رقم غير صحيح. استخدم /list لمعرفة الأرقام.")
        return
    gh_put("azkar.json", config, sha, f"delete {key} item via control bot")
    tg_send(chat_id, f"تم الحذف ✅\n{removed[:150]}")


def cmd_test(chat_id, text):
    if not text:
        tg_send(chat_id, "لازم تكتب نص الرسالة بعد الأمر.")
        return
    tg_send(CHANNEL_ID, f"<b>{text}</b>")
    tg_send(chat_id, "تم الإرسال للقناة ✅")


def cmd_pause(chat_id, paused):
    state, sha = gh_get("state.json")
    state["paused"] = paused
    gh_put("state.json", state, sha, "pause/resume via control bot")
    tg_send(chat_id, "تم إيقاف البوت مؤقتًا ⏸️" if paused else "تم تشغيل البوت ▶️")


def cmd_status(chat_id):
    state, _ = gh_get("state.json")
    config, _ = gh_get("azkar.json")
    paused = state.get("paused", False)
    tg_send(
        chat_id,
        (
            f"<b>حالة البوت:</b> {'متوقف ⏸️' if paused else 'شغال ▶️'}\n"
            f"عدد الأذكار العامة: {len(config['azkar'])}\n"
            f"عدد أذكار الجمعة: {len(config['friday_azkar'])}"
        ),
    )


def cmd_log(chat_id):
    state, _ = gh_get("state.json")
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


@app.route("/", methods=["GET"])
def home():
    return "Azkar Bot Controller is running.", 200