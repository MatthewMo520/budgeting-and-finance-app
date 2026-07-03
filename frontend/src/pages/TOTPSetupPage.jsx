import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../AuthContext"
import { AuthShell } from "./RegisterPage"

export default function TOTPSetupPage() {
  const { user, apiFetch, refreshUser } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState("app")   // "app" | "email"
  const [qrCode, setQrCode] = useState("")
  const [secret, setSecret] = useState("")
  const [code, setCode] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(null)  // "app" | "email" once enabled
  const [emailSent, setEmailSent] = useState(false)
  const [sending, setSending] = useState(false)

  // Fetch the QR only when the authenticator tab is active and TOTP isn't
  // already on (the endpoint 403s while 2FA is enabled).
  useEffect(() => {
    if (tab !== "app" || qrCode || user?.totp_enabled) return
    apiFetch("/auth/setup-totp", { method: "POST" })
      .then(async r => {
        const data = await r.json()
        if (!r.ok) throw new Error(data.detail || "Could not start 2FA setup")
        setQrCode(data.qr_code)
        setSecret(data.secret)
      })
      .catch(err => setError(err.message))
  }, [tab, qrCode, user?.totp_enabled, apiFetch])

  function switchTab(t) {
    setTab(t)
    setCode("")
    setError("")
  }

  async function sendEmailCode() {
    setSending(true)
    setError("")
    try {
      const res = await apiFetch("/auth/setup-email-otp", { method: "POST" })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Couldn't send the code")
      setEmailSent(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  async function handleConfirm(e) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      const endpoint = tab === "email" ? "/auth/confirm-email-otp" : "/auth/confirm-totp"
      const res = await apiFetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Invalid code")
      await refreshUser()
      setDone(tab)
    } catch (err) {
      setError(err.message)
      setCode("")
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <AuthShell>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>🔐</div>
          <div className="auth-h" style={{ marginBottom: 8 }}>2FA enabled</div>
          <p style={{ color: "var(--text2)", fontSize: 14, marginBottom: 24 }}>
            {done === "email"
              ? "We'll email you a 6-digit code each time you sign in."
              : "Your account is now protected with two-factor authentication."}
          </p>
          <button onClick={() => navigate("/")} className="btn-primary">Go to dashboard</button>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <div className="auth-h">Set up 2FA</div>
      <div className="auth-sub">Choose how you want to verify sign-ins.</div>

      <div className="filter-row" style={{ marginBottom: 20 }}>
        <button className={`filter-btn ${tab === "app" ? "active" : ""}`} onClick={() => switchTab("app")}>
          Authenticator app
        </button>
        <button className={`filter-btn ${tab === "email" ? "active" : ""}`} onClick={() => switchTab("email")}>
          Email codes
        </button>
      </div>

      {error && <div className="auth-error">{error}</div>}

      {tab === "app" ? (
        user?.totp_enabled ? (
          <p style={{ fontSize: 14, color: "var(--text2)" }}>
            Authenticator 2FA is already enabled on this account. Manage it in Settings.
          </p>
        ) : (
          <>
            <div className="auth-sub">
              Scan this QR code with <strong>Google Authenticator</strong> or <strong>Authy</strong>, then enter the 6-digit code.
            </div>
            {qrCode && (
              <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
                <img src={qrCode} alt="TOTP QR code" style={{ width: 180, height: 180, borderRadius: 12, border: "1px solid var(--border)" }} />
              </div>
            )}
            <details style={{ marginBottom: 20 }}>
              <summary style={{ fontSize: 13, color: "var(--text2)", cursor: "pointer" }}>Can't scan? Enter code manually</summary>
              <p style={{ marginTop: 8, fontSize: 12, fontFamily: "monospace", background: "var(--bg)", borderRadius: 6, padding: "8px 12px", wordBreak: "break-all", color: "var(--text)" }}>
                {secret}
              </p>
            </details>
            <CodeForm code={code} setCode={setCode} onSubmit={handleConfirm} loading={loading} label="Authenticator code" cta="Enable 2FA" />
          </>
        )
      ) : (
        user?.email_otp_enabled ? (
          <p style={{ fontSize: 14, color: "var(--text2)" }}>
            Email-code 2FA is already enabled on this account. Manage it in Settings.
          </p>
        ) : !emailSent ? (
          <>
            <p style={{ fontSize: 14, color: "var(--text2)", marginBottom: 20 }}>
              We'll email a 6-digit code to <strong>{user?.email}</strong> each time you sign in.
            </p>
            <button className="btn-primary" onClick={sendEmailCode} disabled={sending}>
              {sending ? "Sending…" : "Send code to my email"}
            </button>
          </>
        ) : (
          <>
            <p style={{ fontSize: 14, color: "var(--text2)", marginBottom: 16 }}>
              Enter the code we sent to <strong>{user?.email}</strong>.{" "}
              <a onClick={sendEmailCode} style={{ color: "var(--accent)", cursor: "pointer", fontWeight: 600 }}>Resend</a>
            </p>
            <CodeForm code={code} setCode={setCode} onSubmit={handleConfirm} loading={loading} label="Email code" cta="Enable email codes" />
          </>
        )
      )}
    </AuthShell>
  )
}

function CodeForm({ code, setCode, onSubmit, loading, label, cta }) {
  return (
    <form onSubmit={onSubmit}>
      <div className="field">
        <label>{label}</label>
        <input
          type="text"
          inputMode="numeric"
          pattern="[0-9]{6}"
          maxLength={6}
          value={code}
          onChange={e => setCode(e.target.value)}
          autoFocus
          required
          placeholder="000000"
          style={{ textAlign: "center", fontSize: 22, letterSpacing: 6 }}
        />
      </div>
      <button type="submit" className="btn-primary" disabled={loading || code.length !== 6}>
        {loading ? "Confirming…" : cta}
      </button>
    </form>
  )
}
