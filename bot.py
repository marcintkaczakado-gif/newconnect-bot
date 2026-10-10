import json
import os
import time
import threading
import requests
from flask import Flask
import telebot

# ---------------------------------------------------------
# KONFIGURACJA
# ---------------------------------------------------------
TOKEN = "8871900897:AAFIfU-7-NjDeULChGNqf5XeV-jXwfaD9yA"  # <--- Podmień swój token z BotFather!
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
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("chat_id")
        except Exception:
            return None
    return None

# ---------------------------------------------------------
# POBIERANIE NOTOWAŃ ZE STOOQ
# ---------------------------------------------------------
def get_stock_data(ticker):
    """
    Pobiera aktualny kurs i zmianę procentową dla podanego bocznego symbolu giełdowego.
    """
    try:
        url = f"https://stooq.pl/q/l/?s={ticker.lower()}&f=sd2t2ohlcv&h&e=json"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            symbols = data.get("symbols", [])
            if symbols and len(symbols) > 0:
                symbol_data = symbols[0]
                close_price = symbol_data.get("close")
                change_percent = symbol_data.get("change_percent")
                
                if close_price is not None and close_price != "N/A":
                    return {
                        "price": float(close_price),
                        "change_percent": float(change_percent) if change_percent is not None else 0.0
                    }
    except Exception as e:
        print(f"Błąd podczas pobierania notowań dla {ticker}: {e}")
    return None

# ---------------------------------------------------------
# AUTOMATYCZNY MONITORING W TLE
# ---------------------------------------------------------
def monitor_stock_job():
    while True:
        try:
            chat_id = get_user_chat_id()
            data = load_tracked()
            tickers = data.get("tickers", [])

            if chat_id and tickers:
                print(f"🔍 Pętla tła aktywna dla {len(tickers)} tickerów...")
        except Exception as e:
            print(f"⚠️ Błąd w pętli monitorującej: {e}")

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
        "🔹 `/lista` - Pobiera listę obserwowanych spółek wraz z kursami i zmianą %\n"
        "🔹 `/kurs <TICKER>` - Sprawdza notowanie wybranej spółki\n"
        "🔹 `/dodaj <TICKER> <Nazwa>` - Dodaje ticker do obserwacji\n"
        "🔹 `/usun <TICKER>` - Usuwa ticker z listy\n\n"
        "Przykład dodawania:\n"
        "`/dodaj WASKO Wasko S.A.`"
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

    # Informacja o przetwarzaniu zapytania
    msg = bot.reply_to(message, "⏳ Pobieram aktualne notowania...")

    text = f"📊 **Obserwowane spółki ({len(tickers)}):**\n\n"
    
    for t in tickers:
        ticker = t['ticker']
        name = t.get('name', '')
        name_str = f" ({name})" if name else ""
        
        stock_info = get_stock_data(ticker)
        
        if stock_info:
            price = stock_info["price"]
            change = stock_info["change_percent"]
            
            # Wskaźnik graficzny (zielona/czerwona kropka)
            if change > 0:
                emoji = "🟢"
                sign = "+"
            elif change < 0:
                emoji = "🔴"
                sign = ""
            else:
                emoji = "⚪"
                sign = ""
                
            text += f"{emoji} **{ticker}**{name_str}: `{price:.2f} PLN` ({sign}{change:.2f}%)\n"
        else:
            text += f"⚪ **{ticker}**{name_str}: *brak danych*\n"

    bot.edit_message_text(text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")

@bot.message_handler(commands=['kurs'])
def get_single_stock(message):
    save_user_chat_id(message.chat.id)
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Podaj ticker! Składnia: `/kurs TICKER`", parse_mode="Markdown")
        return

    ticker = args[1].strip().upper()
    stock_info = get_stock_data(ticker)
    
    if stock_info:
        price = stock_info["price"]
        change = stock_info["change_percent"]
        
        if change > 0:
            emoji = "🟢"
            sign = "+"
        elif change < 0:
            emoji = "🔴"
            sign = ""
        else:
            emoji = "⚪"
            sign = ""
            
        text = f"{emoji} **{ticker}**\n📈 **Kurs:** `{price:.2f} PLN`\n📊 **Zmiana:** `{sign}{change:.2f}%`"
    else:
        text = f"❌ Nie udało się pobrać danych dla **{ticker}**."
        
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
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    threading.Thread(target=monitor_stock_job, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


