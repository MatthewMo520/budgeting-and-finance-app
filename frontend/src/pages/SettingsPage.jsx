import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../AuthContext"

function Section({ title, children }) {
  return (
    <div style={{ background: "var(--surface)", borderRadius: "var(--r)", boxShadow: "var(--shadow)", padding: "28px 32px", marginBottom: 18 }}>
      <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: "-.2px", marginBottom: 20, paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>{title}</div>
      {children}
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
    </div>
  )
}

export default function SettingsPage() {
  const { user, apiFetch, refreshUser, logout, saveTokens } = useAuth()
  const navigate = useNavigate()

  const [profileForm, setProfileForm] = useState({ username: user?.username || "" })
  const [profileStatus, setProfileStatus] = useState(null)
  const [profileLoading, setProfileLoading] = useState(false)
  const [avatarPreview, setAvatarPreview] = useState(user?.profile_picture || null)

  async function handleProfileSave(e) {
    e.preventDefault()
    setProfileStatus(null)
    setProfileLoading(true)
    try {
      const res = await apiFetch("/auth/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: profileForm.username || null, profile_picture: avatarPreview || null }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Failed to update profile")
      await refreshUser()
      setProfileStatus({ success: "Profile updated." })
    } catch (err) {
      setProfileStatus({ error: err.message })
    } finally {
      setProfileLoading(false)
    }
  }

  function handleAvatarChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 2 * 1024 * 1024) { setProfileStatus({ error: "Image must be under 2MB" }); return }
    const reader = new FileReader()
    reader.onload = ev => setAvatarPreview(ev.target.result)
    reader.readAsDataURL(file)
  }

  const [pwForm, setPwForm] = useState({ current: "", next: "", confirm: "" })
  const [pwStatus, setPwStatus] = useState(null)
  const [pwLoading, setPwLoading] = useState(false)

  const [deleteConfirm, setDeleteConfirm] = useState("")
  const [deletePassword, setDeletePassword] = useState("")
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteStatus, setDeleteStatus] = useState(null)

  const [disablePassword, setDisablePassword] = useState("")
  const [disableLoading, setDisableLoading] = useState(false)
  const [disableStatus, setDisableStatus] = useState(null)

  const [accounts, setAccounts] = useState([])
  const [removingId, setRemovingId] = useState(null)

  async function loadAccounts() {
    try {
      const res = await apiFetch("/plaid/accounts")
      if (res.ok) setAccounts(await res.json())
    } catch { /* ignore */ }
  }
  useEffect(() => { loadAccounts() }, [])

  async function handleRemoveAccount(id) {
    setRemovingId(id)
    try {
      const res = await apiFetch(`/plaid/accounts/${id}`, { method: "DELETE" })
      if (res.ok) { await loadAccounts(); await refreshUser() }
    } finally {
      setRemovingId(null)
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault()
    setPwStatus(null)
    if (pwForm.next !== pwForm.confirm) { setPwStatus({ error: "New passwords do not match" }); return }
    setPwLoading(true)
    try {
      const res = await apiFetch("/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: pwForm.current, new_password: pwForm.next }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Failed to change password")
      // Backend rotates token_version and returns fresh tokens — adopt them so
      // this session stays logged in while other sessions are revoked.
      if (data.access_token) saveTokens(data.access_token)
      setPwStatus({ success: "Password updated. Other devices have been signed out." })
      setPwForm({ current: "", next: "", confirm: "" })
    } catch (err) {
      setPwStatus({ error: err.message })
    } finally {
      setPwLoading(false)
    }
  }

  async function handleDisable2FA(e) {
    e.preventDefault()
    setDisableLoading(true)
    setDisableStatus(null)
    try {
      const res = await apiFetch("/auth/disable-totp", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: disablePassword }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Failed to disable 2FA")
      setDisablePassword("")
      await refreshUser()
      setDisableStatus({ success: "2FA disabled. You will be asked to set it up again on next login." })
    } catch (err) {
      setDisableStatus({ error: err.message })
    } finally {
      setDisableLoading(false)
    }
  }

  async function handleDeleteAccount(e) {
    e.preventDefault()
    if (deleteConfirm !== user?.email) { setDeleteStatus({ error: "Email does not match." }); return }
    setDeleteLoading(true)
    setDeleteStatus(null)
    try {
      const res = await apiFetch("/auth/delete-account", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: deletePassword }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || "Failed to delete account")
      }
      logout()
    } catch (err) {
      setDeleteStatus({ error: err.message })
    } finally {
      setDeleteLoading(false)
    }
  }

  return (
    <>
      <header className="hdr">
        <div className="hdr-logo">
          <div className="hdr-logomark">F</div>
          <span className="hdr-logotext">Fintrack</span>
        </div>
        <div style={{ flex: 1 }} />
        <button
          onClick={() => navigate("/")}
          style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", fontSize: 13, fontWeight: 500, color: "var(--text)" }}
        >
          ← Back to dashboard
        </button>
      </header>

      <div style={{ maxWidth: 640, margin: "0 auto", padding: "32px 28px" }}>
        <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-.4px", marginBottom: 24 }}>Settings</div>

        <Section title="Profile">
          {profileStatus?.error && <div className="auth-error">{profileStatus.error}</div>}
          {profileStatus?.success && <div className="auth-success">{profileStatus.success}</div>}
          <form onSubmit={handleProfileSave}>
            <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 24 }}>
              <div style={{ position: "relative" }}>
                {avatarPreview
                  ? <img src={avatarPreview} alt="" style={{ width: 72, height: 72, borderRadius: "50%", objectFit: "cover", border: "2px solid var(--border)" }} />
                  : <div style={{ width: 72, height: 72, borderRadius: "50%", background: "var(--green-dark)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28, fontWeight: 700 }}>
                      {(user?.username?.[0] || user?.email?.[0] || "U").toUpperCase()}
                    </div>
                }
              </div>
              <div>
                <label style={{ display: "inline-block", padding: "7px 14px", borderRadius: 8, border: "1.5px solid var(--border)", background: "var(--surface)", fontSize: 13, fontWeight: 600, cursor: "pointer", color: "var(--text)" }}>
                  Upload photo
                  <input type="file" accept="image/*" onChange={handleAvatarChange} style={{ display: "none" }} />
                </label>
                {avatarPreview && (
                  <button type="button" onClick={() => setAvatarPreview(null)} style={{ marginLeft: 10, fontSize: 13, color: "#dc2626", background: "none", border: "none", cursor: "pointer" }}>
                    Remove
                  </button>
                )}
                <div style={{ fontSize: 12, color: "var(--text2)", marginTop: 6 }}>JPG, PNG or GIF · Max 2MB</div>
              </div>
            </div>
            <Field label="Username">
              <input
                type="text"
                value={profileForm.username}
                onChange={e => setProfileForm(f => ({ ...f, username: e.target.value }))}
                placeholder="e.g. matthew"
                maxLength={30}
              />
            </Field>
            <div style={{ fontSize: 13, color: "var(--text2)", marginBottom: 16 }}>Email: {user?.email}</div>
            <button type="submit" className="btn-primary" disabled={profileLoading}>
              {profileLoading ? "Saving…" : "Save profile"}
            </button>
          </form>
        </Section>

        <Section title="Change password">
          {pwStatus?.error && <div className="auth-error">{pwStatus.error}</div>}
          {pwStatus?.success && <div className="auth-success">{pwStatus.success}</div>}
          <form onSubmit={handleChangePassword}>
            <Field label="Current password">
              <input type="password" value={pwForm.current} onChange={e => setPwForm(f => ({ ...f, current: e.target.value }))} placeholder="••••••••" required />
            </Field>
            <Field label="New password">
              <input type="password" value={pwForm.next} onChange={e => setPwForm(f => ({ ...f, next: e.target.value }))} placeholder="At least 8 characters" required />
            </Field>
            <Field label="Confirm new password">
              <input type="password" value={pwForm.confirm} onChange={e => setPwForm(f => ({ ...f, confirm: e.target.value }))} placeholder="••••••••" required />
            </Field>
            <button type="submit" className="btn-primary" disabled={pwLoading} style={{ marginTop: 4 }}>
              {pwLoading ? "Updating…" : "Update password"}
            </button>
          </form>
        </Section>

        <Section title="Two-factor authentication">
          {disableStatus?.error && <div className="auth-error">{disableStatus.error}</div>}
          {disableStatus?.success && <div className="auth-success">{disableStatus.success}</div>}
          {user?.totp_enabled ? (
            <div>
              <p style={{ fontSize: 14, color: "var(--text2)", marginBottom: 16 }}>
                2FA is currently enabled. Disabling it will require you to set it up again on your next login.
              </p>
              <form onSubmit={handleDisable2FA}>
                <Field label="Confirm your password to disable 2FA">
                  <input type="password" value={disablePassword} onChange={e => setDisablePassword(e.target.value)} placeholder="••••••••" required />
                </Field>
                <button
                  type="submit"
                  disabled={disableLoading || !disablePassword}
                  style={{ padding: "9px 18px", borderRadius: 8, border: "1.5px solid #fecaca", background: "#fef2f2", color: "#dc2626", fontSize: 14, fontWeight: 600, opacity: !disablePassword ? 0.5 : 1 }}
                >
                  {disableLoading ? "Disabling…" : "Disable 2FA"}
                </button>
              </form>
            </div>
          ) : (
            <div>
              <p style={{ fontSize: 14, color: "var(--text2)", marginBottom: 16 }}>
                2FA is not enabled. Set it up to secure your account.
              </p>
              <button
                onClick={() => navigate("/setup-2fa")}
                style={{ padding: "9px 18px", borderRadius: 8, border: "1.5px solid #bbf7d0", background: "#f0fdf4", color: "var(--green-dark)", fontSize: 14, fontWeight: 600 }}
              >
                Set up 2FA
              </button>
            </div>
          )}
        </Section>

        <Section title="Linked banks">
          {accounts.length === 0 ? (
            <p style={{ fontSize: 14, color: "var(--text2)" }}>No banks connected yet. Use “+ Connect bank” on the dashboard.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {accounts.map(a => (
                <div key={a.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px", border: "1px solid var(--border)", borderRadius: 10 }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{a.institution_name}</div>
                    {a.linked_at && <div style={{ fontSize: 12, color: "var(--text2)" }}>Linked {a.linked_at.slice(0, 10)}</div>}
                  </div>
                  <button
                    onClick={() => handleRemoveAccount(a.id)}
                    disabled={removingId === a.id}
                    style={{ padding: "7px 14px", borderRadius: 8, border: "1.5px solid #fecaca", background: "#fef2f2", color: "#dc2626", fontSize: 13, fontWeight: 600 }}
                  >
                    {removingId === a.id ? "Removing…" : "Disconnect"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section title="Delete account">
          {deleteStatus?.error && <div className="auth-error">{deleteStatus.error}</div>}
          <p style={{ fontSize: 14, color: "var(--text2)", marginBottom: 16 }}>
            Permanently delete your account and all associated data. This cannot be undone.
          </p>
          <form onSubmit={handleDeleteAccount}>
            <Field label={`Type your email to confirm: ${user?.email}`}>
              <input
                type="email"
                value={deleteConfirm}
                onChange={e => setDeleteConfirm(e.target.value)}
                placeholder={user?.email}
                required
              />
            </Field>
            <Field label="Confirm your password">
              <input
                type="password"
                value={deletePassword}
                onChange={e => setDeletePassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </Field>
            <button
              type="submit"
              disabled={deleteLoading || deleteConfirm !== user?.email || !deletePassword}
              style={{ padding: "9px 18px", borderRadius: 8, border: "1.5px solid #fecaca", background: "#fef2f2", color: "#dc2626", fontSize: 14, fontWeight: 600, opacity: deleteConfirm !== user?.email ? 0.5 : 1 }}
            >
              {deleteLoading ? "Deleting…" : "Delete account"}
            </button>
          </form>
        </Section>
      </div>
    </>
  )
}
