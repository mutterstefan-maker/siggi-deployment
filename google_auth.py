# -*- coding: utf-8 -*-
"""
Einmalige Google Calendar Autorisierung.
Dieses Skript einmal ausfuehren — danach laeuft alles automatisch.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'google_credentials.json')
TOKEN_PATH = os.path.join(BASE_DIR, 'google_token.json')
SCOPES = ['https://www.googleapis.com/auth/calendar']

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

print("Google Calendar Autorisierung wird gestartet...")
print("Ein Browser-Fenster oeffnet sich gleich — bitte mit Google-Account anmelden.\n")

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
creds = flow.run_local_server(port=0)

with open(TOKEN_PATH, 'w') as f:
    f.write(creds.to_json())

print("\nErfolgreich! google_token.json wurde gespeichert.")
print("SIGGI kennt ab jetzt deinen Kalender.")

# Kurzer Test
service = build('calendar', 'v3', credentials=creds)
events = service.events().list(
    calendarId='primary',
    maxResults=3,
    singleEvents=True,
    orderBy='startTime'
).execute().get('items', [])

print(f"\nVerbindung OK — {len(events)} naechste Termine gefunden:")
for e in events:
    print(f"  - {e.get('summary', 'Kein Titel')}")

input("\nEnter druecken zum Beenden...")
