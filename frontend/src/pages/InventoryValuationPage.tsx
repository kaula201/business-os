import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Calculator, Layers, Truck, Factory, ShieldAlert, RefreshCcw, MapPin, FileCheck2 } from 'lucide-react'

import Modal from '../components/ui/Modal'
import { productsApi, inventoryValuationApi, wmsOpsApi, warehousesApi } from '../services/api'

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
  // Inventory Valuation 2.0
  const [negForm, setNegForm] = useState({ product_id: '', negative_stock_allowed: false })
  const [prodForm, setProdForm] = useState({ product_id: '', quantity: '', unit_cost: '' })
  const [adjGlForm, setAdjGlForm] = useState({ product_id: '', quantity_delta: '', unit_cost: '', note: '' })
  const [lcForm, setLcForm] = useState({ landed_cost_id: '' })
  const [recForm, setRecForm] = useState({ warehouse_id: '', product_id: '', counted_quantity: '' })
  const [locForm, setLocForm] = useState({ warehouse_id: '', product_id: '', quantity: '', unit_cost: '' })
  const [v2Error, setV2Error] = useState('')
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

  // Inventory Valuation 2.0 mutations
  const negMut = useMutation({
    mutationFn: () => inventoryValuationApi.setNegativeStock(negForm),
    onSuccess: () => { setV2Error(''); setNegForm({ product_id: '', negative_stock_allowed: false }) },
    onError: (e: any) => setV2Error(e.response?.data?.detail || 'პოლიტიკა ვერ შეინახა'),
  })
  const prodMut = useMutation({
    mutationFn: () => inventoryValuationApi.applyProductionCost(prodForm),
    onSuccess: () => { setV2Error(''); setProdForm({ product_id: '', quantity: '', unit_cost: '' }); qc.invalidateQueries({ queryKey: ['inventory-valuation'] }) },
    onError: (e: any) => setV2Error(e.response?.data?.detail || 'წარმოების ღირებულება ვერ აისახა'),
  })
  const adjGlMut = useMutation({
    mutationFn: () => inventoryValuationApi.adjustToGl(adjGlForm),
    onSuccess: () => { setV2Error(''); setAdjGlForm({ product_id: '', quantity_delta: '', unit_cost: '', note: '' }) },
    onError: (e: any) => setV2Error(e.response?.data?.detail || 'GL კორექტირება ვერ მოხერხდა'),
  })
  const lcMut = useMutation({
    mutationFn: () => inventoryValuationApi.applyLandedCost(lcForm.landed_cost_id),
    onSuccess: () => { setV2Error(''); setLcForm({ landed_cost_id: '' }); qc.invalidateQueries({ queryKey: ['inventory-valuation'] }) },
    onError: (e: any) => setV2Error(e.response?.data?.detail || 'Landed cost ვერ აისახა'),
  })
  const recCreateMut = useMutation({
    mutationFn: () => inventoryValuationApi.createReconciliation({
      warehouse_id: recForm.warehouse_id, period_end: new Date().toISOString().slice(0, 10),
      lines: [{ product_id: recForm.product_id, counted_quantity: Number(recForm.counted_quantity) }],
    }),
    onSuccess: () => { setV2Error(''); setRecForm({ warehouse_id: '', product_id: '', counted_quantity: '' }); qc.invalidateQueries({ queryKey: ['val2-recs'] }) },
    onError: (e: any) => setV2Error(e.response?.data?.detail || 'რეკონსილაცია ვერ შეიქმნა'),
  })
  const recPostMut = useMutation({
    mutationFn: (id: string) => inventoryValuationApi.postReconciliation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['val2-recs'] }),
    onError: (e: any) => setV2Error(e.response?.data?.detail || 'რეკონსილაცია ვერ დაპოსტდა'),
  })
  const locMut = useMutation({
    mutationFn: () => inventoryValuationApi.upsertLocationValuation(locForm),
    onSuccess: () => { setV2Error(''); setLocForm({ warehouse_id: '', product_id: '', quantity: '', unit_cost: '' }); qc.invalidateQueries({ queryKey: ['val2-locs'] }) },
    onError: (e: any) => setV2Error(e.response?.data?.detail || 'მდებარეობის შეფასება ვერ შეინახა'),
  })

  const { data: recs } = useQuery({ queryKey: ['val2-recs'], queryFn: () => inventoryValuationApi.listReconciliations().then((r: any) => r.data.data) })
  const { data: locs } = useQuery({ queryKey: ['val2-locs'], queryFn: () => inventoryValuationApi.listLocationValuations().then((r: any) => r.data.data) })
  const { data: landedCosts } = useQuery({ queryKey: ['val2-lcs'], queryFn: () => wmsOpsApi.listLandedCosts().then((r: any) => r.data.data) })
  const { data: warehouses } = useQuery({ queryKey: ['val2-wh'], queryFn: () => warehousesApi.list().then((r: any) => r.data.data) })

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

      {/* Inventory Valuation 2.0 */}
      <div className="rounded-xl bg-white border border-brandgray-100 shadow-sm dark:bg-dark-200 dark:border-dark-50">
        <div className="px-5 py-3.5 border-b border-brandgray-100 dark:border-dark-50 flex items-center justify-between">
          <h2 className="font-semibold text-brandgray-800 dark:text-gray-100">{t('მარაგების შეფასება 2.0')}</h2>
        </div>
        {v2Error && <div className="mx-5 mt-3 p-3 rounded-lg bg-red-50 text-red-700 text-sm">{v2Error}</div>}
        <div className="p-5 grid md:grid-cols-2 gap-4">
          {/* Landed cost → valuation */}
          <div className="rounded-lg border border-brandgray-100 p-4 dark:border-dark-50">
            <h3 className="font-semibold flex items-center gap-2 text-sm mb-3"><Truck size={15} /> {t('Landed cost → valuation')}</h3>
            <div className="flex gap-2">
              <select className={inputCls} value={lcForm.landed_cost_id} onChange={e => setLcForm({ landed_cost_id: e.target.value })}>
                <option value="">{t('აირჩიეთ landed cost')}</option>
                {(landedCosts || []).filter((l: any) => !l.allocated).map((l: any) => (
                  <option key={l.id} value={l.id}>{l.description} — {l.total_amount} {l.currency}</option>
                ))}
              </select>
              <button className="btn-primary text-sm whitespace-nowrap" onClick={() => lcMut.mutate()} disabled={!lcForm.landed_cost_id}>{t('ჩარიცხვა')}</button>
            </div>
          </div>
          {/* Production cost → valuation */}
          <div className="rounded-lg border border-brandgray-100 p-4 dark:border-dark-50">
            <h3 className="font-semibold flex items-center gap-2 text-sm mb-3"><Factory size={15} /> {t('Production cost → valuation')}</h3>
            <div className="grid grid-cols-3 gap-2">
              <select className={`${inputCls} col-span-1`} value={prodForm.product_id} onChange={e => setProdForm({ ...prodForm, product_id: e.target.value })}>
                <option value="">{t('პროდუქტი')}</option>
                {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <input className={inputCls} placeholder={t('რაოდენობა')} type="number" value={prodForm.quantity} onChange={e => setProdForm({ ...prodForm, quantity: e.target.value })} />
              <input className={inputCls} placeholder={t('თვითღირებულება')} type="number" value={prodForm.unit_cost} onChange={e => setProdForm({ ...prodForm, unit_cost: e.target.value })} />
            </div>
            <button className="btn-primary text-sm w-full mt-2" onClick={() => prodMut.mutate()} disabled={!prodForm.product_id || !prodForm.quantity}>{t('ჩარიცხვა')}</button>
          </div>
          {/* Adjustment → GL */}
          <div className="rounded-lg border border-brandgray-100 p-4 dark:border-dark-50">
            <h3 className="font-semibold flex items-center gap-2 text-sm mb-3"><RefreshCcw size={15} /> {t('Stock adjustment → GL')}</h3>
            <div className="grid grid-cols-3 gap-2">
              <select className={`${inputCls} col-span-1`} value={adjGlForm.product_id} onChange={e => setAdjGlForm({ ...adjGlForm, product_id: e.target.value })}>
                <option value="">{t('პროდუქტი')}</option>
                {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <input className={inputCls} placeholder={t('Δ რაოდენობა')} type="number" value={adjGlForm.quantity_delta} onChange={e => setAdjGlForm({ ...adjGlForm, quantity_delta: e.target.value })} />
              <input className={inputCls} placeholder={t('ფასი')} type="number" value={adjGlForm.unit_cost} onChange={e => setAdjGlForm({ ...adjGlForm, unit_cost: e.target.value })} />
            </div>
            <input className={`${inputCls} mt-2`} placeholder={t('შენიშვნა')} value={adjGlForm.note} onChange={e => setAdjGlForm({ ...adjGlForm, note: e.target.value })} />
            <button className="btn-primary text-sm w-full mt-2" onClick={() => adjGlMut.mutate()} disabled={!adjGlForm.product_id || !adjGlForm.quantity_delta}>{t('GL-ში ასახვა')}</button>
          </div>
          {/* Negative stock policy */}
          <div className="rounded-lg border border-brandgray-100 p-4 dark:border-dark-50">
            <h3 className="font-semibold flex items-center gap-2 text-sm mb-3"><ShieldAlert size={15} /> {t('Negative stock policy')}</h3>
            <div className="flex gap-2 items-end">
              <select className={inputCls} value={negForm.product_id} onChange={e => setNegForm({ ...negForm, product_id: e.target.value })}>
                <option value="">{t('პროდუქტი')}</option>
                {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <label className="flex items-center gap-2 text-sm pb-2 whitespace-nowrap">
                <input type="checkbox" checked={negForm.negative_stock_allowed} onChange={e => setNegForm({ ...negForm, negative_stock_allowed: e.target.checked })} /> {t('ნებადართულია')}
              </label>
              <button className="btn-primary text-sm" onClick={() => negMut.mutate()} disabled={!negForm.product_id}>{t('შენახვა')}</button>
            </div>
          </div>
          {/* Reconciliation */}
          <div className="rounded-lg border border-brandgray-100 p-4 dark:border-dark-50">
            <h3 className="font-semibold flex items-center gap-2 text-sm mb-3"><FileCheck2 size={15} /> {t('Period-end reconciliation')}</h3>
            <div className="grid grid-cols-3 gap-2">
              <select className={inputCls} value={recForm.warehouse_id} onChange={e => setRecForm({ ...recForm, warehouse_id: e.target.value })}>
                <option value="">{t('საწყობი')}</option>
                {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </select>
              <select className={inputCls} value={recForm.product_id} onChange={e => setRecForm({ ...recForm, product_id: e.target.value })}>
                <option value="">{t('პროდუქტი')}</option>
                {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <input className={inputCls} placeholder={t('დათვლილი რაოდ.')} type="number" value={recForm.counted_quantity} onChange={e => setRecForm({ ...recForm, counted_quantity: e.target.value })} />
            </div>
            <button className="btn-primary text-sm w-full mt-2" onClick={() => recCreateMut.mutate()} disabled={!recForm.warehouse_id || !recForm.product_id}>{t('რეკონსილაციის შექმნა')}</button>
            {(recs || []).length > 0 && (
              <div className="mt-3 space-y-1 text-xs">
                {(recs || []).map((r: any) => (
                  <div key={r.id} className="flex justify-between items-center p-1.5 border-b dark:border-dark-50">
                    <span className="font-mono font-semibold">{r.reconciliation_number}</span>
                    <span className="text-gray-500">{r.status} · {r.total_adjustment.toLocaleString('ka-GE')} ₾</span>
                    {r.status === 'draft' && (
                      <button className="text-emerald-600 font-medium" onClick={() => recPostMut.mutate(r.id)}>{t('დაპოსტვა')}</button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
          {/* Location valuation */}
          <div className="rounded-lg border border-brandgray-100 p-4 dark:border-dark-50">
            <h3 className="font-semibold flex items-center gap-2 text-sm mb-3"><MapPin size={15} /> {t('თითო მდებარეობის ღირებულება')}</h3>
            <div className="grid grid-cols-3 gap-2">
              <select className={inputCls} value={locForm.warehouse_id} onChange={e => setLocForm({ ...locForm, warehouse_id: e.target.value })}>
                <option value="">{t('საწყობი')}</option>
                {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </select>
              <select className={inputCls} value={locForm.product_id} onChange={e => setLocForm({ ...locForm, product_id: e.target.value })}>
                <option value="">{t('პროდუქტი')}</option>
                {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <div className="flex gap-1">
                <input className={inputCls} placeholder={t('რაოდ.')} type="number" value={locForm.quantity} onChange={e => setLocForm({ ...locForm, quantity: e.target.value })} />
                <input className={inputCls} placeholder={t('ფასი')} type="number" value={locForm.unit_cost} onChange={e => setLocForm({ ...locForm, unit_cost: e.target.value })} />
              </div>
            </div>
            <button className="btn-primary text-sm w-full mt-2" onClick={() => locMut.mutate()} disabled={!locForm.warehouse_id || !locForm.product_id}>{t('შენახვა')}</button>
            {(locs || []).length > 0 && (
              <div className="mt-3 space-y-1 text-xs">
                {(locs || []).map((l: any) => (
                  <div key={l.id} className="flex justify-between p-1.5 border-b dark:border-dark-50">
                    <span>{l.product_id.slice(0, 8)}</span>
                    <span className="font-mono">{l.quantity} × {l.unit_cost} = {l.total_value} ₾</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
