import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { glApi } from '../services/api'
import type { TrialBalanceAccount } from '../types'

function money(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

const typeLabels: Record<string, string> = {
  asset: 'აქტივები',
  liability: 'ვალდებულებები',
  equity: 'კაპიტალი',
  income: 'შემოსავლები',
  expense: 'ხარჯები',
}

export default function TrialBalancePage() {
  const today = new Date().toISOString().slice(0, 10)
  const [asOfDate, setAsOfDate] = useState(today)

  const { data, isLoading } = useQuery({
    queryKey: ['gl-trial-balance', asOfDate],
    queryFn: () => glApi.trialBalance({ as_of_date: asOfDate }).then(r => r.data.data),
  })

  const accounts: TrialBalanceAccount[] = data?.accounts || []

  const grouped = accounts.reduce<Record<string, TrialBalanceAccount[]>>((acc, a) => {
    const group = typeLabels[a.account_type] || a.account_type
    if (!acc[group]) acc[group] = []
    acc[group].push(a)
    return acc
  }, {})

  const totals = accounts.reduce((sum, a) => ({
    debit: sum.debit + a.total_debit,
    credit: sum.credit + a.total_credit,
  }), { debit: 0, credit: 0 })

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">საცდელი ბალანსი</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Trial Balance — ანგარიშების ნაშთები მოცემულ თარიღზე</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600 dark:text-gray-400">თარიღი:</label>
          <input type="date" value={asOfDate} onChange={e => setAsOfDate(e.target.value)} className="input w-44" />
        </div>
      </div>

      {isLoading ? (
        <div className="card py-12 text-center text-gray-500 dark:text-gray-400">იტვირთება...</div>
      ) : accounts.length === 0 ? (
        <div className="card py-12 text-center text-gray-500 dark:text-gray-400">საცდელი ბალანსის მონაცემები არ არის</div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([group, items]) => (
            <div key={group} className="card overflow-hidden">
              <div className="border-b border-gray-200 dark:border-dark-50 bg-gray-50 dark:bg-dark-100 px-4 py-2 text-sm font-semibold text-gray-700 dark:text-gray-300">{group}</div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-dark-50 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      <th className="px-4 py-2">კოდი</th>
                      <th className="px-4 py-2">სახელი</th>
                      <th className="px-4 py-2 text-right">დებეტი</th>
                      <th className="px-4 py-2 text-right">კრედიტი</th>
                      <th className="px-4 py-2 text-right">ნაშთი</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map(a => (
                      <tr key={a.code} className="border-b border-gray-100 dark:border-dark-50 hover:bg-gray-50 dark:hover:bg-dark-100 dark:bg-dark-100">
                        <td className="px-4 py-2 font-mono text-gray-900 dark:text-gray-100">{a.code}</td>
                        <td className="px-4 py-2 text-gray-900 dark:text-gray-100">{a.name}</td>
                        <td className="px-4 py-2 text-right font-mono text-green-700">{a.total_debit > 0 ? money(a.total_debit) : ''}</td>
                        <td className="px-4 py-2 text-right font-mono text-red-700">{a.total_credit > 0 ? money(a.total_credit) : ''}</td>
                        <td className={`px-4 py-2 text-right font-mono font-semibold ${a.balance >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                          {money(Math.abs(a.balance))} {a.balance >= 0 ? 'Dr' : 'Cr'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}

          <div className="card bg-primary-50">
            <div className="flex justify-between px-4 py-3 text-sm font-semibold">
              <span>ჯამური დებეტი</span>
              <span className="font-mono text-green-700">{money(totals.debit)}</span>
            </div>
            <div className="flex justify-between px-4 py-3 text-sm font-semibold border-t border-primary-200">
              <span>ჯამური კრედიტი</span>
              <span className="font-mono text-red-700">{money(totals.credit)}</span>
            </div>
            <div className="flex justify-between px-4 py-3 text-sm font-semibold border-t border-primary-200">
              <span>სხვაობა</span>
              <span className={`font-mono ${totals.debit === totals.credit ? 'text-green-700' : 'text-red-700'}`}>
                {totals.debit === totals.credit ? 'დაბალანსებულია ✓' : money(totals.debit - totals.credit)}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
