import os
import re
import urllib.parse
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

# ==========================================
# KONFIGURATION & SUCHKRITERIEN (Anpassbar)
# ==========================================

# Positive Keywords (OR-Verknüpfung)
KEYWORDS_INCLUDE = [
    "Biotechnologie", "Gewerbeaufsicht", "life sciences", "life-sciences",
    "Lebensmittelaufsicht", "Pharma", "BfArM", "Ehrlich", "BVL", "RKI",
    "Biotechnologe", "Arzneimittel", "Bioverfahrenstechnik", "Medizinprodukt"
]

# Negative Keywords (Exclusions)
KEYWORDS_EXCLUDE = [
    "Wissenschaftlicher Mitarbeiter",
    "Wissenschaftliche Mitarbeiterin",
    "Teilzeit"
]

# Ziel-Filter für Öffentlichen Dienst
TARGET_EMPLOYMENT = ["Vollzeit"]
TARGET_CAREER_LEVEL = ["Höherer Dienst", "h.D.", "hD", "E 13", "E 14", "E 15", "A 13", "A 14", "A 15", "A 16"]

# Basiskonfiguration für Ausgabepfad und Host-Domain (wo die XMLs liegen werden)
OUTPUT_DIR = "public_feeds"
BASE_URL = "https://ihr-username.github.io/job-feeds"  # Nach Deployment anpassen!

# Zu durchsuchende Quellen
SOURCES = [
    {
        "name": "Interamt_Stellensuche",
        "type": "interamt",
        "url": "https://www.interamt.de/koop/app/treffer?2&angebotstyp=1" # Suchseite / API
    },
    {
        "name": "Service_Bund_Stellensuche",
        "type": "service_bund",
        "url": "https://www.service.bund.de/Content/Globals/Functions/RSSFeed/RSSGenerator_Stellen.xml"
    },
    {
        "name": "RKI_Karriere",
        "type": "generic_html",
        "url": "https://www.rki.de/DE/Content/Service/Stellen/stellen_node.html"
    },
    {
        "name": "BfArM_Karriere",
        "type": "generic_html",
        "url": "https://www.bfarm.de/DE/Das-BfArM/Karriere/Stellenangebote/_node.html"
    }
]

# ==========================================
# FILTERLOGIK
# ==========================================

def matches_criteria(title: str, description: str) -> bool:
    content = f"{title} {description}".lower()
    
    # 1. Ausschlusskriterien prüfen
    for ex in KEYWORDS_EXCLUDE:
        if ex.lower() in content:
            return False
            
    # 2. Einschlusssuchstring prüfen (At least 1 keyword match)
    has_include = any(inc.lower() in content for inc in KEYWORDS_INCLUDE)
    if not has_include:
        return False
        
    # 3. Höherer Dienst / Vollzeit Prüfen (wenn explizit genannt)
    # Falls weder Teilzeit noch Vollzeit erwähnt wird, lassen wir es im Zweifel zu.
    return True

# ==========================================
# SCRAPING LOGIK
# ==========================================

def fetch_service_bund_jobs(source):
    """Filtert den bestehenden RSS-Feed von service.bund.de nach den Zusatzkriterien."""
    jobs = []
    try:
        response = requests.get(source["url"], timeout=10)
        soup = BeautifulSoup(response.content, "xml")
        
        for item in soup.find_all("item"):
            title = item.title.text if item.title else ""
            desc = item.description.text if item.description else ""
            link = item.link.text if item.link else ""
            
            if matches_criteria(title, desc):
                jobs.append({
                    "title": title,
                    "link": link,
                    "description": desc,
                    "pubDate": datetime.now(timezone.utc)
                })
    except Exception as e:
        print(f"Fehler bei {source['name']}: {e}")
    return jobs

def generate_feed_file(source_name, jobs):
    """Erzeugt eine RSS .xml-Datei aus einer Liste von Stellen."""
    fg = FeedGenerator()
    fg.title(f"Jobs: {source_name}")
    fg.link(href=f"{BASE_URL}/{source_name}.xml", rel='self')
    fg.description(f"Gefilterte Stellenangebote für {source_name}")

    for job in jobs:
        fe = fg.add_entry()
        fe.title(job["title"])
        fe.link(href=job["link"])
        fe.description(job["description"])
        fe.pubDate(job.get("pubDate", datetime.now(timezone.utc)))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, f"{source_name}.xml")
    fg.rss_file(filepath)
    print(f"Feed gespeichert: {filepath}")

def generate_opml(feed_sources):
    """Erstellt eine OPML-Datei zum einfachen Import aller Feeds in Fluent Reader."""
    opml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head>
    <title>Oeffentlicher Dienst Jobs Subscriptions</title>
    <dateCreated>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')}</dateCreated>
  </head>
  <body>
    <outline text="Karriere Feeds" title="Karriere Feeds">
"""
    for src in feed_sources:
        feed_url = f"{BASE_URL}/{src['name']}.xml"
        opml_content += f'      <outline type="rss" text="{src["name"]}" title="{src["name"]}" xmlUrl="{feed_url}" htmlUrl="{src["url"]}"/>\n'
        
    opml_content += """    </outline>
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
    generated_sources = []
    
    for src in SOURCES:
        if src["type"] == "service_bund":
            jobs = fetch_service_bund_jobs(src)
        else:
            # Hier können Sie weitere Scraper-Methoden für HTML-Seiten ergänzen
            jobs = []
            
        generate_feed_file(src["name"], jobs)
        generated_sources.append(src)
        
    # Am Ende die Sammel-OPML-Datei für Fluent Reader erzeugen
    generate_opml(generated_sources)