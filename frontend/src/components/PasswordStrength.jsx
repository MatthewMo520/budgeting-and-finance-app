import { useEffect, useState } from "react"

const LABELS = ["Very weak", "Weak", "Okay", "Good", "Strong"]
const COLORS = ["var(--red)", "var(--red)", "var(--amber)", "var(--green)", "var(--green)"]

// Live zxcvbn strength meter matching the server's threshold (score ≥ 2).
// The library is heavy, so it's lazy-loaded only when a password field is used.
export function usePasswordStrength(password, userInputs = []) {
  const [result, setResult] = useState(null)
  useEffect(() => {
    if (!password) { setResult(null); return }
    let active = true
    import("zxcvbn").then(({ default: zxcvbn }) => {
      if (active) setResult(zxcvbn(password, userInputs.filter(Boolean)))
    }).catch(() => { /* meter is progressive enhancement; server still validates */ })
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [password, ...userInputs])
  return result
}

export default function PasswordStrength({ strength }) {
  if (!strength) return null
  const { score, feedback } = strength
  const hint = score < 2
    ? (feedback?.suggestions?.[0] || "Try a longer passphrase — a few random words work well.")
    : null
  return (
    <div style={{ marginTop: 8 }} aria-live="polite">
      <div style={{ display: "flex", gap: 4 }}>
        {[0, 1, 2, 3].map(i => (
          <div key={i} style={{
            flex: 1, height: 4, borderRadius: 99,
            background: i < score ? COLORS[score] : "var(--track)",
            transition: "background .2s",
          }} />
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 5, fontSize: 12 }}>
        <span style={{ color: COLORS[score], fontWeight: 600 }}>{LABELS[score]}</span>
        {hint && <span style={{ color: "var(--text2)", textAlign: "right", marginLeft: 12 }}>{hint}</span>}
      </div>
    </div>
  )
}
