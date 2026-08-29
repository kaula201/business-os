import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Calculator, Layers } from 'lucide-react'

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

// P0.2: business-meaningful valuation statuses (Odoo-style)
function statusColor(status: string) {
  switch (status) {
    case 'reconciled': return 'text-green-600 dark:text-green-400'
    case 'no_data': return 'text-gray-400 dark:text-gray-500'
    case 'computing': return 'text-blue-600 dark:text-blue-400'
    case 'gl_posting_needed': return 'text-amber-600 dark:text-amber-400'
    default: return 'text-red-600 dark:text-red-400' // difference
  }
}

function statusLabel(status: string, t: (k: string) => string) {
  switch (status) {
    case 'reconciled': return t('შეჯერებულია (მარაგი)')
    case 'no_data': return t('მონაცემები არ არის')
    case 'computing': return t('გამოთვლა მიმდინარეობს')
    case 'gl_posting_needed': return t('GL გატარება საჭიროა')
    default: return t('სხვაობაა')
  }
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

  const { data: methods } = useQuery({
    queryKey: ['inventory-valuation-methods'],
    queryFn: () => inventoryValuationApi.methods().then(r => r.data.data),
  })
  const [methodForm, setMethodForm] = useState({ product_id: '', method: 'avco', standard_cost: '' })
  const [methodOpen, setMethodOpen] = useState(false)
  const setMethod = useMutation({
    mutationFn: () => inventoryValuationApi.setMethod({
      product_id: methodForm.product_id,
      method: methodForm.method as 'standard' | 'avco' | 'fifo',
      ...(methodForm.method === 'standard' && methodForm.standard_cost ? { standard_cost: Number(methodForm.standard_cost) } : {}),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory-valuation-methods'] })
      setMethodOpen(false)
    },
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
            <div className={`mt-1 text-lg font-bold ${statusColor(summary.status)}`}>
              {statusLabel(summary.status, t)}
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
        <button onClick={() => setMethodOpen(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border border-brandgray-200 text-brandgray-700 hover:bg-brandgray-50 dark:border-dark-50 dark:text-gray-300 dark:hover:bg-dark-100">
          <Layers size={15} /> {t('შეფასების მეთოდი')}
        </button>
      </div>

      {(methods || []).length > 0 && (
        <div className="rounded-xl bg-white border border-brandgray-100 shadow-sm dark:bg-dark-200 dark:border-dark-50">
          <div className="px-5 py-3.5 border-b border-brandgray-100 dark:border-dark-50">
            <h2 className="font-semibold text-brandgray-800 dark:text-gray-100">{t('შეფასების მეთოდები')}</h2>
          </div>
          <div className="p-5 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(methods || []).map((m: any) => (
              <div key={m.product_id} className="rounded-lg border border-brandgray-100 p-3 text-sm dark:border-dark-50">
                <div className="font-medium text-brandgray-800 dark:text-gray-100">{m.product_name || m.product_id.slice(0, 8)}</div>
                <div className="mt-1 text-xs uppercase tracking-wide text-brandgray-400 dark:text-gray-500">
                  {m.method === 'fifo' ? 'FIFO' : m.method === 'standard' ? 'Standard' : 'AVCO'}
                  {m.standard_cost != null ? ` · ${money(m.standard_cost)}` : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
      <Modal open={methodOpen} onClose={() => setMethodOpen(false)} title={t('შეფასების მეთოდი')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტი')}</label>
            <select className={inputCls} value={methodForm.product_id} onChange={(e) => setMethodForm({ ...methodForm, product_id: e.target.value })}>
              <option value="">—</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.sku || p.code} — {p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მეთოდი')}</label>
            <select className={inputCls} value={methodForm.method} onChange={(e) => setMethodForm({ ...methodForm, method: e.target.value })}>
              <option value="avco">AVCO — {t('საშუალო შეწონილი')}</option>
              <option value="fifo">FIFO — {t('პირველი შესული, პირველი გასული')}</option>
              <option value="standard">Standard — {t('ფიქსირებული ღირებულება')}</option>
            </select>
          </div>
          {methodForm.method === 'standard' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სტანდარტული ღირებულება')}</label>
              <input type="number" step="0.01" className={inputCls} value={methodForm.standard_cost} onChange={(e) => setMethodForm({ ...methodForm, standard_cost: e.target.value })} />
            </div>
          )}
          <button onClick={() => setMethod.mutate()} disabled={setMethod.isPending || !methodForm.product_id}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
