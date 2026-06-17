import { useState } from "react"
import { Link } from "react-router-dom"

const apiBase = import.meta.env.VITE_API_URL || "/api"

export function AuthShell({ children }) {
  return (
    <div className="auth-page">
      <div className="auth-card fadein">
        <div className="auth-logorow">
          <div className="auth-logomark">F</div>
          <span className="auth-logotext">Fintrack</span>
        </div>
        {children}
      </div>
    </div>
  )
}

export default function RegisterPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState("")
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError("")
    if (password !== confirm) { setError("Passwords do not match"); return }
    if (password.length < 8) { setError("Password must be at least 8 characters"); return }
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Registration failed")
      setSuccess(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <AuthShell>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>📧</div>
          <div className="auth-h" style={{ marginBottom: 8 }}>Check your email</div>
          <p style={{ color: "var(--text2)", fontSize: 14, marginBottom: 24, lineHeight: 1.6 }}>
            We sent a verification link to <strong style={{ color: "var(--text)" }}>{email}</strong>.
          </p>
          <Link to="/login" style={{ color: "var(--green-dark)", fontWeight: 600, fontSize: 14 }}>Back to login</Link>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <div className="auth-h">Create account</div>
      <div className="auth-sub">Start tracking your finances today</div>
      {error && <div className="auth-error">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label>Email address</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="At least 8 characters" required />
        </div>
        <div className="field">
          <label>Confirm password</label>
          <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="••••••••" required />
        </div>
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Creating account…" : "Create account"}
        </button>
      </form>
      <div className="auth-switch">
        Already have an account? <Link to="/login">Sign in</Link>
      </div>
    </AuthShell>
  )
}
