
# GroupMe Utility Bot — Google Apps Script Port
 
> ⚠️ **This is an unofficial port of [flipphoneguy/groupme](https://github.com/flipphoneguy/groupme).** All credit for the original concept, commands, and logic goes to [@flipphoneguy](https://github.com/flipphoneguy). This repo simply re-implements the same bot to run on **Google Apps Script** instead of Python/Flask, so no server or hosting is needed.
 
---
 
## What's different from the original
 
| | [Original](https://github.com/flipphoneguy/groupme) | This port |
|---|---|---|
| Language | Python | JavaScript (GAS) |
| Server | Flask (PythonAnywhere / VPS) | Google Apps Script (no server needed) |
| Dependencies | pip packages | None — all built-in GAS services |
| Spellcheck | `pyspellchecker` | LanguageTool API |
| Translation | `deep-translator` (Google) | MyMemory API |
| Stock/Currency | `yfinance` | Yahoo Finance URL directly |
| Config | `.env` + `config.json` | GAS Script Properties |
 
Everything else — commands, behavior, API endpoints, output format — is identical to the original.
 
---
 
## Commands
 
Commands are not case-sensitive.
 
### Utility commands (anyone)
 
| Command | What it does | Example |
|---|---|---|
| `-help` | List all commands | `-help` |
| `-weather [city or zip]` | 7-day forecast (defaults to Jerusalem) | `-weather Chicago` |
| `-weather hour [city or zip]` | Hourly forecast for today | `-weather hour 10001` |
| `-zmanim [city or zip]` | Today and tomorrow's halachic times | `-zmanim Lakewood` |
| `-currency [amount] [from] [to ...]` | Convert currency; up to 10 targets at once | `-currency 100 USD ILS EUR` |
| `-stock [ticker]` | Price + 1D/1W/1M/1Y/5Y change. Works for crypto (`BTC-USD`) | `-stock AAPL` |
| `-temp [number] [F or C]` | Convert temperature | `-temp 100 C` |
| `-spellcheck [text]` | Find and suggest fixes for misspelled words | `-spellcheck helo wrld` |
| `-dictionary [word]` | Define a word | `-dictionary serendipity` |
| `-translate [lang code] [text]` | Translate text (auto-detects source) | `-translate es hello` |
 
### `+` to ask Copilot
 
A message starting with `+` makes the bot @mention GroupMe's built-in Copilot assistant with the rest of the text — useful for SMS users who can't send mentions from their phone:
 
```
+ tell me a joke
```
 
### Admin commands
 
Only works for the user whose ID is set in `ADMIN_UID`. Use `.` as the group ID to mean the current group.
 
| Command | What it does |
|---|---|
| `-@ <group id or .> <name> [message]` | @mention a member (or `all`) |
| `-add <group id or .> <nickname> <phone>` | Add a member by phone number |
| `-remove <group id or .> <name or id>` | Remove a member |
| `-groups` | List your groups and their IDs |
| `-members <name / phone / id>` | List a group's members with IDs |
| `--help` | Show admin command list |
 
---
 
## Setup
 
### 1. Create the project
 
Go to [script.google.com](https://script.google.com) → **New project**.
 
### 2. Add the files
 
- Rename the default `Code.gs` to `main.gs` and paste in the contents of `main.gs`
- Click **+** next to Files → Script → name it `utilities` → paste in `utilities.gs`
### 3. Set Script Properties
 
Click the **gear icon** (Project Settings) → **Script Properties** → **Add script property** for each of these:
 
| Property | Required | Value |
|---|---|---|
| `GROUPME_TOKEN` | Yes (for admin + Copilot) | Your token from [dev.groupme.com](https://dev.groupme.com) → profile → Access Token |
| `ADMIN_UID` | Yes (for admin commands) | Your GroupMe user ID (see below) |
| `BOT_MAP` | Yes | JSON mapping group IDs to bot IDs — see below |
| `FALLBACK_TOKEN` | No | A second account's token for non-admin `+` messages |
| `AUTH_CODE` | No | If set, callback URL must include `?auth=THIS_VALUE` |
 
**Finding your `ADMIN_UID`:** paste this function into `main.gs`, run it once, check the Execution Log, then delete it:
 
```javascript
function getMyUID() {
  var token = PropertiesService.getScriptProperties().getProperty("GROUPME_TOKEN");
  var res = UrlFetchApp.fetch("https://api.groupme.com/v3/users/me?token=" + token);
  Logger.log(JSON.parse(res.getContentText()).response.id);
}
```
 
**`BOT_MAP` format** — get your group ID and bot ID from [dev.groupme.com/bots](https://dev.groupme.com/bots):
 
```json
{"115426752": "aef2e6581dd0205bbba8e28c8c"}
```
 
Multiple groups:
```json
{"115426752": "aef2e6581dd0205bbba8e28c8c", "987654321": "another_bot_id_here"}
```
 
### 4. Deploy as a Web App
 
1. Click **Deploy** → **New deployment**
2. Type: **Web app**
3. Execute as: **Me**
4. Who has access: **Anyone**
5. Click **Deploy** → copy the Web App URL
### 5. Register the webhook in GroupMe
 
Go to [dev.groupme.com/bots](https://dev.groupme.com/bots) → create a bot for your group → set its **Callback URL** to your Web App URL:
 
```
https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec
```
 
If you set `AUTH_CODE`:
```
https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec?auth=YOUR_CODE
```
 
> **Note:** Every time you edit the code, go to **Deploy** → **Manage deployments** → edit the existing deployment to push the update live. GAS does not auto-update.
 
---
 
## How it works
 
GroupMe sends every group message to a callback URL as a POST request. GAS exposes a `doPost(e)` function that receives it, checks if it's a command, and sends a reply back to the group using the bot ID mapped to that group. Admin commands and Copilot forwarding use a real user token since bots can't create @mentions.
 
### Two routes
 
The original Python version had two URL endpoints (`/` and `/general/`). In GAS this is handled via a query parameter:
 
| URL | Behavior |
|---|---|
| `.../exec` | Full functionality including `+` Copilot bridge |
| `.../exec?route=general` | Same but `+` Copilot bridge is disabled |
 
---
 
## License
 
GNU GPLv3 — same as the original. See [LICENSE](LICENSE).
 
Original project by [@flipphoneguy](https://github.com/flipphoneguy) — this is purely a platform port, not an independent work.
 
