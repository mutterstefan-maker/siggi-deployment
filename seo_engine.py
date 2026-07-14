# -*- coding: utf-8 -*-
"""
SEO Audit Engine für SIGGI
Crawlt chefblick.de und prüft Meta-Descriptions, H1, Title Tags und Inhalt.
"""
import os
import json
import re
import requests
from urllib.parse import urljoin, urlparse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(BASE_DIR, 'settings.json')

TARGET_DOMAIN = 'chefblick.de'
TARGET_URL    = 'https://www.chefblick.de'
ZIELGRUPPE    = ['Handwerker', 'Restaurant', 'Gastronomie', 'Immobilien', 'Arztpraxis', 'Beauty', 'Fitness', 'Elektriker']

HEADERS = {
    'User-Agent': 'SIGGI-SEO-Bot/1.0 (ChefBlick internal audit)',
    'Accept-Language': 'de-DE,de;q=0.9'
}


def _load_settings():
    with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


# ──────────────────────────────────────────────
# SEITEN ENTDECKEN
# ──────────────────────────────────────────────

def get_pages_from_sitemap():
    """Liest URLs aus sitemap.xml."""
    urls = []
    for sitemap_url in [
        f'{TARGET_URL}/sitemap.xml',
        f'{TARGET_URL}/sitemap_index.xml',
        f'{TARGET_URL}/sitemap/sitemap.xml',
    ]:
        try:
            r = requests.get(sitemap_url, headers=HEADERS, timeout=10)
            if r.ok and 'xml' in r.headers.get('content-type', ''):
                found = re.findall(r'<loc>(https?://[^<]+)</loc>', r.text)
                for u in found:
                    if TARGET_DOMAIN in u and u not in urls:
                        urls.append(u.strip())
                if urls:
                    break
        except Exception:
            continue
    return urls


def get_pages_by_crawl(max_pages=20):
    """Crawlt die Website und sammelt interne Links."""
    visited = set()
    to_visit = [TARGET_URL]
    pages = []

    while to_visit and len(pages) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if not r.ok or 'text/html' not in r.headers.get('content-type', ''):
                continue
            pages.append(url)
            # Links sammeln
            links = re.findall(r'href=["\']([^"\']+)["\']', r.text)
            for link in links:
                full = urljoin(url, link).split('#')[0].split('?')[0]
                if TARGET_DOMAIN in full and full not in visited and full not in to_visit:
                    to_visit.append(full)
        except Exception:
            continue
    return pages


def discover_pages():
    """Sitemap zuerst, dann Crawl als Fallback."""
    pages = get_pages_from_sitemap()
    if not pages:
        pages = get_pages_by_crawl(20)
    # Startseite immer dabei
    if TARGET_URL not in pages and TARGET_URL + '/' not in pages:
        pages.insert(0, TARGET_URL)
    return pages[:30]  # max 30 Seiten


# ──────────────────────────────────────────────
# SEITE ANALYSIEREN
# ──────────────────────────────────────────────

