import os
import json
import time
import threading
from datetime import datetime

import requests
from flask import Flask, request
from dotenv import load_dotenv

from utilities import zmanim, weather, temp, currency, spellcheck, stock, dictionary, translate

load_dotenv()

# --- Configuration (all optional) ---
ADMIN_TOKEN = os.getenv("GROUPME_TOKEN", "")
ADMIN_UID = os.getenv("ADMIN_UID", "")
FALLBACK_TOKEN = os.getenv("FALLBACK_TOKEN", "")
AUTH_CODE = os.getenv("AUTH_CODE", "")

# Copilot is a built-in GroupMe assistant account with the same user ID in every group.
COPILOT_UID = "128934125"

# Tokens tried in order for read-only lookups (e.g. -list), since not every account is in every group.
READ_TOKENS = [t for t in (ADMIN_TOKEN, FALLBACK_TOKEN) if t]

# group_id -> bot_id, loaded from config.json (see config.example.json)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
try:
    with open(CONFIG_PATH) as f:
        BOT_MAP = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    BOT_MAP = {}

HELP = """
commands are not case-sensitive.
Chat (Copilot): +[Your question](ex: + tell me a joke)
Roster of this group: -list
Translate: -translate [lang code] [text](ex: -translate es hello)
== Weather & Zmanim ==
(Location defaults to Jerusalem if not provided)
7-Day Forecast: -weather [city or zip]
Hourly Forecast: -weather hour [city or zip]
Zmanim: -zmanim [city or zip]
== Utilities ==
Currency: -currency [amount] [from] [to](ex: -currency 100 USD ILS)(defaults to 1 usd to ils) (you can provide multiple [to] options. ex: '-currency 3 usd ils gbp eur' up to 10.)
Stocks: -stock [ticker](ex: -stock AAPL)(default: spym - s&p. works for crypto.)
Spell Check: -spellcheck [your text here]
Dictionary: -dictionary [word]
Temp Converter:-temp [number] [F or C](ex: -temp 100 C)

credits: @flipphoneguy
"""

ADMIN_HELP = (
    "Admin commands (group is the LAST arg; . = current group):\n"
    "-@ <group id or .> <name> [message]  — @mention a member\n"
    "-add <nickname> <phone> [group id or .]  — add a member\n"
    "-remove <name or id> [group id or .]  — remove a member\n"
    "-groups  — list your groups\n"
    "-members [group name/phone/id]  — detailed member list (defaults to this group)"
)

app = Flask(__name__)


def bot_send(bot_id, message):
    """Post a message to a group as the bot."""
    if not bot_id or not message:
        return
    requests.post("https://api.groupme.com/v3/bots/post",
                  json={"bot_id": bot_id, "text": message})


# GroupMe doesn't deliver Copilot's messages to bot callbacks, so after mentioning Copilot we poll the group for its reply (~2-3s later) and echo it via the bot, so SMS users see the text. In-app users see it twice.
COPILOT_FIRST_DELAY = 2.0
COPILOT_POLL_INTERVAL = 0.7
COPILOT_POLL_DEADLINE = 12   # seconds


def schedule_copilot_echo(token, group_id, bot_id, since_id):
    if not (token and bot_id and since_id):
        return
    deadline = time.time() + COPILOT_POLL_DEADLINE
    threading.Timer(COPILOT_FIRST_DELAY, _poll_copilot_echo,
                    args=(token, group_id, bot_id, since_id, deadline)).start()


def _poll_copilot_echo(token, group_id, bot_id, since_id, deadline):
    try:
        r = requests.get(f"https://api.groupme.com/v3/groups/{group_id}/messages",
                         params={"token": token, "since_id": since_id, "limit": 20})
        msgs = r.json().get("response", {}).get("messages", []) if r.ok else []
        cop = sorted([m for m in msgs if m.get("user_id") == COPILOT_UID], key=lambda m: m["created_at"])
        if cop:
            bot_send(bot_id, cop[0].get("text"))
            return
    except Exception:
        pass
    if time.time() < deadline:
        threading.Timer(COPILOT_POLL_INTERVAL, _poll_copilot_echo,
                        args=(token, group_id, bot_id, since_id, deadline)).start()


