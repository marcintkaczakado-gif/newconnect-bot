import json
import os
import threading
from flask import Flask
import telebot

# ---------------------------------------------------------
# KONFIGURACJA
# ---------------------------------------------------------
TOKEN = "TUTAJ_WKLEJ_SWOJ_TOKEN_Z_BOTFATHER"  # <--- Podmień na swój token z BotFather!
TRACKED_FILE = "tracked.json"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ---------------------------------------------------------
# FUNKCJE POMOCNICZE DANYCH
# ---------------------------------------------------------
def load_tracked():
    if not os.path.exists(TRACKED_FILE):
        return {"tickers": []}
    try:
        with open(TRACKED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "tickers" in data:
                return data
    except (json.JSONDecodeError, IOError):
        pass
    return {"tickers": []}

def save_tracked(data):
    if "tickers" in data:
        data["tickers"] = sorted(data["tickers"], key=lambda x: x["ticker"])
    with open(TRACKED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------
# OBSŁUGA KOMEND TELEGRAMA
# ---------------------------------------------------------

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = (
        "🤖 **Monitor NewConnect - Bot**\n\n"
        "Dostępne komendy:\n"
        "🔹 `/lista` - Wyświetla listę obserwowanych spółek\n"
        "🔹 `/dodaj <TICKER> <Nazwa>` - Dodaje ticker do obserwacji\n"
        "🔹 `/usun <TICKER>` - Usuwa ticker z listy\n\n"
        "Przykład dodawania:\n"
        "`/dodaj ABC Firma ABC S.A.`"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['lista'])
def list_tickers(message):
    data = load_tracked()
    tickers = data.get("tickers", [])
    
    if not tickers:
        bot.reply_to(message, "📂 Lista obserwowanych tickerów jest pusta.")
        return

    text = f"📊 **Obserwowane tickery ({len(tickers)}):**\n\n"
    for t in tickers:
        name_str = f" - {t['name']}" if t.get('name') else ""
        text += f"• **{t['ticker']}**{name_str}\n"

    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['dodaj'])
def add_ticker(message):
    args = message.text.split(maxsplit=2)
    
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Podaj ticker! Składnia: `/dodaj TICKER Nazwa spółki`", parse_mode="Markdown")
        return

    ticker = args[1].strip().upper()
    name = args[2].strip() if len(args) > 2 else ""

    data = load_tracked()
    existing = {x["ticker"]: x for x in data["tickers"]}

    if ticker not in existing:
        data["tickers"].append({"ticker": ticker, "name": name})
        response = f"✅ Dodano ticker: **{ticker}**" + (f" ({name})" if name else "")
    else:
        if name:
            existing[ticker]["name"] = name
            response = f"🔄 Zaktualizowano nazwę dla: **{ticker}** -> {name}"
        else:
            response = f"ℹ️ Ticker **{ticker}** już znajduje się na liście."

    save_tracked(data)
    bot.reply_to(message, response, parse_mode="Markdown")

@bot.message_handler(commands=['usun'])
def remove_ticker(message):
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Podaj ticker do usunięcia! Składnia: `/usun TICKER`", parse_mode="Markdown")
        return

    ticker = args[1].strip().upper()
    data = load_tracked()
    
    initial_count = len(data["tickers"])
    data["tickers"] = [x for x in data["tickers"] if x["ticker"] != ticker]
    
    if len(data["tickers"]) < initial_count:
        save_tracked(data)
        bot.reply_to(message, f"🗑️ Usunięto ticker: **{ticker}**", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"❌ Nie znaleziono tickera **{ticker}** na liście.", parse_mode="Markdown")

# ---------------------------------------------------------
# ATROPA DLA RENDERA (PROSTY SERWER FLASK)
# ---------------------------------------------------------
@app.route("/")
def home():
    return "Bot NewConnect działa na Render.com!"

# ---------------------------------------------------------
# URUCHOMIENIE BOTA I SERWERA
# ---------------------------------------------------------
if __name__ == "__main__":
    # Uruchomienie pętli bota Telegram w osobnym wątku
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    
    # Uruchomienie serwera WWW wymaganego przez darmowy plan Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
