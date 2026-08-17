import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo  # Python 3.9+ Standardbibliothek
import requests
from feedgen.feed import FeedGenerator

# ==========================================
# KONFIGURATION & SUCHKRITERIEN
# ==========================================

# Deutsche Zeitzone definieren (wechselt automatisch zwischen CET und CEST)
GERMAN_TZ = ZoneInfo("Europe/Berlin")

# Positive Keywords
KEYWORDS_INCLUDE = [
    "Biotechnologie",
    "Gewerbeaufsicht",
    "life sciences",
    "life-sciences",
    "Lebensmittelaufsicht",
    "Pharma",
    "BfArM",
    "Ehrlich",
    "BVL",
    "RKI",
    "Biotechnologe",
    "Arzneimittel",
    "Bioverfahrenstechnik",
    "Medizinprodukt",
]

# Negative Keywords (Exclusions)
KEYWORDS_EXCLUDE = [
    "Wissenschaftlicher Mitarbeiter",
    "Wissenschaftliche Mitarbeiterin",
    "Teilzeit",
]

# Ziel-Filter für Höheren Dienst / Entgeltgruppen (zur optionalen Zusatzprüfung)
TARGET_CAREER_LEVEL = [
    "Höherer Dienst",
    "h.D.",
    "hD",
    "E 13",
    "E 14",
    "E 15",
    "A 13",
    "A 14",
    "A 15",
    "A 16",
]

# Basiskonfiguration
OUTPUT_DIR = "public_feeds"
BASE_URL = "https://H4T4.github.io/-D_Stellen_parser"
FEED_NAME = "Arbeitsagentur_Stellensuche"

# Arbeitsagentur API Details
API_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
HEADERS = {
    "X-API-Key": "jobboerse-jobsuche",
    "User-Agent": "PublicSectorJobFeedBot/1.0",
}

# ==========================================
# FILTERLOGIK
# ==========================================


def matches_criteria(title: str, description: str) -> bool:
    content = f"{title} {description}".lower()

    # 1. Ausschlusskriterien prüfen
    for ex in KEYWORDS_EXCLUDE:
        if ex.lower() in content:
            return False

    return True


# ==========================================
# API ABFRAGE
# ==========================================


def fetch_arbeitsagentur_jobs():
    """Fragt die Arbeitsagentur-API für alle Positiv-Keywords ab."""
    jobs_dict = {}  # Nutzt RefNr als Key gegen Duplikate

    for kw in KEYWORDS_INCLUDE:
        params = {
            "was": kw,
            "arbeitszeit": "vz",  # vz = Vollzeit
            "size": 50,
        }

        try:
            response = requests.get(API_URL, headers=HEADERS, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for job in data.get("stellenangebote", []):
                    refnr = job.get("refnr")
                    title = job.get("titel", "Kein Titel")
                    employer = job.get("arbeitgeber", "Unbekannt")
                    location = job.get("arbeitsort", {}).get("ort", "")
                    desc = f"Arbeitgeber: {employer} | Ort: {location} | Keyword: {kw}"

                    # Negativ-Filter anwenden
                    if matches_criteria(title, desc):
                        jobs_dict[refnr] = {
                            "title": f"{title} - {employer} ({location})",
                            "link": f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}",
                            "description": f"<b>Arbeitgeber:</b> {employer}<br><b>Ort:</b> {location}<br><b>Referenznummer:</b> {refnr}",
                            "pubDate": datetime.now(GERMAN_TZ),
                        }
            else:
                print(f"Fehler bei Keyword '{kw}': Status {response.status_code}")
        except Exception as e:
            print(f"Fehler bei Abfrage für '{kw}': {e}")

    return list(jobs_dict.values())


# ==========================================
# FEED & OPML GENERIERUNG
# ==========================================


def generate_feed_file(source_name, jobs):
    """Erzeugt die RSS .xml-Datei."""
    fg = FeedGenerator()
    fg.title(f"Jobs: {source_name}")
    fg.link(href=f"{BASE_URL}/{source_name}.xml", rel="self")
    fg.description(f"Gefilterte Stellenangebote für {source_name}")

    for job in jobs:
        fe = fg.add_entry()
        fe.title(job["title"])
        fe.link(href=job["link"])
        fe.description(job["description"])
        fe.pubDate(job.get("pubDate", datetime.now(GERMAN_TZ)))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, f"{source_name}.xml")
    fg.rss_file(filepath)
    print(f"Feed gespeichert: {filepath} ({len(jobs)} Stellen)")


def generate_opml(source_name):
    """Erstellt die subscriptions.opml Datei für Fluent Reader."""
    feed_url = f"{BASE_URL}/{source_name}.xml"
    opml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head>
    <title>Oeffentlicher Dienst Jobs Subscriptions</title>
    <dateCreated>{datetime.now(GERMAN_TZ).strftime("%a, %d %b %Y %H:%M:%S %z")}</dateCreated>
  </head>
  <body>
    <outline text="Karriere Feeds" title="Karriere Feeds">
      <outline type="rss" text="{source_name}" title="{source_name}" xmlUrl="{feed_url}" htmlUrl="https://www.arbeitsagentur.de/jobsuche/"/>
    </outline>
  </body>
</opml>"""

    opml_path = os.path.join(OUTPUT_DIR, "subscriptions.opml")
    with open(opml_path, "w", encoding="utf-8") as f:
        f.write(opml_content)
    print(f"OPML-Datei erzeugt: {opml_path}")


# ==========================================
# HAUPTAUSFÜHRUNG
# ==========================================

if __name__ == "__main__":
    jobs = fetch_arbeitsagentur_jobs()
    generate_feed_file(FEED_NAME, jobs)
    generate_opml(FEED_NAME)
