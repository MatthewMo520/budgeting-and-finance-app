import { useState, useEffect } from "react"
import { displayCat, catStyle, ICONS, EDITABLE_CATEGORIES } from "../categories.jsx"

const fmt = (n) => "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function CatIcon({ mlCategory, logoUrl }) {
  const name = displayCat(mlCategory)
  const { color, bg } = catStyle(mlCategory)
  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt=""
        loading="lazy"
        style={{ width: 36, height: 36, borderRadius: 9, objectFit: "cover", background: bg, flexShrink: 0 }}
        onError={e => { e.currentTarget.style.display = "none" }}
      />
    )
  }
  return (
    <div className="txicon" style={{ width: 36, height: 36, background: bg, color }}>
      {ICONS[name] || ICONS.Other}
    </div>
  )
}

export default function TransactionList({ transactions, onEditCategory, onExport, categoryFilter, onClearCategory, onDismissAnomaly }) {
  const [filter, setFilter] = useState("all")
  const [showAll, setShowAll] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [query, setQuery] = useState("")
  const [bankFilter, setBankFilter] = useState("")

  useEffect(() => { setFilter("all"); setShowAll(false); setQuery(""); setBankFilter("") }, [transactions])

  const banks = [...new Set(transactions.map(t => t.institution_name).filter(Boolean))]
  const anomalyCount = transactions.filter(t => t.is_anomaly).length
  const q = query.trim().toLowerCase()
  const filtered = transactions.filter(t =>
    (filter !== "anomalies" || t.is_anomaly) &&
    (!categoryFilter || displayCat(t.ml_category) === categoryFilter) &&
    (!bankFilter || t.institution_name === bankFilter) &&
    (!q || t.name.toLowerCase().includes(q) || (t.merchant_name || "").toLowerCase().includes(q) || displayCat(t.ml_category).toLowerCase().includes(q))
  )
  const shown = showAll ? filtered : filtered.slice(0, 7)

  return (
    <div className="txcard">
      <div className="txcard-hdr">
        <div className="txcard-title">Recent transactions</div>
        <div className="filter-row">
          {categoryFilter && (
            <button className="filter-btn active" onClick={onClearCategory} title="Clear category filter">
              {categoryFilter} ✕
            </button>
          )}
          {banks.length > 1 && (
            <select
              className="tx-bank-select"
              value={bankFilter}
              onChange={e => setBankFilter(e.target.value)}
              aria-label="Filter by bank"
            >
              <option value="">All banks</option>
              {banks.map(b => <option key={b} value={b}>{b}</option>)}
            </select>
          )}
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
            <CatIcon mlCategory={t.ml_category} logoUrl={t.logo_url} />
            <div className="txinfo">
              <div className="txname">{t.merchant_name || t.name}</div>
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
                {t.account_name && (
                  <span title={`${t.institution_name || "Bank"} — ${t.account_name}`}>
                    {" · "}{t.institution_name ? `${t.institution_name} ` : ""}{t.account_name}
                  </span>
                )}
              </div>
            </div>
            <div className="txright">
              {/* Plaid: positive = money out (spend), negative = money in (income/refund). */}
              <div className="txamt" style={t.amount < 0 ? { color: "var(--green)" } : undefined}>
                {t.amount < 0 ? "+" : "-"}{fmt(t.amount)}
              </div>
              <div className="txdate">{t.date?.slice(0, 10)}</div>
              <div>
                {t.is_anomaly
                  ? (
                    <button
                      className="badge badge-anom badge-btn"
                      title="Not unusual? Click to mark as expected — it won't be flagged again"
                      onClick={() => onDismissAnomaly?.(t.id)}
                    >
                      anomaly ✕
                    </button>
                  )
                  : <span className="badge badge-norm">{t.anomaly_dismissed ? "expected" : "normal"}</span>}
              </div>
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div style={{ padding: "32px", textAlign: "center", color: "var(--text2)", fontSize: 14 }}>
            {q
              ? `No transactions match “${query.trim()}”.`
              : categoryFilter
                ? `No ${categoryFilter} transactions this month.`
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
