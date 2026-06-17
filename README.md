# Fintrack

A personal finance dashboard that connects to real bank accounts via Plaid. Tracks spending by category, flags unusual transactions with ML, and runs everything behind proper auth.

![Stack](https://img.shields.io/badge/FastAPI-PostgreSQL-React-informational)

## What it does

- Links real bank accounts through Plaid (sandbox + development mode)
- Pulls 12 months of transaction history and auto-categorizes with a Random Forest classifier
- Flags anomalies using Isolation Forest (~15% contamination rate)
- Month-by-month spending breakdown with animated charts
- JWT auth with email verification and mandatory TOTP 2FA

## Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL 15
- **ML:** scikit-learn (TF-IDF + Random Forest for categorization, Isolation Forest for anomaly detection)
- **Bank data:** Plaid API
- **Frontend:** React + Vite + Tailwind CSS
- **Auth:** JWT + bcrypt + TOTP (pyotp) + SendGrid
- **Deploy:** Railway

## Running locally

You'll need Docker and Node 20+.

```bash
# Start Postgres + backend
docker compose up --build

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs

## Environment variables

Create a `.env` file in the root:

```
PLAID_CLIENT_ID=
PLAID_SECRET=
PLAID_ENV=sandbox
DATABASE_URL=postgresql://financeuser:financepass@db:5432/financedb
JWT_SECRET_KEY=          # openssl rand -hex 32
SENDGRID_API_KEY=
FROM_EMAIL=
FRONTEND_URL=http://localhost:5173
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

## Sandbox testing

Use Plaid's sandbox credentials when prompted by the Link widget:
- Username: `user_good`
- Password: `pass_good`
- Institution: mock Chase (`ins_109508`)
