import { displayCat } from "../categories.jsx"

function getReason(transaction, allTransactions) {
  const cat = transaction.ml_category
  const amount = Math.abs(transaction.amount)
  const sameCat = allTransactions.filter(t => t.ml_category === cat && !t.is_anomaly)
  if (sameCat.length >= 2) {
    const avg = sameCat.reduce((s, t) => s + Math.abs(t.amount), 0) / sameCat.length
    if (avg > 0) {
      const mult = (amount / avg).toFixed(1)
      return `$${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} is ${mult}× your average for this category ($${avg.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })})`
    }
  }
  return `$${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} is unusually high for this category`
}

export default function AnomalyAlert({ anomalies, allTransactions = [] }) {
  if (!anomalies.length) return null
  const top = anomalies[0]
  const cat = displayCat(top.ml_category)
  const dateStr = top.date ? top.date.slice(0, 10) : ""
  const reason = getReason(top, allTransactions)

  return (
    <div className="alert-banner">
      <div className="alert-icon">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
      </div>
      <div className="alert-body">
        <strong>Anomaly detected</strong> — {cat.toLowerCase()} spend on {dateStr}: {reason}.
        {anomalies.length > 1 && <span> +{anomalies.length - 1} more flagged.</span>}
        <a className="alert-link" href="https://en.wikipedia.org/wiki/Isolation_forest" target="_blank" rel="noopener noreferrer">How is this detected? ↗</a>
      </div>
    </div>
  )
}
