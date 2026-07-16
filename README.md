# GroupMe Utility Bot

A self-hosted GroupMe bot with a handful of text commands: weather, stock and crypto quotes, currency conversion, a dictionary, translation, spell-check, temperature conversion, Jewish prayer times (zmanim), and a bridge to GroupMe's built-in Copilot assistant.

The main reason it exists is to give SMS-only members access to things that otherwise need the GroupMe app as well as the utilities. Mentions and Copilot can't be done over SMS, so the bot exposes them as plain text commands. Adding and removing also often fail by SMS.

None of the data sources need an API key. Weather comes from open-meteo, zmanim from Hebcal, stocks/crypto/currency from Yahoo Finance via `yfinance`, definitions from the free Dictionary API, and translation from Google Translate via `deep-translator`.

> **No server?** [@jayjaytech](https://github.com/jayjaytech) ported this bot to [Google Apps Script](https://github.com/jayjaytech/Groupme-flipphoneguy), so you can run it without hosting anything yourself.

## Commands

Commands are not case-sensitive. `[bracketed]` parts are values you supply; where there's a default it's noted below.

### Utility commands (anyone)

| Command | What it does | Example |
| --- | --- | --- |
| `-help` | List all commands | `-help` |
| `-list` | Plain roster of the current group (nicknames with admin/muted tags) | `-list` |
| `-weather [city or zip]` | 7-day forecast (defaults to Jerusalem) | `-weather Chicago` |
| `-weather hour [city or zip]` | Hourly forecast for today | `-weather hour 10001` |
| `-zmanim [city or zip]` | Today and tomorrow's halachic times | `-zmanim Lakewood` |
| `-currency [amount] [from] [to ...]` | Convert currency; up to 10 targets at once | `-currency 100 USD ILS EUR` |
| `-stock [ticker]` | Price plus 1D/1W/1M/1Y/5Y change. Works for crypto (`BTC-USD`) | `-stock AAPL` |
| `-temp [number] [F or C]` | Convert temperature | `-temp 100 C` |
| `-spellcheck [text]` | Find and suggest fixes for misspelled words | `-spellcheck helo wrld` |
| `-dictionary [word]` | Define a word | `-dictionary serendipity` |
| `-translate [lang code] [text]` | Translate text (auto-detects source) | `-translate es hello there` |

### `+` to ask Copilot

GroupMe has a built-in assistant called Copilot that only replies when it's @mentioned, and mentions can only be sent from the app, never over SMS. A message starting with `+` makes the bot @mention Copilot with the rest of the text, so SMS users can use it too:

```
+ tell me a joke
```

GroupMe recently stopped delivering Copilot's replies to SMS members as text — they now see only a "Copilot sent a message. View it here: <link>" placeholder — and it doesn't deliver Copilot's messages to bot callbacks either, so the bot can't just forward them. Instead, after mentioning Copilot the bot briefly polls the group for the reply (it lands a few seconds later) and reposts it as the bot, so SMS members get the actual text. In-app members see it twice (Copilot's own message plus the echo); only SMS members need the echo. The token used for the mention is covered under [How the `+` Copilot feature works](#how-the--copilot-feature-works).

### Admin commands

These wrap actions that are awkward or impossible over SMS. They only work for the configured admin, and require `GROUPME_TOKEN` and a matching `ADMIN_UID`. For `-add`, `-remove`, and `-members` the group is the **last** argument and defaults to the current group; `.` also means the current group. Because names can contain spaces, a multi-word name/nickname must be followed by an explicit trailing group (`.` for the current one).

| Command | What it does |
| --- | --- |
| `-@ <group id or .> <name> [message]` | @mention a member by nickname (or `all`) in any of your groups |
| `-add <nickname> <phone> [group id or .]` | Add a member by phone number |
| `-remove <name or id> [group id or .]` | Remove a member |
| `-groups` | List your groups and their IDs |
| `-members [name / phone / id]` | Detailed member list with user and message IDs (defaults to the current group). For a lightweight roster anyone can pull, see `-list`. |
| `--help` | Show the admin command list |

Admin command output and any errors are sent back to the group the command came from.

## How it works

GroupMe delivers every message in a group to a callback URL you register for a bot. This app is a small Flask server that receives those webhooks, decides whether a message is a command, and responds. Utility replies are posted by the bot using the `bot_id` mapped to each group. Mentions and Copilot are posted as a real user using a personal access token, since bots can't create mentions.

### Two endpoints

| Endpoint | Behavior |
| --- | --- |
| `POST /` | Full functionality, including the `+` Copilot bridge. |
| `POST /general/` | Same, but the `+` Copilot bridge is disabled. Point a group's callback URL here if you don't want `+` messages forwarded to Copilot there. |

### How the `+` Copilot feature works

By default, every `+` message is sent using your `GROUPME_TOKEN` (your own account). If you set a `FALLBACK_TOKEN` (a second account, such as a Google Voice number or spare phone that's a member of the relevant groups), then `+` messages from anyone other than the admin are sent from that spare account instead of your own. This is useful when you don't want to personally be a member of every group the bot serves. If neither token is set, `+` is inactive and the bot still answers everything else.

## Configuration

There are two files. `config.json` is required: the bot posts every reply through a group's bot ID, so a group that isn't listed there gets no responses at all. `.env` is optional and only needed for admin features and the `+` Copilot bridge.

### config.json

This maps each group's ID to the bot ID that posts replies in it, and is what makes the bot respond in a group. Copy the example and fill in your own:

```bash
cp config.example.json config.json
```

```json
{
    "012345678": "0123456789abcdef0123456789",
    "087654321": "fedcba9876543210fedcba9876"
}
```

To get these, create a bot at <https://dev.groupme.com/bots>:

1. Click Create Bot, choose the group it should live in, and give it a name.
2. Set its Callback URL to your deployed app, e.g. `https://yourname.pythonanywhere.com/`.
3. Copy the Bot ID and Group ID shown on the page into `config.json`.

Repeat for each group. Bots that should skip the Copilot bridge get a callback URL ending in `/general/` instead.

### .env

Copy the example and fill in what you need:

```bash
cp .env.example .env
```

| Variable | Needed for | Notes |
| --- | --- | --- |
| `GROUPME_TOKEN` | Admin commands and `+` Copilot | Your personal access token from <https://dev.groupme.com/applications>. |
| `ADMIN_UID` | Admin commands | The user ID allowed to run admin commands. |
| `FALLBACK_TOKEN` | Optional | A second account's token for non-admin `+` messages. |
| `AUTH_CODE` | Optional | If set, callback URLs must include `?auth=THIS_VALUE`. Leave empty to accept all webhooks. |

#### Finding your user ID

With your token, list your groups; each member entry includes a `user_id`:

```bash
curl "https://api.groupme.com/v3/groups?token=YOUR_TOKEN"
```

Find your nickname in the `members` array and copy its `user_id` into `ADMIN_UID`. Once the bot is running, its `-members` command prints the same information.

## Setup

Requires Python 3.9+.

```bash
git clone https://github.com/flipphoneguy/groupme.git
cd groupme

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                  # then edit
cp config.example.json config.json    # then edit
```

Run it locally:

```bash
python main.py                  # serves on http://0.0.0.0:5000
```

GroupMe only delivers webhooks to a public HTTPS URL, so local runs are mainly for testing. To test request handling, tunnel it with something like [ngrok](https://ngrok.com/) (`ngrok http 5000`) and use the HTTPS URL as your bot's callback.

## Deployment

GroupMe requires the callback URL to be reachable over HTTPS.

### PythonAnywhere

[PythonAnywhere](https://www.pythonanywhere.com/) is the easiest option, and the free tier works since all of this bot's data sources are on its allowed-sites list. The catch is that free accounts have to be renewed every few months; you can automate that with [pythonanywhere-forever](https://github.com/flipphoneguy/pythonanywhere-forever).

1. Create a Web app, choose Flask and your Python version.
2. Upload the project or `git clone` it from a Bash console, then `pip install -r requirements.txt` into the web app's virtualenv.
3. Edit the WSGI configuration file so it imports this app:

   ```python
   import sys
   path = "/home/yourname/groupme"
   if path not in sys.path:
       sys.path.insert(0, path)

   from main import app as application
   ```

4. Create `.env` and `config.json` in the project directory.
5. Reload the web app. Your callback URL is `https://yourname.pythonanywhere.com/` (or `.../general/` for groups that should skip the Copilot bridge).

### VPS with gunicorn

```bash
pip install gunicorn
gunicorn -w 2 -b 127.0.0.1:5000 main:app
```

Put it behind a reverse proxy that terminates HTTPS, such as [Caddy](https://caddyserver.com/) or nginx with Let's Encrypt, and point the bot's callback URL at `https://yourdomain/`. Run gunicorn under systemd or a process manager so it stays up.

## License

GNU GPLv3, see [LICENSE](LICENSE). Built by [@flipphoneguy](https://github.com/flipphoneguy).
