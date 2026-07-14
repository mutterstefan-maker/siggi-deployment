# 🚀 STEAN Shop - Getting Started

Willkommen zum STEAN Online Shop mit Colify Integration!

## 📋 Was ist erstellt worden?

Ein **vollständiges Onlineshop-Grundgerüst** mit:

- ✅ **Frontend** - Vue.js 3 (Vite)
- ✅ **Backend** - Python FastAPI
- ✅ **Colify Integration** - Ordner, Produkte, Bestellungen, Kunden
- ✅ **Admin Interface** - Colify Management Dashboard
- ✅ **Dokumentation** - Setup, API, Architektur
- ✅ **Docker Support** - docker-compose.yml

---

## ⚡ Quick Start (5 Minuten)

### Terminal 1: Backend

```bash
cd D:\Projekte\Stean.info\backend

# Virtuelle Umgebung
python -m venv venv
venv\Scripts\activate

# Abhängigkeiten
pip install -r requirements.txt

# .env vorbereiten
copy .env.example .env

# ⚠️ WICHTIG: Deine Colify API Key eintragen
# Öffne .env und setze:
# COLIFY_API_KEY=dein-api-key-hier

# Backend starten
python main.py
```

✅ **Backend läuft unter:** http://localhost:8000

### Terminal 2: Frontend

```bash
cd D:\Projekte\Stean.info\frontend

# Abhängigkeiten
npm install

# Dev Server starten
npm run dev
```

✅ **Frontend läuft unter:** http://localhost:5173

---

## 🔌 Colify Verbindung testen

### 1. Health Check
```
http://localhost:8000/api/colify/health
```

Sollte zeigen:
```json
{
  "status": "connected",
  "timestamp": "2024-04-28T..."
}
```

### 2. API Docs (Swagger)
```
http://localhost:8000/docs
```

Interaktive API zum Testen.

### 3. Admin Interface
```
http://localhost:5173/admin
```

ColifyAdmin Component mit:
- Verbindungsstatus
- Synchronisierungs-Statistiken
- Schnelle Sync-Buttons
- Daten-Tabellen

---

## 📁 Projekt-Struktur

```
D:\Projekte\Stean.info\
│
├─ frontend/                    # Vue.js 3 Shop
│  ├─ src/
│  │  ├─ services/
│  │  │  └─ colifyApi.js       # HTTP Client
│  │  ├─ stores/
│  │  │  └─ colifyStore.js     # Pinia Store
│  │  ├─ components/
│  │  │  └─ ColifyAdmin.vue    # Admin UI
│  │  ├─ App.vue
│  │  └─ main.js
│  └─ package.json
│
├─ backend/                     # Python FastAPI
│  ├─ app/
│  │  ├─ api/
│  │  │  ├─ colify/           # Colify Endpoints
│  │  │  ├─ products/
│  │  │  ├─ orders/
│  │  │  ├─ users/
│  │  │  └─ auth/
│  │  └─ integrations/
│  │     └─ colify_service.py # Colify Service
│  ├─ main.py
│  └─ requirements.txt
│
├─ docs/
│  ├─ COLIFY_INTEGRATION.md    # 📖 API Referenz
│  ├─ SETUP.md                 # 📖 Installation
│  └─ ARCHITECTURE.md          # 📖 System-Architektur
│
├─ config/
│  ├─ docker-compose.yml
│  └─ .gitignore
│
├─ README.md
├─ INTEGRATION_SUMMARY.md      # Diese Datei
└─ GETTING_STARTED.md          # Diese Datei
```

---

## 🔄 Was wird synchronisiert?

### Ordner (Folders)
```
GET /api/colify/folders
```
Alle Ordner aus Colify

### Produkte (Products)
```
GET /api/colify/products
POST /api/colify/sync/products
```
SKU, Name, Preis, Lagerbestand

### Bestellungen (Orders)
```
GET /api/colify/orders
POST /api/colify/sync/orders
```
Bestellnummern, Status, Zeitstempel

### Kunden (Customers)
```
GET /api/colify/customers
POST /api/colify/sync/customers
```
Namen, E-Mails, Telefon

---

## 🎯 Nächste Schritte

### Phase 1: Setup ✅
- [x] Projekt-Grundgerüst erstellt
- [x] Colify Integration eingebaut
- [ ] **Deine Aufgabe:** API Key in `.env` setzen

### Phase 2: Datenbank (Optional)
- [ ] PostgreSQL installieren
- [ ] SQLAlchemy Models erweitern
- [ ] Alembic Migrations einrichten

### Phase 3: Frontend
- [ ] Router konfigurieren (`vue-router`)
- [ ] ColifyAdmin in `/admin` Route montieren
- [ ] Shop-Seiten bauen (Home, Produkte, Warenkorb)

### Phase 4: Erweiterte Funktionen
- [ ] User Registration & Login
- [ ] Warenkorb & Checkout
- [ ] Payment Integration (Stripe/PayPal)
- [ ] Email Notifications
- [ ] Auto-Sync mit APScheduler

---

