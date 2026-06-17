import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../AuthContext"
import { AuthShell } from "./RegisterPage"

export default function TOTPSetupPage() {
  const { apiFetch, refreshUser } = useAuth()
  const navigate = useNavigate()
  const [qrCode, setQrCode] = useState("")
  const [secret, setSecret] = useState("")
  const [code, setCode] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    apiFetch("/auth/setup-totp", { method: "POST" })
      .then(r => r.json())
      .then(data => { setQrCode(data.qr_code); setSecret(data.secret) })
  }, [apiFetch])

  async function handleConfirm(e) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      const res = await apiFetch("/auth/confirm-totp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Invalid code")
      await refreshUser()
      setDone(true)
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
            Your account is now protected with two-factor authentication.
          </p>
          <button onClick={() => navigate("/")} className="btn-primary">Go to dashboard</button>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <div className="auth-h">Set up 2FA</div>
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

      {error && <div className="auth-error">{error}</div>}
      <form onSubmit={handleConfirm}>
        <div className="field">
          <label>Authenticator code</label>
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
          {loading ? "Confirming…" : "Enable 2FA"}
        </button>
      </form>
    </AuthShell>
  )
}
