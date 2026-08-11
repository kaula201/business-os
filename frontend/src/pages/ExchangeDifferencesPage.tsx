import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, TrendingDown, TrendingUp } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import { glApi } from '../services/api'

interface ExchangeDiff {
  id: string
  currency: string
  revaluation_date: string
  outstanding_amount: number
  rate: number
  gel_equivalent: number
  previous_gel_equivalent: number | null
  difference: number
  journal_entry_id: string | null
  created_at: string
}

function money(v: number) {
  return new Intl.NumberFormat('ka-GE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v)
}

export default function ExchangeDifferencesPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [runDate, setRunDate] = useState(new Date().toISOString().slice(0, 10))

  const { data, isLoading } = useQuery({
    queryKey: ['gl-exchange-diffs'],
    queryFn: () => glApi.listExchangeDifferences({ page_size: 100 }).then(r => r.data.data),
  })
  const items: ExchangeDiff[] = data?.items || []

  const run = useMutation({
    mutationFn: () => glApi.runExchangeDifferences(runDate),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gl-exchange-diffs'] }),
  })

  const columns = [
    { key: 'currency', label: 'ვალუტა', priority: true, render: (d: ExchangeDiff) => (
      <span className="font-mono font-semibold text-gray-900 dark:text-gray-100">{d.currency}</span>) },
    { key: 'revaluation_date', label: 'თარიღი', render: (d: ExchangeDiff) => new Date(d.revaluation_date).toLocaleDateString('ka-GE') },
    { key: 'outstanding_amount', label: 'ნაშთი', render: (d: ExchangeDiff) => money(d.outstanding_amount) },
    { key: 'rate', label: 'კურსი', render: (d: ExchangeDiff) => money(d.rate) },
    { key: 'gel_equivalent', label: 'GEL ეკვივალენტი', render: (d: ExchangeDiff) => money(d.gel_equivalent) },
    { key: 'difference', label: 'სხვაობა', render: (d: ExchangeDiff) => (
      <span className={`inline-flex items-center gap-1 font-semibold ${d.difference >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
        {d.difference >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
        {money(d.difference)}
      </span>) },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('საკურსო სხვაობები')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('უცხოური ვალუტის მოთხოვნების გადაფასება')}</p>
        </div>
        <div className="flex items-center gap-2">
          <input type="date" value={runDate} onChange={(e) => setRunDate(e.target.value)}
            className="rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          <button onClick={() => run.mutate()} disabled={run.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50">
            <RefreshCw size={15} /> {t('გადაფასება')}
          </button>
        </div>
      </div>

      {run.data?.data && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-800 dark:bg-emerald-900/20 dark:border-emerald-800/50 dark:text-emerald-300">
          {t('გადაფასებულია')}: {run.data.data.revaluated} · {t('ჩანაწერები')}: {run.data.data.posted_entries} · {t('ჯამური სხვაობა')}: {money(run.data.data.total_difference)} GEL
        </div>
      )}

      <DataTable columns={columns} data={items} isLoading={isLoading} emptyMessage={t('საკურსო სხვაობები არ არის')} />
    </div>
  )
}
