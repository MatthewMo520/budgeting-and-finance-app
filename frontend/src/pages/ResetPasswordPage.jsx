import { useState } from "react"
import { useSearchParams, Link } from "react-router-dom"
import { AuthShell } from "./RegisterPage"
import PasswordStrength, { usePasswordStrength } from "../components/PasswordStrength"

const apiBase = import.meta.env.VITE_API_URL || "/api"

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get("token")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState("")
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)
  const strength = usePasswordStrength(password)
  const tooWeak = strength !== null && strength.score < 2

  async function handleSubmit(e) {
    e.preventDefault()
    setError("")
    if (password !== confirm) { setError("Passwords do not match"); return }
    if (password.length < 8) { setError("Password must be at least 8 characters"); return }
    if (tooWeak) { setError("Password is too weak — see the suggestion below the field"); return }
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Reset failed")
      setDone(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <AuthShell>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>❌</div>
          <div className="auth-h" style={{ marginBottom: 8 }}>Invalid link</div>
          <p style={{ color: "var(--text2)", fontSize: 14, marginBottom: 24 }}>This reset link is missing or malformed.</p>
          <Link to="/forgot-password" style={{ color: "var(--green-dark)", fontWeight: 600, fontSize: 14 }}>Request a new one</Link>
        </div>
      </AuthShell>
    )
  }

  if (done) {
    return (
      <AuthShell>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>✅</div>
          <div className="auth-h" style={{ marginBottom: 8 }}>Password updated</div>
          <p style={{ color: "var(--text2)", fontSize: 14, marginBottom: 24 }}>You can now sign in with your new password.</p>
          <Link to="/login" className="btn-primary" style={{ display: "inline-block", textDecoration: "none", textAlign: "center", padding: "11px 28px", width: "auto" }}>
            Sign in
          </Link>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <div className="auth-h">Set new password</div>
      <div className="auth-sub">Choose a strong password for your account.</div>
      {error && <div className="auth-error">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label>New password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="At least 8 characters" required />
          <PasswordStrength strength={strength} />
        </div>
        <div className="field">
          <label>Confirm password</label>
          <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="••••••••" required />
        </div>
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Updating…" : "Set new password"}
        </button>
      </form>
    </AuthShell>
  )
}
