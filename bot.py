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
TOKEN = "8871900897:AAFIfU-7-NjDeULChGNqf5XeV-jXwfaD9yA"  # <--- Wklej swój token!
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
    except Exception:
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
    Pobiera dane giełdowe, testując różne warianty symboli na Stooq.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    clean_ticker = ticker.lower().strip()
    # Lista wariantów symbolu do sprawdzenia na Stooq dla polskiej giełdy
    variants = [
        clean_ticker, 
        f"{clean_ticker}.pl", 
        f"{clean_ticker}e" # czasami NewConnect ma końcówkę e lub inne oznaczenia
    ]
    
    for var in variants:
        try:
            url = f"https://stooq.pl/q/l/?s={var}&f=sd2t2ohlcv&h&e=json"
            response = requests.get(url, headers=headers, timeout=3)
            if response.status_code == 200:
                data = response.json()
                symbols = data.get("symbols", [])
                if symbols:
                    symbol_data = symbols[0]
                    close_price = symbol_data.get("close")
                    change_percent = symbol_data.get("change_percent")
                    
                    if close_price is not None and str(close_price) != "N/A":
                        return {
                            "price": float(close_price),
                            "change_percent": float(change_percent) if change_percent is not None else 0.0
                        }
        except Exception as e:
            print(f"Stooq API err ({var}): {e}")

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
        "🔹 `/lista` - Wyświetla obserwowani spółki z notowaniami\n"
        "🔹 `/kurs <TICKER>` - Sprawdza pojedynczą spółkę\n"
        "🔹 `/dodaj <TICKER> <Nazwa>` - Dodaje ticker\n"
        "🔹 `/usun <TICKER>` - Usuwa ticker\n\n"
        "Przykład:\n"
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
            text += f"⚪ **{ticker}**{name_str}: *brak danych z giełdy*\n"

    try:
        bot.edit_message_text(text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, text, parse_mode="Markdown")

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



