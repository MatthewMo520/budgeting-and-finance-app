import { useState, useEffect } from "react"
import { displayCat, catStyle, ICONS, EDITABLE_CATEGORIES } from "../categories.jsx"

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

export default function TransactionList({ transactions, onEditCategory, onExport }) {
  const [filter, setFilter] = useState("all")
  const [showAll, setShowAll] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [query, setQuery] = useState("")

  useEffect(() => { setFilter("all"); setShowAll(false); setQuery("") }, [transactions])

  const anomalyCount = transactions.filter(t => t.is_anomaly).length
  const q = query.trim().toLowerCase()
  const filtered = transactions.filter(t =>
    (filter !== "anomalies" || t.is_anomaly) &&
    (!q || t.name.toLowerCase().includes(q) || displayCat(t.ml_category).toLowerCase().includes(q))
  )
  const shown = showAll ? filtered : filtered.slice(0, 7)

  return (
    <div className="txcard">
      <div className="txcard-hdr">
        <div className="txcard-title">Recent transactions</div>
        <div className="filter-row">
          <input
            type="search"
            className="tx-search"
            placeholder="Search transactions"
            value={query}
            onChange={e => setQuery(e.target.value)}
            aria-label="Search transactions by name or category"
          />
          <button className={`filter-btn ${filter === "all" ? "active" : ""}`} onClick={() => setFilter("all")}>
            All
          </button>
          <button className={`filter-btn ${filter === "anomalies" ? "active" : ""}`} onClick={() => setFilter("anomalies")}>
            Anomalies {anomalyCount > 0 && `(${anomalyCount})`}
          </button>
          {onExport && (
            <button className="filter-btn" onClick={onExport} title="Download this month as CSV">
              ↓ CSV
            </button>
          )}
        </div>
      </div>

      <div className="txlist">
        {shown.map(t => (
          <div key={t.id} className="txrow">
            <CatIcon mlCategory={t.ml_category} />
            <div className="txinfo">
              <div className="txname">{t.name}</div>
              <div className="txmeta">
                {editingId === t.id ? (
                  <select
                    autoFocus
                    defaultValue={displayCat(t.ml_category)}
                    onChange={e => { onEditCategory?.(t.id, e.target.value); setEditingId(null) }}
                    onBlur={() => setEditingId(null)}
                    style={{ fontSize: 12, padding: "2px 4px", borderRadius: 6, border: "1px solid var(--border)" }}
                  >
                    {EDITABLE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                ) : (
                  <button
                    onClick={() => onEditCategory && setEditingId(t.id)}
                    title="Click to change category"
                    style={{ background: "none", border: "none", padding: 0, font: "inherit", color: "inherit", cursor: onEditCategory ? "pointer" : "default" }}
                  >
                    {displayCat(t.ml_category)} · {t.category_overridden ? "edited ✎" : "auto-categorized"}
                  </button>
                )}
              </div>
            </div>
            <div className="txright">
              {/* Plaid: positive = money out (spend), negative = money in (income/refund). */}
              <div className="txamt" style={t.amount < 0 ? { color: "#166534" } : undefined}>
                {t.amount < 0 ? "+" : "-"}{fmt(t.amount)}
              </div>
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
            {q
              ? `No transactions match “${query.trim()}”.`
              : filter === "anomalies"
                ? "No anomalies this month — all clear."
                : "No transactions found."}
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
