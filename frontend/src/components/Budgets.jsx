import { useState, useEffect } from "react"
import { useAuth } from "../AuthContext"
import { EDITABLE_CATEGORIES } from "../categories.jsx"

const fmt = (n) => "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })

export default function Budgets({ categoryTotals }) {
  const { apiFetch } = useAuth()
  const [budgets, setBudgets] = useState([])
  const [adding, setAdding] = useState(false)
  const [cat, setCat] = useState(EDITABLE_CATEGORIES[0])
  const [limit, setLimit] = useState("")

  async function load() {
    try {
      const res = await apiFetch("/budgets")
      if (res.ok) setBudgets(await res.json())
    } catch { /* ignore */ }
  }
  useEffect(() => { load() }, [])

  async function save(e) {
    e.preventDefault()
    const value = parseFloat(limit)
    if (!value || value <= 0) return
    const res = await apiFetch("/budgets", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category: cat, monthly_limit: value }),
    })
    if (res.ok) { setLimit(""); setAdding(false); load() }
  }

  async function remove(category) {
    const res = await apiFetch(`/budgets/${encodeURIComponent(category)}`, { method: "DELETE" })
    if (res.ok) load()
  }

  return (
    <div className="card" style={{ background: "var(--surface)", borderRadius: "var(--r)", boxShadow: "var(--shadow)", padding: "24px 28px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
        <div style={{ fontSize: 16, fontWeight: 700 }}>Budgets</div>
        <button onClick={() => setAdding(a => !a)} style={{ fontSize: 13, fontWeight: 600, color: "var(--accent)", background: "none", border: "none", cursor: "pointer" }}>
          {adding ? "Cancel" : "+ Add budget"}
        </button>
      </div>

      {adding && (
        <form onSubmit={save} style={{ display: "flex", gap: 8, marginBottom: 18 }}>
          <select value={cat} onChange={e => setCat(e.target.value)} style={{ flex: 1, padding: "8px 10px", borderRadius: 8, border: "1px solid var(--border)" }}>
            {EDITABLE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <input type="number" min="1" step="1" value={limit} onChange={e => setLimit(e.target.value)} placeholder="Monthly $" style={{ width: 110, padding: "8px 10px", borderRadius: 8, border: "1px solid var(--border)" }} />
          <button type="submit" className="btn-primary" style={{ width: "auto", padding: "8px 16px" }}>Save</button>
        </form>
      )}

      {budgets.length === 0 && !adding ? (
        <p style={{ fontSize: 14, color: "var(--text2)" }}>No budgets yet. Set a monthly limit per category to track your spending.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {budgets.map(b => {
            const spent = categoryTotals[b.category] || 0
            const pct = Math.min(100, (spent / b.monthly_limit) * 100)
            const over = spent > b.monthly_limit
            return (
              <div key={b.category}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
                  <span style={{ fontWeight: 600 }}>{b.category}</span>
                  <span style={{ color: over ? "var(--red)" : "var(--text2)" }}>
                    {fmt(spent)} / {fmt(b.monthly_limit)}
                    <button onClick={() => remove(b.category)} title="Remove" style={{ marginLeft: 10, background: "none", border: "none", color: "var(--text2)", cursor: "pointer" }}>✕</button>
                  </span>
                </div>
                <div style={{ height: 8, borderRadius: 999, background: "var(--track)" }}>
                  <div style={{ width: `${pct}%`, height: "100%", borderRadius: 999, background: over ? "var(--red)" : "var(--bar-active)", transition: "width .4s" }} />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
