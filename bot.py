import json
import os
import time
import threading
import requests
import feedparser
from flask import Flask
import telebot

# ---------------------------------------------------------
# KONFIGURACJA
# ---------------------------------------------------------
TOKEN = "8871900897:AAFIfU-7-NjDeULChGNqf5XeV-jXwfaD9yA"  # <--- Podmień na swój token!
TRACKED_FILE = "tracked.json"
CONFIG_FILE = "config.json"
SENT_NEWS_FILE = "sent_news.json"

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

def load_sent_news():
    if not os.path.exists(SENT_NEWS_FILE):
        return []
    try:
        with open(SENT_NEWS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_sent_news(sent_list):
    sent_list = sent_list[-200:]
    with open(SENT_NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(sent_list, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------
# AUTOMATYCZNY MONITORING WIADOMOŚCI W TLE
# ---------------------------------------------------------
def check_news_feed():
    chat_id = get_user_chat_id()
    if not chat_id:
        return

    data = load_tracked()
    tickers = data.get("tickers", [])
    if not tickers:
        return

    rss_url = "https://www.bankier.pl/rss/wiadomosci.xml"
    
    try:
        feed = feedparser.parse(rss_url)
        sent_news = load_sent_news()
        updated_sent = False

        for entry in feed.entries:
            news_id = getattr(entry, 'id', entry.link)
            if news_id in sent_news:
                continue

            title = entry.title
            link = entry.link

            for item in tickers:
                ticker = item["ticker"].upper()
                name = item.get("name", "").upper()

                match_ticker = f" {ticker} " in f" {title.upper()} " or f"({ticker})" in title.upper()
                match_name = name and len(name) > 3 and name in title.upper()

                if match_ticker or match_name:
                    message_text = (
                        f"🔔 **Nowa informacja: {ticker}**\n\n"
                        f"📰 **{title}**\n\n"
                        f"🔗 [Przeczytaj artykuł]({link})"
                    )
                    
                    bot.send_message(chat_id, message_text, parse_mode="Markdown")
                    sent_news.append(news_id)
                    updated_sent = True
                    break

        if updated_sent:
            save_sent_news(sent_news)

    except Exception as e:
        print(f"⚠️ Błąd podczas sprawdzania wiadomości: {e}")

def monitor_stock_job():
    while True:
        try:
            check_news_feed()
        except Exception as e:
            print(f"⚠️ Błąd w monitor_stock_job: {e}")

        time.sleep(600)

# ---------------------------------------------------------
# OBSŁUGA KOMEND TELEGRAMA
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    save_user_chat_id(message.chat.id)
    help_text = (
        "🤖 **Monitor NewConnect - Bot**\n\n"
        "Dostępne komendy:\n"
        "🔹 `/lista` - Wyświetla prostą listę obserwowanych spółek\n"
        "🔹 `/dodaj <TICKER> <Nazwa>` - Dodaje ticker do obserwacji\n"
        "🔹 `/usun <TICKER>` - Usuwa ticker z listy\n\n"
        "🔔 *Bot automatycznie powiadamia Cię na bieżąco o nowych komunikatach!*"
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

    text = f"📋 **Obserwowane spółki ({len(tickers)}):**\n\n"
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
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    threading.Thread(target=monitor_stock_job, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

