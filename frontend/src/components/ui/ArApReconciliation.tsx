import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Scale } from 'lucide-react'
import { api } from '../../services/api'

interface ReconSide {
  gl_balance: number
  subledger_total: number
  difference: number
  in_balance: boolean
}

const money = (v: number) => new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)

function SideCard({ title, side }: { title: string; side: ReconSide | undefined }) {
  const { t } = useTranslation()
  if (!side) return null
  return (
    <div className="rounded-xl border border-brandgray-100 bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-brandgray-700 dark:text-gray-300">{title}</div>
        <span className={`badge ${side.in_balance ? 'badge-green' : 'badge-red'}`}>
          {side.in_balance ? t('შეჯერებულია') : t('სხვაობაა')}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-xs text-brandgray-400 dark:text-gray-500">{t('GL ბალანსი')}</div>
          <div className="mt-0.5 text-sm font-semibold text-brandgray-900 dark:text-gray-100">{money(side.gl_balance)}</div>
        </div>
        <div>
          <div className="text-xs text-brandgray-400 dark:text-gray-500">{t('Subledger')}</div>
          <div className="mt-0.5 text-sm font-semibold text-brandgray-900 dark:text-gray-100">{money(side.subledger_total)}</div>
        </div>
        <div>
          <div className="text-xs text-brandgray-400 dark:text-gray-500">{t('სხვაობა')}</div>
          <div className={`mt-0.5 text-sm font-semibold ${side.difference === 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
            {money(side.difference)}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function ArApReconciliation() {
  const { t } = useTranslation()
  const { data, isLoading } = useQuery({
    queryKey: ['ar-ap-reconciliation'],
    queryFn: () => api.get('/analytic/ar-ap-reconciliation').then(r => r.data.data),
  })

  return (
    <section className="card p-5 dark:bg-dark-200 dark:border-dark-50">
      <div className="flex items-center gap-2">
        <Scale size={17} className="text-primary-600 dark:text-primary-400" />
        <h2 className="font-semibold text-brandgray-800 dark:text-gray-100">{t('AR/AP subledger შეჯერება')}</h2>
      </div>
      <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">
        {t('GL საკონტროლო ანგარიშები (1300/2100) vs subledger ჯამები — ჯანსაღი წიგნი ორივე მხარეს ემთხვევა')}
      </p>
      {isLoading ? (
        <div className="mt-4 text-sm text-brandgray-500 dark:text-gray-400">{t('იტვირთება...')}</div>
      ) : (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <SideCard title={t('მოთხოვნები (AR) — 1300')} side={data?.ar} />
          <SideCard title={t('ვალდებულებები (AP) — 2100')} side={data?.ap} />
        </div>
      )}
    </section>
  )
}
