from __future__ import annotations

# Menu copy: short verbs, benefit-led descriptions (Telegram menu ~4s glance).
COMMAND_MENU: list[dict[str, str]] = [
    {"command": "start", "description": "Get started — how alerts work"},
    {"command": "help", "description": "See what I can do"},
    {"command": "desk", "description": "Open filter & history catalog"},
    {"command": "status", "description": "Last check & alert health"},
    {"command": "filters", "description": "Your current match rules"},
    {"command": "sources", "description": "Boards I'm watching"},
    {"command": "latest", "description": "Recent jobs that matched"},
    {"command": "mute", "description": "Pause alerts until you unmute"},
    {"command": "unmute", "description": "Turn alerts back on"},
]

BOT_SHORT_DESCRIPTION = "Personal job alerts for roles you care about."
BOT_DESCRIPTION = (
    "I watch company career pages and job boards, then ping you only when "
    "something new matches your filters.\n\n"
    "Tap Catalog (menu) or /desk for the Web App. Alerts stay private to your chat."
)


def start_keyboard() -> dict:
    from jw.webapp.link import start_keyboard as _sk

    return _sk()


# Kept for imports that expect a constant; rebuilt dynamically at use sites.
START_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "Open catalog", "callback_data": "cmd:desk"},
            {"text": "Latest jobs", "callback_data": "cmd:latest"},
        ],
        [
            {"text": "Status", "callback_data": "cmd:status"},
            {"text": "Help", "callback_data": "cmd:help"},
        ],
    ]
}
