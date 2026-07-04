import { isSpend } from "../categories.jsx"

const fmtK = n => n >= 1000 ? "$" + (n / 1000).toFixed(1) + "k" : "$" + Math.round(n)
const DOW = ["S", "M", "T", "W", "T", "F", "S"]

export default function SpendCalendar({ transactions, month }) {
  if (!month) return null
  const [y, m] = month.split("-").map(Number)
  const daysInMonth = new Date(y, m, 0).getDate()
  const firstDow = new Date(y, m - 1, 1).getDay()

  const totals = {}
  for (const t of transactions) {
    if (!isSpend(t)) continue
    const d = parseInt(t.date.slice(8, 10), 10)
    totals[d] = (totals[d] || 0) + t.amount
  }
  const max = Math.max(...Object.values(totals), 1)
  const monthName = new Date(y, m - 1).toLocaleDateString("en-US", { month: "long" })

  return (
    <div className="chart-card">
      <div className="chart-title" style={{ marginBottom: 16 }}>Daily spending</div>
      <div className="cal-grid" role="img" aria-label={`Daily spending heatmap for ${monthName}`}>
        {DOW.map((d, i) => <div key={`h${i}`} className="cal-dow" aria-hidden="true">{d}</div>)}
        {Array.from({ length: firstDow }, (_, i) => <div key={`b${i}`} />)}
        {Array.from({ length: daysInMonth }, (_, i) => {
          const day = i + 1
          const v = totals[day] || 0
          // Single-hue sequential ramp; capped at 55% so the day number stays
          // readable on the deepest cells in both themes.
          const pct = v > 0 ? 8 + Math.round((v / max) * 47) : 0
          return (
            <div
              key={day}
              className="cal-cell"
              style={{ background: v > 0 ? `color-mix(in srgb, var(--bar-active) ${pct}%, var(--surface))` : "var(--track)" }}
              title={`${monthName} ${day} — ${v > 0 ? "$" + v.toFixed(2) + " spent" : "no spending"}`}
            >
              <span>{day}</span>
              {v > 0 && <span className="cal-amt">{fmtK(v)}</span>}
            </div>
          )
        })}
      </div>
    </div>
  )
}
