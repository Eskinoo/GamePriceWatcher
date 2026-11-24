
import json
import os
import re
import sys
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
STATE_PATH = BASE / "data" / "state.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def parse_price(text):
    cleaned = text.replace("\xa0", " ").replace("EUR", "€")
    matches = re.findall(
        r"(?:(?:€)\s*)?(\d{1,3}(?:[.\s]\d{3})*(?:[,.]\d{2})|\d+(?:[,.]\d{2})?)\s*€?",
        cleaned
    )

    for raw in matches:
        raw = raw.replace(" ", "")
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            raw = raw.replace(",", ".")

        try:
            return float(raw)
        except ValueError:
            continue

    return None


def fetch_price(game, browser):
    url = game["url"]
    selector = game.get("price_selector", "").strip()

    if not selector:
        raise ValueError("Selettore CSS del prezzo non configurato")

    page = browser.new_page()

    try:
        print(f"[INFO] Apro la pagina: {url}")

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        locator = page.locator(selector).first

        locator.wait_for(
            state="visible",
            timeout=45000
        )

        price_text = locator.inner_text(timeout=15000)
        price = parse_price(price_text)

        if price is None:
            raise ValueError(
                f"Prezzo non interpretabile: {price_text!r}"
            )

        print(f"[INFO] Prezzo trovato nella pagina: {price_text}")
        return price

    finally:
        page.close()


def telegram_send(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        raise RuntimeError(
            "Mancano TELEGRAM_BOT_TOKEN e/o TELEGRAM_CHAT_ID"
        )

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": message
        },
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"Telegram ha rifiutato il messaggio: {data}"
        )


def main():
    config = load_json(CONFIG_PATH, {"games": []})
    state = load_json(STATE_PATH, {})
    errors = 0
    enabled_games = [
        game for game in config.get("games", [])
        if game.get("enabled", False)
    ]

    if not enabled_games:
        print("[INFO] Nessun gioco attivo nel file config.json")
        return

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

        try:
            for game in enabled_games:
                name = game.get("name", "Gioco senza nome")
                key = game.get("url", name)
                previous = state.get(key, {})

                try:
                    price = fetch_price(game, browser)
                    threshold = float(game["threshold"])

                    state[key] = {
                        "last_price": price,
                        "below_threshold": price <= threshold
                    }

                    print(
                        f"[OK] {name}: {price:.2f} EUR "
                        f"(soglia {threshold:.2f})"
                    )

                    was_below = previous.get(
                        "below_threshold", False
                    )

                    if price <= threshold and not was_below:
                        msg = (
                            f"🎮 OFFERTA TROVATA!\n"
                            f"{name}\n"
                            f"Prezzo rilevato: {price:.2f} €\n"
                            f"Prezzo obiettivo: {threshold:.2f} €\n"
                            f"{game.get('site', '')}\n"
                            f"{game['url']}"
                        )

                        telegram_send(msg)
                        print("[TELEGRAM] Notifica inviata.")

                except Exception as exc:
                    errors += 1
                    print(
                        f"[ERRORE] {name}: {exc}",
                        file=sys.stderr
                    )

        finally:
            browser.close()

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    if errors:
        print(f"Completato con {errors} errore/i.")
    else:
        print("Controllo completato.")


if __name__ == "__main__":
    main()
