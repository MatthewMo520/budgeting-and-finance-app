import { useEffect, useRef, useState } from "react"

const fmt = (n) => "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

// Animate a number toward its target (~600ms ease-out); jumps instantly when
// the user prefers reduced motion.
function useCountUp(target) {
  const [val, setVal] = useState(0)
  const prevRef = useRef(0)
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      prevRef.current = target
      setVal(target)
      return
    }
    const from = prevRef.current
    prevRef.current = target
    if (from === target) { setVal(target); return }
    const t0 = performance.now()
    let raf
    const tick = now => {
      const p = Math.min((now - t0) / 600, 1)
      const eased = 1 - Math.pow(1 - p, 3)
      setVal(from + (target - from) * eased)
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target])
  return val
}

// Hero band: monthly spend as the headline figure, compact stats down the side.
export default function MetricCards({ totalSpend, prevSpend, transactionCount, prevCount, anomalyCount, topCategory, forecast }) {
  const pct = prevSpend > 0 ? ((totalSpend - prevSpend) / prevSpend) * 100 : null
  const countDiff = prevCount > 0 ? transactionCount - prevCount : null
  const spendVal = useCountUp(totalSpend)
  const countVal = useCountUp(transactionCount)
  const anomVal = useCountUp(anomalyCount)

  const delta = pct !== null
    ? { cls: pct > 0 ? "red" : "green", text: `${pct > 0 ? "↑" : "↓"} ${Math.abs(pct).toFixed(0)}% vs last month` }
    : { cls: "muted", text: "No previous month data" }

  return (
    <div className="hero">
      <div className="hero-main">
        <div className="eyebrow">Monthly spend</div>
        <div className="hero-value">{fmt(spendVal)}</div>
        <div className={`hero-delta ${delta.cls}`}>{delta.text}</div>
        {forecast && forecast.projected_spend > 0 && forecast.days_left > 0 && (
          <div className="hero-note">On track for ~{fmt(forecast.projected_spend)} this month</div>
        )}
      </div>
      <div className="hero-side">
        <div className="hero-stat">
          <div>
            <div className="hero-stat-label">Transactions</div>
            <div className="hero-stat-sub">
              {countDiff !== null
                ? countDiff === 0 ? "Same as last month" : `${countDiff > 0 ? "+" : ""}${countDiff} vs last month`
                : "No previous month data"}
            </div>
          </div>
          <div className="hero-stat-value">{Math.round(countVal)}</div>
        </div>
        <div className="hero-stat">
          <div>
            <div className="hero-stat-label">Anomalies flagged</div>
            <div className="hero-stat-sub">{anomalyCount > 0 ? "Needs review" : "All clear"}</div>
          </div>
          <div className="hero-stat-value" style={{ color: anomalyCount > 0 ? "var(--amber)" : "var(--green)" }}>
            {Math.round(anomVal)}
          </div>
        </div>
        <div className="hero-stat">
          <div>
            <div className="hero-stat-label">Top category</div>
            <div className="hero-stat-sub">{topCategory ? `${fmt(topCategory[1])} this month` : "No data"}</div>
          </div>
          <div className="hero-stat-value plain">{topCategory?.[0]?.replace(/_/g, " ") ?? "—"}</div>
        </div>
      </div>
    </div>
  )
}
