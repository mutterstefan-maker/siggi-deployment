# -*- coding: utf-8 -*-
"""ChefBlick Website Audit Engine v2 - Tiefenanalyse"""
import os, re, json, time, requests
from datetime import datetime
from urllib.parse import urlparse, urljoin

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'}

RUNTIME_API_KEY = ''  # wird von app.py gesetzt

def load_api_key():
    # 1. Runtime Key (von app.py gesetzt)
    if RUNTIME_API_KEY and len(RUNTIME_API_KEY) > 30:
        return RUNTIME_API_KEY
    # 2. settings.json
    try:
        s = json.load(open(os.path.join(BASE_DIR, 'settings.json'), encoding='utf-8'))
        key = s.get('anthropic_api_key', '')
        if key and len(key) > 30 and key.startswith('sk-'):
            return key
    except: pass
    # 3. mail_engine
    try:
        from mail_engine import load_settings
        s = load_settings()
        key = s.get('anthropic_api_key', '')
        if key and len(key) > 30 and key.startswith('sk-'):
            return key
    except: pass
    return ''

def fetch_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        return r.text, r.status_code, r.url, dict(r.headers)
    except Exception as e:
        return None, 0, url, {}

def check_pagespeed(url):
    try:
        results = {}
        for strategy in ['mobile', 'desktop']:
            r = requests.get(PAGESPEED_API, params={
                'url': url, 'strategy': strategy,
                'category': ['performance','accessibility','best-practices','seo']
            }, timeout=40).json()
            cats = r.get('lighthouseResult',{}).get('categories',{})
            audits = r.get('lighthouseResult',{}).get('audits',{})
            perf_score = cats.get('performance',{}).get('score')
        if perf_score is None:
            raise Exception('Keine PageSpeed-Daten erhalten')
        results[strategy] = {
                'performance': round(perf_score * 100),
                'accessibility': round((cats.get('accessibility',{}).get('score') or 0)*100),
                'best_practices': round((cats.get('best-practices',{}).get('score') or 0)*100),
                'seo': round((cats.get('seo',{}).get('score') or 0)*100),
                'fcp': audits.get('first-contentful-paint',{}).get('displayValue','N/A'),
                'lcp': audits.get('largest-contentful-paint',{}).get('displayValue','N/A'),
                'cls': audits.get('cumulative-layout-shift',{}).get('displayValue','N/A'),
                'tbt': audits.get('total-blocking-time',{}).get('displayValue','N/A'),
                'speed_index': audits.get('speed-index',{}).get('displayValue','N/A'),
            }
        return {'success': True, **results}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def check_google_index(domain):
    """Prüft Google-Indexierung via Sitemap + robots.txt"""
    clean = domain.replace('https://','').replace('http://','').rstrip('/')
    base_url = f'https://{clean}'
    result = {'indexed': None, 'count_text': 'N/A', 'sample_pages': [], 'has_sitemap': False, 'has_robots': False}

    # 1. robots.txt prüfen
    try:
        r = requests.get(f'{base_url}/robots.txt', headers=HEADERS, timeout=10)
        if r.status_code == 200:
            result['has_robots'] = True
            result['robots_content'] = r.text[:500]
            if 'sitemap' in r.text.lower():
                sitemap_match = re.search(r'Sitemap:\s*(https?://[^\s]+)', r.text, re.IGNORECASE)
                if sitemap_match:
                    result['sitemap_url'] = sitemap_match.group(1)
    except: pass

    # 2. Sitemap prüfen
    sitemap_urls = [
        result.get('sitemap_url',''),
        f'{base_url}/sitemap.xml',
        f'{base_url}/sitemap_index.xml',
        f'{base_url}/wp-sitemap.xml',
    ]
    for sm_url in sitemap_urls:
        if not sm_url: continue
        try:
            r = requests.get(sm_url, headers=HEADERS, timeout=10)
            if r.status_code == 200 and ('xml' in r.headers.get('content-type','') or '<url>' in r.text or '<sitemap>' in r.text):
                result['has_sitemap'] = True
                urls = re.findall(r'<loc>(.*?)</loc>', r.text)
                result['count_text'] = f'{len(urls)}+'
                result['sample_pages'] = [u.replace(base_url,'') for u in urls[:5]]
                result['indexed'] = True
                break
        except: continue

    # 3. Wenn keine Sitemap: direkten Google-Check versuchen
    if result['indexed'] is None:
        try:
            r = requests.get(
                f'https://www.google.com/search?q=site:{clean}',
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36', 'Accept-Language': 'de-DE,de;q=0.9'},
                timeout=15
            )
            html = r.text
            has_results = 'did not match any documents' not in html.lower() and 'keine übereinstimmenden dokumente' not in html.lower()
            count_match = re.search(r'(?:Ungefähr|About)\s+([\d\.,]+)\s+(?:Ergebnisse|results)', html)
            if count_match:
                result['count_text'] = count_match.group(1)
                result['indexed'] = True
            elif has_results and r.status_code == 200:
                result['indexed'] = True
                result['count_text'] = 'Indexiert'
        except: pass

    if result['indexed'] is None:
        result['indexed'] = result['has_sitemap'] or result['has_robots']

    return result

def check_google_business(company_name, domain):
    """Prüft ob Google Business Profile vorhanden ist"""
    clean_domain = domain.replace('https://','').replace('http://','').replace('www.','').rstrip('/')
    clean_name = (company_name or clean_domain.split('.')[0]).strip()
    base_url = f'https://{clean_domain}'

    # 1. Prüfe ob Schema.org LocalBusiness auf der Website
    try:
        r = requests.get(base_url, headers=HEADERS, timeout=10)
        html = r.text
        has_local_business = bool(re.search(r'LocalBusiness|PostalAddress|GeoCoordinates', html, re.IGNORECASE))
        if has_local_business:
            return {'likely_exists': True, 'confidence': 'Schema.org LocalBusiness gefunden', 'score': 3}
    except: pass

    # 2. Prüfe Google Maps Link auf der Website
    try:
        if 'maps.google' in html or 'google.com/maps' in html or 'goo.gl/maps' in html:
            return {'likely_exists': True, 'confidence': 'Google Maps Link auf Website', 'score': 2}
    except: pass

    # 3. Google Suche
    try:
        for query in [f'"{clean_name}" Bayern', f'"{clean_name}" Webdesign']:
            r = requests.get(
                f'https://www.google.com/search?q={requests.utils.quote(query)}&hl=de&gl=de',
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/604.1', 'Accept-Language': 'de-DE'},
                timeout=15
            )
            html = r.text
            indicators = [
                '/maps/place/' in html,
                'ludocid' in html,
                'Öffnungszeiten' in html,
                'kp_blk' in html,
                'business.google.com' in html,
                clean_domain in html and 'maps' in html,
            ]
            score = sum(indicators)
            if score >= 1:
                return {'likely_exists': True, 'confidence': f'Google-Suche: {score} Indikatoren', 'score': score}
    except: pass

    return {'likely_exists': None, 'confidence': 'Konnte nicht geprüft werden', 'score': 0, 'note': 'Bitte manuell prüfen: business.google.com'}

