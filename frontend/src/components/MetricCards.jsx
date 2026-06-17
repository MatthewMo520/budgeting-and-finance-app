const fmt = (n) => "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export default function MetricCards({ totalSpend, prevSpend, transactionCount, anomalyCount, topCategory }) {
  const pct = prevSpend > 0 ? ((totalSpend - prevSpend) / prevSpend) * 100 : null

  const cards = [
    {
      label: "Monthly spend",
      value: fmt(totalSpend),
      sub: pct !== null
        ? { cls: pct > 0 ? "red" : "green", text: `${pct > 0 ? "↑" : "↓"} ${Math.abs(pct).toFixed(0)}% vs last month` }
        : { cls: "muted", text: "No previous month data" },
    },
    {
      label: "Transactions",
      value: transactionCount,
      sub: { cls: "muted", text: "Normal range" },
    },
    {
      label: "Anomalies flagged",
      value: anomalyCount,
      valueColor: anomalyCount > 0 ? "#dc2626" : "#16a34a",
      sub: anomalyCount > 0
        ? { cls: "amber", text: "Needs review" }
        : { cls: "green", text: "All clear" },
    },
    {
      label: "Top category",
      value: topCategory?.[0]?.replace(/_/g, " ") ?? "—",
      valueSize: 22,
      sub: topCategory
        ? { cls: "green", text: `${fmt(topCategory[1])} this month` }
        : { cls: "muted", text: "No data" },
    },
  ]

  return (
    <div className="metric-grid">
      {cards.map(card => (
        <div key={card.label} className="mcard">
          <div className="mcard-label">{card.label}</div>
          <div className="mcard-value" style={{ color: card.valueColor, fontSize: card.valueSize }}>
            {card.value}
          </div>
          <div className={`mcard-sub ${card.sub.cls}`}>{card.sub.text}</div>
        </div>
      ))}
    </div>
  )
}
