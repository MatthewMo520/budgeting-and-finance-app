import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"

export default function SpendingChart({ categoryTotals }) {
  const data = Object.entries(categoryTotals)
    .sort((a, b) => b[1] - a[1])
    .map(([category, amount]) => ({
      category: category.replace(/_/g, " "),
      amount: parseFloat(amount.toFixed(2))
    }))

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
      <h2 className="text-sm font-medium text-gray-700 mb-4">Spending by category</h2>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} layout="vertical">
          <XAxis type="number" tick={{ fontSize: 12 }} />
          <YAxis type="category" dataKey="category" tick={{ fontSize: 11 }} width={140} />
          <Tooltip formatter={(val) => `$${val.toFixed(2)}`} />
          <Bar dataKey="amount" fill="#1D9E75" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}