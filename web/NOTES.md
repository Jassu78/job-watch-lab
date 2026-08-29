# Phosphor Catalog + Telegram Web App plugin

## Same-host wiring
```bash
export JW_LAB_ROOT=/path/to/job-watch-lab   # required
export JW_WEB_HOST=0.0.0.0                  # or your bind address
export JW_WEB_PORT=3099
python3 server.py
```

Shares filters/state with the lab via `JW_LAB_ROOT`. Auth plugin lives in the lab: `jw/webapp/`.

## Telegram Mini App
In lab `config/secrets.env`:
```
WEB_APP_URL=https://YOUR_HTTPS_HOST
WEB_UI_SECRET=...   # already present
```

Then on the bot host:
```bash
python3 scripts/bot.py --install-menu
```
That sets commands + **Catalog** chat menu button (`web_app`).

Until `WEB_APP_URL` is HTTPS, `/desk` uses same-host desk-key fallback (`WEB_UI_HOST` / `WEB_UI_URL`).

## Auth modes
1. **Mini App** — `Telegram.WebApp.initData` → `POST /api/auth/telegram` → session token  
2. **Fallback** — daily desk key from `/desk` (`?k=` or gate form)
