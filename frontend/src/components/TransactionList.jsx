import { useState, useEffect } from "react"
import { displayCat, catStyle, ICONS } from "../categories.jsx"

const fmt = (n) => "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function CatIcon({ mlCategory }) {
  const name = displayCat(mlCategory)
  const { color, bg } = catStyle(mlCategory)
  return (
    <div className="txicon" style={{ width: 40, height: 40, background: bg, color }}>
      {ICONS[name] || ICONS.Other}
    </div>
  )
}

export default function TransactionList({ transactions }) {
  const [filter, setFilter] = useState("all")
  const [showAll, setShowAll] = useState(false)

  useEffect(() => { setFilter("all"); setShowAll(false) }, [transactions])

  const anomalyCount = transactions.filter(t => t.is_anomaly).length
  const filtered = filter === "anomalies" ? transactions.filter(t => t.is_anomaly) : transactions
  const shown = showAll ? filtered : filtered.slice(0, 7)

  return (
    <div className="txcard">
      <div className="txcard-hdr">
        <div className="txcard-title">Recent transactions</div>
        <div className="filter-row">
          <button className={`filter-btn ${filter === "all" ? "active" : ""}`} onClick={() => setFilter("all")}>
            All
          </button>
          <button className={`filter-btn ${filter === "anomalies" ? "active" : ""}`} onClick={() => setFilter("anomalies")}>
            Anomalies {anomalyCount > 0 && `(${anomalyCount})`}
          </button>
        </div>
      </div>

      <div className="txlist">
        {shown.map(t => (
          <div key={t.id} className="txrow">
            <CatIcon mlCategory={t.ml_category} />
            <div className="txinfo">
              <div className="txname">{t.name}</div>
              <div className="txmeta">{displayCat(t.ml_category)} · auto-categorized</div>
            </div>
            <div className="txright">
              <div className="txamt">-{fmt(t.amount)}</div>
              <div className="txdate">{t.date?.slice(0, 10)}</div>
              <div>
                {t.is_anomaly
                  ? <span className="badge badge-anom">anomaly</span>
                  : <span className="badge badge-norm">normal</span>}
              </div>
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div style={{ padding: "32px", textAlign: "center", color: "var(--text2)", fontSize: 14 }}>
            No transactions found.
          </div>
        )}
      </div>

      {filtered.length > 7 && (
        <button className="txmore" onClick={() => setShowAll(v => !v)}>
          {showAll ? "Show less ↑" : `Show ${filtered.length - 7} more transactions ↓`}
        </button>
      )}
    </div>
  )
}
