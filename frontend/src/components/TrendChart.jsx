import { useEffect, useState } from "react"

const fmtK = n => n >= 1000 ? "$" + (n / 1000).toFixed(1) + "k" : "$" + Math.round(n)

function monthLabel(ym) {
  const [y, m] = ym.split("-")
  const name = new Date(y, m - 1).toLocaleDateString("en-US", { month: "short" })
  // Mark year boundaries so a 12-month window spanning two years stays readable.
  return m === "01" ? `${name} '${y.slice(2)}` : name
}

export default function TrendChart({ summary, selectedMonth, onMonth }) {
  const [on, setOn] = useState(false)
  const [hover, setHover] = useState(null)

  useEffect(() => {
    const t = setTimeout(() => setOn(true), 140)
    return () => clearTimeout(t)
  }, [])

  const months = summary.slice(-12)
  if (months.length < 2) return null
  const max = Math.max(...months.map(m => m.spend), 1)

  return (
    <div className="chart-card">
      <div className="trend-hdr">
        <div className="chart-title" style={{ marginBottom: 0 }}>Spending trend</div>
        <span className="trend-sub">last {months.length} months — click a bar to jump to it</span>
      </div>
      <div className="trend-bars">
        {months.map((m, i) => {
          const active = m.month === selectedMonth
          const showAmt = active || hover === m.month
          return (
            <button
              key={m.month}
              className="trend-col"
              onClick={() => onMonth(m.month)}
              onMouseEnter={() => setHover(m.month)}
              onMouseLeave={() => setHover(null)}
              aria-label={`${monthLabel(m.month)}: ${fmtK(m.spend)} spent — view this month`}
              aria-pressed={active}
            >
              <span className={`trend-amt ${showAmt ? "show" : ""}`}>{fmtK(m.spend)}</span>
              <span className="trend-barzone">
                <span
                  className={`trend-bar ${active ? "active" : ""}`}
                  style={{
                    height: on ? `${Math.max((m.spend / max) * 100, 3)}%` : "0%",
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
