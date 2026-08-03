import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { glApi } from '../services/api'

function money(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

export default function ProfitLossPage() {
  const today = new Date()
  const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10)
  const lastDay = today.toISOString().slice(0, 10)
  const [dateFrom, setDateFrom] = useState(firstDay)
  const [dateTo, setDateTo] = useState(lastDay)

  const { data, isLoading } = useQuery({
    queryKey: ['gl-profit-loss', dateFrom, dateTo],
    queryFn: () => glApi.profitLoss({ date_from: dateFrom, date_to: dateTo }).then(r => r.data.data),
  })

  const income: { code: string; name: string; balance: number }[] = data?.income_accounts || []
  const expenses: { code: string; name: string; balance: number }[] = data?.expense_accounts || []
  const totalIncome = data?.total_income || 0
  const totalExpenses = data?.total_expenses || 0
  const netProfit = data?.net_income || 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">მოგება-ზარალი</h1>
          <p className="mt-1 text-sm text-gray-500">Profit & Loss — შემოსავლები და ხარჯები პერიოდის მიხედვით</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600">დან:</label>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="input w-40" />
          <label className="text-sm text-gray-600">მდე:</label>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="input w-40" />
        </div>
      </div>

      {isLoading ? (
        <div className="card py-12 text-center text-gray-500">იტვირთება...</div>
      ) : (
        <div className="space-y-6">
          <div className="card overflow-hidden">
            <div className="border-b border-green-200 bg-green-50 px-4 py-2 text-sm font-semibold text-green-800">შემოსავლები</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <th className="px-4 py-2">კოდი</th>
                    <th className="px-4 py-2">სახელი</th>
                    <th className="px-4 py-2 text-right">თანხა</th>
                  </tr>
                </thead>
                <tbody>
                  {income.length === 0 ? (
                    <tr><td colSpan={3} className="px-4 py-6 text-center text-gray-400">მონაცემები არ არის</td></tr>
                  ) : income.map(a => (
                    <tr key={a.code} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-gray-900">{a.code}</td>
                      <td className="px-4 py-2 text-gray-900">{a.name}</td>
                      <td className="px-4 py-2 text-right font-mono text-green-700">{money(a.balance)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-green-300 bg-green-50">
                    <td colSpan={2} className="px-4 py-2 text-sm font-semibold text-green-800">მთლიანი შემოსავალი</td>
                    <td className="px-4 py-2 text-right font-mono font-bold text-green-800">{money(totalIncome)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm font-semibold text-red-800">ხარჯები</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <th className="px-4 py-2">კოდი</th>
                    <th className="px-4 py-2">სახელი</th>
                    <th className="px-4 py-2 text-right">თანხა</th>
                  </tr>
                </thead>
                <tbody>
                  {expenses.length === 0 ? (
                    <tr><td colSpan={3} className="px-4 py-6 text-center text-gray-400">მონაცემები არ არის</td></tr>
                  ) : expenses.map(a => (
                    <tr key={a.code} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-gray-900">{a.code}</td>
                      <td className="px-4 py-2 text-gray-900">{a.name}</td>
                      <td className="px-4 py-2 text-right font-mono text-red-700">{money(a.balance)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-red-300 bg-red-50">
                    <td colSpan={2} className="px-4 py-2 text-sm font-semibold text-red-800">მთლიანი ხარჯი</td>
                    <td className="px-4 py-2 text-right font-mono font-bold text-red-800">{money(totalExpenses)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          <div className={`card ${netProfit >= 0 ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
            <div className="flex justify-between items-center px-4 py-4">
              <span className="text-lg font-bold">{netProfit >= 0 ? 'წმინდა მოგება' : 'წმინდა ზარალი'}</span>
              <span className={`text-xl font-bold font-mono ${netProfit >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                {money(Math.abs(netProfit))}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