def user_send(token, group, message, mention=True):
    """Send to a group as a real user (for @mentions / Copilot).
    Returns (message_id, error): id on success, error string on failure.
    """
    url = f"https://api.groupme.com/v3/groups/{group}/messages?token={token}"
    if mention:
        name = message.split()[0]
        if name == "Copilot":
            uids = [COPILOT_UID]
        else:
            resp = requests.get(f"https://api.groupme.com/v3/groups/{group}?token={token}")
            if not resp.ok:
                return None, f"couldn't fetch members.\n{resp.status_code} {resp.text}"
            members = resp.json()["response"]["members"]
            if name == "all":
                uids = [m["user_id"] for m in members]
            else:
                uids = None
                for m in members:
                    if name in (m["nickname"], m["user_id"]):
                        uids = [m["user_id"]]
                        name = m["nickname"]
                        message = f"{name} {' '.join(message.split()[1:])}"
                        break
                if not uids:
                    return None, f"couldn't find user '{name}'"
        loci = [[0, len(name) + 1] for _ in uids]
        data = {"message": {"source_guid": str(datetime.now().timestamp()),
                            "text": f"@{message}",
                            "attachments": [{"type": "mentions", "user_ids": uids, "loci": loci}]}}
    else:
        data = {"message": {"source_guid": str(datetime.now().timestamp()), "text": message}}
    resp = requests.post(url, json=data)
    if not resp.ok:
        return None, f"couldn't send message.\n{resp.status_code} {resp.text}"
    try:
        return resp.json()["response"]["message"]["id"], None
    except Exception:
        return None, None


def add_member(token, group, nickname, number):
    """Add a member by phone (defaults to +1). Returns an error string, or None on success."""
    phone = number if number.startswith("+") else f"+1{number}"
    resp = requests.post(
        f"https://api.groupme.com/v3/groups/{group}/members/add?token={token}",
        json={"members": [{"nickname": nickname, "phone_number": phone}]})
    if not resp.ok:
        return f"failed to add {nickname} ({phone})\n{resp.status_code} {resp.text}"


def remove_member(token, group, name_or_id):
    """Remove a member by nickname or user id. Returns an error string, or None on success."""
    resp = requests.get(f"https://api.groupme.com/v3/groups/{group}?token={token}")
    if not resp.ok:
        return f"couldn't fetch group {group}\n{resp.status_code} {resp.text}"
    mid = None
    for m in resp.json()["response"]["members"]:
        if name_or_id in (m["nickname"], m["user_id"]):
            mid = m["id"]
            break
    if not mid:
        return f"no member found for '{name_or_id}'"
    resp = requests.post(f"https://api.groupme.com/v3/groups/{group}/members/{mid}/remove?token={token}")
    if not resp.ok:
        return f"error removing '{name_or_id}'\n{resp.status_code} {resp.text}"


def fetch_groups(token):
    response = requests.get(f"https://api.groupme.com/v3/groups?token={token}&per_page=30&omit=memberships").json()["response"]
    groups = ""
    for group in response or []:
        groups += f"{group['name']}: {group['group_id']}. {group['phone_number']}\n"
    return groups or "no groups found."


def fetch_members(token, query):
    response = requests.get(f"https://api.groupme.com/v3/groups?token={token}&per_page=30").json()["response"]
    target = None
    for group in response or []:
        if query in (group["name"], group["phone_number"], group["group_id"]):
            target = group
            break
    if target is None:
        return f"no group found for '{query}'"
    members = f"{target['name']} {target['group_id']} {target['phone_number']}\n\n"
    for member in target["members"]:
        muted = " muted" if member["muted"] else ""
        kicked = " autokicked" if member["autokicked"] else ""
        roles = member["roles"] if member["roles"] != ["user"] else ""
        members += f"{member['nickname']} ({member['name']}){muted}{kicked} {roles} uid: {member['user_id']} mid: {member['id']}\n"
    return members


def list_members(group):
    """Plain roster: group name, then nicknames with (admin)/(muted) tags. Tries each token; None if unreadable."""
    g = None
    for token in READ_TOKENS:
        resp = requests.get(f"https://api.groupme.com/v3/groups/{group}?token={token}")
        if resp.ok:
            g = resp.json()["response"]
            break
    if not g:
        return None
    lines = [g["name"], ""]
    for m in g["members"]:
        tags = []
        if any(r in ("admin", "owner") for r in m.get("roles", [])):
            tags.append("admin")
        if m.get("muted"):
            tags.append("muted")
        tag = f" ({', '.join(tags)})" if tags else ""
        lines.append(f"{m['nickname']}{tag}")
    return "\n".join(lines)


