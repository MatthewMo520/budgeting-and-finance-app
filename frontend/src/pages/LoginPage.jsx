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
  const [needsVerification, setNeedsVerification] = useState(false)
  const [resendStatus, setResendStatus] = useState("")
  const [methods, setMethods] = useState(["totp"])
  const [mfaMode, setMfaMode] = useState("totp")
  const [otpStatus, setOtpStatus] = useState("")

  async function sendEmailCode(token) {
    setOtpStatus("Sending code…")
    try {
      const res = await fetch(`${apiBase}/auth/send-login-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ challenge_token: token }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Couldn't send the code")
      setOtpStatus("Code sent — check your email.")
    } catch (err) {
      setOtpStatus(err.message)
    }
  }

  function switchMfaMode(mode, token) {
    setMfaMode(mode)
    setTotpCode("")
    setError("")
    setOtpStatus("")
    if (mode === "email") sendEmailCode(token)
  }

  async function handleResendVerification() {
    setResendStatus("")
    try {
      const res = await fetch(`${apiBase}/auth/resend-verification`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Could not resend email")
      setResendStatus("Verification email sent — check your inbox.")
    } catch (err) {
      setResendStatus(err.message)
    }
  }

  async function handleLogin(e) {
    e.preventDefault()
    setError("")
    setNeedsVerification(false)
    setResendStatus("")
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        if (res.status === 403) setNeedsVerification(true)
        throw new Error(data.detail || "Login failed")
      }
      if (data.totp_required) {
        const m = data.methods || ["totp"]
        setChallengeToken(data.challenge_token)
        setMethods(m)
        setTotpRequired(true)
        if (!m.includes("totp")) {
          switchMfaMode("email", data.challenge_token)
        } else {
          setMfaMode("totp")
        }
      } else {
        await saveTokens(data.access_token)
        navigate(data.totp_enabled || data.is_demo ? "/" : "/setup-2fa")
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
      const endpoint = mfaMode === "email" ? "verify-email-otp-login" : "verify-totp-login"
      const res = await fetch(`${apiBase}/auth/${endpoint}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ challenge_token: challengeToken, code: totpCode }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Invalid code")
      await saveTokens(data.access_token)
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
        <div className="auth-sub">
          {mfaMode === "email"
            ? "Enter the 6-digit code we emailed you."
            : "Enter the 6-digit code from your authenticator app."}
        </div>
        {error && <div className="auth-error">{error}</div>}
        {mfaMode === "email" && otpStatus && (
          <div className="auth-switch" style={{ marginTop: 0, marginBottom: 14 }}>
            <span style={{ fontSize: 13, color: "var(--text2)" }}>{otpStatus}</span>
            {" "}<a onClick={() => sendEmailCode(challengeToken)}>Resend</a>
          </div>
        )}
        <form onSubmit={handleTOTP}>
          <div className="field">
            <label>{mfaMode === "email" ? "Email code" : "Authenticator code"}</label>
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
        {methods.includes("totp") && methods.includes("email") && (
          <div className="auth-switch">
            {mfaMode === "totp"
              ? <a onClick={() => switchMfaMode("email", challengeToken)}>Email me a code instead</a>
              : <a onClick={() => switchMfaMode("totp", challengeToken)}>Use my authenticator app instead</a>}
          </div>
        )}
        <div className="auth-switch">
          <a onClick={() => { setTotpRequired(false); setError(""); setOtpStatus("") }}>Back to login</a>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <div className="auth-h">Welcome back</div>
      <div className="auth-sub">Sign in to your account</div>
      {error && <div className="auth-error">{error}</div>}
      {needsVerification && (
        <div className="auth-switch" style={{ marginBottom: 14 }}>
          {resendStatus
            ? <span style={{ fontSize: 13, color: "var(--text2)" }}>{resendStatus}</span>
            : <a onClick={handleResendVerification}>Resend verification email</a>}
        </div>
      )}
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
