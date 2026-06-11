#!/usr/bin/env python3

import requests
from datetime import datetime, date, timedelta
import yfinance as yf
from deep_translator import GoogleTranslator
from spellchecker import SpellChecker
spell = SpellChecker()


def spellcheck(words):
    misspelled = spell.unknown(words.split())
    if not misspelled:
        return("No spelling mistakes found!")
    else:
        send = ""
        for word in misspelled:
            if word not in ("lol",):
                correction = spell.correction(word)
                candidates = spell.candidates(word)
                send += f"Misspelled: {word}"
                send += f"  Correction: {correction}"
                send += f"\ncandidates: {candidates}"
    return send or "No spelling mistakes found!"

def stock(company="spym"):
    company = company.lower().strip()
    symbol = company.upper()
    hist = yf.Ticker(symbol).history(period="5y")
    hist = hist[hist["Close"].notna()]
    if hist.empty:
        return f"No data for '{symbol}'."
    price = hist["Close"].iloc[-1]

    def pct(n): return (price / hist["Close"].iloc[-n] - 1) * 100 if len(hist) >= n else None
    fmt = lambda p: f"{p:+.2f}%" if p is not None else "N/A"

    return (f"{symbol} -- ${price:.2f}\n"
        f"1D: {fmt(pct(2))}  1W: {fmt(pct(6))}  1M: {fmt(pct(22))}  "
        f"1Y: {fmt(pct(252))}  5Y: {fmt(pct(1260))}")

def currency(*args):
    try:
        amount = float(args[0])
        args = args[1:]
    except (ValueError, IndexError):
        amount = 1.0
    try:
        fromC = args[0].upper()
        args = args[1:]
    except IndexError:
        fromC = "USD"
    try:
        args = [i.upper() for i in args[:10]] or ["ILS"]
    except ValueError:
        return "Invalid input. Try '-help currency' for more info."

    rv = f"{amount} {fromC} =\n"
    for to in args:
        hist = yf.Ticker(f"{fromC}{to}=X").history(period="1d")
        hist = hist[hist["Close"].notna()]
        if hist.empty:
            return f"invalid currencies {fromC} {to}"
        rate = hist["Close"].iloc[-1]
        rv += f"  {round(amount * rate, 4)} {to}\n"
    return rv


def dictionary(word = ""):
    try:
        data = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}").json()
        return data[0]['meanings'][0]['definitions'][0]['definition']
    except Exception: return "no such word"


def translate(target, words):
    try:
        translator = GoogleTranslator(source="auto", target=target)
    except:
        return f"Invalid language code: {target}.\nusage: '-translate [lang code] word or sentance'\ne.g. '-translate es hello'"
    try:
        return translator.translate(words)
    except Exception:
        return "translation failed:"


def temp(number, type):
    type = type.lower()
    try: a = float(number)
    except ValueError:
        return "invalid. numbers only here"
    c = (a - 32) * 5/9
    f = (a * 9/5) + 32
    if type == 'f': return f"{a} °f is {c} °c"
    elif type == 'c': return f"{a} °c is {f} °f"
    else: return "invalid input"



def _get_coords(city_or_zip):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_or_zip, "count": 1}
    results = requests.get(url, params=params).json().get('results')
    if not results:
        return None
    loc = results[0]
    return {
        "name": loc["name"],
        "lat": loc["latitude"],
        "lon": loc["longitude"],
        "tzid": loc["timezone"]
    }

def _fetch_zmanim(lat, lon, tzid, day):
    url = "https://www.hebcal.com/zmanim"
    params = {
        "cfg": "json",
        "latitude": lat,
        "longitude": lon,
        "tzid": tzid,
        "date": day.isoformat()
    }
    return requests.get(url, params=params).json()["times"]

