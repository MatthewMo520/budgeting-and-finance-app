export default function MetricCards({ totalSpend, transactionCount, anomalyCount, topCategory }) {
  const cards = [
    {
      label: "Monthly spend",
      value: `$${totalSpend.toFixed(2)}`,
      sub: null
    },
    {
      label: "Transactions",
      value: transactionCount,
      sub: <span className="text-green-400 text-xs">Normal range</span>
    },
    {
      label: "Anomalies flagged",
      value: anomalyCount,
      sub: anomalyCount > 0 ? <span className="text-amber-400 text-xs">Needs review</span> : <span className="text-green-400 text-xs">All clear</span>
    },
    {
      label: "Top category",
      value: topCategory?.[0]?.replace(/_/g," "),
      sub: topCategory ? <span className="text-green-400 text-xs">${topCategory[1].toFixed(2)} this month</span> : null
    },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      {cards.map(card => (
        <div key={card.label} className="rounded-xl p-4" style={{background:"#1a1d27",border:"1px solid #2a2d3a"}}>
          <p className="text-xs text-gray-400 mb-2">{card.label}</p>
          <p className="text-2xl font-semibold text-white mb-1">{card.value}</p>
          {card.sub}
        </div>
      ))}
    </div>
  )
}