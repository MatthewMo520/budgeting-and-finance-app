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

export default function MetricCards({ totalSpend, prevSpend, transactionCount, prevCount, anomalyCount, topCategory, forecast }) {
  const pct = prevSpend > 0 ? ((totalSpend - prevSpend) / prevSpend) * 100 : null
  const countDiff = prevCount > 0 ? transactionCount - prevCount : null
  const spendVal = useCountUp(totalSpend)
  const countVal = useCountUp(transactionCount)
  const anomVal = useCountUp(anomalyCount)

  const cards = [
    {
      label: "Monthly spend",
      value: fmt(spendVal),
      sub: pct !== null
        ? { cls: pct > 0 ? "red" : "green", text: `${pct > 0 ? "↑" : "↓"} ${Math.abs(pct).toFixed(0)}% vs last month` }
        : { cls: "muted", text: "No previous month data" },
      extra: forecast && forecast.projected_spend > 0 && forecast.days_left > 0
        ? `on track for ~${fmt(forecast.projected_spend)} this month`
        : null,
    },
    {
      label: "Transactions",
      value: Math.round(countVal),
      sub: countDiff !== null
        ? { cls: "muted", text: countDiff === 0 ? "Same as last month" : `${countDiff > 0 ? "+" : ""}${countDiff} vs last month` }
        : { cls: "muted", text: "No previous month data" },
    },
    {
      label: "Anomalies flagged",
      value: Math.round(anomVal),
      valueColor: anomalyCount > 0 ? "var(--red)" : "var(--green)",
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
          {card.extra && <div className="mcard-extra">{card.extra}</div>}
        </div>
      ))}
    </div>
  )
}
