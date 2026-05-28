import random
import json
import os
import html
import httpx
from datetime import date, time
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================================
#  CONFIGURAZIONE — i valori vengono letti dalle variabili
#  d'ambiente impostate su Railway (non modificare qui)
# ============================================================
BOT_TOKEN         = os.environ.get("BOT_TOKEN", "")
GROUP_CHAT_ID     = int(os.environ.get("GROUP_CHAT_ID", "0"))
INTERVALLO_MINUTI = 30
DATA_CONCERTO     = date(2027, 3, 12)
ORE_BUONGIORNO    = time(13, 0, tzinfo=ZoneInfo("Europe/Rome"))
# ============================================================

SONGS_FILE    = "songs.txt"
PROGRESS_FILE = "progress.json"


# ---------- helper ----------

def load_songs():
    if not os.path.exists(SONGS_FILE):
        return []
    with open(SONGS_FILE, "r", encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return {"index": 0}
    with open(PROGRESS_FILE, "r") as f:
        return json.load(f)

def save_progress(data):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f)

def giorni_al_concerto():
    return (DATA_CONCERTO - date.today()).days

async def get_youtube_title(url):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://www.youtube.com/oembed",
                params={"url": url, "format": "json"},
                timeout=5
            )
            return r.json().get("title", url)
    except Exception:
        return url


# ---------- job automatici ----------

async def buongiorno(context):
    songs = load_songs()
    if not songs:
        return

    giorni = giorni_al_concerto()
    index  = giorni % len(songs)
    url    = songs[index]
    titolo = html.escape(await get_youtube_title(url))

    testo = (
        f"🌅 Buongiorno! Mancano <b>{giorni} giorni</b> al concerto!\n\n"
        f"🎵 La canzone di oggi:\n<b>{titolo}</b>\n{url}"
    )
    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=testo,
        parse_mode="HTML"
    )


async def invia_roulette(context):
    songs = load_songs()
    if not songs:
        return

    url    = random.choice(songs)
    titolo = html.escape(await get_youtube_title(url))

    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"🎲 <b>Roulette musicale:</b>\n{titolo}\n{url}",
        parse_mode="HTML"
    )


# ---------- comandi ----------

async def canzone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    songs = load_songs()
    if not songs:
        await update.message.reply_text("❌ Nessuna canzone trovata in songs.txt!")
        return

    progress = load_progress()
    index    = progress["index"] % len(songs)
    url      = songs[index]

    progress["index"] = index + 1
    save_progress(progress)

    titolo = html.escape(await get_youtube_title(url))

    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"🎵 <b>Canzone del giorno</b> ({index + 1}/{len(songs)}):\n{titolo}\n{url}",
        parse_mode="HTML"
    )

    if update.effective_chat.id != GROUP_CHAT_ID:
        await update.message.reply_text(f"✅ Canzone #{index + 1} inviata al gruppo!")


async def random_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    songs = load_songs()
    if not songs:
        await update.message.reply_text("❌ Nessuna canzone trovata in songs.txt!")
        return

    url    = random.choice(songs)
    titolo = html.escape(await get_youtube_title(url))

    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"🎲 <b>Canzone casuale:</b>\n{titolo}\n{url}",
        parse_mode="HTML"
    )

    if update.effective_chat.id != GROUP_CHAT_ID:
        await update.message.reply_text("✅ Canzone casuale inviata al gruppo!")


async def start_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name("roulette")
    if jobs:
        await update.message.reply_text("⚠️ La roulette è già attiva!")
        return

    context.job_queue.run_repeating(
        invia_roulette,
        interval=INTERVALLO_MINUTI * 60,
        first=10,
        name="roulette"
    )
    await update.message.reply_text(
        f"▶️ Roulette avviata! Invierò una canzone casuale ogni {INTERVALLO_MINUTI} minuti."
    )


async def stop_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name("roulette")
    if not jobs:
        await update.message.reply_text("⚠️ La roulette non è attiva.")
        return

    for job in jobs:
        job.schedule_removal()
    await update.message.reply_text("⏹️ Roulette fermata.")


async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    songs    = load_songs()
    progress = load_progress()
    prossima = (progress["index"] % len(songs)) + 1 if songs else "—"
    jobs     = context.job_queue.get_jobs_by_name("roulette")
    stato    = f"▶️ Attiva (ogni {INTERVALLO_MINUTI} min)" if jobs else "⏹️ Ferma"
    giorni   = giorni_al_concerto()

    await update.message.reply_text(
        f"📋 <b>Playlist:</b> {len(songs)} canzoni\n"
        f"▶️ Prossima in ordine: #{prossima}\n"
        f"🎲 Roulette: {stato}\n"
        f"📅 Giorni al concerto: <b>{giorni}</b>",
        parse_mode="HTML"
    )


async def mio_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await update.message.reply_text(
        f"📌 <b>Chat ID:</b> <code>{chat.id}</code>\n"
        f"📛 Nome: {chat.title or chat.first_name}",
        parse_mode="HTML"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 <b>Comandi disponibili:</b>\n\n"
        "/canzone       — prossima canzone in ordine\n"
        "/random        — canzone casuale (manuale)\n"
        "/startroulette — avvia roulette automatica\n"
        "/stoproulette  — ferma roulette automatica\n"
        "/lista         — stato playlist e roulette\n"
        "/help          — questo messaggio",
        parse_mode="HTML"
    )


# ---------- avvio ----------

def main():
    if not BOT_TOKEN:
        print("⚠️  Imposta BOT_TOKEN nelle variabili d'ambiente!")
        return
    if GROUP_CHAT_ID == 0:
        print("⚠️  GROUP_CHAT_ID non ancora impostato.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.job_queue.run_daily(
        buongiorno,
        time=ORE_BUONGIORNO,
        name="buongiorno"
    )

    app.add_handler(CommandHandler("canzone",       canzone))
    app.add_handler(CommandHandler("random",        random_song))
    app.add_handler(CommandHandler("startroulette", start_roulette))
    app.add_handler(CommandHandler("stoproulette",  stop_roulette))
    app.add_handler(CommandHandler("lista",         lista))
    app.add_handler(CommandHandler("mio_id",        mio_id))
    app.add_handler(CommandHandler("help",          help_cmd))

    print("🤖 Bot avviato! Premi CTRL+C per fermarlo.")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
