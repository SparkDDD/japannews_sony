import os, json, re, requests
from datetime import datetime
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googletrans import Translator

# ── CONFIG ─────────────────────────────────────────────────────────────
SHEET_ID   = "1YXdD3PLHSNs_rbdA052QZxLxr2R3tvE_qL-vxtWXzUI"
TAB_NAME   = "Sony"
URL        = "https://www.nikkei.com/nkd/company/news/?scode=6758&ba=1"
BASE_URL   = "https://www.nikkei.com"
HEADERS    = {"User-Agent": "Mozilla/5.0"}

# ── Parse date ─────────────────────────────────────────────────────────
def parse_pub_date(raw: str, today: datetime) -> str:
    raw = raw.strip()
    m = re.search(r"(\d{1,2})/(\d{1,2})", raw)
    if m:
        month, day = map(int, m.groups())
        return datetime(today.year, month, day).strftime("%Y-%m-%d")
    if re.match(r"^\d{1,2}:\d{2}$", raw):
        return today.strftime("%Y-%m-%d")
    return today.strftime("%Y-%m-%d")

# ── Translator ─────────────────────────────────────────────────────────
translator = Translator()
def ja_to_en(text: str) -> str:
    try:
        return translator.translate(text, dest="en").text
    except Exception as e:
        print(f"⚠️ Translation failed ({e}); using original.")
        return text

# ── Scrape ─────────────────────────────────────────────────────────────
resp  = requests.get(URL, headers=HEADERS, timeout=20)
resp.raise_for_status()
soup  = BeautifulSoup(resp.text, "html.parser")
items = soup.select("li.m-listFormat_item")
today = datetime.today()

scraped = []
print(f"🔍 Found {len(items)} article blocks.")
for it in items:
    a    = it.select_one(".m-listItem_text_text a")
    date = it.select_one(".m-listItem_time")
    if not (a and date):
        continue
    title_ja = a.get_text(strip=True)
    url      = BASE_URL + a["href"]
    pub_date = parse_pub_date(date.get_text(strip=True), today)
    title_en = ja_to_en(title_ja)
    scraped.append((title_ja, title_en, url, pub_date))
    print(f"📄 {title_ja} | {title_en} | {url} | {pub_date}")

# ── Sheets auth ────────────────────────────────────────────────────────
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(os.environ["GOOGLE_CREDS_JSON"]),
    scope
)
ws = gspread.authorize(creds).open_by_key(SHEET_ID).worksheet(TAB_NAME)

# ── Deduplicate and append ─────────────────────────────────────────────
rows      = ws.get_all_values()
url_index = rows[0].index("Article URL")
existing  = {r[url_index] for r in rows[1:] if len(r) > url_index}

new_rows = [
    [title_ja, title_en, url, pub_date]
    for title_ja, title_en, url, pub_date in scraped
    if url not in existing
]

if new_rows:
    ws.append_rows(new_rows)
    print(f"✅ Uploaded {len(new_rows)} new articles.")
else:
    print("ℹ️ No new articles to upload.")
