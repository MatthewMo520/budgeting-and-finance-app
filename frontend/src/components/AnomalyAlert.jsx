export default function AnomalyAlert({ anomalies }) {
  if (anomalies.length === 0) return null

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
      <div className="flex items-start gap-3">
        <span className="text-amber-500 text-lg">⚠</span>
        <div>
          <p className="text-sm font-medium text-amber-800">
            {anomalies.length} anomaly {anomalies.length > 1 ? "anomalies" : "anomaly"} detected
          </p>
          <ul className="mt-1 space-y-1">
            {anomalies.map(t => (
              <li key={t.id} className="text-sm text-amber-700">
                {t.name} — ${Math.abs(t.amount).toFixed(2)} is unusually {Math.abs(t.amount) > 500 ? "large" : "small"} for {t.ml_category}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}