def check_subpages(url, html):
    """Analysiert interne Links / Unterseiten"""
    domain = urlparse(url).netloc
    base = f"{urlparse(url).scheme}://{domain}"
    links = re.findall(r'href=["\']([^"\'#?]+)["\']', html, re.IGNORECASE)
    internal = set()
    for link in links:
        if link.startswith('/') and len(link) > 1:
            internal.add(link)
        elif domain in link and link != url and link != base and link != base+'/':
            path = urlparse(link).path
            if len(path) > 1:
                internal.add(path)
    return {
        'count': len(internal),
        'pages': sorted(list(internal))[:20]
    }

def check_legal_texts(html, url):
    """Analysiert Rechtstexte auf Vollständigkeit"""
    html_lower = html.lower()
    result = {}

    # Impressum
    has_impressum = bool(re.search(r'impressum', html_lower))
    if has_impressum:
        imp_match = re.search(r'impressum.{0,5000}', html_lower, re.DOTALL)
        imp_text = imp_match.group(0)[:2000] if imp_match else ''
        result['impressum'] = {
            'found': True,
            'has_name': bool(re.search(r'(?:inhaber|geschäftsführer|name|stefan|mutter|chefblick)', imp_text, re.IGNORECASE)),
            'has_address': bool(re.search(r'(?:straße|str\.|weg|platz|haag|amper|\d{5})', imp_text, re.IGNORECASE)),
            'has_phone': bool(re.search(r'(?:tel|telefon|\+49|0\d{3,})', imp_text, re.IGNORECASE)),
            'has_email': bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', imp_text)),
            'has_register': bool(re.search(r'(?:handelsregister|amtsgericht|ust-id|steuernummer|gewerbeanmeldung)', imp_text, re.IGNORECASE)),
        }
    else:
        # Versuche Impressum-Seite zu laden
        try:
            imp_url = url.rstrip('/') + '/impressum'
            r = requests.get(imp_url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                imp_text = r.text.lower()
                result['impressum'] = {
                    'found': True,
                    'url': imp_url,
                    'has_name': bool(re.search(r'(?:inhaber|geschäftsführer|name|stefan)', imp_text)),
                    'has_address': bool(re.search(r'(?:straße|str\.|weg|\d{5})', imp_text)),
                    'has_phone': bool(re.search(r'(?:tel|telefon|\+49)', imp_text)),
                    'has_email': bool(re.search(r'@', imp_text)),
                    'has_register': bool(re.search(r'(?:handelsregister|ust-id|steuernummer)', imp_text)),
                }
            else:
                result['impressum'] = {'found': False}
        except:
            result['impressum'] = {'found': False}

    # Datenschutz
    has_privacy = bool(re.search(r'datenschutz|privacy', html_lower))
    if not has_privacy:
        try:
            priv_url = url.rstrip('/') + '/datenschutz'
            r = requests.get(priv_url, headers=HEADERS, timeout=10)
            has_privacy = r.status_code == 200
        except: pass

    if has_privacy:
        priv_text = html_lower
        result['datenschutz'] = {
            'found': True,
            'has_dsgvo': bool(re.search(r'dsgvo|ds-gvo|datenschutz-grundverordnung', priv_text)),
            'has_cookies': bool(re.search(r'cookie', priv_text)),
            'has_google_analytics': bool(re.search(r'google analytics|google tag|gtag|ga4', priv_text)),
            'has_third_party': bool(re.search(r'drittanbieter|third.party|facebook|instagram|youtube', priv_text)),
            'has_betroffenenrechte': bool(re.search(r'auskunft|löschung|widerruf|betroffenenrecht|widerspruch', priv_text)),
            'has_verantwortlicher': bool(re.search(r'verantwortliche|responsible|controller', priv_text)),
        }
    else:
        result['datenschutz'] = {'found': False}

    # Cookie Banner
    result['cookie_banner'] = {
        'found': bool(re.search(r'cookiebot|cookie-consent|klaro|borlabs|usercentrics|consent', html_lower)),
        'type': 'Cookiebot' if 'cookiebot' in html_lower else 'Borlabs' if 'borlabs' in html_lower else 'Usercentrics' if 'usercentrics' in html_lower else 'Unbekannt' if re.search(r'cookie-consent|klaro|consent', html_lower) else None
    }

    # AGB
    result['agb'] = {
        'found': bool(re.search(r'\bagb\b|allgemeine geschäftsbedingungen|terms of service', html_lower))
    }

    return result

def analyze_html_deep(html, url):
    """Tiefgreifende HTML-Analyse"""
    result = {'meta': {}, 'headings': {}, 'images': {}, 'performance_hints': {}, 'elements': {}, 'technical': {}, 'content': {}}
    h = html.lower()

    # Meta
    t = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
    result['meta']['title'] = re.sub(r'<[^>]+>','',t.group(1)).strip() if t else ''
    result['meta']['title_length'] = len(result['meta']['title'])
    result['meta']['title_ok'] = 30 <= result['meta']['title_length'] <= 65

    d = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if not d: d = re.search(r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']', html, re.IGNORECASE)
    result['meta']['description'] = d.group(1).strip() if d else ''
    result['meta']['description_length'] = len(result['meta']['description'])
    result['meta']['description_ok'] = 120 <= result['meta']['description_length'] <= 160

    result['meta']['has_og'] = bool(re.search(r'og:title|og:description|og:image', html, re.IGNORECASE))
    result['meta']['has_twitter_card'] = bool(re.search(r'twitter:card|twitter:title', html, re.IGNORECASE))
    result['meta']['has_canonical'] = bool(re.search(r'rel=["\']canonical["\']', html, re.IGNORECASE))
    result['meta']['has_robots'] = bool(re.search(r'<meta[^>]*name=["\']robots["\']', html, re.IGNORECASE))
    result['meta']['lang'] = re.search(r'<html[^>]*lang=["\']([^"\']+)["\']', html, re.IGNORECASE)
    result['meta']['lang'] = result['meta']['lang'].group(1) if result['meta']['lang'] else ''

    # Headings
    h1s = re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE|re.DOTALL)
    h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.IGNORECASE|re.DOTALL)
    h3s = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.IGNORECASE|re.DOTALL)
    result['headings']['h1'] = [re.sub(r'<[^>]+>','',x).strip()[:100] for x in h1s]
    result['headings']['h2'] = [re.sub(r'<[^>]+>','',x).strip()[:80] for x in h2s[:8]]
    result['headings']['h3_count'] = len(h3s)
    result['headings']['h1_count'] = len(h1s)

    # Images
    imgs = re.findall(r'<img[^>]*>', html, re.IGNORECASE)
    imgs_no_alt = [i for i in imgs if 'alt=' not in i.lower() or 'alt=""' in i]
    result['images']['total'] = len(imgs)
    result['images']['without_alt'] = len(imgs_no_alt)
    result['images']['has_lazy'] = bool(re.search(r'loading=["\']lazy["\']', html, re.IGNORECASE))
    result['images']['has_webp'] = bool(re.search(r'\.webp', html, re.IGNORECASE))

    # Performance hints
    result['performance_hints']['has_minified_css'] = bool(re.search(r'\.min\.css', html))
    result['performance_hints']['has_minified_js'] = bool(re.search(r'\.min\.js', html))
    result['performance_hints']['external_scripts'] = len(re.findall(r'<script[^>]*src=["\']https?://', html, re.IGNORECASE))
    result['performance_hints']['has_preload'] = bool(re.search(r'rel=["\']preload["\']', html, re.IGNORECASE))
    result['performance_hints']['has_font_display'] = bool(re.search(r'font-display', html))

    # Elements
    result['elements']['has_ssl'] = url.startswith('https://')
    result['elements']['has_viewport'] = bool(re.search(r'viewport', h))
    # Kontaktformular: direkt im HTML oder als Link zu Kontaktseite
    has_form = bool(re.search(r'<form[^>]*>.*?(?:kontakt|contact|email|nachricht|submit)', html, re.IGNORECASE|re.DOTALL))
    has_contact_link = bool(re.search(r'href=.*?kontakt|href=.*?contact', html, re.IGNORECASE))
    has_contact_section = bool(re.search(r'kontaktformular|contact.form|anfrage.stellen|nachricht.schicken', html, re.IGNORECASE))
    result['elements']['has_contact_form'] = has_form or has_contact_link or has_contact_section
    result['elements']['has_phone'] = bool(re.search(r'(?:tel:|telefon|phone|\+49|\b0\d{3,9}\b)', h))
    result['elements']['has_email'] = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html))
    result['elements']['has_address'] = bool(re.search(r'(?:straße|strasse|str\.|weg|platz|\d{5}\s+[A-Z])', h))
    result['elements']['has_impressum'] = bool(re.search(r'impressum', h))
    result['elements']['has_datenschutz'] = bool(re.search(r'datenschutz|privacy', h))
    result['elements']['has_cookie_banner'] = bool(re.search(r'cookie|gdpr|dsgvo|consent', h))
    result['elements']['has_google_maps'] = bool(re.search(r'maps\.google|google\.com/maps|maps\.googleapis', h))
    result['elements']['has_social_links'] = bool(re.search(r'facebook\.com|instagram\.com|linkedin\.com|tiktok\.com|youtube\.com', h))
    result['elements']['has_reviews'] = bool(re.search(r'bewertung|review|testimonial|kundenstimme|sterne|rating|trusted|provenexpert', h))
    result['elements']['has_cta'] = bool(re.search(r'(?:jetzt|anfrage|kontakt|buchen|termin|kostenlos|gratis|angebot|starten|loslegen)', h))
    result['elements']['has_newsletter'] = bool(re.search(r'newsletter|abonnieren|subscribe', h))
    result['elements']['has_blog'] = bool(re.search(r'blog|news|artikel|beiträge', h))
    result['elements']['has_faq'] = bool(re.search(r'faq|häufig|frequently', h))
    result['elements']['has_chatbot'] = bool(re.search(r'chat|tawkto|intercom|zendesk|tidio|crisp', h))
    result['elements']['has_whatsapp'] = bool(re.search(r'whatsapp|wa\.me', h))
    result['elements']['has_video'] = bool(re.search(r'<video|youtube\.com/embed|vimeo', h))
    result['elements']['has_structured_data'] = bool(re.search(r'application/ld\+json|schema\.org', h))
    result['elements']['has_responsive'] = bool(re.search(r'@media|bootstrap|tailwind|responsive', h))
    result['elements']['has_analytics'] = bool(re.search(r'google-analytics|googletagmanager|gtag|ga4|_ga', h))
    result['elements']['has_sitemap_link'] = bool(re.search(r'sitemap', h))

    # Technical
    result['technical']['charset_utf8'] = bool(re.search(r'charset=utf-8', h))
    result['technical']['framework'] = (
        'Next.js' if 'next.js' in h or '__next' in h or '_next/' in html else
        'Nuxt.js' if 'nuxt' in h else
        'WordPress' if 'wp-content' in h or 'wp-includes' in h else
        'Shopify' if 'shopify' in h else
        'Wix' if 'wix.com' in h else
        'Squarespace' if 'squarespace' in h else
        'Webflow' if 'webflow' in h else
        'React' if 'react' in h else
        'Unbekannt'
    )

    # Content
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    result['content']['word_count'] = len(text.split())
    result['content']['text_snippet'] = text[:500]

    return result

