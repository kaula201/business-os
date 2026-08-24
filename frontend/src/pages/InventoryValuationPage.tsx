import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Calculator } from 'lucide-react'

import Modal from '../components/ui/Modal'
import { productsApi, inventoryValuationApi } from '../services/api'

interface Valuation {
  product_id: string
  quantity: number
  weighted_avg_cost: number
  total_value: number
}

function money(v: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)
}

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function InventoryValuationPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ product_id: '', quantity: '', unit_cost: '' })
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: products } = useQuery({
    queryKey: ['products-all'],
    queryFn: () => productsApi.list({ page_size: 100 }).then(r => r.data.data.items),
  })

  const { data: valuation } = useQuery({
    queryKey: ['inventory-valuation', selectedId],
    queryFn: () => inventoryValuationApi.get(selectedId!).then(r => r.data),
    enabled: !!selectedId,
  })

  const { data: summary } = useQuery({
    queryKey: ['inventory-valuation-summary'],
    queryFn: () => inventoryValuationApi.summary().then(r => r.data),
  })

  const adjust = useMutation({
    mutationFn: () => inventoryValuationApi.adjust({
      product_id: form.product_id, quantity: Number(form.quantity), unit_cost: Number(form.unit_cost),
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['inventory-valuation'] })
      setSelectedId(form.product_id)
      setOpen(false)
    },
  })

  const v: Valuation | null = valuation || null

  return (
    <div className="space-y-5">
      {summary && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <div className="text-xs text-gray-500 dark:text-gray-400">{t('პროდუქტები')}</div>
            <div className="mt-1 text-lg font-bold text-brandgray-900 dark:text-gray-100">{summary.total_products}</div>
          </div>
          <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <div className="text-xs text-gray-500 dark:text-gray-400">{t('მარაგის ღირებულება (შეფასება)')}</div>
            <div className="mt-1 text-lg font-bold text-brandgray-900 dark:text-gray-100">{money(summary.total_value)}</div>
          </div>
          <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <div className="text-xs text-gray-500 dark:text-gray-400">{t('GL 1200 ბალანსი')}</div>
            <div className="mt-1 text-lg font-bold text-brandgray-900 dark:text-gray-100">{money(summary.gl_inventory_balance)}</div>
          </div>
          <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <div className="text-xs text-gray-500 dark:text-gray-400">{t('სხვაობა')}</div>
            <div className={`mt-1 text-lg font-bold ${summary.reconciled ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
              {money(summary.difference)}
            </div>
          </div>
          <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <div className="text-xs text-gray-500 dark:text-gray-400">{t('სტატუსი')}</div>
            <div className={`mt-1 text-lg font-bold ${summary.reconciled ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
              {summary.reconciled ? t('შეჯერებულია (მარაგი)') : t('არ არის შეჯერებული (მარაგი)')}
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('მარაგების შეფასება')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('საშუალო შეწონილი ღირებულება (WAC)')}</p>
        </div>
        <button onClick={() => setOpen(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
          <Calculator size={15} /> {t('კორექტირება')}
        </button>
      </div>

      {selectedId && (
        <div className="rounded-xl bg-white border border-brandgray-100 shadow-sm dark:bg-dark-200 dark:border-dark-50">
          <div className="px-5 py-3.5 border-b border-brandgray-100 dark:border-dark-50">
            <h2 className="font-semibold text-brandgray-800 dark:text-gray-100">{t('მიმდინარე შეფასება')}</h2>
          </div>
          <div className="p-5 grid sm:grid-cols-3 gap-4">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-brandgray-400 dark:text-gray-500">{t('რაოდენობა')}</div>
              <div className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{v ? v.quantity : '—'}</div>
            </div>
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-brandgray-400 dark:text-gray-500">{t('საშუალო ღირებულება')}</div>
              <div className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{v ? money(v.weighted_avg_cost) : '—'}</div>
            </div>
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-brandgray-400 dark:text-gray-500">{t('ჯამური ღირებულება')}</div>
              <div className="text-2xl font-bold text-primary-700 dark:text-primary-400 mt-1">{v ? money(v.total_value) : '—'}</div>
            </div>
          </div>
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={t('მარაგების კორექტირება')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტი')}</label>
            <select className={inputCls} value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value })}>
              <option value="">—</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.sku || p.code} — {p.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('რაოდენობა')}</label>
              <input type="number" step="0.001" className={inputCls} value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ერთეულის ღირებულება')}</label>
              <input type="number" step="0.01" className={inputCls} value={form.unit_cost} onChange={(e) => setForm({ ...form, unit_cost: e.target.value })} />
            </div>
          </div>
          <button onClick={() => adjust.mutate()} disabled={adjust.isPending || !form.product_id || !form.quantity || !form.unit_cost}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