def handle_admin(text, group_id):
    """Run an admin command. Returns a result/error string to post, or None (nothing to say)."""
    parts = text.split()
    cmd = parts[0].lower()

    if text.startswith("-@"):
        if len(parts) < 2:
            return "usage: -@<group id or .> <name> [message]"
        group = group_id if parts[0][2:] in ("", ".") else parts[0][2:]
        _, err = user_send(ADMIN_TOKEN, group, " ".join(parts[1:]))
        return err
    elif cmd == "-add":
        # Group is the LAST arg (. = current); a multi-word nickname thus needs an explicit trailing group.
        if len(parts) < 3:
            return "usage: -add <nickname> <phone> [group id or .]"
        if len(parts) == 3:
            nickname, phone, group = parts[1], parts[2], group_id
        else:
            group = group_id if parts[-1] == "." else parts[-1]
            phone, nickname = parts[-2], " ".join(parts[1:-2])
        return add_member(ADMIN_TOKEN, group, nickname, phone)
    elif cmd == "-remove":
        # Group is the LAST arg (. = current); a multi-word name thus needs an explicit trailing group.
        if len(parts) < 2:
            return "usage: -remove <name or id> [group id or .]"
        if len(parts) == 2:
            name, group = parts[1], group_id
        else:
            group = group_id if parts[-1] == "." else parts[-1]
            name = " ".join(parts[1:-1])
        return remove_member(ADMIN_TOKEN, group, name)
    elif cmd == "-groups":
        return fetch_groups(ADMIN_TOKEN)
    elif cmd == "-members":
        # -members [group name/phone/id]   Defaults to the current group.
        query = parts[1] if len(parts) > 1 and parts[1] != "." else group_id
        return fetch_members(ADMIN_TOKEN, query)
    elif cmd == "--help":
        return ADMIN_HELP
    return None


def handle_command(text, group_id):
    """Run a command available to everyone. Returns a result string, or None if nothing matched."""
    low = text.lower()
    if low.startswith("-help"):
        return HELP
    elif low.startswith("-list"):
        return list_members(group_id) or "couldn't fetch member list."
    elif low.startswith("-currency"):
        return currency(*text.split()[1:])
    elif low.startswith("-weather"):
        return weather(text[9:]) if text[9:] else weather()
    elif low.startswith("-zmanim"):
        return zmanim(text[8:]) if text[8:] else zmanim()
    elif low.startswith("-temp"):
        return temp(text.split()[1], text.split()[2]) if text.split()[2:] else "invalid input"
    elif low.startswith("-stock"):
        return stock(text[7:]) if text[7:] else stock()
    elif low.startswith("-spellcheck"):
        return spellcheck(text[12:]) if text[12:] else "invalid input"
    elif low.startswith("-dictionary"):
        return dictionary(text[12:])
    elif low.startswith("-translate"):
        return translate(text.split()[1], " ".join(text.split()[2:])) if text.split()[2:] else "invalid input"
    return None


def calculate_response(text, sender_id, group_id, route):
    bot_id = BOT_MAP.get(group_id)
    result = None

    # + forwards a message to Copilot on the sender's behalf (mentions can't be done via SMS).
    if text.startswith("+") and route != "general":
        token = ADMIN_TOKEN if sender_id == ADMIN_UID else (FALLBACK_TOKEN or ADMIN_TOKEN)
        if token:
            mention_id, err = user_send(token, group_id, f"Copilot {text[1:]}")
            # GroupMe won't push Copilot's reply to our webhook, so poll for it and echo it to SMS users.
            schedule_copilot_echo(token, group_id, bot_id, mention_id)
            result = err
    # Admin commands, only for the configured admin.
    elif sender_id and sender_id == ADMIN_UID and ADMIN_TOKEN:
        result = handle_admin(text, group_id)

    # Commands available to everyone (utilities and -list).
    if result is None:
        result = handle_command(text, group_id)

    if result and bot_id:
        bot_send(bot_id, result)


def getGroupMeMessage(data, route="groupme"):
    if not data or not data.get("text"):
        return "no data from groupme"
    if data.get("sender_type") == "bot":
        return  # ignore bots (including ourselves) to avoid loops
    calculate_response(
        text=data.get("text"),
        sender_id=data.get("user_id"),
        group_id=data.get("group_id"),
        route=route,
    )


def _authorized():
    return not AUTH_CODE or request.args.get("auth") == AUTH_CODE


@app.route("/", methods=["POST"])
def groupme():
    if not _authorized():
        return "denied", 403
    getGroupMeMessage(request.get_json())
    return "ok"


@app.route("/general/", methods=["POST"])
def general():
    if not _authorized():
        return "denied", 403
    getGroupMeMessage(request.get_json(), route="general")
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