def _show_zmanim(location_name, lat, lon, tzid):
    send = ""
    today = date.today()
    tomorrow = today + timedelta(days=1)
    format = '%I:%M %p'

    for day, label in [(today, "Today"), (tomorrow, "Tomorrow")]:
        t = _fetch_zmanim(lat, lon, tzid, day)
        send += f"\n{label} – Zmanim for {location_name} ({day.strftime('%a')})\n"
        send += f"Alos Hashachar : {datetime.fromisoformat(t.get('alotHaShachar', 'N/A')).strftime(format)}\n"
        send += f"Misheyakir     : {datetime.fromisoformat(t.get('misheyakir', 'N/A')).strftime(format)}\n"
        send += f"Netz Hachama   : {datetime.fromisoformat(t.get('sunrise', 'N/A')).strftime(format)}\n"
        send += f"SZ\"K MGA       : {datetime.fromisoformat(t.get('sofZmanShmaMGA', 'N/A')).strftime(format)}\n"
        send += f"SZ\"K GRA       : {datetime.fromisoformat(t.get('sofZmanShma')).strftime(format)}\n"
        send += f"SZ Tefila GRA  : {datetime.fromisoformat(t.get('sofZmanTfilla', 'N/A')).strftime(format)}\n"
        send += f"Chatzos        : {datetime.fromisoformat(t.get('chatzot', 'N/A')).strftime(format)}\n"
        send += f"Shkiah         : {datetime.fromisoformat(t.get('sunset', 'N/A')).strftime(format)}\n"
        send += f"Tzeit 72 min   : {datetime.fromisoformat(t.get('tzeit72min', 'N/A')).strftime(format)}\n"
    return send

def zmanim(city_or_zip="Jerusalem"):
    geo = _get_coords(city_or_zip)
    if not geo: return "❌ Could not find location."
    return _show_zmanim(geo['name'], geo['lat'], geo['lon'], geo['tzid'])

def weather(cityzip="Jerusalem"):
    if cityzip.lower().startswith('hour'):
        hourly = True
        cityzip = ' '.join(cityzip.split()[1:]) or "Jerusalem"
    else:
        hourly = False
    geo = _get_coords(cityzip)
    if not geo: return "couldn't find location."
    base = f"https://api.open-meteo.com/v1/forecast?latitude={geo['lat']}&longitude={geo['lon']}&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto"

    if hourly:
        data = requests.get(f"{base}&hourly=temperature_2m,apparent_temperature,relative_humidity_2m,rain,snowfall&forecast_days=1").json()['hourly']
        send = [f"hourly forecast for {geo['name']}",]
        for time, temp, feel, humidity, rain, snow in zip(data['time'], data['temperature_2m'], data['apparent_temperature'], data['relative_humidity_2m'], data['rain'], data['snowfall']):
            h = datetime.strptime(time, '%Y-%m-%dT%H:%M').strftime('%I %p')
            send.append(f"{h}: {temp}°, feels {feel}°, humidity {humidity}%{f', rain {rain} in' if rain > 0 else ''}{f', snow {snow} in' if snow > 0 else ''}")
        return '\n'.join(send[::2])

    response = requests.get(f"{base}&daily=temperature_2m_max,temperature_2m_min,relative_humidity_2m_mean,precipitation_sum,rain_sum,snowfall_sum,wind_speed_10m_max,wind_gusts_10m_max&forecast_days=7").json()['daily']
    send = f"7 day forecast for {geo['name']}"
    for day, max, min, humidity, rain, snow, wind in zip(response['time'], response['temperature_2m_max'], response['temperature_2m_min'], response['relative_humidity_2m_mean'], response['rain_sum'], response['snowfall_sum'], response['wind_speed_10m_max']):
        send += f"\n\n{datetime.strptime(day,'%Y-%m-%d').strftime('%a')}: max temp = {max}, min temp = {min}, humidity = {humidity}, {f'rain = {rain} in., ' if rain > 0 else ''}{f'snow = {snow} in., ' if snow > 0 else ''}wind = {wind}"
    return send



if __name__ == "__main__":
    import sys, inspect

    FUNCS = {n: f for n, f in globals().items() if inspect.isfunction(f) and not n.startswith("_")}

    def print_help():
        print("Functions:")
        for name, fn in FUNCS.items():
            print(f"  {name}{inspect.signature(fn)}")

    if len(sys.argv) > 1:
        fname, *args = sys.argv[1:]
        if fname not in FUNCS:
            print(f"Unknown function '{fname}'")
            print_help()
            sys.exit(1)
        print(FUNCS[fname](*args))
    else:
        print_help()
        while True:
            try:
                line = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line: continue
            if line.lower() in ("q", "quit"): break
            fname, *args = line.split()
            if fname in FUNCS:
                print(FUNCS[fname](*args))
            else:
                print(f"Unknown function '{fname}'")
                print_help()

