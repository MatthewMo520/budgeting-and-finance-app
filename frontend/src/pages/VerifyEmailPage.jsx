import { useEffect, useState } from "react"
import { useSearchParams, Link } from "react-router-dom"
import { AuthShell } from "./RegisterPage"

const apiBase = import.meta.env.VITE_API_URL || "/api"

export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = params.get("token")
  const [status, setStatus] = useState("loading")
  const [message, setMessage] = useState("")

  useEffect(() => {
    if (!token) { setStatus("error"); setMessage("Missing verification token."); return }
    fetch(`${apiBase}/auth/verify-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    })
      .then(r => r.json().then(d => ({ ok: r.ok, data: d })))
      .then(({ ok, data }) => {
        if (ok) setStatus("success")
        else { setStatus("error"); setMessage(data.detail || "Verification failed.") }
      })
      .catch(() => { setStatus("error"); setMessage("Network error. Please try again.") })
  }, [token])

  return (
    <AuthShell>
      {status === "loading" && (
        <p style={{ color: "var(--text2)", fontSize: 14, textAlign: "center" }}>Verifying your email…</p>
      )}
      {status === "success" && (
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>✅</div>
          <div className="auth-h" style={{ marginBottom: 8 }}>Email verified</div>
          <p style={{ color: "var(--text2)", fontSize: 14, marginBottom: 24 }}>Your account is active. You can now sign in.</p>
          <Link to="/login" className="btn-primary" style={{ display: "inline-block", textDecoration: "none", textAlign: "center", padding: "11px 28px", width: "auto" }}>
            Sign in
          </Link>
        </div>
      )}
      {status === "error" && (
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>❌</div>
          <div className="auth-h" style={{ marginBottom: 8 }}>Verification failed</div>
          <p style={{ color: "var(--text2)", fontSize: 14, marginBottom: 24 }}>{message}</p>
          <Link to="/login" style={{ color: "var(--green-dark)", fontWeight: 600, fontSize: 14 }}>Back to login</Link>
        </div>
      )}
    </AuthShell>
  )
}
