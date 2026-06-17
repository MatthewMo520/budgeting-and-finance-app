import { useEffect, useState, useCallback, useRef } from "react"
import { Routes, Route, Navigate, useNavigate } from "react-router-dom"
import { useAuth } from "./AuthContext"
import { displayCat } from "./categories.jsx"
import MetricCards from "./components/MetricCards"
import TransactionList from "./components/TransactionList"
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
  if (require2FA && user && !user.totp_enabled) return <Navigate to="/setup-2fa" replace />
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
        {months.length > 0 && (
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
  const [selectedMonth, setSelectedMonth] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [prevTransactions, setPrevTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [synced, setSynced] = useState(null)
  const [dashKey, setDashKey] = useState(0)

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

  useEffect(() => { loadMonths() }, [loadMonths])

  useEffect(() => {
    if (selectedMonth) {
      loadTransactions(selectedMonth)
      loadPrevTransactions(selectedMonth, months)
      setDashKey(k => k + 1)
    }
  }, [selectedMonth])

  function handleBankLinked(count) {
    setSynced(count)
    loadMonths()
  }

  async function handleSync() {
    setSyncing(true)
    try {
      const res = await apiFetch("/plaid/sync", { method: "POST" })
      const data = await res.json()
      setSynced(data.transactions_synced)
      if (data.transactions_synced > 0) loadMonths()
    } finally {
      setSyncing(false)
    }
  }

  function switchMonth(m) {
    setSelectedMonth(m)
  }

  const anomalies = transactions.filter(t => t.is_anomaly)
  const totalSpend = transactions.reduce((s, t) => s + Math.abs(t.amount), 0)
  const prevSpend = prevTransactions.reduce((s, t) => s + Math.abs(t.amount), 0)

  const categoryTotals = transactions.reduce((acc, t) => {
    const cat = displayCat(t.ml_category)
    acc[cat] = (acc[cat] || 0) + Math.abs(t.amount)
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
            <h2 className="empty-h">Connect your bank</h2>
            <p className="empty-sub">
              Link your bank account to start tracking transactions, spotting anomalies, and understanding your spending.
            </p>
            <PlaidLinkButton onSuccess={handleBankLinked} className="btn-primary" label="Connect bank account" style={{ width: "auto", display: "inline-block", padding: "11px 28px" }} />
          </div>
        </div>
      ) : (
        <div key={dashKey} className="dash fadein">
          {synced !== null && (
            <div className="sync-banner">
              <span>✓ Synced {synced} transactions. Run ML to categorize them.</span>
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
                anomalyCount={anomalies.length}
                topCategory={topCategory}
              />
              <SpendingChart categoryTotals={categoryTotals} totalSpend={totalSpend} />
              <TransactionList transactions={transactions} />
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
