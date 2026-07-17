import { useEffect, useState } from "react"
import { CAT } from "../categories.jsx"

const fmt = (n) => "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtK = (n) => n >= 1000 ? "$" + (n / 1000).toFixed(1) + "k" : "$" + Math.round(n)

function getCatEntries(categoryTotals) {
  return Object.entries(categoryTotals)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([name, val]) => ({ name, val, ...(CAT[name] || CAT.Other) }))
}

function DonutChart({ categoryTotals, totalSpend, selectedCategory, onSelectCategory }) {
  const [on, setOn] = useState(false)
  const cats = getCatEntries(categoryTotals)

  useEffect(() => {
    setOn(false)
    const t = setTimeout(() => setOn(true), 120)
    return () => clearTimeout(t)
  }, [categoryTotals])

  if (!totalSpend) return null

  const cx = 100, cy = 100, OR = 84, IR = 54, GAP = 2.5
  let ang = -90
  const segs = cats.map(({ name, val, color }) => {
    const pct = val / totalSpend
    const sweep = Math.max(pct * 360 - GAP, 0.5)
    const s = ang + GAP / 2, e = s + sweep
    ang += pct * 360
    const r = d => d * Math.PI / 180
    const P = (a, R) => [cx + R * Math.cos(r(a)), cy + R * Math.sin(r(a))]
    const [x1, y1] = P(s, OR), [x2, y2] = P(e, OR)
    const [x3, y3] = P(e, IR), [x4, y4] = P(s, IR)
    const la = sweep > 180 ? 1 : 0
    const d = `M${x1} ${y1} A${OR} ${OR} 0 ${la} 1 ${x2} ${y2} L${x3} ${y3} A${IR} ${IR} 0 ${la} 0 ${x4} ${y4}Z`
    return { name, val, pct, color, d }
  })

  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 200 200" width="196" height="196">
        {segs.map((s, i) => (
          <path key={i} d={s.d} fill={s.color} style={{
            transformOrigin: "100px 100px",
            transform: on ? "scale(1)" : "scale(0.82)",
            opacity: !on ? 0 : (selectedCategory && selectedCategory !== s.name ? 0.3 : 1),
            transition: `transform .55s cubic-bezier(.34,1.4,.64,1) ${i * .06}s, opacity .3s ease ${i * .06}s`,
            cursor: "pointer",
          }} onClick={() => onSelectCategory?.(s.name)}>
            <title>{`${s.name} — ${fmt(s.val)} (click to filter transactions)`}</title>
          </path>
        ))}
        <text x="100" y="92" textAnchor="middle" fontSize="20" fontWeight="600" fill="var(--text)" fontFamily="var(--font-mono)">{fmtK(totalSpend)}</text>
        <text x="100" y="111" textAnchor="middle" fontSize="11.5" fill="var(--text2)" fontFamily="var(--font-sans)">total</text>
      </svg>
      <div className="donut-legend">
        {segs.map((s, i) => (
          <div key={i} className="legend-row">
            <span className="legend-dot" style={{ background: s.color }} />
            <span className="legend-name">{s.name}</span>
            <span className="legend-pct">{Math.round(s.pct * 100)}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function SpendingChart({ categoryTotals, totalSpend, selectedCategory, onSelectCategory }) {
  const [on, setOn] = useState(false)
  const cats = getCatEntries(categoryTotals)
  const max = cats[0]?.val || 1

  useEffect(() => {
    setOn(false)
    const t = setTimeout(() => setOn(true), 160)
    return () => clearTimeout(t)
  }, [categoryTotals])

  return (
    <div className="charts-grid">
      <div className="chart-card">
        <div className="chart-title">Spending by category</div>
        <div className="bar-rows">
          {cats.map(({ name, val, color }, i) => (
            <div
              key={name}
              className={`bar-row clickable ${selectedCategory && selectedCategory !== name ? "dimmed" : ""}`}
              onClick={() => onSelectCategory?.(name)}
              title={`Click to ${selectedCategory === name ? "clear the filter" : "filter transactions to " + name}`}
              role="button"
              tabIndex={0}
              onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelectCategory?.(name) } }}
            >
              <span className="bar-label">{name}</span>
              <div className="bar-track">
                <div className="bar-fill" style={{
                  width: on ? `${(val / max) * 100}%` : "0%",
                  background: color,
                  transition: `width .85s cubic-bezier(.4,0,.2,1) ${i * .07}s`,
                }} />
              </div>
              <span className="bar-amt" style={{ color }}>{fmt(val)}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="chart-card">
        <div className="chart-title">Category split</div>
        <DonutChart categoryTotals={categoryTotals} totalSpend={totalSpend} selectedCategory={selectedCategory} onSelectCategory={onSelectCategory} />
      </div>
    </div>
  )
}
