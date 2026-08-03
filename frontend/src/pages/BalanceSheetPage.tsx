import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { glApi } from '../services/api'

function money(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

export default function BalanceSheetPage() {
  const today = new Date().toISOString().slice(0, 10)
  const [asOfDate, setAsOfDate] = useState(today)

  const { data, isLoading } = useQuery({
    queryKey: ['gl-balance-sheet', asOfDate],
    queryFn: () => glApi.balanceSheet({ as_of_date: asOfDate }).then(r => r.data.data),
  })

  const assets: { code: string; name: string; balance: number }[] = data?.asset_accounts || []
  const liabilities: { code: string; name: string; balance: number }[] = data?.liability_accounts || []
  const equity: { code: string; name: string; balance: number }[] = data?.equity_accounts || []

  const totalAssets = data?.total_assets || 0
  const totalLiabilities = data?.total_liabilities || 0
  const totalEquity = data?.total_equity || 0
  const totalLiabilitiesEquity = totalLiabilities + totalEquity

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">ბალანსი</h1>
          <p className="mt-1 text-sm text-gray-500">Balance Sheet — ფინანსური მდგომარეობის ანგარიშგება</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600">თარიღი:</label>
          <input type="date" value={asOfDate} onChange={e => setAsOfDate(e.target.value)} className="input w-44" />
        </div>
      </div>

      {isLoading ? (
        <div className="card py-12 text-center text-gray-500">იტვირთება...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-6">
            <div className="card overflow-hidden">
              <div className="border-b border-blue-200 bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-800">აქტივები</div>
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
                    {assets.length === 0 ? (
                      <tr><td colSpan={3} className="px-4 py-6 text-center text-gray-400">მონაცემები არ არის</td></tr>
                    ) : assets.map(a => (
                      <tr key={a.code} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-2 font-mono text-gray-900">{a.code}</td>
                        <td className="px-4 py-2 text-gray-900">{a.name}</td>
                        <td className="px-4 py-2 text-right font-mono text-blue-700">{money(a.balance)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-blue-300 bg-blue-50">
                      <td colSpan={2} className="px-4 py-2 text-sm font-semibold text-blue-800">აქტივები სულ</td>
                      <td className="px-4 py-2 text-right font-mono font-bold text-blue-800">{money(totalAssets)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="card overflow-hidden">
              <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-800">ვალდებულებები</div>
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
                    {liabilities.length === 0 ? (
                      <tr><td colSpan={3} className="px-4 py-6 text-center text-gray-400">მონაცემები არ არის</td></tr>
                    ) : liabilities.map(a => (
                      <tr key={a.code} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-2 font-mono text-gray-900">{a.code}</td>
                        <td className="px-4 py-2 text-gray-900">{a.name}</td>
                        <td className="px-4 py-2 text-right font-mono text-amber-700">{money(a.balance)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-amber-300 bg-amber-50">
                      <td colSpan={2} className="px-4 py-2 text-sm font-semibold text-amber-800">ვალდებულებები სულ</td>
                      <td className="px-4 py-2 text-right font-mono font-bold text-amber-800">{money(totalLiabilities)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>

            <div className="card overflow-hidden">
              <div className="border-b border-purple-200 bg-purple-50 px-4 py-2 text-sm font-semibold text-purple-800">კაპიტალი</div>
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
                    {equity.length === 0 ? (
                      <tr><td colSpan={3} className="px-4 py-6 text-center text-gray-400">მონაცემები არ არის</td></tr>
                    ) : equity.map(a => (
                      <tr key={a.code} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-2 font-mono text-gray-900">{a.code}</td>
                        <td className="px-4 py-2 text-gray-900">{a.name}</td>
                        <td className="px-4 py-2 text-right font-mono text-purple-700">{money(a.balance)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-purple-300 bg-purple-50">
                      <td colSpan={2} className="px-4 py-2 text-sm font-semibold text-purple-800">კაპიტალი სულ</td>
                      <td className="px-4 py-2 text-right font-mono font-bold text-purple-800">{money(totalEquity)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className={`card ${totalAssets === totalLiabilitiesEquity ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
        <div className="grid grid-cols-2 gap-4 px-4 py-4">
          <div>
            <div className="text-sm text-gray-600">აქტივები</div>
            <div className="text-lg font-bold font-mono text-blue-700">{money(totalAssets)}</div>
          </div>
          <div>
            <div className="text-sm text-gray-600">ვალდებულებები + კაპიტალი</div>
            <div className="text-lg font-bold font-mono text-amber-700">{money(totalLiabilitiesEquity)}</div>
          </div>
        </div>
        <div className={`px-4 py-2 text-center text-sm font-semibold border-t ${totalAssets === totalLiabilitiesEquity ? 'border-green-200 text-green-700' : 'border-red-200 text-red-700'}`}>
          {totalAssets === totalLiabilitiesEquity ? 'ბალანსი დაბალანსებულია ✓' : `სხვაობა: ${money(totalAssets - totalLiabilitiesEquity)}`}
        </div>
      </div>
    </div>
  )
}
