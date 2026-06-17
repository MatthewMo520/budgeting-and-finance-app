import { useState } from "react"
import { Link } from "react-router-dom"
import { AuthShell } from "./RegisterPage"

const apiBase = import.meta.env.VITE_API_URL || "/api"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError("")
    try {
      const res = await fetch(`${apiBase}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      })
      if (!res.ok) throw new Error("Something went wrong")
      setSent(true)
    } catch {
      setError("Something went wrong. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <AuthShell>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>📧</div>
          <div className="auth-h" style={{ marginBottom: 8 }}>Check your email</div>
          <p style={{ color: "var(--text2)", fontSize: 14, marginBottom: 24, lineHeight: 1.6 }}>
            If <strong style={{ color: "var(--text)" }}>{email}</strong> is registered, we sent a reset link. Check your inbox.
          </p>
          <Link to="/login" style={{ color: "var(--green-dark)", fontWeight: 600, fontSize: 14 }}>Back to login</Link>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <div className="auth-h">Forgot password</div>
      <div className="auth-sub">Enter your email and we'll send you a reset link.</div>
      {error && <div className="auth-error">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label>Email address</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
          />
        </div>
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Sending…" : "Send reset link"}
        </button>
      </form>
      <div className="auth-switch">
        <Link to="/login">Back to login</Link>
      </div>
    </AuthShell>
  )
}
