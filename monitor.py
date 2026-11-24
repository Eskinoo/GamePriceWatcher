import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
STATE_PATH = BASE / "data" / "state.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GamePriceWatcher/1.0; price-check)"
}

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def parse_price(text):
    # Supports common formats such as 9,99 €, €9.99, 1.299,00 €
    cleaned = text.replace("\xa0", " ").replace("EUR", "€")
    matches = re.findall(r"(?:(?:€)\s*)?(\d{1,3}(?:[.\s]\d{3})*(?:[,.]\d{2})|\d+(?:[,.]\d{2})?)\s*€?", cleaned)
    values = []
    for raw in matches:
        raw = raw.replace(" ", "")
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            raw = raw.replace(",", ".")
        try:
            values.append(float(raw))
        except ValueError:
            pass
    return values[0] if values else None

def fetch_price(game):
    url = game["url"]
    selector = game.get("price_selector", "").strip()
    if not selector:
        raise ValueError("Selettore CSS del prezzo non configurato")
    response = requests.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    element = soup.select_one(selector)
    if element is None:
        raise ValueError(f"Selettore CSS non trovato: {selector}")
    price = parse_price(element.get_text(" ", strip=True))
    if price is None:
        raise ValueError(f"Non riesco a interpretare il prezzo: {element.get_text(' ', strip=True)!r}")
    return price

def telegram_send(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Mancano i segreti TELEGRAM_BOT_TOKEN e/o TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=20)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram ha rifiutato il messaggio: {data}")

def main():
    config = load_json(CONFIG_PATH, {"games": []})
    state = load_json(STATE_PATH, {})
    errors = 0
    for game in config.get("games", []):
        if not game.get("enabled", False):
            continue
        name = game.get("name", "Gioco senza nome")
        key = game.get("url", name)
        previous = state.get(key, {})
        try:
            price = fetch_price(game)
            threshold = float(game["threshold"])
            state[key] = {"last_price": price, "below_threshold": price <= threshold}
            print(f"[OK] {name}: {price:.2f} EUR (soglia {threshold:.2f})")
            was_below = previous.get("below_threshold", False)
            if price <= threshold and not was_below:
                msg = (
                    f"🎮 OFFERTA TROVATA!\n{name}\n"
                    f"Prezzo rilevato: {price:.2f} €\n"
                    f"Prezzo obiettivo: {threshold:.2f} €\n"
                    f"{game.get('site', '')}\n{game['url']}"
                )
                telegram_send(msg)
                print("[TELEGRAM] Notifica inviata.")
        except Exception as exc:
            errors += 1
            print(f"[ERRORE] {name}: {exc}", file=sys.stderr)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if errors:
        print(f"Completato con {errors} errore/i.")
    else:
        print("Controllo completato.")

if __name__ == "__main__":
    main()