def ai_deep_audit(url, html_analysis, pagespeed, legal, subpages, google_index, google_business, html_snippet):
    """Claude KI Tiefenanalyse"""
    api_key = load_api_key()
    if not api_key: return {'error': 'Kein API-Key'}

    clean = re.sub(r'<script[^>]*>.*?</script>', '', html_snippet, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<!--.*?-->', '', clean, flags=re.DOTALL)
    clean = clean[:6000]

    ps_m = pagespeed.get('mobile',{}) if pagespeed.get('success') else {}
    ps_d = pagespeed.get('desktop',{}) if pagespeed.get('success') else {}
    el = html_analysis.get('elements',{})
    meta = html_analysis.get('meta',{})
    tech = html_analysis.get('technical',{})
    imp = legal.get('impressum',{})
    priv = legal.get('datenschutz',{})
    cookie = legal.get('cookie_banner',{})

    prompt = f"""Du bist ein erfahrener Webdesign-, SEO- und Rechts-Experte der Agentur ChefBlick aus Bayern.
Führe eine schonungslose, detaillierte Analyse dieser Website durch. Sei präzise und konkret.

URL: {url}
Framework/CMS: {tech.get('framework','Unbekannt')}
Sprache: {meta.get('lang','N/A')}

GOOGLE-SICHTBARKEIT:
- Google indexiert: {'Ja, ca. ' + google_index.get('count_text','?') + ' Seiten' if google_index.get('indexed') else 'NEIN oder sehr wenige Seiten'}
- Indexierte Beispielseiten: {', '.join(google_index.get('sample_pages',[])[:3]) or 'Keine gefunden'}
- Google Business Profile: {'Wahrscheinlich vorhanden' if google_business.get('likely_exists') else 'NICHT GEFUNDEN - kritisch für lokale Sichtbarkeit' if google_business.get('likely_exists') == False else 'Unklar'}
- Google Maps Eintrag auf Seite: {'Ja' if el.get('has_google_maps') else 'Nein'}

UNTERSEITEN ({subpages.get('count',0)} gefunden):
{chr(10).join(subpages.get('pages',[])[:15]) or 'Keine internen Links gefunden'}

PAGESPEED:
- Mobile: Performance {ps_m.get('performance','N/A')}/100, SEO {ps_m.get('seo','N/A')}/100, LCP {ps_m.get('lcp','N/A')}, CLS {ps_m.get('cls','N/A')}
- Desktop: Performance {ps_d.get('performance','N/A')}/100, SEO {ps_d.get('seo','N/A')}/100

SEO:
- Title: "{meta.get('title','')}" ({meta.get('title_length',0)} Zeichen, {'OK' if meta.get('title_ok') else 'PROBLEM'})
- Meta Description: "{meta.get('description','')}" ({meta.get('description_length',0)} Zeichen, {'OK' if meta.get('description_ok') else 'PROBLEM'})
- H1: {html_analysis.get('headings',{}).get('h1',[])}
- H2: {html_analysis.get('headings',{}).get('h2',[])}
- Canonical: {'Ja' if meta.get('has_canonical') else 'Nein'}
- Sprach-Attribut: {'Ja: ' + meta.get('lang','') if meta.get('lang') else 'FEHLT'}
- Strukturierte Daten: {'Ja' if el.get('has_structured_data') else 'FEHLT'}
- OG-Tags: {'Ja' if meta.get('has_og') else 'Fehlt'}
- Bilder ohne Alt-Text: {html_analysis.get('images',{}).get('without_alt',0)} von {html_analysis.get('images',{}).get('total',0)}
- WebP-Format: {'Ja' if html_analysis.get('images',{}).get('has_webp') else 'Nein'}
- Lazy Loading: {'Ja' if html_analysis.get('images',{}).get('has_lazy') else 'Nein'}

TECHNIK:
- SSL: {'Ja' if el.get('has_ssl') else 'NEIN - KRITISCH'}
- Mobile Viewport: {'Ja' if el.get('has_viewport') else 'FEHLT'}
- Responsive: {'Ja' if el.get('has_responsive') else 'Unklar'}
- Analytics: {'Ja' if el.get('has_analytics') else 'FEHLT'}
- Externe Scripts: {html_analysis.get('performance_hints',{}).get('external_scripts',0)}
- Preload: {'Ja' if html_analysis.get('performance_hints',{}).get('has_preload') else 'Nein'}

INHALTE & CONVERSION:
- Kontaktformular: {'Ja' if el.get('has_contact_form') else 'FEHLT'}
- Telefon: {'Ja' if el.get('has_phone') else 'FEHLT'}
- E-Mail: {'Ja' if el.get('has_email') else 'FEHLT'}
- Adresse: {'Ja' if el.get('has_address') else 'Nicht gefunden'}
- Call-to-Action: {'Ja' if el.get('has_cta') else 'SCHWACH'}
- Kundenbewertungen: {'Ja' if el.get('has_reviews') else 'FEHLEN'}
- Social Media Links: {'Ja' if el.get('has_social_links') else 'Fehlen'}
- Blog/News: {'Ja' if el.get('has_blog') else 'Nein'}
- FAQ: {'Ja' if el.get('has_faq') else 'Nein'}
- Chat/WhatsApp: {'Ja' if el.get('has_chatbot') or el.get('has_whatsapp') else 'Nein'}
- Video-Inhalte: {'Ja' if el.get('has_video') else 'Nein'}
- Newsletter: {'Ja' if el.get('has_newsletter') else 'Fehlt'}
- Wortanzahl: {html_analysis.get('content',{}).get('word_count',0)}

RECHTLICHES (sehr wichtig):
- Impressum: {'Gefunden' if imp.get('found') else 'FEHLT - ABMAHNRISIKO'}
  - Name/Inhaber: {'Ja' if imp.get('has_name') else 'FEHLT'}
  - Adresse: {'Ja' if imp.get('has_address') else 'FEHLT'}
  - Telefon: {'Ja' if imp.get('has_phone') else 'FEHLT'}
  - E-Mail: {'Ja' if imp.get('has_email') else 'FEHLT'}
  - Handelsregister/Steuer: {'Ja' if imp.get('has_register') else 'Nicht gefunden'}
- Datenschutz: {'Gefunden' if priv.get('found') else 'FEHLT - DSGVO-VERSTOESS'}
  - DSGVO erwähnt: {'Ja' if priv.get('has_dsgvo') else 'Nein'}
  - Cookie-Info: {'Ja' if priv.get('has_cookies') else 'Fehlt'}
  - Betroffenenrechte: {'Ja' if priv.get('has_betroffenenrechte') else 'FEHLT'}
  - Verantwortlicher: {'Ja' if priv.get('has_verantwortlicher') else 'FEHLT'}
  - Drittanbieter: {'Erwähnt' if priv.get('has_third_party') else 'Nicht erwähnt'}
- Cookie-Banner: {'Ja, Typ: ' + (cookie.get('type') or 'Unbekannt') if cookie.get('found') else 'FEHLT - DSGVO-PFLICHT'}
- AGB: {'Ja' if legal.get('agb',{}).get('found') else 'Nicht vorhanden'}

HTML-AUSZUG:
{clean}

Erstelle einen DETAILLIERTEN Audit als JSON:
{{
  "gesamtnote": "A/B/C/D/F",
  "gesamtpunkte": 0-100,
  "gesamtbewertung": "3-4 Sätze Zusammenfassung",
  "ist_altbacken": true/false,
  "altbacken_begruendung": "Konkrete Begründung warum veraltet oder modern",
  "staerken": ["Stärke 1", "Stärke 2", "Stärke 3"],
  "groesste_schwaechen": ["Schwäche 1", "Schwäche 2", "Schwäche 3"],
  "kategorien": {{
    "design": {{"note": "A-F", "punkte": 0-100, "bewertung": "...", "probleme": ["..."], "empfehlungen": ["..."]}},
    "seo": {{"note": "A-F", "punkte": 0-100, "bewertung": "...", "probleme": ["..."], "empfehlungen": ["..."]}},
    "technik": {{"note": "A-F", "punkte": 0-100, "bewertung": "...", "probleme": ["..."], "empfehlungen": ["..."]}},
    "mobile": {{"note": "A-F", "punkte": 0-100, "bewertung": "...", "probleme": ["..."], "empfehlungen": ["..."]}},
    "inhalte": {{"note": "A-F", "punkte": 0-100, "bewertung": "...", "probleme": ["..."], "empfehlungen": ["..."]}},
    "rechtliches": {{"note": "A-F", "punkte": 0-100, "bewertung": "...", "probleme": ["..."], "empfehlungen": ["..."]}},
    "google_sichtbarkeit": {{"note": "A-F", "punkte": 0-100, "bewertung": "...", "probleme": ["..."], "empfehlungen": ["..."]}}
  }},
  "top_massnahmen": [
    {{"prioritaet": "KRITISCH/HOCH/MITTEL", "massnahme": "konkrete Maßnahme", "begruendung": "warum wichtig", "aufwand": "Klein/Mittel/Groß", "zeitrahmen": "Tage/Wochen/Monate"}}
  ],
  "rechtliche_risiken": ["Konkretes Risiko 1", "Konkretes Risiko 2"],
  "google_business_empfehlung": "Konkrete Empfehlung zum Google Business Profil",
  "chefblick_angebot": "Personalisierter Angebotstext was ChefBlick konkret verbessern würde (3-5 Sätze)"
}}

WICHTIGE BEWERTUNGSRICHTLINIEN:
- Note A (90-100): Nahezu perfekt, kaum Verbesserungsbedarf
- Note B (70-89): Gut, einige Optimierungen möglich
- Note C (50-69): Durchschnittlich, deutlicher Verbesserungsbedarf
- Note D (30-49): Schlecht, erhebliche Mängel
- Note F (0-29): Sehr schlecht, kritische Probleme

Sei KONKRET und DIFFERENZIERT - gib nicht einfach überall C. 
Wenn SSL vorhanden, Mobile OK und Design modern ist → Design mindestens B.
Wenn Impressum und Datenschutz vorhanden → Rechtliches mindestens B.
Wenn Next.js/React verwendet → Technik mindestens B.
Nur wirklich fehlende KRITISCHE Elemente rechtfertigen D oder F.
Google Maps und Newsletter sind KEINE kritischen Mängel - max. eine Note schlechter.

Antworte NUR mit dem JSON, keine weiteren Erklärungen."""

    try:
        resp = requests.post(ANTHROPIC_API,
            headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
            json={'model': 'claude-haiku-4-5-20251001', 'max_tokens': 5000, 'messages': [{'role': 'user', 'content': prompt}]},
            timeout=90).json()
        text = resp.get('content',[{}])[0].get('text','{}').strip()
        if '```json' in text: text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text: text = text.split('```')[1].split('```')[0].strip()
        return json.loads(text)
    except Exception as e:
        return {'error': str(e), 'raw': text[:500] if 'text' in dir() else ''}

def generate_pdf_report(url, html_analysis, pagespeed, legal, subpages, google_index, google_business, ai_result, output_path, screenshot_data=None):
    """PDF mit ChefBlick Briefkopf"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor, white, black
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY

        W, H = A4
        doc = SimpleDocTemplate(output_path, pagesize=A4,
            rightMargin=18*mm, leftMargin=18*mm, topMargin=15*mm, bottomMargin=20*mm)

        CB = HexColor('#0d0f14')
        ACC = HexColor('#4f8ef7')
        ACC2 = HexColor('#7c3aed')
        GRN = HexColor('#22c55e')
        RED = HexColor('#ef4444')
        ORG = HexColor('#f59e0b')
        GRY = HexColor('#8892a4')
        LGT = HexColor('#f0f2f8')
        WHT = white

        def nc(n): return {'A':GRN,'B':HexColor('#84cc16'),'C':ORG,'D':HexColor('#f97316'),'F':RED}.get(n,GRY)
        def pc(p): return {'KRITISCH':RED,'HOCH':ORG,'MITTEL':ACC}.get(p,GRY)

        def S(name,**kw): return ParagraphStyle(name,**kw)
        s_h1 = S('h1',fontSize=20,textColor=WHT,fontName='Helvetica-Bold',leading=24)
        s_h2 = S('h2',fontSize=13,textColor=CB,fontName='Helvetica-Bold',spaceBefore=10,spaceAfter=5)
        s_h3 = S('h3',fontSize=10,textColor=ACC,fontName='Helvetica-Bold',spaceBefore=6,spaceAfter=3)
        s_body = S('body',fontSize=8.5,textColor=CB,fontName='Helvetica',leading=13,spaceAfter=3)
        s_small = S('small',fontSize=7.5,textColor=GRY,fontName='Helvetica',leading=11)
        s_bold = S('bold',fontSize=8.5,textColor=CB,fontName='Helvetica-Bold',leading=13)
        s_white = S('white',fontSize=9,textColor=WHT,fontName='Helvetica',leading=13)
        s_white_bold = S('wb',fontSize=9,textColor=WHT,fontName='Helvetica-Bold',leading=13)
        s_center = S('center',fontSize=8.5,textColor=CB,fontName='Helvetica',leading=13,alignment=TA_CENTER)

        story = []

        # ── BRIEFKOPF mit Logo ──
        from reportlab.platypus import Image as RLImage
        logo_path = os.path.join(BASE_DIR, 'chefblick_logo.png')
        logo_cell = RLImage(logo_path, width=52*mm, height=18*mm) if os.path.exists(logo_path) else Paragraph('<b>ChefBlick</b>', S('lb',fontSize=16,textColor=WHT,fontName='Helvetica-Bold'))

        header = Table([[
            logo_cell,
            Paragraph(f'<font color="#a0aec0" size="8">Stefan Mutter | Inhaber<br/>In der Stockwiese 6, 85410 Haag a. d. Amper<br/>team@chefblick.de | www.chefblick.de<br/><br/><b>Website Audit Report</b><br/>{datetime.now().strftime("%d. %B %Y")}</font>',
                      S('hd2',fontSize=8,textColor=GRY,fontName='Helvetica',leading=13,alignment=TA_RIGHT))
        ]], colWidths=[80*mm,92*mm])
        header.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),CB),
            ('PADDING',(0,0),(-1,-1),12),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ]))
        story.append(header)
        story.append(Spacer(1,5*mm))

        # ── SCREENSHOT ──
        if screenshot_data:
            try:
                import io
                from reportlab.platypus import Image as RLImage
                img_buffer = io.BytesIO(screenshot_data)
                img = RLImage(img_buffer, width=172*mm, height=96*mm)
                img.hAlign = 'CENTER'
                story.append(img)
                story.append(Spacer(1,3*mm))
                story.append(Paragraph('Screenshot der analysierten Website', S('sc',fontSize=7.5,textColor=GRY,fontName='Helvetica',alignment=TA_CENTER)))
                story.append(Spacer(1,4*mm))
            except Exception as e:
                print(f"Screenshot im PDF Fehler: {e}")

        # ── URL + Datum ──
        story.append(Paragraph(f'Analysierte URL: <b>{url}</b>', S('url',fontSize=9,textColor=GRY,fontName='Helvetica',leading=13)))
        story.append(Spacer(1,4*mm))

        # ── GESAMTNOTE ──
        ai = ai_result or {}
        note = ai.get('gesamtnote','C')
        punkte = ai.get('gesamtpunkte',50)
        altbacken = ai.get('ist_altbacken',False)

        summary_data = [[
            Table([[Paragraph(f'{punkte}', S('gn',fontSize=52,textColor=nc(note),fontName='Helvetica-Bold',alignment=TA_CENTER,leading=56)),
                    Paragraph(f'von 100 Pkt. | Note: {note}', S('gp',fontSize=8,textColor=GRY,fontName='Helvetica',alignment=TA_CENTER))
                   ]], colWidths=[38*mm]),
            Table([[
                Paragraph('<b>Gesamtbewertung</b>', s_bold),
                Paragraph('DESIGN VERALTET' if altbacken else 'DESIGN MODERN',
                          S('dstat',fontSize=9,textColor=RED if altbacken else GRN,fontName='Helvetica-Bold',alignment=TA_RIGHT))
            ],[
                Paragraph(ai.get('gesamtbewertung',''), S('gb',fontSize=8.5,textColor=CB,fontName='Helvetica',leading=13)),''
            ]], colWidths=[100*mm,37*mm]),
        ]]
        sum_table = Table(summary_data, colWidths=[38*mm, 134*mm])
        sum_table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),LGT),
            ('PADDING',(0,0),(-1,-1),10),
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('GRID',(0,0),(-1,-1),0.5,HexColor('#d1d9e6')),
            ('ROUNDEDCORNERS',[6]),
        ]))
        story.append(sum_table)
        story.append(Spacer(1,3*mm))

        if ai.get('altbacken_begruendung'):
            story.append(Paragraph(ai['altbacken_begruendung'], s_body))

        # Stärken / Schwächen
        if ai.get('staerken') or ai.get('groesste_schwaechen'):
            sw_data = [[
                Paragraph('<b>✓ Stärken</b>', S('sh',fontSize=9,textColor=GRN,fontName='Helvetica-Bold')),
                Paragraph('<b>✗ Größte Schwächen</b>', S('wh',fontSize=9,textColor=RED,fontName='Helvetica-Bold'))
            ]]
            max_rows = max(len(ai.get('staerken',[])), len(ai.get('groesste_schwaechen',[])))
            for i in range(max_rows):
                s = ai.get('staerken',[])[i] if i < len(ai.get('staerken',[])) else ''
                w = ai.get('groesste_schwaechen',[])[i] if i < len(ai.get('groesste_schwaechen',[])) else ''
                sw_data.append([
                    Paragraph(f'• {s}', S('si',fontSize=8,textColor=CB,fontName='Helvetica',leading=12)) if s else Paragraph(' ', getSampleStyleSheet()['Normal']),
                    Paragraph(f'• {w}', S('wi',fontSize=8,textColor=CB,fontName='Helvetica',leading=12)) if w else Paragraph(' ', getSampleStyleSheet()['Normal'])
                ])
            sw_table = Table(sw_data, colWidths=[86*mm,86*mm])
            sw_table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(0,-1),HexColor('#f0fdf4')),
                ('BACKGROUND',(1,0),(1,-1),HexColor('#fef2f2')),
                ('PADDING',(0,0),(-1,-1),8),
                ('GRID',(0,0),(-1,-1),0.5,HexColor('#d1d9e6')),
                ('ROUNDEDCORNERS',[4]),
            ]))
            story.append(Spacer(1,4*mm))
            story.append(sw_table)

        story.append(Spacer(1,5*mm))

        # ── GOOGLE SICHTBARKEIT ──
        story.append(Paragraph('Google-Sichtbarkeit', s_h2))
        story.append(HRFlowable(width='100%',thickness=1,color=ACC))
        story.append(Spacer(1,3*mm))

        gi = google_index or {}
        gb = google_business or {}
        ps = pagespeed or {}
        ps_m = ps.get('mobile',{})
        ps_d = ps.get('desktop',{})

        g_data = [
            [Paragraph('<b>Metrik</b>',s_bold), Paragraph('<b>Status</b>',s_bold), Paragraph('<b>Bewertung</b>',s_bold)],
            ['Google Indexierung', f"{'✓ Ja, ca. ' + gi.get('count_text','?') + ' Seiten' if gi.get('indexed') else '✗ Nicht/kaum indexiert'}", 'Gut' if gi.get('indexed') else 'KRITISCH'],
            ['Google Business Profil', '✓ Gefunden' if gb.get('likely_exists') else '✗ Nicht gefunden', 'OK' if gb.get('likely_exists') else 'Handlungsbedarf'],
            ['Unterseiten (intern)', f"{subpages.get('count',0)} gefunden", 'Gut' if subpages.get('count',0) > 5 else 'Wenig Content'],
        ] + ([
            ['PageSpeed Mobile', f"{ps_m.get('performance','N/A')}/100", 'Gut' if (ps_m.get('performance') or 0) >= 70 else 'Verbesserung nötig'],
            ['PageSpeed Desktop', f"{ps_d.get('performance','N/A')}/100", 'Gut' if (ps_d.get('performance') or 0) >= 70 else 'Verbesserung nötig'],
            ['SEO Score (Mobile)', f"{ps_m.get('seo','N/A')}/100", 'Gut' if (ps_m.get('seo') or 0) >= 80 else 'Optimierung nötig'],
        ] if ps.get('success') else [])
        g_table = Table(g_data, colWidths=[65*mm,65*mm,42*mm])
        g_table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),CB),
            ('TEXTCOLOR',(0,0),(-1,0),WHT),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHT,LGT]),
            ('GRID',(0,0),(-1,-1),0.5,HexColor('#d1d9e6')),
            ('PADDING',(0,0),(-1,-1),7),
            ('FONTSIZE',(0,0),(-1,-1),8.5),
        ]))
        story.append(g_table)

        if gi.get('sample_pages'):
            story.append(Spacer(1,3*mm))
            story.append(Paragraph('<b>Indexierte Seiten (Beispiele):</b> ' + ', '.join(gi['sample_pages'][:5]), s_small))

        if ai.get('google_business_empfehlung'):
            story.append(Spacer(1,3*mm))
            story.append(Paragraph(f'<b>Google Business:</b> {ai["google_business_empfehlung"]}', s_body))

        story.append(Spacer(1,5*mm))

        # ── KATEGORIEN ──
        story.append(Paragraph('Detailbewertung', s_h2))
        story.append(HRFlowable(width='100%',thickness=1,color=ACC))
        story.append(Spacer(1,3*mm))

        kats = ai.get('kategorien',{})
        kat_map = {'design':'Design & UX','seo':'SEO','technik':'Technik','mobile':'Mobile',
                   'inhalte':'Inhalte & Conversion','rechtliches':'Rechtliches','google_sichtbarkeit':'Google Sichtbarkeit'}

        for key, label in kat_map.items():
            k = kats.get(key,{})
            kn = k.get('note','C')
            kp = k.get('punkte',50)

            # Header mit Note und Balken
            h_row = Table([[
                Paragraph(f'<b>{label}</b>', S('kh',fontSize=10,textColor=WHT,fontName='Helvetica-Bold')),
                Paragraph(f'<b>{kp}/100</b> — Note {kn}', S('kn',fontSize=9,textColor=WHT,fontName='Helvetica-Bold',alignment=TA_RIGHT))
            ]], colWidths=[120*mm,52*mm])
            h_row.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),nc(kn)),('PADDING',(0,0),(-1,-1),8)]))
            story.append(h_row)

            # Bewertungstext
            if k.get('bewertung'):
                story.append(Spacer(1,2*mm))
                story.append(Paragraph(k['bewertung'], s_body))

            # Probleme
            if k.get('probleme'):
                story.append(Spacer(1,2*mm))
                story.append(Paragraph('<b>Probleme / Handlungsbedarf:</b>', S('ph',fontSize=8.5,textColor=RED,fontName='Helvetica-Bold')))
                prob_rows = []
                for p in k['probleme']:
                    prob_rows.append([
                        Paragraph('✗', S('xi',fontSize=9,textColor=RED,fontName='Helvetica-Bold',alignment=TA_CENTER)),
                        Paragraph(p, S('pr',fontSize=8.5,textColor=CB,fontName='Helvetica',leading=13))
                    ])
                pt = Table(prob_rows, colWidths=[8*mm,164*mm])
                pt.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,-1),HexColor('#fef2f2')),
                    ('PADDING',(0,0),(-1,-1),5),
                    ('GRID',(0,0),(-1,-1),0.3,HexColor('#fca5a5')),
                    ('VALIGN',(0,0),(-1,-1),'TOP'),
                ]))
                story.append(pt)

            # Empfehlungen
            if k.get('empfehlungen'):
                story.append(Spacer(1,2*mm))
                story.append(Paragraph('<b>Empfehlungen / Maßnahmen:</b>', S('eh',fontSize=8.5,textColor=GRN,fontName='Helvetica-Bold')))
                emp_rows = []
                for e in k['empfehlungen']:
                    emp_rows.append([
                        Paragraph('✓', S('ci',fontSize=9,textColor=GRN,fontName='Helvetica-Bold',alignment=TA_CENTER)),
                        Paragraph(e, S('er',fontSize=8.5,textColor=CB,fontName='Helvetica',leading=13))
                    ])
                et = Table(emp_rows, colWidths=[8*mm,164*mm])
                et.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,-1),HexColor('#f0fdf4')),
                    ('PADDING',(0,0),(-1,-1),5),
                    ('GRID',(0,0),(-1,-1),0.3,HexColor('#86efac')),
                    ('VALIGN',(0,0),(-1,-1),'TOP'),
                ]))
                story.append(et)

            story.append(Spacer(1,5*mm))

        # ── RECHTLICHE RISIKEN ──
        if ai.get('rechtliche_risiken'):
            story.append(Paragraph('Rechtliche Risiken', s_h2))
            story.append(HRFlowable(width='100%',thickness=1,color=RED))
            story.append(Spacer(1,3*mm))
            risk_rows = [[Paragraph('⚠', S('wr',fontSize=9,textColor=RED,fontName='Helvetica-Bold')),
                          Paragraph(r, S('rr',fontSize=8.5,textColor=CB,fontName='Helvetica',leading=13))]
                         for r in ai['rechtliche_risiken']]
            rt = Table(risk_rows, colWidths=[8*mm,164*mm])
            rt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),HexColor('#fef2f2')),('PADDING',(0,0),(-1,-1),6),('GRID',(0,0),(-1,-1),0.3,HexColor('#fca5a5'))]))
            story.append(rt)
            story.append(Spacer(1,5*mm))

        # ── CHECKLISTE ──
        story.append(Paragraph('Inhalts-Checkliste', s_h2))
        story.append(HRFlowable(width='100%',thickness=1,color=ACC))
        story.append(Spacer(1,3*mm))

        el = html_analysis.get('elements',{})
        checks = [
            ('SSL/HTTPS', el.get('has_ssl')), ('Kontaktformular', el.get('has_contact_form')),
            ('Telefonnummer', el.get('has_phone')), ('E-Mail sichtbar', el.get('has_email')),
            ('Adresse/Standort', el.get('has_address')), ('Impressum', el.get('has_impressum')),
            ('Datenschutz', el.get('has_datenschutz')), ('Cookie-Banner', el.get('has_cookie_banner')),
            ('Google Maps', el.get('has_google_maps')), ('Social Media', el.get('has_social_links')),
            ('Kundenbewertungen', el.get('has_reviews')), ('Call-to-Action', el.get('has_cta')),
            ('Newsletter', el.get('has_newsletter')), ('Mobile Viewport', el.get('has_viewport')),
            ('Analytics', el.get('has_analytics')), ('Strukturierte Daten', el.get('has_structured_data')),
            ('Blog/News', el.get('has_blog')), ('FAQ', el.get('has_faq')),
            ('Chat/WhatsApp', el.get('has_chatbot') or el.get('has_whatsapp')), ('Video-Inhalte', el.get('has_video')),
        ]
        # 4 Spalten
        cols = 4
        rows_data = []
        for i in range(0, len(checks), cols):
            row = []
            for label, ok in checks[i:i+cols]:
                row.append(Paragraph(f'{"✓" if ok else "✗"} {label}',
                    S('ck',fontSize=7.5,textColor=GRN if ok else RED,fontName='Helvetica',leading=12)))
            while len(row) < cols:
                row.append(Paragraph(' ', getSampleStyleSheet()['Normal']))
            rows_data.append(row)
        ck_table = Table(rows_data, colWidths=[43*mm]*4)
        ck_table.setStyle(TableStyle([('PADDING',(0,0),(-1,-1),5),('GRID',(0,0),(-1,-1),0.3,HexColor('#d1d9e6'))]))
        story.append(ck_table)
        story.append(Spacer(1,5*mm))

        # ── MASSNAHMEN ──
        story.append(Paragraph('Empfohlene Maßnahmen (nach Priorität)', s_h2))
        story.append(HRFlowable(width='100%',thickness=1,color=ACC))
        story.append(Spacer(1,3*mm))

        for i, m in enumerate(ai.get('top_massnahmen',[])[:12], 1):
            prio = m.get('prioritaet','MITTEL')
            m_data = [[
                Paragraph(f'<b>{i}. {m.get("massnahme","")}</b>', S('mt',fontSize=9,textColor=CB,fontName='Helvetica-Bold')),
                Paragraph(prio, S('mp',fontSize=8,textColor=WHT,fontName='Helvetica-Bold',alignment=TA_CENTER)),
                Paragraph(f'Aufwand: {m.get("aufwand","?")}', S('ma',fontSize=7.5,textColor=GRY,fontName='Helvetica',alignment=TA_CENTER)),
                Paragraph(m.get('zeitrahmen',''), S('mz',fontSize=7.5,textColor=GRY,fontName='Helvetica',alignment=TA_CENTER)),
            ],[
                Paragraph(m.get('begruendung',''), S('mb',fontSize=8,textColor=GRY,fontName='Helvetica',leading=12)),
                '', '', ''
            ]]
            mt = Table(m_data, colWidths=[90*mm,28*mm,28*mm,26*mm])
            mt.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),LGT),
                ('BACKGROUND',(1,0),(1,0),pc(prio)),
                ('SPAN',(0,1),(-1,1)),
                ('PADDING',(0,0),(-1,-1),7),
                ('GRID',(0,0),(-1,-1),0.3,HexColor('#d1d9e6')),
                ('ROUNDEDCORNERS',[4]),
            ]))
            story.append(mt)
            story.append(Spacer(1,2*mm))

        # ── CHEFBLICK ANGEBOT ──
        if ai.get('chefblick_angebot'):
            story.append(Spacer(1,4*mm))
            offer = Table([[
                Paragraph('<b>💡 ChefBlick — Ihr Partner für digitalen Erfolg</b>',
                          S('oh',fontSize=10,textColor=WHT,fontName='Helvetica-Bold'))
            ],[
                Paragraph(ai['chefblick_angebot'],
                          S('ob',fontSize=8.5,textColor=CB,fontName='Helvetica',leading=13))
            ],[
                Paragraph('<b>Jetzt kostenlos anfragen: team@chefblick.de | www.chefblick.de</b>',
                          S('oc',fontSize=8.5,textColor=ACC,fontName='Helvetica-Bold'))
            ]], colWidths=[172*mm])
            offer.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(0,0),ACC),
                ('BACKGROUND',(0,1),(0,1),HexColor('#eff6ff')),
                ('BACKGROUND',(0,2),(0,2),LGT),
                ('PADDING',(0,0),(-1,-1),12),
                ('GRID',(0,0),(-1,-1),0.5,ACC),
                ('ROUNDEDCORNERS',[6]),
            ]))
            story.append(offer)

        # ── FOOTER ──
        story.append(Spacer(1,8*mm))
        story.append(HRFlowable(width='100%',thickness=0.5,color=GRY))
        story.append(Spacer(1,3*mm))
        ft = Table([[
            Paragraph('<b>ChefBlick</b> | Webdesign & Software | Haag an der Amper | www.chefblick.de | team@chefblick.de',
                      S('fl',fontSize=7.5,textColor=GRY,fontName='Helvetica')),
            Paragraph(f'Erstellt: {datetime.now().strftime("%d.%m.%Y %H:%M")} Uhr',
                      S('fr',fontSize=7.5,textColor=GRY,fontName='Helvetica',alignment=TA_RIGHT))
        ]], colWidths=[120*mm,52*mm])
        ft.setStyle(TableStyle([('PADDING',(0,0),(-1,-1),0)]))
        story.append(ft)

        doc.build(story)
        return True
    except Exception as e:
        import traceback; traceback.print_exc()
        return False


def get_page_screenshot(url):
    """Holt Screenshot der Seite via screenshotone.com (kostenlos)"""
    try:
        import urllib.parse
        encoded = urllib.parse.quote(url, safe='')
        # Kostenloser Screenshot-Service
        screenshot_url = f"https://s.wordpress.com/mshots/v1/{encoded}?w=1200&h=800"
        r = requests.get(screenshot_url, timeout=30, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 10000:
            return r.content
        # Fallback: Google PageSpeed Screenshot
        ps_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={encoded}&strategy=desktop&screenshot=true"
        r2 = requests.get(ps_url, timeout=30)
        data = r2.json()
        screenshot_data = data.get('lighthouseResult',{}).get('audits',{}).get('final-screenshot',{}).get('details',{}).get('data','')
        if screenshot_data and screenshot_data.startswith('data:image'):
            import base64
            img_data = screenshot_data.split(',')[1]
            return base64.b64decode(img_data)
        return None
    except Exception as e:
        print(f"Screenshot Fehler: {e}")
        return None

def run_full_audit(url):
    if not url.startswith('http'): url = 'https://' + url

    print(f"Audit gestartet: {url}")
    screenshot_data = None
    result = {'url': url, 'timestamp': datetime.now().isoformat(), 'status': 'running'}

    html, status_code, final_url, headers = fetch_page(url)
    result['status_code'] = status_code
    result['final_url'] = final_url

    if not html:
        result['status'] = 'error'
        result['error'] = 'Seite nicht erreichbar'
        return result

    print("Screenshot erstellen...")
    screenshot_data = get_page_screenshot(final_url)
    result['has_screenshot'] = screenshot_data is not None

    domain = urlparse(final_url).netloc

    print("HTML analysieren...")
    html_analysis = analyze_html_deep(html, final_url)
    result['html_analysis'] = html_analysis

    print("Rechtstexte prüfen...")
    legal = check_legal_texts(html, final_url)
    result['legal'] = legal

    print("Unterseiten zählen...")
    subpages = check_subpages(final_url, html)
    result['subpages'] = subpages

    print("Google Indexierung prüfen...")
    google_index = check_google_index(domain)
    result['google_index'] = google_index

    print("Google Business prüfen...")
    company_name = html_analysis.get('meta',{}).get('title','').split('|')[0].strip()
    google_business = check_google_business(company_name, domain)
    result['google_business'] = google_business

    print("PageSpeed abrufen...")
    pagespeed = check_pagespeed(final_url)
    result['pagespeed'] = pagespeed

    print("KI-Tiefenanalyse...")
    ai_result = ai_deep_audit(final_url, html_analysis, pagespeed, legal, subpages, google_index, google_business, html[:15000])
    result['ai_result'] = ai_result

    print("PDF erstellen...")
    domain_clean = domain.replace('www.','').replace('.','_')
    pdf_fn = f"audit_{domain_clean}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = os.path.join(BASE_DIR, 'audits', pdf_fn)
    os.makedirs(os.path.join(BASE_DIR, 'audits'), exist_ok=True)

    pdf_ok = generate_pdf_report(final_url, html_analysis, pagespeed, legal, subpages, google_index, google_business, ai_result, pdf_path, screenshot_data=screenshot_data)
    result['pdf_path'] = pdf_path if pdf_ok else None
    result['pdf_filename'] = pdf_fn if pdf_ok else None
    result['status'] = 'done'
    print(f"Fertig: {pdf_fn}")
    return result
