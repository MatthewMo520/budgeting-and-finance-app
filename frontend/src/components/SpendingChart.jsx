import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis } from "recharts"

const COLORS = ["#1D9E75","#D85A30","#378ADD","#7F77DD","#888780","#B4B2A9"]

export default function SpendingChart({ categoryTotals, totalSpend }) {
  const data = Object.entries(categoryTotals)
    .sort((a,b) => b[1]-a[1])
    .map(([category, amount], i) => ({
      category: category.replace(/_/g," "),
      amount: parseFloat(amount.toFixed(2)),
      color: COLORS[i % COLORS.length]
    }))

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      <div className="rounded-xl p-4" style={{background:"#1a1d27",border:"1px solid #2a2d3a"}}>
        <p className="text-sm font-medium text-gray-300 mb-4">Spending by category</p>
        <div className="space-y-3">
          {data.map(d => (
            <div key={d.category} className="flex items-center gap-3">
              <span className="text-xs text-gray-400 w-32 shrink-0">{d.category}</span>
              <div className="flex-1 h-2 rounded-full" style={{background:"#2a2d3a"}}>
                <div
                  className="h-2 rounded-full"
                  style={{
                    width: `${(d.amount / data[0].amount) * 100}%`,
                    background: d.color
                  }}
                />
              </div>
              <span className="text-xs text-gray-300 w-16 text-right">${d.amount.toFixed(0)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl p-4 flex flex-col items-center" style={{background:"#1a1d27",border:"1px solid #2a2d3a"}}>
        <p className="text-sm font-medium text-gray-300 mb-4 self-start">Category split</p>
        <ResponsiveContainer width="100%" height={160}>
          <PieChart>
            <Pie data={data} dataKey="amount" nameKey="category" innerRadius={50} outerRadius={75} paddingAngle={2}>
              {data.map((d, i) => <Cell key={i} fill={d.color} />)}
            </Pie>
            <Tooltip formatter={(val) => `$${val.toFixed(2)}`} contentStyle={{background:"#1a1d27",border:"1px solid #2a2d3a",borderRadius:8,color:"#fff"}} />
          </PieChart>
        </ResponsiveContainer>
        <div className="grid grid-cols-2 gap-x-6 gap-y-1 mt-2 w-full">
          {data.map(d => (
            <div key={d.category} className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full shrink-0" style={{background:d.color}}/>
              <span className="text-xs text-gray-400">{d.category} {((d.amount/totalSpend)*100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}