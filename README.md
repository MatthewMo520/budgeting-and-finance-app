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
- Shows **live account balances** per linked bank and tracks **net worth over time**; supports **multiple linked banks** per user (connect/disconnect); transactions stay current via Plaid's **cursor-based sync API** + webhooks (handles corrections and removals, not just new rows)
- Pulls full transaction history with **merchant names and logos**, and categorizes each transaction — with **manual category override** that the model learns from
- **Honest spend accounting**: credit-card payments and inter-account transfers don't count as spending (no double-counting a purchase and the payment that covers it)
- Flags anomalies per user using Isolation Forest, plus a rule-based **insights feed**: category spending spikes, newly detected subscriptions, possible duplicate charges
- **Budgets** with progress bars and **email alerts** at 90% / 100% of a limit; **recurring/subscription detection**
- Month-by-month breakdown with animated charts, a **12-month trend chart** (spending / income / net — click a bar to jump to that month), and **category drill-down** (click a chart category to filter the list)
- **Cash-flow forecast** ("on track for ~$2,400 this month" — run-rate plus upcoming recurring charges) and **savings goals** funded by your real net cash flow
- A **month-end email recap** (total spend, top categories, anomalies, insights) sent automatically on the 1st
- **Daily-spend calendar heatmap**, keyboard shortcuts (← → months, / to search), **transaction search**, and one-click **CSV export**
- JWT auth with email verification and mandatory 2FA — **authenticator app or emailed codes**, user's choice
- **Dark mode** (light / dark / system, persisted) and a mobile-friendly layout that installs as a **PWA**

## ML layer

- **Anomaly detection (unsupervised):** `IsolationForest`, fit **per user** on a 3-feature matrix — absolute amount, amount relative to its category's average, and day-of-month — so "unusual" is relative to that person's own patterns (a big-but-normal Rent charge isn't flagged, an oversized Dining charge is). Plaid doesn't provide this.
- **Categorization (layered):** a precedence chain — high-precision **keyword rules** (bank-statement patterns like payroll → Income, card payment → Loan) → **Plaid's `personal_finance_category`** → a **TF-IDF (char n-grams) + Random Forest** classifier as the ML fallback. Char n-grams let the model generalize to dirty/unseen names (e.g. `McDonald's` matches a `McDonalds` example). The categorizer is trained once and cached in memory.

## Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL 15
- **ML:** scikit-learn (TF-IDF + Random Forest categorizer, Isolation Forest anomaly detector)
- **Bank data:** Plaid API (per-user sandbox/production routing)
- **Frontend:** React + Vite + Tailwind CSS
- **Auth:** JWT (access in memory, refresh in an httpOnly cookie) + bcrypt + 2FA via TOTP (pyotp) or email codes + SendGrid
- **Deploy:** Railway

## Security

- Access token in memory, refresh token in an `httpOnly` cookie (no JWTs in `localStorage`)
- JWT revocation via a per-user `token_version`; password change/reset revokes existing sessions
- Plaid access tokens encrypted at rest (Fernet); email-verification / password-reset tokens and email 2FA codes stored as SHA-256 hashes; TOTP secrets encrypted
- Email 2FA codes expire after 10 minutes with a 5-attempt cap; verification links expire after 24h
- Re-authentication required to disable 2FA or delete an account; the TOTP secret can't be re-generated while 2FA is on
- Deleting an account revokes the linked Plaid items, so bank connections don't stay live
- Redis-backed rate limiting (proxy-aware), security headers (incl. HSTS), CORS allow-list, timing-safe login, zxcvbn password strength

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
PLAID_WEBHOOK_URL=          # https://<backend>/plaid/webhook — enables transaction auto-sync
PLAID_TOKEN_ENC_KEY=        # Fernet key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DATABASE_URL=postgresql://financeuser:financepass@db:5432/financedb
JWT_SECRET_KEY=             # openssl rand -hex 32 (required — app won't start without it)
SENDGRID_API_KEY=
FROM_EMAIL=
FRONTEND_URL=http://localhost:5173
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
COOKIE_SECURE=false         # true in prod (https)
COOKIE_SAMESITE=lax         # none in prod if frontend/backend are different domains
REDIS_URL=                  # rate-limit store (optional locally; set in prod)
DEMO_EMAIL=                 # optional — shared demo account (auto-provisioned on startup)
DEMO_PASSWORD=
```

## Tests

Unit tests (pure logic: categorization, recurring detection, insights, forecast, auth helpers) plus a full **API integration suite** — register→verify→login→2FA, transaction scoping, spend accounting, and the mocked Plaid sync engine — run against a throwaway Postgres database:

```bash
docker compose up db -d                            # integration tests need Postgres
cd backend && JWT_SECRET_KEY=test pytest -q tests/  # integration auto-skips if the DB is down
```

CI (GitHub Actions) runs everything against a `postgres:15` service container, plus a frontend build, on every push/PR.

## Sandbox testing

Use Plaid's sandbox credentials when prompted by the Link widget:
- Username: `user_good`
- Password: `pass_good`
- Institution: mock Chase (`ins_109508`)
