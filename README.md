# OLXRadar

Monitors one or more OLX.pl searches (with any filters you set — location, price range, category, condition, etc.) and sends a separate Telegram message for every new listing, with the description auto-translated to Russian.

Runs for free, in the cloud, on a schedule via GitHub Actions — no server or laptop needs to stay on.

## How a notification looks

```
🔍 Playstation 5

Play station 5 slim z padem 1TB      (bold title, original language)
💰 1 950 zł (цена окончательная / торг уместен)
📝 Translated description...
🔗 Link to the ad
```

## How it works

1. `main.py` reads the search URLs from `target_urls.txt`.
2. `scraper_manager.py` fetches the results (via `curl_cffi`, which mimics a real browser's TLS fingerprint so OLX's anti-bot protection doesn't block it), filters out ads OLX added from other locations once it runs out of local matches, and extracts each ad's title, price, negotiability and description.
3. Every ad not yet seen is compared against `database.db` (a small SQLite file); new ones get a Telegram message and are recorded so they're never sent twice.
4. On GitHub Actions, `database.db` is committed back to the repository after each run, so "already seen" state persists between runs even though every run starts on a fresh machine.

## Setup

### 1. Create a Telegram bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token it gives you.
2. Send any message to your new bot (e.g. `/start`).
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and copy the `"chat":{"id": ...}` value — that's your chat ID.

### 2. Add your search(es)

Open olx.pl, search with whatever filters you want (location, price, category...), and paste the resulting URL into `target_urls.txt` — one URL per line.

### 3. Run it

**Option A — GitHub Actions (recommended, runs in the cloud for free):**

1. Fork/push this repository to your own GitHub account.
2. In the repo settings, go to **Settings → Secrets and variables → Actions** and add two repository secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. That's it — `.github/workflows/olxradar.yml` runs the check every 5 minutes automatically. You can also trigger a run manually from the **Actions** tab (`Run workflow`).

**Option B — run it yourself (local machine or your own server):**

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Create a `.env` file in the project directory:
   ```
   TELEGRAM_BOT_TOKEN="your_token_here"
   TELEGRAM_CHAT_ID="your_chat_id_here"
   ```
3. Run `python main.py` on a schedule — e.g. Windows Task Scheduler (`Control Panel → Administrative Tools → Task Scheduler → Create Basic Task`, action: run `python main.py`), or a cron entry on Linux:
   ```
   */5 * * * * /path/to/olxradar/venv/bin/python /path/to/olxradar/main.py
   ```
