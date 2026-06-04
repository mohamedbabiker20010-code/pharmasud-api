# PharmaSUD
## Pharmacy Point of Sale System

**Stage 1 - Version 1.0.0**

---

## Project Overview

PharmaSUD is a pharmacy management system built for Sudanese pharmacies with:
- FEFO (First Expired First Out) inventory tracking
- Multi-unit support (box/strip/tablet)
- Offline-first architecture with sync
- RTL Arabic interface
- Mobile-first responsive design

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.8+ + FastAPI |
| Database | PostgreSQL 13+ |
| ORM | SQLAlchemy 2.0 |
| Frontend | HTML5 + Tailwind CSS + Alpine.js |
| Offline DB | Dexie.js (IndexedDB) |
| Hosting | Railway |

---

## Project Structure

```
pharmasud/
├── main.py              # FastAPI application entry point
├── database.py          # PostgreSQL connection & session management
├── models.py            # SQLAlchemy models (7 tables)
├── schema.sql           # Database schema & indexes
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (not in git)
└── README.md           # This file
```

---

## Database Schema (7 Tables)

1. **pharmacies** - Pharmacy accounts with product key activation
2. **users** - Admin & employee user accounts
3. **medicines** - Medicine master data
4. **units** - Unit conversions (box/strip/tablet)
5. **batches** - FEFO batch tracking with expiry dates
6. **sales** - Sale transactions
7. **sale_items** - Sale line items with batch tracking

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API status check |
| `/health` | GET | Database health check |
| `/api/test-db` | GET | Table row counts |
| `/dashboard` | GET | Main dashboard HTML page |

---

## Quick Start (Local Development)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup PostgreSQL

```bash
# Create database
sudo -u postgres psql -c "CREATE DATABASE pharmasud;"

# Run schema
psql -U postgres -d pharmasud -f schema.sql
```

### 3. Configure Environment

```bash
# Copy and edit environment file
cp .env .env.local
# Edit .env.local with your database URL
```

### 4. Run Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open Browser

- Dashboard: http://localhost:8000/dashboard
- API Docs: http://localhost:8000/docs

---

## Deployment (Railway)

### 1. Create Project
- Go to https://railway.app
- New Project → Deploy from GitHub repo

### 2. Add PostgreSQL
- New → Database → Add PostgreSQL

### 3. Deploy
- Railway auto-detects Python/FastAPI
- Environment variables auto-configured

### 4. Get Domain
- Railway provides URL like: `https://pharmasud-production.up.railway.app`

---

## Security Checklist

- [x] SQL injection protection via SQLAlchemy ORM
- [x] Password hashing with bcrypt (prepared)
- [x] JWT authentication (prepared)
- [x] CORS configured
- [ ] Change SECRET_KEY in production
- [ ] Restrict CORS origins in production
- [ ] Enable HTTPS only
- [ ] Add rate limiting

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `SECRET_KEY` | JWT signing key | Change in prod! |
| `ENVIRONMENT` | development/production | development |
| `DEBUG` | Enable debug mode | true |

---

## Stage 1 Complete ✓

- [x] FastAPI structure
- [x] 7 database tables
- [x] Health check endpoints
- [x] Dashboard HTML page
- [x] Arabic RTL interface

---

## Next: Stage 2

- Authentication system
- Medicine CRUD API
- Batch management
- POS interface

---

## License

Private - All rights reserved

---

**END - README.md - Stage 1**
