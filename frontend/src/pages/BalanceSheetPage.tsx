import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { glApi } from '../services/api'
import { Scale } from 'lucide-react'

function money(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

function SectionHeader({ label, color }: { label: string; color: 'blue' | 'amber' | 'purple' }) {
  const map = {
    blue: 'border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900/50 dark:bg-blue-950/40 dark:text-blue-300',
    amber: 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300',
    purple: 'border-purple-200 bg-purple-50 text-purple-800 dark:border-purple-900/50 dark:bg-purple-950/40 dark:text-purple-300',
  }
  return (
    <div className={`border-b px-4 py-2 text-sm font-semibold ${map[color]}`}>{label}</div>
  )
}

function AmountCell({ value, color }: { value: number; color: string }) {
  return <td className={`px-4 py-2 text-right font-mono ${color}`}>{money(value)}</td>
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
  const balanced = totalAssets === totalLiabilitiesEquity

  const renderSection = (
    title: string,
    rows: { code: string; name: string; balance: number }[],
    total: number,
    color: 'blue' | 'amber' | 'purple',
    totalClass: string,
    amountClass: string,
  ) => (
    <div className="card overflow-hidden">
      <SectionHeader label={title} color={color} />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:border-dark-50 dark:text-gray-400">
              <th className="px-4 py-2">კოდი</th>
              <th className="px-4 py-2">სახელი</th>
              <th className="px-4 py-2 text-right">თანხა</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={3} className="px-4 py-6 text-center text-gray-400 dark:text-gray-500">მონაცემები არ არის</td></tr>
            ) : rows.map(a => (
              <tr key={a.code} className="border-b border-gray-100 hover:bg-gray-50 dark:border-dark-50 dark:hover:bg-dark-100">
                <td className="px-4 py-2 font-mono text-gray-900 dark:text-gray-200">{a.code}</td>
                <td className="px-4 py-2 text-gray-900 dark:text-gray-200">{a.name}</td>
                <AmountCell value={a.balance} color={amountClass} />
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className={`border-t-2 ${totalClass}`}>
              <td colSpan={2} className="px-4 py-2 text-sm font-semibold">{title} სულ</td>
              <td className="px-4 py-2 text-right font-mono font-bold">{money(total)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">ბალანსი</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Balance Sheet — ფინანსური მდგომარეობის ანგარიშგება</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600 dark:text-gray-400">თარიღი:</label>
          <input type="date" value={asOfDate} onChange={e => setAsOfDate(e.target.value)} className="input w-44" />
        </div>
      </div>

      {isLoading ? (
        <div className="card py-12 text-center text-gray-500 dark:text-gray-400" role="status">იტვირთება...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-6">
            {renderSection(
              'აქტივები', assets, totalAssets, 'blue',
              'border-blue-300 bg-blue-50 text-blue-800 dark:border-blue-900/60 dark:bg-blue-950/40 dark:text-blue-300',
              'text-blue-700 dark:text-blue-400',
            )}
          </div>

          <div className="space-y-6">
            {renderSection(
              'ვალდებულებები', liabilities, totalLiabilities, 'amber',
              'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300',
              'text-amber-700 dark:text-amber-400',
            )}
            {renderSection(
              'კაპიტალი', equity, totalEquity, 'purple',
              'border-purple-300 bg-purple-50 text-purple-800 dark:border-purple-900/60 dark:bg-purple-950/40 dark:text-purple-300',
              'text-purple-700 dark:text-purple-400',
            )}
          </div>
        </div>
      )}

      <div className={`card ${balanced ? 'bg-green-50 border border-green-200 dark:bg-green-950/30 dark:border-green-900/50' : 'bg-red-50 border border-red-200 dark:bg-red-950/30 dark:border-red-900/50'}`}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 px-4 py-4">
          <div>
            <div className="text-sm text-gray-600 dark:text-gray-400">აქტივები</div>
            <div className="text-lg font-bold font-mono text-blue-700 dark:text-blue-400">{money(totalAssets)}</div>
          </div>
          <div>
            <div className="text-sm text-gray-600 dark:text-gray-400">ვალდებულებები + კაპიტალი</div>
            <div className="text-lg font-bold font-mono text-amber-700 dark:text-amber-400">{money(totalLiabilitiesEquity)}</div>
          </div>
        </div>
        <div className={`flex items-center justify-center gap-2 px-4 py-2 text-center text-sm font-semibold border-t dark:border-dark-50 ${balanced ? 'border-green-200 text-green-700 dark:border-green-900/50 dark:text-green-400' : 'border-red-200 text-red-700 dark:border-red-900/50 dark:text-red-400'}`}>
          <Scale size={15} />
          {balanced ? 'ბალანსი დაბალანსებულია ✓' : `სხვაობა: ${money(totalAssets - totalLiabilitiesEquity)}`}
        </div>
      </div>
    </div>
  )
}
