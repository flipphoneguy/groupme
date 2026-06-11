// utilities.gs — GroupMe utility bot for Google Apps Script
// Paste this into a second script file named "utilities" in script.google.com

// ---------------------------------------------------------------------------
// Spell checker  (LanguageTool — free, no key)
// ---------------------------------------------------------------------------
function spellcheck(words) {
  var res = UrlFetchApp.fetch("https://api.languagetool.org/v2/check", {
    method: "post",
    payload: { text: words, language: "en-US" },
    muteHttpExceptions: true
  });
  var data = JSON.parse(res.getContentText());
  if (!data.matches || !data.matches.length) return "No spelling mistakes found!";

  var IGNORE = ["lol"];
  var out = "";
  data.matches.forEach(function(m) {
    var word = m.context.text.substring(m.context.offset, m.context.offset + m.context.length);
    if (IGNORE.indexOf(word.toLowerCase()) !== -1) return;
    var correction = m.replacements.length ? m.replacements[0].value : "(none)";
    var candidates = m.replacements.slice(0, 5).map(function(r) { return r.value; }).join(", ") || "(none)";
    out += "Misspelled: " + word + "  Correction: " + correction + "\ncandidates: " + candidates + "\n";
  });
  return out || "No spelling mistakes found!";
}

// ---------------------------------------------------------------------------
// Stock  (Yahoo Finance — no key needed)
// ---------------------------------------------------------------------------
function _yahooCloses(symbol, range) {
  var url = "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol + "?interval=1d&range=" + range;
  var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  try {
    var data = JSON.parse(res.getContentText());
    var closes = data.chart.result[0].indicators.quote[0].close;
    return closes.filter(function(c) { return c != null; });
  } catch (e) {
    return [];
  }
}

function stock(company) {
  if (!company) company = "spym";
  var symbol = company.trim().toUpperCase();
  var closes = _yahooCloses(symbol, "5y");
  if (!closes.length) return "No data for '" + symbol + "'.";

  var price = closes[closes.length - 1];
  function pct(n) {
    return closes.length >= n ? ((price / closes[closes.length - n] - 1) * 100).toFixed(2) : null;
  }
  function fmt(p) {
    return p !== null ? (p > 0 ? "+" : "") + p + "%" : "N/A";
  }

  return symbol + " -- $" + price.toFixed(2) + "\n" +
    "1D: " + fmt(pct(2)) + "  1W: " + fmt(pct(6)) + "  1M: " + fmt(pct(22)) +
    "  1Y: " + fmt(pct(252)) + "  5Y: " + fmt(pct(1260));
}

// ---------------------------------------------------------------------------
// Currency  (Yahoo Finance forex tickers — no key needed)
// ---------------------------------------------------------------------------
function currency() {
  var args = Array.prototype.slice.call(arguments);
  var amount = 1.0;
  if (args.length && !isNaN(parseFloat(args[0]))) {
    amount = parseFloat(args.shift());
  }
  var fromC = (args.shift() || "USD").toUpperCase();
  var toCurrencies = args.length ? args.slice(0, 10).map(function(s) { return s.toUpperCase(); }) : ["ILS"];

  var out = amount + " " + fromC + " =\n";
  toCurrencies.forEach(function(to) {
    var closes = _yahooCloses(fromC + to + "=X", "5d");
    if (!closes.length) { out += "  invalid currencies " + fromC + " " + to + "\n"; return; }
    out += "  " + (amount * closes[closes.length - 1]).toFixed(4) + " " + to + "\n";
  });
  return out;
}

// ---------------------------------------------------------------------------
// Dictionary  (dictionaryapi.dev — free, no key)
// ---------------------------------------------------------------------------
function dictionary(word) {
  if (!word) return "no such word";
  try {
    var res  = UrlFetchApp.fetch("https://api.dictionaryapi.dev/api/v2/entries/en/" + encodeURIComponent(word.trim()), { muteHttpExceptions: true });
    var data = JSON.parse(res.getContentText());
    return data[0].meanings[0].definitions[0].definition;
  } catch (e) {
    return "no such word";
  }
}

// ---------------------------------------------------------------------------
// Translate  (MyMemory — free, no key needed)
// ---------------------------------------------------------------------------
function translate(target, words) {
  try {
    var res  = UrlFetchApp.fetch(
      "https://api.mymemory.translated.net/get?q=" + encodeURIComponent(words) + "&langpair=en|" + encodeURIComponent(target),
      { muteHttpExceptions: true }
    );
    var data = JSON.parse(res.getContentText());
    if (data.responseStatus !== 200) throw new Error();
    return data.responseData.translatedText;
  } catch (e) {
    return "Invalid language code or translation failed: " + target + ".\n" +
      "usage: '-translate [lang code] word or sentence'\n" +
      "e.g. '-translate es hello'";
  }
}

// ---------------------------------------------------------------------------
// Temperature converter
// ---------------------------------------------------------------------------
function temp(number, type) {
  var a = parseFloat(number);
  if (isNaN(a)) return "invalid. numbers only here";
  var t = (type || "").toLowerCase();
  if (t === "f") return a + " °F is " + (((a - 32) * 5) / 9).toFixed(2) + " °C";
  if (t === "c") return a + " °C is " + ((a * 9) / 5 + 32).toFixed(2) + " °F";
  return "invalid input";
}

// ---------------------------------------------------------------------------
// Geocoding helper  (Open-Meteo — free, no key)
// ---------------------------------------------------------------------------
function _getCoords(cityOrZip) {
  var res  = UrlFetchApp.fetch(
    "https://geocoding-api.open-meteo.com/v1/search?name=" + encodeURIComponent(cityOrZip) + "&count=1",
    { muteHttpExceptions: true }
  );
  var data = JSON.parse(res.getContentText());
  var loc  = data.results && data.results[0];
  if (!loc) return null;
  return { name: loc.name, lat: loc.latitude, lon: loc.longitude, tzid: loc.timezone };
}