def analyze_page(url):
    """Analysiert eine Seite auf SEO-Qualität."""
    result = {
        'url':         url,
        'ok':          False,
        'title':       '',
        'description': '',
        'h1':          [],
        'h2':          [],
        'word_count':  0,
        'issues':      [],
        'suggestions': [],
    }
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if not r.ok:
            result['issues'].append(f'Seite nicht erreichbar ({r.status_code})')
            return result
        html = r.text
        result['ok'] = True

        # Title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        result['title'] = title_match.group(1).strip() if title_match else ''

        # Meta Description
        desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if not desc_match:
            desc_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', html, re.IGNORECASE)
        result['description'] = desc_match.group(1).strip() if desc_match else ''

        # H1
        result['h1'] = [re.sub(r'<[^>]+>', '', h).strip() for h in re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)]

        # H2
        result['h2'] = [re.sub(r'<[^>]+>', '', h).strip() for h in re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.IGNORECASE | re.DOTALL)][:5]

        # Wörter im Body
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.IGNORECASE | re.DOTALL)
        if body_match:
            body_text = re.sub(r'<[^>]+>', ' ', body_match.group(1))
            body_text = re.sub(r'\s+', ' ', body_text)
            result['word_count'] = len(body_text.split())

        # ── CHECKS ────────────────────────────────────────────────────────

        # 1. Meta Description
        desc = result['description']
        if not desc:
            result['issues'].append('❌ Meta Description fehlt komplett')
            result['suggestions'].append('Meta Description hinzufügen (120–160 Zeichen, mit Call-to-Action wie "Jetzt anfragen" oder "Kostenlos testen")')
        elif len(desc) > 160:
            result['issues'].append(f'⚠️ Meta Description zu lang ({len(desc)} Zeichen, max. 160)')
            result['suggestions'].append(f'Auf max. 160 Zeichen kürzen: "{desc[:120]}..."')
        elif len(desc) < 70:
            result['issues'].append(f'⚠️ Meta Description zu kurz ({len(desc)} Zeichen)')
            result['suggestions'].append('Meta Description auf 120–160 Zeichen ausbauen')

        cta_words = ['jetzt', 'kostenlos', 'anfragen', 'testen', 'starten', 'entdecken', 'kontakt', 'angebot', 'gratis']
        if desc and not any(w in desc.lower() for w in cta_words):
            result['issues'].append('⚠️ Kein Call-to-Action in Meta Description')
            result['suggestions'].append('Call-to-Action ergänzen z.B. "Jetzt kostenlos anfragen" oder "Angebot einholen"')

        # 2. H1
        if not result['h1']:
            result['issues'].append('❌ Kein H1-Tag gefunden')
            result['suggestions'].append('H1 mit Haupt-Keyword hinzufügen (z.B. "Webdesign für Handwerker in Bayern")')
        elif len(result['h1']) > 1:
            result['issues'].append(f'⚠️ Mehrere H1-Tags ({len(result["h1"])})')
            result['suggestions'].append('Nur einen H1-Tag pro Seite verwenden')

        # 3. Title
        if not result['title']:
            result['issues'].append('❌ Title Tag fehlt')
            result['suggestions'].append('Title Tag mit Haupt-Keyword + Markenname hinzufügen')
        elif len(result['title']) > 65:
            result['issues'].append(f'⚠️ Title zu lang ({len(result["title"])} Zeichen, max. 60–65)')
        elif len(result['title']) < 30:
            result['issues'].append(f'⚠️ Title zu kurz ({len(result["title"])} Zeichen)')

        # 4. Title & Description stimmen überein?
        if result['title'] and result['description']:
            title_words = set(result['title'].lower().split())
            desc_words  = set(result['description'].lower().split())
            common = title_words & desc_words - {'und', 'die', 'der', 'das', 'für', 'mit', 'von', 'in', 'an', 'auf', 'ist', 'bei'}
            if not common:
                result['issues'].append('⚠️ Title und Meta Description teilen keine Keywords — evtl. nicht konsistent')

        # 5. Zielgruppe
        zg_found = [z for z in ZIELGRUPPE if z.lower() in html.lower()]
        if not zg_found and url == TARGET_URL:
            result['issues'].append('⚠️ Keine klaren Zielgruppen-Begriffe auf der Startseite')
            result['suggestions'].append(f'Zielgruppen explizit nennen: {", ".join(ZIELGRUPPE[:4])} etc.')

        # 6. Wenig Content
        if result['word_count'] < 200:
            result['issues'].append(f'⚠️ Wenig Text ({result["word_count"]} Wörter) — Google bevorzugt 300+ Wörter')
            result['suggestions'].append('Mehr informativen Content hinzufügen (mind. 300 Wörter)')

    except Exception as e:
        result['issues'].append(f'Analyse-Fehler: {e}')

    return result


# ──────────────────────────────────────────────
# VOLLSTÄNDIGER AUDIT
# ──────────────────────────────────────────────

def run_seo_audit(max_pages=15):
    """Führt einen vollständigen SEO-Audit durch."""
    pages = discover_pages()
    pages = pages[:max_pages]
    results = []
    for url in pages:
        print(f'[SEO] Analysiere: {url}')
        results.append(analyze_page(url))
    return {
        'timestamp': datetime.now().isoformat(),
        'domain': TARGET_DOMAIN,
        'pages_checked': len(results),
        'results': results,
        'summary': _build_summary(results)
    }


def _build_summary(results):
    total_issues = sum(len(r['issues']) for r in results)
    pages_ok     = sum(1 for r in results if not r['issues'])
    missing_desc = sum(1 for r in results if not r['description'])
    missing_h1   = sum(1 for r in results if not r['h1'])
    return {
        'total_pages':   len(results),
        'pages_ok':      pages_ok,
        'total_issues':  total_issues,
        'missing_desc':  missing_desc,
        'missing_h1':    missing_h1,
    }


def get_seo_context():
    """Kurze SEO-Zusammenfassung für SIGGIs System-Prompt (kein Full-Audit, nur Status)."""
    try:
        # Nur Startseite schnell prüfen
        r = analyze_page(TARGET_URL)
        issues = r['issues']
        if not issues:
            return 'SEO-STATUS (Startseite): Alles OK.'
        top = issues[:3]
        return 'SEO-STATUS (Startseite):\n' + '\n'.join(f'  {i}' for i in top)
    except Exception as e:
        return f'SEO-STATUS: Fehler ({e})'
