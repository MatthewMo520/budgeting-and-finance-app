import { useEffect, useState } from "react"
import MetricCards from "./components/MetricCards"
import TransactionList from "./components/TransactionList"
import SpendingChart from "./components/SpendingChart"
import AnomalyAlert from "./components/AnomalyAlert"

export default function App() {
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch("http://localhost:8000/transactions")
      .then(res => res.json())
      .then(data => {
        setTransactions(data)
        setLoading(false)
      })
  }, [])

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center text-gray-400"
      style={{background:"#0f1117"}}>
      Loading...
    </div>
  )

  const anomalies = transactions.filter(t => t.is_anomaly)
  const totalSpend = transactions.reduce((sum, t) => sum + Math.abs(t.amount), 0)
  const categoryTotals = transactions.reduce((acc, t) => {
    const cat = t.ml_category || "OTHER"
    acc[cat] = (acc[cat] || 0) + Math.abs(t.amount)
    return acc
  }, {})

  const topCategory = Object.entries(categoryTotals).sort((a,b) => b[1]-a[1])[0]

  return (
    <div className="min-h-screen p-6" style={{background:"#0f1117"}}>
      <div className="max-w-5xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-semibold text-white">Finance dashboard</h1>
          <span className="text-sm text-gray-500">Sandbox data</span>
        </div>
        <AnomalyAlert anomalies={anomalies} />
        <MetricCards
          totalSpend={totalSpend}
          transactionCount={transactions.length}
          anomalyCount={anomalies.length}
          topCategory={topCategory}
        />
        <SpendingChart categoryTotals={categoryTotals} totalSpend={totalSpend} />
        <TransactionList transactions={transactions} />
      </div>
    </div>
  )
}