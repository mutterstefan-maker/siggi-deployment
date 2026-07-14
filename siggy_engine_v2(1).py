# -*- coding: utf-8 -*-
"""
SIGGY Engine v2 - Vollständiger AI-Assistant mit Dashboard-Integration
Alle Funktionen für Voice + Dashboard UI
"""

import sqlite3
import json
import os
import re
from datetime import datetime, timedelta
import requests

class SIGGYEngine:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.db_path = os.path.join(base_dir, 'mails.db')
        self.settings_path = os.path.join(base_dir, 'settings.json')
    
    def load_settings(self):
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def save_settings(self, settings):
        with open(self.settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    
    # =========== TIME & GREETINGS ===========
    def get_time_period(self):
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return 'morning', 'Morgen'
        elif 12 <= hour < 17:
            return 'afternoon', 'Mittag'
        else:
            return 'evening', 'Abend'
    
    def get_greeting(self):
        period, german = self.get_time_period()
        greetings = {
            'morning': f'Guten Morgen, Mutti! 🌅 Lass mich dir einen Überblick über deinen Tag geben.',
            'afternoon': f'Guten Mittag, Mutti! ☀️ Hier ist dein aktueller Status.',
            'evening': f'Guten Abend, Mutti! 🌙 Dein Überblick für den Feierabend.'
        }
        return greetings.get(period, 'Hallo Mutti!')
    
    # =========== EMAIL FUNCTIONS ===========
    def get_email_count(self, category=None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if category:
            c.execute("SELECT COUNT(*) FROM mails WHERE category=? AND deleted=0", (category,))
        else:
            c.execute("SELECT COUNT(*) FROM mails WHERE category NOT IN ('spam', 'sent_archive', 'knowledge_gap') AND deleted=0")
        count = c.fetchone()[0]
        conn.close()
        return count
    
    def get_spam_count(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM mails WHERE is_spam=1 AND deleted=0")
        count = c.fetchone()[0]
        conn.close()
        return count
    
    def get_recent_emails(self, limit=10):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""SELECT id, from_addr, subject, body, category, created_at FROM mails 
                     WHERE deleted=0 AND is_spam=0 AND category != 'sent_archive'
                     ORDER BY created_at DESC LIMIT ?""", (limit,))
        emails = c.fetchall()
        conn.close()
        return emails
    
    def get_emails_by_category(self):
        """Zählt Emails nach Kategorie für Dashboard"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""SELECT category, COUNT(*) FROM mails WHERE deleted=0 AND is_spam=0
                     GROUP BY category ORDER BY COUNT(*) DESC""")
        data = c.fetchall()
        conn.close()
        return [{'category': cat, 'count': cnt} for cat, cnt in data]
    
    def delete_all_spam(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE mails SET deleted=1 WHERE is_spam=1")
        deleted_count = c.rowcount
        conn.commit()
        conn.close()
        return deleted_count
    
    def get_email_summary(self):
        inbox_count = self.get_email_count('inbox')
        callback_count = self.get_email_count('callbacks')
        invoice_count = self.get_email_count('invoices')
        spam_count = self.get_spam_count()
        
        summary = f"📧 Emails: {inbox_count} neue Anfragen"
        if callback_count > 0:
            summary += f", {callback_count} Rückruf-Anfragen"
        if invoice_count > 0:
            summary += f", {invoice_count} Rechnungen"
        if spam_count > 0:
            summary += f" | ⚠️ {spam_count} Spam"
        
        return summary
    
    # =========== WEATHER ===========
    def get_weather(self):
        try:
            response = requests.get(
                'https://api.open-meteo.com/v1/forecast?latitude=48.3419&longitude=11.7461&current=temperature_2m,weather_code,is_day&timezone=Europe/Berlin',
                timeout=5
            )
            data = response.json()['current']
            temp = data['temperature_2m']
            code = data['weather_code']
            
            weather_map = {
                0: 'Klar ☀️', 1: 'Leicht bewölkt ⛅', 2: 'Bewölkt ☁️', 3: 'Übercast ☁️',
                45: 'Nebel 🌫️', 51: 'Leichter Regen 🌧️', 61: 'Regen 🌧️', 80: 'Regenschauer 🌧️', 95: 'Gewitter ⛈️'
            }
            
            desc = weather_map.get(code, 'Unbekannt')
            return {'temp': temp, 'condition': desc, 'display': f"🌤️ {temp}°C, {desc}"}
        except:
            return {'temp': 0, 'condition': 'Error', 'display': '🌤️ Wetter nicht verfügbar'}
    
    # =========== ANALYTICS ===========
    def get_analytics_summary(self):
        try:
            from analytics_engine import AnalyticsEngine
            analytics = AnalyticsEngine(
                os.path.join(self.base_dir, 'siggi-dashboard-ac0baeaaaef6.json'),
                '534389721'
            )
            return analytics.get_analytics_summary_for_prompt(7)
        except:
            return "📊 Analytics nicht verfügbar"
    
    def get_analytics_data(self):
        """Gibt Charts-Daten für Dashboard"""
        try:
            from analytics_engine import AnalyticsEngine
            analytics = AnalyticsEngine(
                os.path.join(self.base_dir, 'siggi-dashboard-ac0baeaaaef6.json'),
                '534389721'
            )
            summary = analytics.get_traffic_summary(7)
            pages = analytics.get_top_pages(7)
            sources = analytics.get_traffic_sources(7)
            
            return {
                'summary': summary,
                'top_pages': pages,
                'sources': sources,
                'chart_data': {
                    'daily': summary.get('daily', []),
                    'users': summary.get('total_users', 0),
                    'pageviews': summary.get('total_pageviews', 0)
                }
            }
        except Exception as e:
            return {'error': str(e)}
    
    # =========== INSTAGRAM/TIKTOK ===========
    def get_instagram_status(self):
        return "📷 Instagram: Verbunden"
    
    def get_tiktok_status(self):
        return "🎵 TikTok: Wartet auf Freischaltung"
    
    # =========== TODOS ===========
    def get_todos(self):
        settings = self.load_settings()
        todos = settings.get('daily_todos', [])
        if not todos:
            return "📋 Keine Todos für heute"
        return "📋 Todos:\n" + "\n".join(f"  • {t}" for t in todos)
    
    def add_todo(self, todo_text):
        settings = self.load_settings()
        if 'daily_todos' not in settings:
            settings['daily_todos'] = []
        settings['daily_todos'].append(todo_text)
        self.save_settings(settings)
        return f"✅ Todo hinzugefügt: {todo_text}"
    
    def clear_todos(self):
        settings = self.load_settings()
        settings['daily_todos'] = []
        self.save_settings(settings)
        return "✅ Alle Todos gelöscht"
    
    # =========== MORNING BRIEFING ===========
    def get_morning_briefing(self):
        briefing = self.get_greeting() + "\n\n"
        briefing += self.get_weather()['display'] + "\n"
        briefing += self.get_email_summary() + "\n"
        briefing += self.get_instagram_status() + "\n"
        briefing += self.get_tiktok_status() + "\n"
        briefing += self.get_todos() + "\n"
        briefing += self.get_analytics_summary() + "\n"
        briefing += "\n💪 Lass uns vollgas geben heute!"
        return briefing
    
    # =========== DASHBOARD DATA ===========
    def get_dashboard_data(self):
        """Alle Daten für Dashboard UI"""
        return {
            'greeting': self.get_greeting(),
            'weather': self.get_weather(),
            'emails': {
                'summary': self.get_email_summary(),
                'by_category': self.get_emails_by_category(),
                'recent': [
                    {
                        'id': e[0],
                        'from': e[1],
                        'subject': e[2][:50],
                        'category': e[4],
                        'date': e[5]
                    } for e in self.get_recent_emails(5)
                ]
            },
            'todos': self.load_settings().get('daily_todos', []),
            'analytics': self.get_analytics_data(),
            'instagram': self.get_instagram_status(),
            'tiktok': self.get_tiktok_status(),
            'spam_count': self.get_spam_count()
        }
    
    # =========== INTENT PROCESSING ===========
    def process_intent(self, text):
        text_lower = text.lower().strip()
        
        if any(phrase in text_lower for phrase in ['guten morgen', 'guten tag', 'guten mittag', 'guten abend', 'morgen siggy', 'tag siggy']):
            return {'intent': 'morning_briefing', 'action': 'briefing', 'data': self.get_morning_briefing()}
        
        if any(phrase in text_lower for phrase in ['wie viele emails', 'email count', 'wie viele mails', 'neue emails']):
            return {'intent': 'email_count', 'action': 'info', 'data': self.get_email_summary()}
        
        if 'zeig mir spam' in text_lower or 'spam count' in text_lower:
            count = self.get_spam_count()
            return {'intent': 'spam_count', 'action': 'info', 'data': f"⚠️ Du hast {count} Spam-Nachrichten"}
        
        if 'lösche spam' in text_lower or 'delete spam' in text_lower:
            deleted = self.delete_all_spam()
            return {'intent': 'delete_spam', 'action': 'delete', 'data': f"✅ {deleted} Spam-Nachrichten gelöscht"}
        
        if 'letzte emails' in text_lower or 'recent emails' in text_lower:
            emails = self.get_recent_emails(3)
            summary = "📧 Letzte Emails:\n"
            for e in emails:
                summary += f"  • Von: {e[1]}\n    Betreff: {e[2]}\n"
            return {'intent': 'recent_emails', 'action': 'info', 'data': summary}
        
        if any(phrase in text_lower for phrase in ['website performance', 'wie läuft', 'analytics', 'zugriffszahlen']):
            return {'intent': 'analytics', 'action': 'info', 'data': self.get_analytics_summary()}
        
        if 'wetter' in text_lower:
            return {'intent': 'weather', 'action': 'info', 'data': self.get_weather()['display']}
        
        if 'todos' in text_lower or 'to do' in text_lower:
            return {'intent': 'show_todos', 'action': 'info', 'data': self.get_todos()}
        
        if 'lösche todos' in text_lower:
            return {'intent': 'clear_todos', 'action': 'delete', 'data': self.clear_todos()}
        
        if 'instagram' in text_lower:
            return {'intent': 'instagram_status', 'action': 'info', 'data': self.get_instagram_status()}
        
        return {'intent': 'general_chat', 'action': 'ask_claude', 'data': text}