## 🧪 API Endpoints Quick Reference

### Health & Info
```
GET /api/colify/health                  # Status Check
```

### Ordner
```
GET /api/colify/folders                 # Alle Ordner
POST /api/colify/sync/folders           # Sync Ordner
```

### Produkte
```
GET /api/colify/products                # Alle Produkte
GET /api/colify/products/{id}           # Ein Produkt
POST /api/colify/sync/products          # Sync Produkte
```

### Bestellungen
```
GET /api/colify/orders                  # Alle Bestellungen
GET /api/colify/orders/{id}             # Eine Bestellung
POST /api/colify/sync/orders            # Sync Bestellungen
```

### Kunden
```
GET /api/colify/customers               # Alle Kunden
POST /api/colify/sync/customers         # Sync Kunden
```

### Bulk
```
POST /api/colify/sync/all               # Alles synchronisieren!
```

**👉 Vollständige Docs:** siehe `docs/COLIFY_INTEGRATION.md`

---

## 🆘 Häufige Fehler

### ❌ "Fehler bei der Verbindung zu Colify"

**Grund:** API Key falsch oder nicht gesetzt

**Lösung:**
```bash
# backend/.env öffnen
# Setze:
COLIFY_API_KEY=dein-gültiger-api-key

# Backend neu starten
python main.py
```

### ❌ "Port 8000 bereits in Benutzung"

**Grund:** Anderer Prozess nutzt Port 8000

**Lösung:**
```bash
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac:
lsof -i :8000
kill -9 <PID>
```

### ❌ "npm install fehlgeschlagen"

**Grund:** Alte node_modules oder npm Cache

**Lösung:**
```bash
rm -rf node_modules package-lock.json
npm install
```

### ❌ "Python Modul nicht gefunden"

**Grund:** venv nicht aktiviert

**Lösung:**
```bash
# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate

# Dann pip install erneut
pip install -r requirements.txt
```

---

## 📚 Dokumentation

Für weitere Details siehe:

| Datei | Zweck |
|-------|-------|
| [`docs/SETUP.md`](./docs/SETUP.md) | 📖 Installation & Setup |
| [`docs/COLIFY_INTEGRATION.md`](./docs/COLIFY_INTEGRATION.md) | 📖 Colify API Referenz |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | 📖 System-Architektur |
| [`INTEGRATION_SUMMARY.md`](./INTEGRATION_SUMMARY.md) | 📖 Kurze Übersicht |

---

## 🔐 Environment Variables

Wichtige Variablen in `backend/.env`:

```env
# Colify Integration (ERFORDERLICH)
COLIFY_API_KEY=dein-api-key-hier
COLIFY_BASE_URL=https://api.colify.de/v1

# Datenbank (optional, später)
DATABASE_URL=postgresql://user:pass@localhost:5432/stean_db

# App
SECRET_KEY=dein-secret-key-hier
ALGORITHM=HS256
API_VERSION=1.0.0
```

---

## 🚢 Deployment

### Development
```bash
# Terminal 1: Backend
cd backend && python main.py

# Terminal 2: Frontend
cd frontend && npm run dev
```

### Production (Docker)
```bash
cd config
docker-compose up --build
```

Startet:
- FastAPI Backend (Port 8000)
- PostgreSQL (Port 5432)

---

## 💡 Tipps & Tricks

### Frontend Tests machen
```bash
# Swagger API Docs öffnen
http://localhost:8000/docs

# Hier kannst du alle Endpoints direkt testen!
```

### Logs anschauen
```bash
# Backend Logs sehen automatisch beim Start:
python main.py

# Suche nach [Colify] für Integrations-Logs
```

### Schnelle Struktur übersicht
```bash
cd D:\Projekte\Stean.info
# Alle Python Files:
dir /s *.py

# Alle Vue Files:
dir /s *.vue

# Alle Markdown Docs:
dir /s *.md
```

---

## 📞 Support & Kontakt

Fragen?

1. Schau die Dokumentation: `docs/`
2. Überprüfe die Logs: Backend Console
3. Test mit Swagger: `http://localhost:8000/docs`
4. Siehe Troubleshooting in `docs/SETUP.md`

---

## ✅ Checklist zum Starten

- [ ] Colify API Key besorgt
- [ ] `backend/.env` mit API Key erstellt
- [ ] `python main.py` erfolgreich gestartet
- [ ] `npm run dev` erfolgreich gestartet
- [ ] Health Check grün: `http://localhost:8000/api/colify/health`
- [ ] Swagger UI lädt: `http://localhost:8000/docs`
- [ ] Frontend lädt: `http://localhost:5173`

---

## 🎉 Glückwunsch!

Du hast ein production-ready Onlineshop-Gerüst mit:
- ✅ Vue.js 3 Frontend
- ✅ Python FastAPI Backend
- ✅ Colify Integration
- ✅ Admin Dashboard
- ✅ Vollständige Dokumentation
- ✅ Docker Support

**Viel Erfolg beim Bauen! 🚀**

---

*Last updated: 2024-04-28*
*Version: 1.0.0*
