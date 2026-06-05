const CATEGORY_ICONS = {
  FOOD_AND_DRINK: "🍔",
  TRANSPORTATION: "🚗",
  TRAVEL: "✈️",
  ENTERTAINMENT: "🎬",
  GENERAL_MERCHANDISE: "🛍️",
  RENT_AND_UTILITIES: "⚡",
  LOAN_PAYMENTS: "💳",
  TRANSFER_OUT: "↗️",
  TRANSFER_IN: "↙️",
  PERSONAL_CARE: "💆",
}

export default function TransactionList({ transactions }) {
  return (
    <div className="rounded-xl p-4" style={{background:"#1a1d27",border:"1px solid #2a2d3a"}}>
      <p className="text-sm font-medium text-gray-300 mb-4">Recent transactions</p>
      <div className="space-y-1">
        {transactions.map(t => (
          <div key={t.id} className="flex items-center gap-3 py-3 border-b border-white/5 last:border-0">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center text-lg shrink-0"
              style={{background:"#2a2d3a"}}>
              {CATEGORY_ICONS[t.ml_category] || "💰"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{t.name}</p>
              <p className="text-xs text-gray-500">
                {t.ml_category?.replace(/_/g," ")} · auto-categorized · {t.date.slice(0,10)}
              </p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-sm font-medium text-white">${Math.abs(t.amount).toFixed(2)}</p>
              {t.is_anomaly
                ? <span className="text-xs font-medium text-amber-400">anomaly</span>
                : <span className="text-xs font-medium text-green-400">normal</span>
              }
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}