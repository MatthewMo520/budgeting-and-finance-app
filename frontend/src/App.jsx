import { useEffect, useState, useCallback, useRef } from "react"
import { Routes, Route, Navigate, useNavigate } from "react-router-dom"
import { useAuth } from "./AuthContext"
import { displayCat } from "./categories.jsx"
import MetricCards from "./components/MetricCards"
import TrendChart from "./components/TrendChart"
import TransactionList from "./components/TransactionList"
import Budgets from "./components/Budgets"
import Recurring from "./components/Recurring"
import SpendingChart from "./components/SpendingChart"
import AnomalyAlert from "./components/AnomalyAlert"
import PlaidLinkButton from "./components/PlaidLinkButton"
import LoginPage from "./pages/LoginPage"
import RegisterPage from "./pages/RegisterPage"
import VerifyEmailPage from "./pages/VerifyEmailPage"
import TOTPSetupPage from "./pages/TOTPSetupPage"
import ForgotPasswordPage from "./pages/ForgotPasswordPage"
import ResetPasswordPage from "./pages/ResetPasswordPage"
import SettingsPage from "./pages/SettingsPage"

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/setup-2fa" element={<PrivateRoute require2FA={false}><TOTPSetupPage /></PrivateRoute>} />
      <Route path="/settings" element={<PrivateRoute><SettingsPage /></PrivateRoute>} />
      <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
    </Routes>
  )
}

function PrivateRoute({ children, require2FA = true }) {
  const { accessToken, user, loading } = useAuth()
  if (loading) return <Spinner />
  if (!accessToken) return <Navigate to="/login" replace />
  if (require2FA && user && !user.totp_enabled && !user.is_demo) return <Navigate to="/setup-2fa" replace />
  return children
}

function Spinner() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text2)" }}>
      Loading…
    </div>
  )
}

