import { useEffect, useState } from "react"

const fmtK = n => {
  const sign = n < 0 ? "−" : ""
  const v = Math.abs(n)
  return sign + (v >= 1000 ? "$" + (v / 1000).toFixed(1) + "k" : "$" + Math.round(v))
}

const MODES = [
  { key: "spend", label: "Spending" },
  { key: "income", label: "Income" },
  { key: "net", label: "Net" },
]

function monthLabel(ym) {
  const [y, m] = ym.split("-")
  const name = new Date(y, m - 1).toLocaleDateString("en-US", { month: "short" })
  // Mark year boundaries so a 12-month window spanning two years stays readable.
  return m === "01" ? `${name} '${y.slice(2)}` : name
}

export default function TrendChart({ summary, selectedMonth, onMonth }) {
  const [on, setOn] = useState(false)
  const [hover, setHover] = useState(null)
  const [mode, setMode] = useState("spend")

  useEffect(() => {
    const t = setTimeout(() => setOn(true), 140)
    return () => clearTimeout(t)
  }, [])

  const months = summary.slice(-12)
  if (months.length < 2) return null

  const valueOf = m => mode === "net" ? m.income - m.spend : m[mode]
  const max = Math.max(...months.map(m => Math.abs(valueOf(m))), 1)

  return (
    <div className="chart-card">
      <div className="trend-hdr">
        <div className="chart-title" style={{ marginBottom: 0 }}>Trend</div>
        <div className="filter-row">
          {MODES.map(m => (
            <button
              key={m.key}
              className={`filter-btn ${mode === m.key ? "active" : ""}`}
              onClick={() => setMode(m.key)}
            >
              {m.label}
            </button>
          ))}
        </div>
        <span className="trend-sub">last {months.length} months — click a bar to jump to it</span>
      </div>
      <div className="trend-bars">
        {months.map((m, i) => {
          const v = valueOf(m)
          const active = m.month === selectedMonth
          const showAmt = active || hover === m.month
          const negative = mode === "net" && v < 0
          return (
            <button
              key={m.month}
              className="trend-col"
              onClick={() => onMonth(m.month)}
              onMouseEnter={() => setHover(m.month)}
              onMouseLeave={() => setHover(null)}
              aria-label={`${monthLabel(m.month)}: ${fmtK(v)} ${mode === "net" ? "net" : mode} — view this month`}
              aria-pressed={active}
            >
              <span className={`trend-amt ${showAmt ? "show" : ""}`}>{fmtK(v)}</span>
              <span className="trend-barzone">
                <span
                  className={`trend-bar ${active ? "active" : ""} ${negative ? "negative" : ""}`}
                  style={{
                    height: on ? `${Math.max((Math.abs(v) / max) * 100, 3)}%` : "0%",
                    transitionDelay: `${i * 0.035}s`,
                  }}
                />
              </span>
              <span className={`trend-label ${active ? "active" : ""}`}>{monthLabel(m.month)}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
