# -*- coding: utf-8 -*-
"""
Brevo (ehemals Sendinblue) Engine für SIGGI
Newsletter, Kampagnen, Kontakte, Stats und Transaktionsmails
API-Doku: https://developers.brevo.com/reference
"""
import os
import json
import requests
from datetime import datetime

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(BASE_DIR, 'settings.json')
BASE_URL     = 'https://api.brevo.com/v3'


def _load_settings():
    with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _headers():
    key = _load_settings().get('brevo_api_key', '')
    if not key:
        raise ValueError('brevo_api_key fehlt in settings.json')
    return {
        'api-key': key,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


# ──────────────────────────────────────────────
# ACCOUNT
# ──────────────────────────────────────────────

def get_account():
    """Account-Info (Name, E-Mail, Plan)."""
    r = requests.get(f'{BASE_URL}/account', headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────────
# KONTAKTLISTEN
# ──────────────────────────────────────────────

def get_lists():
    """Alle Kontaktlisten."""
    r = requests.get(f'{BASE_URL}/contacts/lists', headers=_headers(),
                     params={'limit': 50, 'offset': 0}, timeout=10)
    r.raise_for_status()
    return r.json().get('lists', [])


def get_contacts(list_id=None, limit=20):
    """Kontakte abrufen (optional nach Liste filtern)."""
    params = {'limit': limit, 'offset': 0}
    if list_id:
        url = f'{BASE_URL}/contacts/lists/{list_id}/contacts'
    else:
        url = f'{BASE_URL}/contacts'
    r = requests.get(url, headers=_headers(), params=params, timeout=10)
    r.raise_for_status()
    return r.json().get('contacts', [])


def add_contact(email, first_name='', last_name='', list_ids=None):
    """Kontakt hinzufügen."""
    body = {
        'email': email,
        'attributes': {},
        'updateEnabled': True,
    }
    if first_name:
        body['attributes']['FIRSTNAME'] = first_name
    if last_name:
        body['attributes']['LASTNAME'] = last_name
    if list_ids:
        body['listIds'] = list_ids
    r = requests.post(f'{BASE_URL}/contacts', headers=_headers(),
                      json=body, timeout=10)
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────────
# KAMPAGNEN
# ──────────────────────────────────────────────

def get_campaigns(limit=10, status='sent'):
    """
    Kampagnen abrufen.
    status: 'sent' | 'scheduled' | 'draft' | 'archive'
    """
    params = {'limit': limit, 'offset': 0}
    if status:
        params['status'] = status
    r = requests.get(f'{BASE_URL}/emailCampaigns', headers=_headers(),
                     params=params, timeout=10)
    r.raise_for_status()
    return r.json().get('campaigns', [])


def get_campaign(campaign_id):
    """Details einer Kampagne."""
    r = requests.get(f'{BASE_URL}/emailCampaigns/{campaign_id}',
                     headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def create_campaign(name, subject, sender_name, sender_email,
                    html_content, list_ids, reply_to=''):
    """
    Neue E-Mail-Kampagne erstellen (Status: Draft).
    Gibt campaign_id zurück.
    """
    body = {
        'name':        name,
        'subject':     subject,
        'sender':      {'name': sender_name, 'email': sender_email},
        'htmlContent': html_content,
        'recipients':  {'listIds': list_ids},
    }
    if reply_to:
        body['replyTo'] = reply_to
    r = requests.post(f'{BASE_URL}/emailCampaigns', headers=_headers(),
                      json=body, timeout=15)
    r.raise_for_status()
    return r.json().get('id')


def send_campaign_now(campaign_id):
    """Kampagne sofort senden."""
    r = requests.post(f'{BASE_URL}/emailCampaigns/{campaign_id}/sendNow',
                      headers=_headers(), timeout=15)
    r.raise_for_status()
    return True


def schedule_campaign(campaign_id, scheduled_at_iso):
    """Kampagne zu bestimmtem Zeitpunkt planen (ISO 8601)."""
    r = requests.put(f'{BASE_URL}/emailCampaigns/{campaign_id}',
                     headers=_headers(),
                     json={'scheduledAt': scheduled_at_iso}, timeout=10)
    r.raise_for_status()
    return True


def get_campaign_stats(campaign_id):
    """
    Detaillierte Statistiken einer Kampagne.
    Gibt dict mit delivered, opens, clicks, bounces, unsubscriptions zurück.
    """
    c = get_campaign(campaign_id)
    stats = c.get('statistics', {}).get('globalStats', {})
    return {
        'name':            c.get('name', ''),
        'subject':         c.get('subject', ''),
        'sent_at':         c.get('sentDate', ''),
        'recipients':      stats.get('uniqueClicks', 0),
        'delivered':       stats.get('delivered', 0),
        'opens':           stats.get('uniqueOpens', 0),
        'open_rate':       stats.get('openRate', 0),
        'clicks':          stats.get('uniqueClicks', 0),
        'click_rate':      stats.get('clickRate', 0),
        'bounces':         stats.get('hardBounces', 0) + stats.get('softBounces', 0),
        'unsubscriptions': stats.get('unsubscriptions', 0),
        'spam':            stats.get('spamReports', 0),
    }


# ──────────────────────────────────────────────
# TRANSAKTIONSMAILS
# ──────────────────────────────────────────────

def get_transactional_stats(days=7):
    """Aggregate Stats für Transaktionsmails."""
    from datetime import timedelta
    end   = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')
    start = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    r = requests.get(f'{BASE_URL}/smtp/statistics/aggregatedReport',
                     headers=_headers(),
                     params={'startDate': start, 'endDate': end}, timeout=10)
    r.raise_for_status()
    return r.json()


def get_recent_transactional(limit=10):
    """Letzte Transaktionsmails."""
    r = requests.get(f'{BASE_URL}/smtp/emails', headers=_headers(),
                     params={'limit': limit, 'offset': 0, 'sort': 'desc'}, timeout=10)
    r.raise_for_status()
    return r.json().get('transactionalEmails', [])


def send_transactional(to_email, to_name, subject, html_content,
                       sender_name='ChefBlick', sender_email='team@chefblick.de'):
    """Einzelne Transaktionsmail senden."""
    body = {
        'sender':      {'name': sender_name, 'email': sender_email},
        'to':          [{'email': to_email, 'name': to_name}],
        'subject':     subject,
        'htmlContent': html_content,
    }
    r = requests.post(f'{BASE_URL}/smtp/email', headers=_headers(),
                      json=body, timeout=15)
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────────
# SIGGI KONTEXT
# ──────────────────────────────────────────────

def get_brevo_context():
    """Kompakte Brevo-Zusammenfassung für SIGGIs System-Prompt."""
    try:
        # Verbindungstest
        _headers()  # wirft ValueError wenn kein Key
        lines = ['BREVO NEWSLETTER:']

        # Letzte gesendete Kampagne
        campaigns = get_campaigns(limit=3, status='sent')
        if campaigns:
            c = campaigns[0]
            stats = c.get('statistics', {}).get('globalStats', {})
            open_rate  = round(stats.get('openRate', 0), 1)
            click_rate = round(stats.get('clickRate', 0), 1)
            lines.append(
                f'  Letzte Kampagne: "{c.get("name", "?")} " | '
                f'Öffnungsrate: {open_rate}% | Klickrate: {click_rate}%'
            )
        else:
            lines.append('  Noch keine gesendeten Kampagnen.')

        # Entwürfe
        drafts = get_campaigns(limit=5, status='draft')
        if drafts:
            names = ', '.join(d.get('name', '?') for d in drafts[:3])
            lines.append(f'  Entwürfe ({len(drafts)}): {names}')

        # Kontaktlisten
        lists = get_lists()
        if lists:
            lst_info = ', '.join(
                f'{l.get("name", "?")} ({l.get("uniqueSubscribers", 0)} Abonnenten)'
                for l in lists[:4]
            )
            lines.append(f'  Listen: {lst_info}')

        # Transaktionsmails (7 Tage)
        try:
            t_stats = get_transactional_stats(7)
            delivered = t_stats.get('delivered', 0)
            bounces   = t_stats.get('hardBounces', 0) + t_stats.get('softBounces', 0)
            lines.append(f'  Transaktionsmails (7 Tage): {delivered} zugestellt, {bounces} Bounces')
        except Exception:
            pass

        return '\n'.join(lines)
    except Exception as e:
        if '401' in str(e):
            return 'BREVO: API-Schlüssel ungültig oder IP nicht freigegeben (Einstellung in Brevo → Security → Authorised IPs prüfen).'
        return f'BREVO: Temporär nicht verfügbar.'
