import os
import json
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
    "Admin commands:\n"
    "-@ <group id or .> <name> [message]  — @mention a member (. = current group)\n"
    "-add <group id or .> <nickname> <phone>  — add a member\n"
    "-remove <group id or .> <name or id>  — remove a member\n"
    "-groups  — list your groups\n"
    "-members <name/phone/id>  — list a group's members"
)

app = Flask(__name__)


def bot_send(bot_id, message):
    """Post a message to a group as the bot."""
    if not bot_id or not message:
        return
    requests.post("https://api.groupme.com/v3/bots/post",
                  json={"bot_id": bot_id, "text": message})


def user_send(token, group, message, mention=True):
    """Send a message to a group as a real user (via their token).

    Used for things SMS users can't do: @mentions and triggering Copilot.
    Returns None on success, or an error string on failure.
    """
    url = f"https://api.groupme.com/v3/groups/{group}/messages?token={token}"
    if mention:
        name = message.split()[0]
        if name == "Copilot":
            uids = [COPILOT_UID]
        else:
            resp = requests.get(f"https://api.groupme.com/v3/groups/{group}?token={token}")
            if not resp.ok:
                return f"couldn't fetch members.\n{resp.status_code} {resp.text}"
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
                    return f"couldn't find user '{name}'"
        loci = [[0, len(name) + 1] for _ in uids]
        data = {"message": {"source_guid": str(datetime.now().timestamp()),
                            "text": f"@{message}",
                            "attachments": [{"type": "mentions", "user_ids": uids, "loci": loci}]}}
    else:
        data = {"message": {"source_guid": str(datetime.now().timestamp()), "text": message}}
    resp = requests.post(url, json=data)
    if not resp.ok:
        return f"couldn't send message.\n{resp.status_code} {resp.text}"
    return None


def add_member(token, group, nickname, number):
    """Add a member by phone number. Numbers without a country code default to +1."""
    phone = number if number.startswith("+") else f"+1{number}"
    resp = requests.post(
        f"https://api.groupme.com/v3/groups/{group}/members/add?token={token}",
        json={"members": [{"nickname": nickname, "phone_number": phone}]})
    if not resp.ok:
        return f"failed to add {nickname} ({phone})\n{resp.status_code} {resp.text}"
    return f"added {nickname}"


def remove_member(token, group, name_or_id):
    mid = None
    members = requests.get(f"https://api.groupme.com/v3/groups/{group}?token={token}").json()["response"]["members"]
    for m in members:
        if name_or_id in (m["nickname"], m["user_id"]):
            mid = m["id"]
            break
    if not mid:
        return f"no member found for '{name_or_id}'"
    resp = requests.post(f"https://api.groupme.com/v3/groups/{group}/members/{mid}/remove?token={token}")
    if not resp.ok:
        return f"error removing '{name_or_id}'\n{resp.status_code} {resp.text}"
    return f"removed {name_or_id}"


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


def handle_admin(text, group_id):
    """Run an admin command. Returns a result string, or None if not an admin command."""
    parts = text.split()
    cmd = parts[0].lower()

    if text.startswith("-@"):
        if len(parts) < 2:
            return "usage: -@<group id or .> <name> [message]"
        group = group_id if parts[0][2:] == "." else parts[0][2:]
        return user_send(ADMIN_TOKEN, group, " ".join(parts[1:]))
    elif cmd == "-add":
        if len(parts) < 4:
            return "usage: -add <group id or .> <nickname> <phone>"
        group = group_id if parts[1] == "." else parts[1]
        return add_member(ADMIN_TOKEN, group, parts[2], parts[3])
    elif cmd == "-remove":
        if len(parts) < 3:
            return "usage: -remove <group id or .> <name or id>"
        group = group_id if parts[1] == "." else parts[1]
        return remove_member(ADMIN_TOKEN, group, parts[2])
    elif cmd == "-groups":
        return fetch_groups(ADMIN_TOKEN)
    elif cmd == "-members":
        if len(parts) < 2:
            return "usage: -members <name/phone/id>"
        return fetch_members(ADMIN_TOKEN, parts[1])
    elif cmd == "--help":
        return ADMIN_HELP
    return None


def handle_command(text):
    """Run a utility command. Returns a result string, or None if no command matched."""
    low = text.lower()
    if low.startswith("-help"):
        return HELP
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
            result = user_send(token, group_id, f"Copilot {text[1:]}")
    # Admin commands, only for the configured admin.
    elif sender_id and sender_id == ADMIN_UID and ADMIN_TOKEN:
        result = handle_admin(text, group_id)

    # Utility commands are available to everyone.
    if result is None:
        result = handle_command(text)

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