// ---------------------------------------------------------------------------
// Zmanim  (Hebcal — free, no key)
// ---------------------------------------------------------------------------
function _fetchZmanim(lat, lon, tzid, day) {
  var dateStr = Utilities.formatDate(day, "UTC", "yyyy-MM-dd");
  var res  = UrlFetchApp.fetch(
    "https://www.hebcal.com/zmanim?cfg=json&latitude=" + lat + "&longitude=" + lon +
    "&tzid=" + encodeURIComponent(tzid) + "&date=" + dateStr,
    { muteHttpExceptions: true }
  );
  return JSON.parse(res.getContentText()).times;
}

function _fmtTime(iso) {
  if (!iso) return "N/A";
  var d = new Date(iso);
  var h = d.getHours() % 12 || 12;
  var m = ("0" + d.getMinutes()).slice(-2);
  var ampm = d.getHours() < 12 ? "AM" : "PM";
  return ("0" + h).slice(-2) + ":" + m + " " + ampm;
}

function zmanim(cityOrZip) {
  if (!cityOrZip) cityOrZip = "Jerusalem";
  var geo = _getCoords(cityOrZip);
  if (!geo) return "❌ Could not find location.";

  var today    = new Date();
  var tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  var days   = [[today, "Today"], [tomorrow, "Tomorrow"]];
  var dow    = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
  var out    = "";

  days.forEach(function(pair) {
    var day   = pair[0];
    var label = pair[1];
    var t     = _fetchZmanim(geo.lat, geo.lon, geo.tzid, day);
    out +=
      "\n" + label + " – Zmanim for " + geo.name + " (" + dow[day.getDay()] + ")\n" +
      "Alos Hashachar : " + _fmtTime(t.alotHaShachar) + "\n" +
      "Misheyakir     : " + _fmtTime(t.misheyakir) + "\n" +
      "Netz Hachama   : " + _fmtTime(t.sunrise) + "\n" +
      'SZ"K MGA       : ' + _fmtTime(t.sofZmanShmaMGA) + "\n" +
      'SZ"K GRA       : ' + _fmtTime(t.sofZmanShma) + "\n" +
      "SZ Tefila GRA  : " + _fmtTime(t.sofZmanTfilla) + "\n" +
      "Chatzos        : " + _fmtTime(t.chatzot) + "\n" +
      "Shkiah         : " + _fmtTime(t.sunset) + "\n" +
      "Tzeit 72 min   : " + _fmtTime(t.tzeit72min) + "\n";
  });
  return out;
}

// ---------------------------------------------------------------------------
// Weather  (Open-Meteo — free, no key)
// ---------------------------------------------------------------------------
function weather(cityzip) {
  if (!cityzip) cityzip = "Jerusalem";
  var hourly   = false;
  var location = cityzip.trim();

  if (location.toLowerCase().indexOf("hour") === 0) {
    hourly   = true;
    location = location.split(/\s+/).slice(1).join(" ") || "Jerusalem";
  }

  var geo = _getCoords(location);
  if (!geo) return "couldn't find location.";

  var base =
    "https://api.open-meteo.com/v1/forecast?latitude=" + geo.lat + "&longitude=" + geo.lon +
    "&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto";

  if (hourly) {
    var res = UrlFetchApp.fetch(
      base + "&hourly=temperature_2m,apparent_temperature,relative_humidity_2m,rain,snowfall&forecast_days=1",
      { muteHttpExceptions: true }
    );
    var d    = JSON.parse(res.getContentText()).hourly;
    var rows = ["hourly forecast for " + geo.name];
    for (var i = 0; i < d.time.length; i += 2) {
      var dt   = new Date(d.time[i]);
      var h    = dt.getHours() % 12 || 12;
      var ampm = dt.getHours() < 12 ? "AM" : "PM";
      var rain = d.rain[i] > 0 ? ", rain " + d.rain[i] + " in" : "";
      var snow = d.snowfall[i] > 0 ? ", snow " + d.snowfall[i] + " in" : "";
      rows.push(
        ("0" + h).slice(-2) + " " + ampm + ": " + d.temperature_2m[i] + "°, feels " +
        d.apparent_temperature[i] + "°, humidity " + d.relative_humidity_2m[i] + "%" + rain + snow
      );
    }
    return rows.join("\n");
  }

  var res2 = UrlFetchApp.fetch(
    base + "&daily=temperature_2m_max,temperature_2m_min,relative_humidity_2m_mean," +
    "rain_sum,snowfall_sum,wind_speed_10m_max&forecast_days=7",
    { muteHttpExceptions: true }
  );
  var d2  = JSON.parse(res2.getContentText()).daily;
  var dow = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
  var out = "7 day forecast for " + geo.name;
  for (var i = 0; i < d2.time.length; i++) {
    var dayName = dow[new Date(d2.time[i]).getDay()];
    var rain    = d2.rain_sum[i] > 0 ? "rain = " + d2.rain_sum[i] + " in., " : "";
    var snow    = d2.snowfall_sum[i] > 0 ? "snow = " + d2.snowfall_sum[i] + " in., " : "";
    out += "\n\n" + dayName + ": max temp = " + d2.temperature_2m_max[i] +
      ", min temp = " + d2.temperature_2m_min[i] +
      ", humidity = " + d2.relative_humidity_2m_mean[i] +
      ", " + rain + snow + "wind = " + d2.wind_speed_10m_max[i];
  }
  return out;
}
