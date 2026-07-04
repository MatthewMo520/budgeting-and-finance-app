import { useState, useEffect } from "react"
import { useAuth } from "../AuthContext"

const fmt = (n) => "$" + n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })

export default function NetWorthChart() {
  const { user, apiFetch } = useAuth()
  const [points, setPoints] = useState(null)

  useEffect(() => {
    if (!user?.has_bank) return
    apiFetch("/networth")
      .then(r => r.ok ? r.json() : [])
      .then(data => setPoints(Array.isArray(data) ? data : []))
      .catch(() => setPoints([]))
  }, [user?.has_bank, apiFetch])

  if (!user?.has_bank || !points || points.length === 0) return null

  if (points.length === 1) {
    return (
      <div className="chart-card">
        <div className="chart-title" style={{ marginBottom: 6 }}>Net worth</div>
        <p style={{ fontSize: 14, color: "var(--text2)" }}>
          Tracking started at <strong>{fmt(points[0].total_available)}</strong> — check back tomorrow to see the trend.
        </p>
      </div>
    )
  }

  const W = 600, H = 160, PAD = 10
  const vals = points.map(p => p.total_available)
  const min = Math.min(...vals), max = Math.max(...vals)
  const span = max - min || 1
  const x = i => PAD + (i / (points.length - 1)) * (W - 2 * PAD)
  const y = v => H - PAD - ((v - min) / span) * (H - 2 * PAD)
  const line = points.map((p, i) => `${x(i)},${y(p.total_available)}`).join(" ")
  const area = `M${x(0)},${H - PAD} L${line.replace(/ /g, " L")} L${x(points.length - 1)},${H - PAD} Z`
  const last = points[points.length - 1]
  const delta = last.total_available - points[0].total_available

  return (
    <div className="chart-card">
      <div className="trend-hdr">
        <div className="chart-title" style={{ marginBottom: 0 }}>Net worth</div>
        <span style={{ fontSize: 15, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{fmt(last.total_available)}</span>
        <span className="trend-sub" style={{ color: delta >= 0 ? "var(--green)" : "var(--red)" }}>
          {delta >= 0 ? "+" : "−"}{fmt(Math.abs(delta))} since {points[0].date}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="160" preserveAspectRatio="none" role="img"
           aria-label={`Net worth from ${points[0].date} to ${last.date}, currently ${fmt(last.total_available)}`}>
        <path d={area} fill="var(--bar-active)" opacity="0.12" />
        <polyline points={line} fill="none" stroke="var(--bar-active)" strokeWidth="2"
                  vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
        {points.map((p, i) => (
          <circle key={p.date} cx={x(i)} cy={y(p.total_available)} r="7" fill="transparent">
            <title>{`${p.date} — ${fmt(p.total_available)} available (${fmt(p.total_current)} current)`}</title>
          </circle>
        ))}
        <circle cx={x(points.length - 1)} cy={y(last.total_available)} r="3.5" fill="var(--bar-active)" />
      </svg>
    </div>
  )
}
