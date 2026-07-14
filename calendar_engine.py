# -*- coding: utf-8 -*-
"""
Google Calendar Engine für SIGGI
Liest und erstellt Termine im Google Kalender von Stefan Mutter
"""
import os
import json
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'google_credentials.json')
TOKEN_PATH = os.path.join(BASE_DIR, 'google_token.json')
SCOPES = ['https://www.googleapis.com/auth/calendar']


def get_calendar_service():
    """Gibt einen autorisierten Google Calendar Service zurück."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None

        if os.path.exists(TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_PATH, 'w') as f:
                    f.write(creds.to_json())
            else:
                # Kein Token — google_auth.py einmalig manuell ausführen
                print("[Calendar] Kein Token vorhanden — bitte python google_auth.py ausführen")
                return None

        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"[Calendar] Fehler beim Verbinden: {e}")
        return None


def get_todays_events():
    """Gibt die heutigen Kalendertermine zurück."""
    try:
        service = get_calendar_service()
        if not service:
            return []

        now = datetime.utcnow()
        start = now.replace(hour=0, minute=0, second=0).isoformat() + 'Z'
        end = now.replace(hour=23, minute=59, second=59).isoformat() + 'Z'

        result = service.events().list(
            calendarId='primary',
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        return result.get('items', [])
    except Exception as e:
        print(f"[Calendar] Fehler beim Abrufen: {e}")
        return []


def get_upcoming_events(days=3):
    """Gibt Termine der nächsten X Tage zurück."""
    try:
        service = get_calendar_service()
        if not service:
            return []

        now = datetime.utcnow()
        end = now + timedelta(days=days)

        result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            timeMax=end.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime',
            maxResults=10
        ).execute()

        return result.get('items', [])
    except Exception as e:
        print(f"[Calendar] Fehler: {e}")
        return []


def create_event(title, start_dt, end_dt=None, description=''):
    """Erstellt einen neuen Kalendereintrag."""
    try:
        service = get_calendar_service()
        if not service:
            return None

        if end_dt is None:
            end_dt = start_dt + timedelta(hours=1)

        event = {
            'summary': title,
            'description': description,
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Europe/Berlin'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Europe/Berlin'},
        }
        created = service.events().insert(calendarId='primary', body=event).execute()
        print(f"[Calendar] Termin erstellt: {title}")
        return created
    except Exception as e:
        print(f"[Calendar] Fehler beim Erstellen: {e}")
        return None


def format_event(event):
    """Formatiert einen Termin für die Anzeige."""
    title = event.get('summary', 'Kein Titel')
    start = event.get('start', {})
    if 'dateTime' in start:
        dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
        time_str = dt.strftime('%H:%M')
    else:
        time_str = 'Ganztags'
    return f"{time_str} Uhr — {title}"


def get_calendar_context():
    """Gibt Kalender-Info als Text für SIGGIs System-Prompt zurück."""
    try:
        events = get_upcoming_events(days=3)
        if not events:
            return 'GOOGLE KALENDER: Keine Termine in den nächsten 3 Tagen.'

        today = datetime.now().date()
        lines = ['GOOGLE KALENDER (nächste 3 Tage):']
        for ev in events:
            start = ev.get('start', {})
            if 'dateTime' in start:
                dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                day = dt.date()
                if day == today:
                    label = 'Heute'
                elif day == today + timedelta(days=1):
                    label = 'Morgen'
                else:
                    label = dt.strftime('%A %d.%m.')
                lines.append(f"  {label} {dt.strftime('%H:%M')} — {ev.get('summary', 'Kein Titel')}")
            else:
                lines.append(f"  Ganztags — {ev.get('summary', 'Kein Titel')}")

        return '\n'.join(lines)
    except Exception as e:
        return f'GOOGLE KALENDER: Nicht verfügbar ({e})'
