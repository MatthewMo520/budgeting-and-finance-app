export default function MetricCards({ totalSpend, transactionCount, anomalyCount, topCategory }) {
  const cards = [
    { label: "Monthly spend", value: `$${totalSpend.toFixed(2)}` },
    { label: "Transactions", value: transactionCount },
    { label: "Anomalies flagged", value: anomalyCount },
    { label: "Top category", value: topCategory?.replace(/_/g, " ") },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      {cards.map(card => (
        <div key={card.label} className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-xs text-gray-500 mb-1">{card.label}</p>
          <p className="text-xl font-medium text-gray-900">{card.value}</p>
        </div>
      ))}
    </div>
  )
}