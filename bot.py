import json
import os
import time
import threading
from flask import Flask
import telebot

# ---------------------------------------------------------
# KONFIGURACJA
# ---------------------------------------------------------
TOKEN = "8871900897:AAFIfU-7-NjDeULChGNqf5XeV-jXwfaD9yA"  # <--- Upewnij się, że wklejasz swój token!
TRACKED_FILE = "tracked.json"
CONFIG_FILE = "config.json"

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

def save_user_chat_id(chat_id):
    """Zapisuje Twój Chat ID, aby bot wiedział, gdzie wysyłać automatyczne powiadomienia."""
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            config = {}
    
    if config.get("chat_id") != chat_id:
        config["chat_id"] = chat_id
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

def get_user_chat_id():
    """Pobiera zapisany Chat ID."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("chat_id")
        except Exception:
            return None
    return None

# ---------------------------------------------------------
# AUTOMATYCZNY MONITORING W TLE
# ---------------------------------------------------------
def monitor_stock_job():
    """Funkcja wykonywana cyklicznie w tle co 15 minut."""
    while True:
        try:
            chat_id = get_user_chat_id()
            data = load_tracked()
            tickers = data.get("tickers", [])

            # Monitoring uruchomi się tylko wtedy, gdy bot zna Twój Chat ID oraz masz dodane spółki
            if chat_id and tickers:
                print(f"🔍 Rozpoczynam automatyczne sprawdzanie dla {len(tickers)} tickerów...")
                
                # --- TUTAJ MOŻNA WSTAWIĆ KOD POBIERAJĄCY NOTOWANIA / KOMUNIKATY ---
                for item in tickers:
                    ticker = item["ticker"]
                    name = item.get("name", "")
                    
                    # Przykład: miejsce na zapytanie HTTP do strony z notowaniami/komunikatami
                    # Jeśli zostanie wykryta ważna zmiana:
                    # bot.send_message(chat_id, f"🔔 **Alert NewConnect**: Nowa informacja dla {ticker}!", parse_mode="Markdown")
                    pass
                # ------------------------------------------------------------------

        except Exception as e:
            print(f"⚠️ Błąd w pętli monitorującej: {e}")

        # Odczekaj 15 minut (900 sekund) do następnego sprawdzania
        time.sleep(900)

# ---------------------------------------------------------
# OBSŁUGA KOMEND TELEGRAMA
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    save_user_chat_id(message.chat.id)
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
    save_user_chat_id(message.chat.id)
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
    save_user_chat_id(message.chat.id)
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
    save_user_chat_id(message.chat.id)
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
# PROSTY SERWER FLASK DLA RENDERA
# ---------------------------------------------------------
@app.route("/")
def home():
    return "Bot NewConnect działa na Render.com!"

# ---------------------------------------------------------
# URUCHOMIENIE BOTA, MONITORINGU I SERWERA
# ---------------------------------------------------------
if __name__ == "__main__":
    # 1. Uruchomienie pętli bota Telegram w osobnym wątku
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    
    # 2. Uruchomienie automatycznego monitora w tle w osobnym wątku
    threading.Thread(target=monitor_stock_job, daemon=True).start()
    
    # 3. Uruchomienie serwera WWW wymaganego przez darmowy plan Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

