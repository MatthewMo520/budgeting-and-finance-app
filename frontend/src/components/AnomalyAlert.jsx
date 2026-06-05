export default function AnomalyAlert({ anomalies }) {
  if (anomalies.length === 0) return null
  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 mb-6 flex gap-3">
      <span className="text-amber-400 mt-0.5">⚠</span>
      <div>
        <p className="text-sm font-medium text-amber-400">
          {anomalies.length} {anomalies.length > 1 ? "anomalies" : "anomaly"} detected
        </p>
        <ul className="mt-1 space-y-0.5">
          {anomalies.map(t => (
            <li key={t.id} className="text-sm text-amber-300/80">
              {t.name} — ${Math.abs(t.amount).toFixed(2)} is unusually {Math.abs(t.amount) > 200 ? "large" : "small"} for {t.ml_category?.replace(/_/g," ")}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}