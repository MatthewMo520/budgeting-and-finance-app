import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import { useAuth } from "../AuthContext"
import { AuthShell } from "./RegisterPage"

const apiBase = import.meta.env.VITE_API_URL || "/api"

export default function LoginPage() {
  const navigate = useNavigate()
  const { saveTokens } = useAuth()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [totpRequired, setTotpRequired] = useState(false)
  const [challengeToken, setChallengeToken] = useState("")
  const [totpCode, setTotpCode] = useState("")

  async function handleLogin(e) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Login failed")
      if (data.totp_required) {
        setChallengeToken(data.challenge_token)
        setTotpRequired(true)
      } else {
        saveTokens(data.access_token, data.refresh_token)
        navigate(data.totp_enabled ? "/" : "/setup-2fa")
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleTOTP(e) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/auth/verify-totp-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ challenge_token: challengeToken, code: totpCode }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Invalid code")
      saveTokens(data.access_token, data.refresh_token)
      navigate("/")
    } catch (err) {
      setError(err.message)
      setTotpCode("")
    } finally {
      setLoading(false)
    }
  }

  if (totpRequired) {
    return (
      <AuthShell>
        <div className="auth-h">Two-factor auth</div>
        <div className="auth-sub">Enter the 6-digit code from your authenticator app.</div>
        {error && <div className="auth-error">{error}</div>}
        <form onSubmit={handleTOTP}>
          <div className="field">
            <label>Authenticator code</label>
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              value={totpCode}
              onChange={e => setTotpCode(e.target.value)}
              autoFocus
              required
              placeholder="000000"
              style={{ textAlign: "center", fontSize: 22, letterSpacing: 6 }}
            />
          </div>
          <button type="submit" className="btn-primary" disabled={loading || totpCode.length !== 6}>
            {loading ? "Verifying…" : "Verify"}
          </button>
        </form>
        <div className="auth-switch">
          <a onClick={() => { setTotpRequired(false); setError("") }}>Back to login</a>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <div className="auth-h">Welcome back</div>
      <div className="auth-sub">Sign in to your account</div>
      {error && <div className="auth-error">{error}</div>}
      <form onSubmit={handleLogin}>
        <div className="field">
          <label>Email address</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" required />
        </div>
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <div className="auth-switch" style={{ marginTop: 12 }}>
        <Link to="/forgot-password" style={{ color: "var(--text2)", fontSize: 13 }}>Forgot password?</Link>
      </div>
      <div className="auth-switch">
        Don't have an account? <Link to="/register">Create one</Link>
      </div>
    </AuthShell>
  )
}