function Header({ user, months, selectedMonth, onMonth, onLogout, onSetup2FA, onConnectBank, onSync, syncing, onSettings }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    function handleClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false)
    }
    document.addEventListener("click", handleClick)
    return () => document.removeEventListener("click", handleClick)
  }, [])

  const displayName = user?.username || user?.email?.split("@")[0] || "U"
  const initial = displayName[0].toUpperCase()

  return (
    <header className="hdr">
      <div className="hdr-logo">
        <div className="hdr-logomark">F</div>
        <span className="hdr-logotext">Fintrack</span>
      </div>

      <div className="hdr-months">
        {months.map(m => (
          <button
            key={m}
            className={`hdr-mtab ${m === selectedMonth ? "active" : ""}`}
            onClick={() => onMonth(m)}
          >
            {formatMonth(m)}
          </button>
        ))}
      </div>

      <div className="hdr-right">
        {(months.length > 0 || user?.has_bank) && (
          <button className="hdr-connect" onClick={onSync} disabled={syncing}>
            {syncing ? "Syncing…" : "↻ Sync"}
          </button>
        )}
        <PlaidLinkButton onSuccess={onConnectBank} className="hdr-connect" label="+ Connect bank" />

        <div style={{ position: "relative" }} ref={menuRef}>
          <button className="hdr-userbtn" onClick={e => { e.stopPropagation(); setMenuOpen(v => !v) }}>
            {user?.profile_picture
              ? <img src={user.profile_picture} alt="" style={{ width: 24, height: 24, borderRadius: "50%", objectFit: "cover" }} />
              : <div className="hdr-avatar">{initial}</div>
            }
            {displayName}
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
          {menuOpen && (
            <div className="hdr-menu">
              <div className="hdr-menuinfo">
                <div className="email">{user?.email}</div>
              </div>
              <button className="hdr-menuitem" onClick={() => { setMenuOpen(false); onSettings() }}>
                Settings
              </button>
              {!user?.totp_enabled && (
                <button className="hdr-menuitem" onClick={() => { setMenuOpen(false); onSetup2FA() }}>
                  Enable 2FA
                </button>
              )}
              <div className="hdr-divider" />
              <button className="hdr-menuitem red" onClick={onLogout}>Sign out</button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

function Dashboard() {
  const { user, logout, apiFetch } = useAuth()
  const navigate = useNavigate()

  const [months, setMonths] = useState([])
  const [summary, setSummary] = useState([])
  const [selectedMonth, setSelectedMonth] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [prevTransactions, setPrevTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [synced, setSynced] = useState(null)
  const [dashKey, setDashKey] = useState(0)

  const loadSummary = useCallback(() => {
    apiFetch("/transactions/summary")
      .then(r => r.json())
      .then(data => setSummary(Array.isArray(data) ? data : []))
      .catch(() => setSummary([]))
  }, [apiFetch])

  const loadMonths = useCallback(() => {
    apiFetch("/transactions/months")
      .then(r => r.json())
      .then(data => {
        setMonths(data)
        if (data.length > 0) {
          setSelectedMonth(prev => prev && data.includes(prev) ? prev : data[0])
        } else {
          setLoading(false)
        }
      })
  }, [apiFetch])

  const loadTransactions = useCallback((month) => {
    if (!month) return
    setLoading(true)
    apiFetch(`/transactions?month=${month}`)
      .then(r => r.json())
      .then(data => {
        setTransactions(data)
        setLoading(false)
      })
  }, [apiFetch])

  const loadPrevTransactions = useCallback((month, allMonths) => {
    const idx = allMonths.indexOf(month)
    if (idx < 0 || idx + 1 >= allMonths.length) { setPrevTransactions([]); return }
    const prev = allMonths[idx + 1]
    apiFetch(`/transactions?month=${prev}`)
      .then(r => r.json())
      .then(data => setPrevTransactions(data))
      .catch(() => setPrevTransactions([]))
  }, [apiFetch])

  useEffect(() => { loadMonths(); loadSummary() }, [loadMonths, loadSummary])

  useEffect(() => {
    if (selectedMonth) {
      loadTransactions(selectedMonth)
      loadPrevTransactions(selectedMonth, months)
      setDashKey(k => k + 1)
    }
  }, [selectedMonth])

  function handleBankLinked(count) {
    setSynced({ count })
    loadMonths()
    loadSummary()
  }

  async function handleSync() {
    setSyncing(true)
    try {
      const res = await apiFetch("/plaid/sync", { method: "POST" })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setSynced({ error: data.detail || "Sync failed. Please try again." })
      } else {
        setSynced({ count: data.transactions_synced })
        if (data.transactions_synced > 0) { loadMonths(); loadSummary() }
      }
    } catch {
      setSynced({ error: "Sync failed. Please try again." })
    } finally {
      setSyncing(false)
    }
  }

  function switchMonth(m) {
    setSelectedMonth(m)
  }

  async function handleExportCsv() {
    try {
      const res = await apiFetch(`/transactions/export?month=${selectedMonth}`)
      if (!res.ok) return
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `transactions-${selectedMonth}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch { /* ignore */ }
  }

  async function handleEditCategory(txnId, displayName) {
    try {
      const res = await apiFetch(`/transactions/${txnId}/category`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: displayName }),
      })
      if (res.ok) loadTransactions(selectedMonth)
    } catch { /* ignore */ }
  }

  const anomalies = transactions.filter(t => t.is_anomaly)
  // Plaid: positive amount = money out (spend). Only outflows count toward spending.
  const totalSpend = transactions.reduce((s, t) => s + (t.amount > 0 ? t.amount : 0), 0)
  const prevSpend = prevTransactions.reduce((s, t) => s + (t.amount > 0 ? t.amount : 0), 0)

  const categoryTotals = transactions.reduce((acc, t) => {
    if (t.amount <= 0) return acc  // skip income / transfers-in
    const cat = displayCat(t.ml_category)
    acc[cat] = (acc[cat] || 0) + t.amount
    return acc
  }, {})
  const topCategory = Object.entries(categoryTotals).sort((a, b) => b[1] - a[1])[0]

  return (
    <>
      <Header
        user={user}
        months={months}
        selectedMonth={selectedMonth}
        onMonth={switchMonth}
        onLogout={logout}
        onSetup2FA={() => navigate("/setup-2fa")}
        onConnectBank={handleBankLinked}
        onSync={handleSync}
        syncing={syncing}
        onSettings={() => navigate("/settings")}
      />

      {months.length === 0 && !loading ? (
        <div className="dash">
          <div className="empty-state">
            <div className="empty-icon">🏦</div>
            {user?.has_bank ? (
              <>
                <h2 className="empty-h">Preparing your transactions…</h2>
                <p className="empty-sub">
                  Your bank is connected. Banks can take a minute or two to make your transaction history available — hit Sync to check.
                </p>
                <button className="btn-primary" onClick={handleSync} disabled={syncing} style={{ width: "auto", display: "inline-block", padding: "11px 28px" }}>
                  {syncing ? "Syncing…" : "↻ Sync now"}
                </button>
                {synced?.error && <p style={{ color: "#dc2626", marginTop: 14, fontSize: 14 }}>{synced.error}</p>}
                {synced && !synced.error && synced.count === 0 && <p style={{ color: "var(--text2)", marginTop: 14, fontSize: 14 }}>Still preparing — try again in a moment.</p>}
              </>
            ) : (
              <>
                <h2 className="empty-h">Connect your bank</h2>
                <p className="empty-sub">
                  Link your bank account to start tracking transactions, spotting anomalies, and understanding your spending.
                </p>
                <PlaidLinkButton onSuccess={handleBankLinked} className="btn-primary" label="Connect bank account" style={{ width: "auto", display: "inline-block", padding: "11px 28px" }} />
              </>
            )}
          </div>
        </div>
      ) : (
        <div key={dashKey} className="dash fadein">
          {synced !== null && (
            <div className="sync-banner" style={synced.error ? { background: "#fef2f2", borderColor: "#fecaca", color: "#dc2626" } : undefined}>
              <span>
                {synced.error
                  ? `⚠ ${synced.error}`
                  : synced.count > 0
                    ? `✓ Synced ${synced.count} new transaction${synced.count === 1 ? "" : "s"}. Categorizing in the background…`
                    : "✓ You're up to date — no new transactions."}
              </span>
              <button className="sync-dismiss" onClick={() => setSynced(null)}>Dismiss</button>
            </div>
          )}
          {loading ? (
            <div style={{ textAlign: "center", color: "var(--text2)", fontSize: 14, padding: "48px 0" }}>
              Loading transactions…
            </div>
          ) : transactions.length === 0 ? (
            <div style={{ textAlign: "center", color: "var(--text2)", fontSize: 14, padding: "48px 0" }}>
              No transactions for {formatMonth(selectedMonth)}.
            </div>
          ) : (
            <>
              <AnomalyAlert anomalies={anomalies} allTransactions={transactions} />
              <MetricCards
                totalSpend={totalSpend}
                prevSpend={prevSpend}
                transactionCount={transactions.length}
                prevCount={prevTransactions.length}
                anomalyCount={anomalies.length}
                topCategory={topCategory}
              />
              <TrendChart summary={summary} selectedMonth={selectedMonth} onMonth={switchMonth} />
              <SpendingChart categoryTotals={categoryTotals} totalSpend={totalSpend} />
              <Budgets categoryTotals={categoryTotals} />
              <Recurring />
              <TransactionList transactions={transactions} onEditCategory={handleEditCategory} onExport={handleExportCsv} />
            </>
          )}
        </div>
      )}
    </>
  )
}

function formatMonth(ym) {
  if (!ym) return ""
  const [year, month] = ym.split("-")
  return new Date(year, month - 1).toLocaleDateString("en-US", { month: "short", year: "numeric" })
}
