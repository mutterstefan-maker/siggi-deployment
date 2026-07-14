#!/usr/bin/env python3
# test_analytics.py - Teste Google Analytics Verbindung

import os
import sys

# Ordner mit Analytics-Dateien
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# Prüfe JSON-Datei
json_file = os.path.join(BASE_DIR, 'siggi-dashboard-ac0baeaaaef6.json')
if not os.path.exists(json_file):
    print(f"❌ JSON-Datei nicht gefunden: {json_file}")
    sys.exit(1)
else:
    print(f"✓ JSON-Datei gefunden: {json_file}")

# Versuche Analytics zu initialisieren
try:
    from analytics_engine import AnalyticsEngine
    print("✓ analytics_engine.py importiert")
except ImportError as e:
    print(f"❌ analytics_engine.py nicht gefunden oder Fehler: {e}")
    sys.exit(1)

try:
    print("\nStarte Analytics Verbindung...")
    analytics = AnalyticsEngine(json_file, '534389721')
    print("✓ Analytics Client initialisiert")
except Exception as e:
    print(f"❌ Fehler beim Initialisieren: {e}")
    sys.exit(1)

# Test: Traffic Summary abrufen
try:
    print("\n📊 Teste Traffic Summary (7 Tage)...")
    summary = analytics.get_traffic_summary(7)
    print(f"  ✓ Users: {summary['total_users']}")
    print(f"  ✓ Pageviews: {summary['total_pageviews']}")
    print(f"  ✓ Bounce Rate: {summary['avg_bounce_rate']}%")
    print(f"  ✓ Session Duration: {summary['avg_session_duration']}s")
except Exception as e:
    print(f"❌ Traffic Summary Fehler: {e}")
    sys.exit(1)

# Test: Top Pages abrufen
try:
    print("\n📄 Teste Top Pages...")
    pages = analytics.get_top_pages(7)
    print(f"  ✓ {len(pages)} Seiten gefunden")
    for i, p in enumerate(pages[:3]):
        print(f"    {i+1}. {p['page']} ({p['pageviews']} Aufrufe)")
except Exception as e:
    print(f"❌ Top Pages Fehler: {e}")
    sys.exit(1)

# Test: Traffic Sources abrufen
try:
    print("\n🔗 Teste Traffic Sources...")
    sources = analytics.get_traffic_sources(7)
    print(f"  ✓ {len(sources)} Quellen gefunden")
    for s in sources:
        print(f"    - {s['channel']}: {s['users']} Users")
except Exception as e:
    print(f"❌ Traffic Sources Fehler: {e}")
    sys.exit(1)

print("\n" + "="*50)
print("✅ ALLE TESTS BESTANDEN!")
print("Analytics ist konfiguriert und funktioniert.")
print("="*50)
