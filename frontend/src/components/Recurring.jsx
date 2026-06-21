import { useState, useEffect } from "react"
import { useAuth } from "../AuthContext"
import { displayCat } from "../categories.jsx"

const fmt = (n) => "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export default function Recurring() {
  const { apiFetch } = useAuth()
  const [items, setItems] = useState(null)

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch("/transactions/recurring")
        if (res.ok) setItems(await res.json())
      } catch { setItems([]) }
    })()
  }, [])

  if (!items || items.length === 0) return null  // hide until we detect something

  const monthlyTotal = items.reduce((s, r) => s + r.estimated_monthly, 0)

  return (
    <div className="card" style={{ background: "var(--surface)", borderRadius: "var(--r)", boxShadow: "var(--shadow)", padding: "24px 28px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
        <div style={{ fontSize: 16, fontWeight: 700 }}>Recurring & subscriptions</div>
        <div style={{ fontSize: 13, color: "var(--text2)" }}>≈ {fmt(monthlyTotal)}/mo</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {items.map((r, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{r.name}</div>
              <div style={{ fontSize: 12, color: "var(--text2)" }}>
                {displayCat(r.category)} · {r.frequency} · {r.occurrences}× · last {r.last_date}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{fmt(r.amount)}</div>
              <div style={{ fontSize: 12, color: "var(--text2)" }}>≈ {fmt(r.estimated_monthly)}/mo</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
