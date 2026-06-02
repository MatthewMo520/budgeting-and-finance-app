export default function TransactionList({ transactions }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h2 className="text-sm font-medium text-gray-700 mb-4">Recent transactions</h2>
      <div className="divide-y divide-gray-100">
        {transactions.map(t => (
          <div key={t.id} className="flex items-center justify-between py-3">
            <div className="flex items-center gap-3">
              <div>
                <p className="text-sm font-medium text-gray-900">{t.name}</p>
                <p className="text-xs text-gray-400">
                  {t.ml_category?.replace(/_/g, " ")} · {t.date.slice(0, 10)}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-900">
                ${Math.abs(t.amount).toFixed(2)}
              </span>
              {t.is_anomaly && (
                <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                  anomaly
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}