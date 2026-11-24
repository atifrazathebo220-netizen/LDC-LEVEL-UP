"""
LEGENDCHEATS — Telegram Bot
----------------------------
Ek saaf bot jo:
  - /start   -> LEGENDCHEATS branding + welcome
  - /number  -> phone number leta hai aur validate karta hai
  - number format check: no leading 0, valid country code, 10-15 digits
  - ek LEGIT public API (phone metadata) se info laa kar dikhata hai

Hosting:
  1. pip install python-telegram-bot==21.6 requests
  2. niche BOT_TOKEN ki jagah apna token daaliye (ya env var BOT_TOKEN set kijiye)
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
# CONFIG  — apna bot token yahan daaliye (ya environment variable set kijiye)
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")   # <-- apna Telegram bot token yahan

BRAND = "LEGENDCHEATS"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(BRAND)


# ---------------------------------------------------------------------------
# Number validation
#   - sirf digits (+ optional leading +)
#   - 0 se shuru nahi hona chahiye
#   - country code ke baad total 10 se 15 digits (E.164 standard)
# ---------------------------------------------------------------------------
def clean_number(raw: str) -> str:
    """Spaces, dashes, brackets hata do."""
    return re.sub(r"[\s\-\(\)]", "", raw.strip())


def validate_number(raw: str):
    """
    Return (is_valid: bool, reason: str, normalized: str)
    """
    num = clean_number(raw)

    # optional leading + allow karo
    core = num[1:] if num.startswith("+") else num

    if not core.isdigit():
        return False, "Sirf digits allowed hain (+ country code ke saath).", num

    if core.startswith("0"):
        return False, "Number 0 se shuru nahi hona chahiye (country code use kijiye).", num

    if len(core) < 10 or len(core) > 15:
        return False, "Number 10 se 15 digits ke beech hona chahiye (E.164).", num

    normalized = "+" + core
    return True, "OK", normalized


# ---------------------------------------------------------------------------
# LEGIT API lookup  — public number metadata (carrier / country / line type)
# Yahan sirf info di jaati hai, koi message/call nahi bheja jaata.
# ---------------------------------------------------------------------------
def lookup_number(normalized: str) -> str:
    """
    Public, read-only lookup. Agar aapke paas apni API key hai to use kar sakte
    hain; by default yeh ek basic offline-style summary deta hai.
    """
    try:
        # Example of a legit read-only API call (metadata only).
        # Replace with your own provider + key agar chahiye.
        api_key = os.environ.get("NUMVERIFY_KEY", "")
        if api_key:
            resp = requests.get(
                "http://apilayer.net/api/validate",
                params={"access_key": api_key, "number": normalized},
                timeout=10,
            )
            data = resp.json()
            if data.get("valid"):
                return (
                    f"📍 Country : {data.get('country_name', '-')}\n"
                    f"📞 Carrier : {data.get('carrier') or '-'}\n"
                    f"🔖 Type    : {data.get('line_type') or '-'}"
                )
            return "ℹ️ Lookup ne number ko valid nahi maana."
        # koi key nahi -> sirf format summary
        return "ℹ️ Format valid hai. (Detailed lookup ke liye NUMVERIFY_KEY set kijiye.)"
    except Exception as e:
        logger.warning("lookup failed: %s", e)
        return "⚠️ Lookup service abhi reachable nahi hai."


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"╔══════════════════════╗\n"
        f"      ⚡ {BRAND} ⚡\n"
        f"╚══════════════════════╝\n\n"
        f"👋 Welcome! Ye {BRAND} ka official bot hai.\n\n"
        f"📋 Commands:\n"
        f"   /number  —  phone number validate + lookup\n"
        f"   /help    —  madad\n\n"
        f"Shuru karne ke liye bhejiye:  /number 923001234567"
    )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"ℹ️ {BRAND} Help\n\n"
        "Usage:\n"
        "   /number <phone>\n\n"
        "Rules:\n"
        "  • 0 se shuru na ho\n"
        "  • country code ke saath (jaise 92..., 91..., 1...)\n"
        "  • 10–15 digits\n\n"
        "Example:  /number +923001234567"
    )


async def number_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📥 Number bhejiye:  /number 923001234567"
        )
        return

    raw = " ".join(context.args)
    is_valid, reason, normalized = validate_number(raw)

    if not is_valid:
        await update.message.reply_text(
            f"❌ Invalid number\n\nReason: {reason}"
        )
        return

    info = lookup_number(normalized)
    await update.message.reply_text(
        f"✅ Valid number\n\n"
        f"🔢 Number : {normalized}\n"
        f"{info}\n\n"
        f"— {BRAND}"
    )


async def plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Agar user bina command ke sirf number bhej de."""
    raw = update.message.text or ""
    if re.search(r"\d{7,}", raw):
        is_valid, reason, normalized = validate_number(raw)
        if is_valid:
            info = lookup_number(normalized)
            await update.message.reply_text(
                f"✅ Valid number\n\n🔢 {normalized}\n{info}\n\n— {BRAND}"
            )
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

    logger.info("%s bot chal raha hai...", BRAND)
    app.run_polling()


if __name__ == "__main__":
    main()
