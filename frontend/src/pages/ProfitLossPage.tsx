import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { glApi } from '../services/api'
import { TrendingUp, TrendingDown } from 'lucide-react'

function money(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

function SectionHeader({ label, positive }: { label: string; positive: boolean }) {
  return (
    <div className={`border-b px-4 py-2 text-sm font-semibold ${positive
      ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-900/50 dark:bg-green-950/40 dark:text-green-300'
      : 'border-red-200 bg-red-50 text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300'}`}>
      {label}
    </div>
  )
}

export default function ProfitLossPage() {
  const { t } = useTranslation()
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
  const profitable = netProfit >= 0

  const renderTable = (
    title: string,
    rows: { code: string; name: string; balance: number }[],
    total: number,
    positive: boolean,
    amountClass: string,
    footerClass: string,
  ) => (
    <div className="card overflow-hidden">
      <SectionHeader label={title} positive={positive} />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:border-dark-50 dark:text-gray-400">
              <th className="px-4 py-2">{t('კოდი')}</th>
              <th className="px-4 py-2">{t('სახელი')}</th>
              <th className="px-4 py-2 text-right">{t('თანხა')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={3} className="px-4 py-6 text-center text-gray-400 dark:text-gray-500">{t('მონაცემები არ არის')}</td></tr>
            ) : rows.map(a => (
              <tr key={a.code} className="border-b border-gray-100 hover:bg-gray-50 dark:border-dark-50 dark:hover:bg-dark-100">
                <td className="px-4 py-2 font-mono text-gray-900 dark:text-gray-200">{a.code}</td>
                <td className="px-4 py-2 text-gray-900 dark:text-gray-200">{a.name}</td>
                <td className={`px-4 py-2 text-right font-mono ${amountClass}`}>{money(a.balance)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className={`border-t-2 ${footerClass}`}>
              <td colSpan={2} className="px-4 py-2 text-sm font-semibold">{title}</td>
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('მოგება-ზარალი')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('Profit & Loss — შემოსავლები და ხარჯები პერიოდის მიხედვით')}</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600 dark:text-gray-400">{t('დან:')}</label>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="input w-40" />
          <label className="text-sm text-gray-600 dark:text-gray-400">{t('მდე:')}</label>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="input w-40" />
        </div>
      </div>

      {isLoading ? (
        <div className="card py-12 text-center text-gray-500 dark:text-gray-400" role="status">{t('იტვირთება...')}</div>
      ) : (
        <div className="space-y-6">
          {renderTable(
            'მთლიანი შემოსავალი', income, totalIncome, true,
            'text-green-700 dark:text-green-400',
            'border-green-300 bg-green-50 text-green-800 dark:border-green-900/60 dark:bg-green-950/40 dark:text-green-300',
          )}

          {renderTable(
            'მთლიანი ხარჯი', expenses, totalExpenses, false,
            'text-red-700 dark:text-red-400',
            'border-red-300 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300',
          )}

          <div className={`card ${profitable
            ? 'bg-green-50 border border-green-200 dark:bg-green-950/30 dark:border-green-900/50'
            : 'bg-red-50 border border-red-200 dark:bg-red-950/30 dark:border-red-900/50'}`}>
            <div className="flex justify-between items-center px-4 py-4">
              <span className="flex items-center gap-2 text-lg font-bold text-gray-900 dark:text-gray-100">
                {profitable ? <TrendingUp size={20} className="text-green-600 dark:text-green-400" /> : <TrendingDown size={20} className="text-red-600 dark:text-red-400" />}
                {profitable ? 'წმინდა მოგება' : 'წმინდა ზარალი'}
              </span>
              <span className={`text-xl font-bold font-mono ${profitable ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>
                {money(Math.abs(netProfit))}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
