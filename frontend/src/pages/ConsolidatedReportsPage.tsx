import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Scale, CheckCircle2, RotateCcw, Sparkles } from 'lucide-react'

import { glApi } from '../services/api'

interface PlRow { code: string; name: string; account_type: string; balance: number }
interface BsRow { code: string; name: string; account_type: string; balance: number }

function money(v: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)
}

function AccountRows({ rows }: { rows: PlRow[] | BsRow[] }) {
  if (!rows.length) return <p className="text-sm text-brandgray-400 dark:text-gray-500">—</p>
  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <div key={r.code} className="flex items-center justify-between text-sm">
          <span className="text-brandgray-600 dark:text-gray-400">
            <span className="font-mono text-xs text-brandgray-400 dark:text-gray-500 mr-2">{r.code}</span>{r.name}
          </span>
          <span className="font-semibold text-gray-900 dark:text-gray-100">{money(r.balance)}</span>
        </div>
      ))}
    </div>
  )
}

export default function ConsolidatedReportsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const today = new Date().toISOString().slice(0, 10)
  const [monthStart] = useState(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`
  })

  const { data: companies } = useQuery({
    queryKey: ['gl-consolidated-companies'],
    queryFn: () => glApi.consolidatedCompanies().then(r => r.data.data),
  })

  const { data: pl, isLoading: plLoading } = useQuery({
    queryKey: ['gl-consolidated-pl', monthStart, today],
    queryFn: () => glApi.consolidatedProfitLoss({ date_from: monthStart, date_to: today }).then(r => r.data.data),
  })

  const { data: bs, isLoading: bsLoading } = useQuery({
    queryKey: ['gl-consolidated-bs', today],
    queryFn: () => glApi.consolidatedBalanceSheet({ as_of_date: today }).then(r => r.data.data),
  })
  const { data: eliminations = [] } = useQuery({
    queryKey: ['consolidation-eliminations'],
    queryFn: () => glApi.consolidationEliminations().then(r => r.data.data),
  })
  const approve = useMutation({ mutationFn: (id: string) => glApi.approveConsolidationElimination(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['consolidation-eliminations'] }) })
  const reverse = useMutation({ mutationFn: (id: string) => glApi.reverseConsolidationElimination(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['consolidation-eliminations'] }) })
  const autoDetect = useMutation({
    mutationFn: () => glApi.autoDetectConsolidationEliminations().then(r => r.data.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['consolidation-eliminations'] }),
  })

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('კონსოლიდირებული ანგარიშები')}</h1>
        <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('მრავალკომპანიის აგრეგირებული ფინანსური ანგარიშები')}</p>
      </div>

      <div className="flex items-center gap-2 rounded-xl bg-brandgray-50 border border-brandgray-100 px-4 py-3 text-sm dark:bg-dark-100 dark:border-dark-50">
        <Building2 size={16} className="text-primary-600 dark:text-primary-400" />
        <span className="font-medium text-brandgray-700 dark:text-gray-300">{t('კომპანიები ანგარიშში')}:</span>
        <span className="text-brandgray-600 dark:text-gray-400">
          {(companies || []).map((c: any) => c.name).join(', ') || '—'}
        </span>
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        {/* P&L */}
        <div className="rounded-xl bg-white border border-brandgray-100 shadow-sm dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-2 px-5 py-3.5 border-b border-brandgray-100 dark:border-dark-50">
            <Scale size={16} className="text-primary-600 dark:text-primary-400" />
            <h2 className="font-semibold text-brandgray-800 dark:text-gray-100">{t('მოგება-ზარალი')}</h2>
            {plLoading && <span className="text-xs text-brandgray-400">…</span>}
          </div>
          <div className="p-5 space-y-5">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-brandgray-400 mb-2 dark:text-gray-500">{t('შემოსავლები')}</h3>
              <AccountRows rows={pl?.income_accounts || []} />
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-brandgray-400 mb-2 dark:text-gray-500">{t('ხარჯები')}</h3>
              <AccountRows rows={pl?.expense_accounts || []} />
            </div>
            <div className="pt-3 border-t border-brandgray-100 dark:border-dark-50 space-y-1.5">
              <div className="flex justify-between text-sm text-brandgray-600 dark:text-gray-400">
                <span>{t('ჯამური შემოსავალი')}</span><span className="font-semibold">{money(pl?.total_income || 0)}</span>
              </div>
              <div className="flex justify-between text-sm text-brandgray-600 dark:text-gray-400">
                <span>{t('ჯამური ხარჯები')}</span><span className="font-semibold">{money(pl?.total_expenses || 0)}</span>
              </div>
              <div className="flex justify-between font-bold text-gray-900 dark:text-gray-100">
                <span>{t('წმინდა მოგება')}</span><span className={pl?.net_income >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}>{money(pl?.net_income || 0)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Balance Sheet */}
        <div className="rounded-xl bg-white border border-brandgray-100 shadow-sm dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-2 px-5 py-3.5 border-b border-brandgray-100 dark:border-dark-50">
            <Scale size={16} className="text-primary-600 dark:text-primary-400" />
            <h2 className="font-semibold text-brandgray-800 dark:text-gray-100">{t('ბალანსი')}</h2>
            {bsLoading && <span className="text-xs text-brandgray-400">…</span>}
          </div>
          <div className="p-5 space-y-5">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-brandgray-400 mb-2 dark:text-gray-500">{t('აქტივები')}</h3>
              <AccountRows rows={bs?.asset_accounts || []} />
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-brandgray-400 mb-2 dark:text-gray-500">{t('ვალდებულებები')}</h3>
              <AccountRows rows={bs?.liability_accounts || []} />
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-brandgray-400 mb-2 dark:text-gray-500">{t('კაპიტალი')}</h3>
              <AccountRows rows={bs?.equity_accounts || []} />
            </div>
            <div className="pt-3 border-t border-brandgray-100 dark:border-dark-50 space-y-1.5">
              <div className="flex justify-between text-sm text-brandgray-600 dark:text-gray-400">
                <span>{t('აქტივები სულ')}</span><span className="font-semibold">{money(bs?.total_assets || 0)}</span>
              </div>
              <div className="flex justify-between text-sm text-brandgray-600 dark:text-gray-400">
                <span>{t('ვალდებულებები სულ')}</span><span className="font-semibold">{money(bs?.total_liabilities || 0)}</span>
              </div>
              <div className="flex justify-between text-sm text-brandgray-600 dark:text-gray-400">
                <span>{t('კაპიტალი სულ')}</span><span className="font-semibold">{money(bs?.total_equity || 0)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl bg-white border border-brandgray-100 shadow-sm dark:bg-dark-200 dark:border-dark-50">
        <div className="flex items-center gap-2 px-5 py-3.5 border-b border-brandgray-100 dark:border-dark-50">
          <Building2 size={16} className="text-primary-600" />
          <h2 className="font-semibold text-brandgray-800 dark:text-gray-100">{t('კონსოლიდაციის გამორიცხვები')}</h2>
          <div className="ml-auto">
            <button
              onClick={() => autoDetect.mutate()}
              disabled={autoDetect.isPending}
              className="btn-secondary text-xs flex items-center gap-1"
            >
              <Sparkles size={14} />
              {autoDetect.isPending ? t('მუშავდება...') : t('ავტო-გამოვლენა')}
            </button>
          </div>
        </div>
        {autoDetect.data && (
          <div className="px-5 py-2 text-sm text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-900/20 border-b border-emerald-100 dark:border-emerald-900/30">
            {t('ავტო-გამოვლენა დასრულდა')}: {autoDetect.data.created} {t('შექმნილი')}, {autoDetect.data.skipped} {t('არსებული')}
          </div>
        )}
        <div className="divide-y divide-brandgray-100 dark:divide-dark-50">{eliminations.length === 0 ? <p className="p-5 text-sm text-brandgray-400">{t('მონაცემები არ არის')}</p> : eliminations.map((e: any) => <div key={e.id} className="flex items-center justify-between gap-3 p-4 text-sm"><div><span className="font-mono text-xs mr-2">{e.revenue_account} → {e.expense_account}</span><span>{money(e.amount)}</span><span className="ml-2 text-brandgray-400">{e.status}</span></div><div className="flex gap-2">{e.status === 'draft' && <button onClick={() => approve.mutate(e.id)} className="btn-secondary text-xs flex items-center gap-1"><CheckCircle2 size={14}/>{t('დადასტურება')}</button>}{e.status === 'approved' && <button onClick={() => reverse.mutate(e.id)} className="btn-secondary text-xs text-red-600 flex items-center gap-1"><RotateCcw size={14}/>{t('გაუქმება')}</button>}</div></div>)}</div>
      </div>
    </div>
  )
}