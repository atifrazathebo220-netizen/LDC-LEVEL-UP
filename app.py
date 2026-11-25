"""
LEGENDCHEATS — Telegram Number Lookup Bot
------------------------------------------
Read-only number testing. Kisi number par koi SMS / call / WhatsApp message
NAHI bheja jaata — sirf lookup (database se info) hoti hai.

Commands:
  /start   -> LEGENDCHEATS branding + welcome
  /help    -> madad
  /number  -> number validate + lookup (active, carrier, country, line type)

Lookup sources (optional, jo key aapke paas ho wahi use hogi):
  - NUMVERIFY_KEY  : HLR lookup (valid/active, carrier, country, line type)
  - WHATSAPP_TOKEN : WhatsApp Business number registered hai ya nahi (read-only)

Hosting:
  1. pip install -r requirements.txt
  2. export BOT_TOKEN="apna-telegram-token"
     export NUMVERIFY_KEY="apni-numverify-key"      # optional
  3. python app.py
"""

import os
import re
import logging

import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------------------------------------------------------------------
# CONFIG  — tokens/keys yahan ya environment variables se
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")          # <-- Telegram bot token
NUMVERIFY_KEY = os.environ.get("NUMVERIFY_KEY", "")  # <-- numverify.com key (optional)

BRAND = "LEGENDCHEATS"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(BRAND)


# ---------------------------------------------------------------------------
# Number format validation (E.164)
#   - 0 se shuru nahi
#   - country code ke saath, 10-15 digits
# ---------------------------------------------------------------------------
def clean_number(raw: str) -> str:
    return re.sub(r"[\s\-\(\)]", "", raw.strip())


def validate_number(raw: str):
    num = clean_number(raw)
    core = num[1:] if num.startswith("+") else num

    if not core.isdigit():
        return False, "Sirf digits allowed hain (+ country code).", num
    if core.startswith("0"):
        return False, "Number 0 se shuru nahi hona chahiye (country code use kijiye).", num
    if len(core) < 10 or len(core) > 15:
        return False, "Number 10 se 15 digits ke beech hona chahiye (E.164).", num

    return True, "OK", "+" + core


# ---------------------------------------------------------------------------
# HLR lookup (read-only) — valid/active, carrier, country, line type
# ---------------------------------------------------------------------------
def hlr_lookup(normalized: str) -> str:
    if not NUMVERIFY_KEY:
        return "ℹ️ HLR lookup off (NUMVERIFY_KEY set nahi hai). Format valid hai."
    try:
        resp = requests.get(
            "http://apilayer.net/api/validate",
            params={"access_key": NUMVERIFY_KEY, "number": normalized},
            timeout=10,
        )
        data = resp.json()
        if data.get("valid"):
            return (
                f"🟢 Status  : Active / Valid\n"
                f"📍 Country : {data.get('country_name', '-')} ({data.get('country_code', '-')})\n"
                f"📶 Carrier : {data.get('carrier') or '-'}\n"
                f"🔖 Type    : {data.get('line_type') or '-'}"
            )
        return "🔴 Status : Number lookup mein valid nahi nikla."
    except Exception as e:
        logger.warning("hlr lookup failed: %s", e)
        return "⚠️ Lookup service abhi reachable nahi hai."


# ---------------------------------------------------------------------------
# WhatsApp registration check (read-only)
#   NOTE: WhatsApp par "registered hai ya nahi" check ke liye aapka apna
#   WhatsApp Business account chahiye. Yahan sirf hook rakha hai — key hogi to
#   aap apna provider endpoint laga sakte hain. Koi message NAHI jaata.
# ---------------------------------------------------------------------------
def whatsapp_check(normalized: str) -> str:
    token = os.environ.get("WHATSAPP_TOKEN", "")
    if not token:
        return ""  # feature off
    # Yahan apna WhatsApp Business "contacts"/lookup endpoint laga sakte hain.
    # Jaan-boojh kar message-send ka koi code nahi — sirf registration check.
    return "💬 WhatsApp : check ke liye apna Business API endpoint configure kijiye."


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"╔══════════════════════╗\n"
        f"      ⚡ {BRAND} ⚡\n"
        f"╚══════════════════════╝\n\n"
        f"👋 Welcome! Ye {BRAND} ka official number-lookup bot hai.\n"
        f"🔍 Read-only testing — koi SMS/call/WhatsApp message nahi bheja jaata.\n\n"
        f"📋 Commands:\n"
        f"   /number  —  number validate + lookup\n"
        f"   /help    —  madad\n\n"
        f"Example:  /number 923001234567"
    )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"ℹ️ {BRAND} Help\n\n"
        "Usage:  /number <phone>\n\n"
        "Rules:\n"
        "  • 0 se shuru na ho\n"
        "  • country code ke saath (92..., 91..., 1...)\n"
        "  • 10–15 digits\n\n"
        "Lookup read-only hai: number active/valid, carrier, country, line type.\n"
        "Example:  /number +923001234567"
    )


def build_report(normalized: str) -> str:
    lines = [f"✅ Format valid", f"🔢 Number : {normalized}", "", hlr_lookup(normalized)]
    wa = whatsapp_check(normalized)
    if wa:
        lines.append(wa)
    lines.append("")
    lines.append(f"— {BRAND}")
    return "\n".join(lines)


async def number_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📥 Number bhejiye:  /number 923001234567")
        return

    raw = " ".join(context.args)
    is_valid, reason, normalized = validate_number(raw)
    if not is_valid:
        await update.message.reply_text(f"❌ Invalid number\n\nReason: {reason}")
        return

    await update.message.reply_text(build_report(normalized))


async def plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text or ""
    if re.search(r"\d{7,}", raw):
        is_valid, reason, normalized = validate_number(raw)
        if is_valid:
            await update.message.reply_text(build_report(normalized))
        else:
            await update.message.reply_text(f"❌ Invalid number\n\nReason: {reason}")
    else:
        await update.message.reply_text("Type /start to begin.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN set nahi hai. app.py mein daaliye ya `export BOT_TOKEN=...`"
        )

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("number", number_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, plain_text))

    logger.info("%s lookup bot chal raha hai...", BRAND)
    app.run_polling()


if __name__ == "__main__":
    main()
