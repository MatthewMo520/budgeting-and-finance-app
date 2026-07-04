import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../AuthContext"

const fmt = (n) => "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })

export default function Goals() {
  const { apiFetch } = useAuth()
  const [goals, setGoals] = useState([])
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState("")
  const [target, setTarget] = useState("")
  const [targetDate, setTargetDate] = useState("")

  const load = useCallback(async () => {
    try {
      const res = await apiFetch("/goals")
      if (res.ok) setGoals(await res.json())
    } catch { /* ignore */ }
  }, [apiFetch])
  useEffect(() => { load() }, [load])

  async function save(e) {
    e.preventDefault()
    const value = parseFloat(target)
    if (!name.trim() || !value || value <= 0) return
    const res = await apiFetch("/goals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), target_amount: value, target_date: targetDate || null }),
    })
    if (res.ok) { setName(""); setTarget(""); setTargetDate(""); setAdding(false); load() }
  }

  async function remove(id) {
    const res = await apiFetch(`/goals/${id}`, { method: "DELETE" })
    if (res.ok) load()
  }

  return (
    <div className="card" style={{ background: "var(--surface)", borderRadius: "var(--r)", boxShadow: "var(--shadow)", padding: "24px 28px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
        <div style={{ fontSize: 16, fontWeight: 700 }}>Savings goals</div>
        <button onClick={() => setAdding(a => !a)} style={{ fontSize: 13, fontWeight: 600, color: "var(--accent)", background: "none", border: "none", cursor: "pointer" }}>
          {adding ? "Cancel" : "+ Add goal"}
        </button>
      </div>

      {adding && (
        <form onSubmit={save} style={{ display: "flex", gap: 8, marginBottom: 18, flexWrap: "wrap" }}>
          <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Emergency fund" maxLength={60}
                 style={{ flex: "2 1 140px", padding: "8px 10px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)" }} />
          <input type="number" min="1" step="1" value={target} onChange={e => setTarget(e.target.value)} placeholder="Target $"
                 style={{ flex: "1 1 90px", padding: "8px 10px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)" }} />
          <input type="date" value={targetDate} onChange={e => setTargetDate(e.target.value)} aria-label="Target date (optional)"
                 style={{ flex: "1 1 130px", padding: "8px 10px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)" }} />
          <button type="submit" className="btn-primary" style={{ width: "auto", padding: "8px 16px", marginTop: 0 }}>Save</button>
        </form>
      )}

      {goals.length === 0 && !adding ? (
        <p style={{ fontSize: 14, color: "var(--text2)" }}>
          No goals yet. Set a target and progress fills from what you save each month (income minus spending).
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {goals.map(g => {
            const pct = Math.min(100, (g.saved / g.target_amount) * 100)
            const done = g.saved >= g.target_amount
            return (
              <div key={g.id}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
                  <span style={{ fontWeight: 600 }}>
                    {g.name}{done && " 🎉"}
                    {g.target_date && <span style={{ color: "var(--text2)", fontWeight: 500 }}> · by {g.target_date}</span>}
                  </span>
                  <span style={{ color: "var(--text2)" }}>
                    {fmt(g.saved)} / {fmt(g.target_amount)}
                    <button onClick={() => remove(g.id)} title="Remove" style={{ marginLeft: 10, background: "none", border: "none", color: "var(--text2)", cursor: "pointer" }}>✕</button>
                  </span>
                </div>
                <div style={{ height: 8, borderRadius: 999, background: "var(--track)" }}>
                  <div style={{ width: `${pct}%`, height: "100%", borderRadius: 999, background: done ? "var(--green)" : "var(--bar-active)", transition: "width .4s" }} />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
