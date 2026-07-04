import { useState, useEffect } from "react"
import { useAuth } from "../AuthContext"

const DOT = { alert: "var(--red)", warn: "var(--amber)", info: "var(--accent)" }

export default function Insights() {
  const { apiFetch } = useAuth()
  const [items, setItems] = useState([])
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    apiFetch("/insights")
      .then(r => r.ok ? r.json() : [])
      .then(data => setItems(Array.isArray(data) ? data : []))
      .catch(() => setItems([]))
  }, [apiFetch])

  if (items.length === 0) return null
  const shown = expanded ? items : items.slice(0, 3)

  return (
    <div className="chart-card">
      <div className="chart-title" style={{ marginBottom: 14 }}>Insights</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {shown.map((it, i) => (
          <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: DOT[it.severity] || "var(--text3)", marginTop: 6, flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{it.title}</div>
              <div style={{ fontSize: 13, color: "var(--text2)", marginTop: 1 }}>{it.detail}</div>
            </div>
          </div>
        ))}
      </div>
      {items.length > 3 && (
        <button
          onClick={() => setExpanded(v => !v)}
          style={{ marginTop: 12, fontSize: 13, fontWeight: 600, color: "var(--accent)", background: "none", border: "none", cursor: "pointer", padding: 0 }}
        >
          {expanded ? "Show less ↑" : `Show ${items.length - 3} more ↓`}
        </button>
      )}
    </div>
  )
}
