# Fintrack

A personal finance dashboard that connects to real bank accounts via Plaid. Tracks spending by category, flags unusual transactions with ML, and runs everything behind proper auth.

![Stack](https://img.shields.io/badge/FastAPI-PostgreSQL-React-informational)

## Live demo

Try it without creating an account or linking a real bank:

- **App:** https://frontend-production-fcda.up.railway.app
- **Demo login:** `demo@fintrack.app` / `FintrackDemo123` (no 2FA)
- Click **Connect bank**, pick any bank, and use Plaid sandbox creds **`user_good`** / **`pass_good`** to load sample data.

> Use Chrome — Safari blocks the cross-site session cookie. The demo account is routed to Plaid **sandbox**; real accounts use **production**.

## What it does

- Links real bank accounts through Plaid (production), with a sandbox-routed demo account
- Pulls 12 months of transaction history and categorizes each transaction
- Flags anomalies per user using Isolation Forest (~15% contamination)
- Month-by-month spending breakdown with animated charts
- JWT auth with email verification and mandatory TOTP 2FA

## ML layer

- **Anomaly detection (unsupervised):** `IsolationForest`, fit **per user** on their own transaction amounts, so "unusual" is relative to that person's spending. Plaid doesn't provide this.
- **Categorization (layered):** a precedence chain — high-precision **keyword rules** (bank-statement patterns like payroll → Income, card payment → Loan) → **Plaid's `personal_finance_category`** → a **TF-IDF (char n-grams) + Random Forest** classifier as the ML fallback. Char n-grams let the model generalize to dirty/unseen names (e.g. `McDonald's` matches a `McDonalds` example). The categorizer is trained once and cached in memory.

## Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL 15
- **ML:** scikit-learn (TF-IDF + Random Forest categorizer, Isolation Forest anomaly detector)
- **Bank data:** Plaid API (per-user sandbox/production routing)
- **Frontend:** React + Vite + Tailwind CSS
- **Auth:** JWT (access in memory, refresh in an httpOnly cookie) + bcrypt + TOTP (pyotp) + SendGrid
- **Deploy:** Railway

## Security

- Access token in memory, refresh token in an `httpOnly` cookie (no JWTs in `localStorage`)
- JWT revocation via a per-user `token_version`; password change/reset revokes existing sessions
- Plaid access tokens encrypted at rest (Fernet); email-verification / password-reset tokens stored as SHA-256 hashes; TOTP secrets encrypted
- Re-authentication required to disable 2FA or delete an account
- Rate limiting, security headers (incl. HSTS), CORS allow-list, timing-safe login, zxcvbn password strength

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
PLAID_SECRET=                # secret for PLAID_ENV (per-environment)
PLAID_ENV=sandbox           # sandbox | production
PLAID_SANDBOX_SECRET=       # only in prod, so the demo account can use sandbox
PLAID_TOKEN_ENC_KEY=        # Fernet key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DATABASE_URL=postgresql://financeuser:financepass@db:5432/financedb
JWT_SECRET_KEY=             # openssl rand -hex 32 (required — app won't start without it)
SENDGRID_API_KEY=
FROM_EMAIL=
FRONTEND_URL=http://localhost:5173
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
COOKIE_SECURE=false         # true in prod (https)
COOKIE_SAMESITE=lax         # none in prod if frontend/backend are different domains
DEMO_EMAIL=                 # optional — shared demo account (auto-provisioned on startup)
DEMO_PASSWORD=
```

## Sandbox testing

Use Plaid's sandbox credentials when prompted by the Link widget:
- Username: `user_good`
- Password: `pass_good`
- Institution: mock Chase (`ins_109508`)
