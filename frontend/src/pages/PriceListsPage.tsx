import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Tags, Calculator, ShieldAlert } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { clientsApi, productsApi, salesToolsApi } from '../services/api'

interface PriceList {
  id: string
  name: string
  currency: string
  is_default: boolean
  is_active: boolean
  description: string | null
  items: { id: string; product_id: string; price: number; min_quantity: number; currency?: string | null; margin_percent?: number | null }[]
  valid_from?: string | null
  valid_until?: string | null
  segment_id?: string | null
  segment_name?: string | null
  pricing_method?: string
  markup_percent?: number
  min_margin_percent?: number | null
  approval_required?: boolean
}

interface PaymentTerm {
  id: string
  name: string
  days: number
  description: string | null
  is_active: boolean
}

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function PriceListsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'pricelists' | 'terms'>('pricelists')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: '', currency: 'GEL', days: '30', description: '' })
  const [items, setItems] = useState([{ product_id: '', price: '', min_quantity: '1', currency: '', margin_percent: '' }])
  // PriceList 2.0 — rule engine
  const [rules, setRules] = useState({
    valid_from: '', valid_until: '', segment_id: '',
    pricing_method: 'fixed', markup_percent: '0', min_margin_percent: '', approval_required: false,
  })
  // resolve tester
  const [resolveForm, setResolveForm] = useState({ product_id: '', quantity: '1', client_id: '', currency: '' })
  const [resolveResult, setResolveResult] = useState<any>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['price-lists'],
    queryFn: () => salesToolsApi.listPriceLists({ page_size: 100 }).then(r => r.data.data),
  })
  const lists: PriceList[] = data?.items || []

  const { data: termsData, isLoading: termsLoading } = useQuery({
    queryKey: ['payment-terms'],
    queryFn: () => salesToolsApi.listPaymentTerms({ page_size: 100 }).then(r => r.data.data),
  })
  const terms: PaymentTerm[] = termsData?.items || []

  const { data: products } = useQuery({
    queryKey: ['products-all-pl'],
    queryFn: () => productsApi.list({ page_size: 100 }).then(r => r.data.data.items),
  })

  const { data: segments } = useQuery({
    queryKey: ['client-groups'],
    queryFn: () => clientsApi.listGroups().then(r => r.data.data),
  })

  const { data: clients } = useQuery({
    queryKey: ['clients-all-pl'],
    queryFn: () => clientsApi.list({ page_size: 100 }).then(r => r.data.data.items),
  })

  const createList = useMutation({
    mutationFn: () => salesToolsApi.createPriceList({
      name: form.name, currency: form.currency,
      valid_from: rules.valid_from || null, valid_until: rules.valid_until || null,
      segment_id: rules.segment_id || null,
      pricing_method: rules.pricing_method, markup_percent: Number(rules.markup_percent || 0),
      min_margin_percent: rules.min_margin_percent ? Number(rules.min_margin_percent) : null,
      approval_required: rules.approval_required,
      items: items.filter(i => i.product_id && i.price).map(i => ({
        product_id: i.product_id, price: Number(i.price), min_quantity: Number(i.min_quantity || 1),
        currency: i.currency || null, margin_percent: i.margin_percent ? Number(i.margin_percent) : null,
      })),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['price-lists'] }); setOpen(false); setItems([{ product_id: '', price: '', min_quantity: '1', currency: '', margin_percent: '' }]); setForm({ name: '', currency: 'GEL', days: '30', description: '' }); setRules({ valid_from: '', valid_until: '', segment_id: '', pricing_method: 'fixed', markup_percent: '0', min_margin_percent: '', approval_required: false }) },
  })

  const createTerm = useMutation({
    mutationFn: () => salesToolsApi.createPaymentTerm({ name: form.name, days: Number(form.days), description: form.description || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['payment-terms'] }); setOpen(false); setForm({ name: '', currency: 'GEL', days: '30', description: '' }) },
  })

  const removeList = useMutation({
    mutationFn: (id: string) => salesToolsApi.deletePriceList(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['price-lists'] }),
  })
  const removeTerm = useMutation({
    mutationFn: (id: string) => salesToolsApi.deletePaymentTerm(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payment-terms'] }),
  })

  const resolvePrice = useMutation({
    mutationFn: () => salesToolsApi.resolvePrice({
      product_id: resolveForm.product_id, quantity: Number(resolveForm.quantity || 1),
      client_id: resolveForm.client_id || undefined, currency: resolveForm.currency || undefined,
    }).then(r => r.data.data),
    onSuccess: (d) => setResolveResult(d),
  })

  const listColumns = [
    { key: 'name', label: 'დასახელება', priority: true, render: (l: PriceList) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100">{l.name}</span>) },
    { key: 'currency', label: 'ვალუტა', render: (l: PriceList) => <span className="font-mono">{l.currency}</span> },
    { key: 'segment', label: 'სეგმენტი', render: (l: PriceList) => l.segment_name
      ? <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300">{l.segment_name}</span> : '—' },
    { key: 'method', label: 'მეთოდი', render: (l: PriceList) => l.pricing_method === 'cost_plus_markup'
      ? <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">cost+{l.markup_percent}%</span>
      : <span className="text-xs text-gray-400">{t('ფიქსირებული')}</span> },
    { key: 'valid', label: 'მოქმედებს', render: (l: PriceList) => l.valid_from || l.valid_until
      ? <span className="text-xs text-gray-500">{(l.valid_from || '').slice(0, 10)} → {(l.valid_until || '').slice(0, 10)}</span> : '—' },
    { key: 'items', label: 'პოზიციები', render: (l: PriceList) => l.items.length },
    { key: 'is_default', label: 'დეფოლტი', render: (l: PriceList) => l.is_default
      ? <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300">✓</span> : null },
    { key: 'actions', label: '', render: (l: PriceList) => (
      <button onClick={() => removeList.mutate(l.id)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30">
        <Trash2 size={15} />
      </button>) },
  ]

  const termColumns = [
    { key: 'name', label: 'დასახელება', priority: true, render: (p: PaymentTerm) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100">{p.name}</span>) },
    { key: 'days', label: 'დღეები', render: (p: PaymentTerm) => <span className="font-mono">{p.days} {t('დღე')}</span> },
    { key: 'description', label: 'აღწერა', render: (p: PaymentTerm) => p.description || '—' },
    { key: 'actions', label: '', render: (p: PaymentTerm) => (
      <button onClick={() => removeTerm.mutate(p.id)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30">
        <Trash2 size={15} />
      </button>) },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('ფასები და გადახდის პირობები')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('Price lists — კლიენტის ფასები · Payment terms — გადახდის ვადები')}</p>
        </div>
        <button onClick={() => setOpen(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
          <Plus size={15} /> {tab === 'pricelists' ? t('ახალი ფასების სია') : t('ახალი გადახდის პირობა')}
        </button>
      </div>

      <div className="flex gap-1 rounded-lg bg-brandgray-100 p-1 w-fit dark:bg-dark-100">
        <button onClick={() => setTab('pricelists')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium ${tab === 'pricelists' ? 'bg-white shadow-sm text-gray-900 dark:bg-dark-200 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'}`}>
          <Tags size={14} className="inline mr-1 -mt-0.5" />{t('ფასების სიები')}
        </button>
        <button onClick={() => setTab('terms')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium ${tab === 'terms' ? 'bg-white shadow-sm text-gray-900 dark:bg-dark-200 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'}`}>
          {t('გადახდის პირობები')}
        </button>
      </div>

      {tab === 'pricelists' ? (
        <div className="space-y-5">
          <DataTable columns={listColumns} data={lists} isLoading={isLoading} emptyMessage={t('ფასების სიები არ არის')} />

          {/* Rule engine tester */}
          <div className="rounded-xl border border-gray-200 p-4 dark:border-dark-50">
            <h3 className="flex items-center gap-2 font-semibold text-gray-900 dark:text-gray-100">
              <Calculator size={16} className="text-primary-600" /> {t('ფასის გამოთვლა (rule engine)')}
            </h3>
            <div className="mt-3 grid gap-2 sm:grid-cols-5">
              <select className={inputCls} value={resolveForm.product_id} onChange={e => setResolveForm({ ...resolveForm, product_id: e.target.value })}>
                <option value="">{t('პროდუქტი')}</option>
                {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.sku || p.code} — {p.name}</option>)}
              </select>
              <input type="number" min="1" className={inputCls} placeholder={t('რაოდენობა')} value={resolveForm.quantity} onChange={e => setResolveForm({ ...resolveForm, quantity: e.target.value })} />
              <select className={inputCls} value={resolveForm.client_id} onChange={e => setResolveForm({ ...resolveForm, client_id: e.target.value })}>
                <option value="">{t('კლიენტი (სეგმენტი)')}</option>
                {(clients || []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <select className={inputCls} value={resolveForm.currency} onChange={e => setResolveForm({ ...resolveForm, currency: e.target.value })}>
                <option value="">{t('ვალუტა')}</option>
                <option>GEL</option><option>USD</option><option>EUR</option>
              </select>
              <button onClick={() => resolveForm.product_id && resolvePrice.mutate()} disabled={!resolveForm.product_id || resolvePrice.isPending}
                className="px-3 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
                {t('გამოთვლა')}
              </button>
            </div>
            {resolveResult && (
              <div className="mt-3 rounded-lg bg-gray-50 dark:bg-dark-100 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-2xl font-bold text-gray-900 dark:text-gray-100">{resolveResult.price} {resolveResult.currency}</span>
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300">{resolveResult.price_list_name}</span>
                  <span className="text-xs text-gray-500">{t('წესი:')} {resolveResult.rule}</span>
                  {resolveResult.margin_floor_violated && (
                    <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300">
                      <ShieldAlert size={13} /> {t('მინიმალურ მარჟაზე დაბალია — მინიმუმი')} {resolveResult.min_allowed_price} ₾
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : <DataTable columns={termColumns} data={terms} isLoading={termsLoading} emptyMessage={t('გადახდის პირობები არ არის')} />}

      <Modal open={open} onClose={() => setOpen(false)} title={tab === 'pricelists' ? t('ახალი ფასების სია') : t('ახალი გადახდის პირობა')} size="lg">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დასახელება')}</label>
            <input className={inputCls} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder={tab === 'pricelists' ? 'ოპტიმი' : '30 დღე'} />
          </div>
          {tab === 'pricelists' ? (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ვალუტა')}</label>
                  <select className={inputCls} value={form.currency} onChange={e => setForm({ ...form, currency: e.target.value })}>
                    <option>GEL</option><option>USD</option><option>EUR</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('აღწერა')}</label>
                  <input className={inputCls} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
                </div>
              </div>

              {/* Rule engine */}
              <div className="rounded-lg border border-gray-100 dark:border-dark-50 p-3 space-y-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{t('წესები (rule engine)')}</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მოქმედებს დან')}</label>
                    <input type="date" className={inputCls} value={rules.valid_from} onChange={e => setRules({ ...rules, valid_from: e.target.value })} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მოქმედებს მდე')}</label>
                    <input type="date" className={inputCls} value={rules.valid_until} onChange={e => setRules({ ...rules, valid_until: e.target.value })} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('კლიენტის სეგმენტი')}</label>
                    <select className={inputCls} value={rules.segment_id} onChange={e => setRules({ ...rules, segment_id: e.target.value })}>
                      <option value="">—</option>
                      {(segments || []).map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მეთოდი')}</label>
                    <select className={inputCls} value={rules.pricing_method} onChange={e => setRules({ ...rules, pricing_method: e.target.value })}>
                      <option value="fixed">{t('ფიქსირებული')}</option>
                      <option value="cost_plus_markup">cost + markup</option>
                    </select>
                  </div>
                  {rules.pricing_method === 'cost_plus_markup' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('Markup %')}</label>
                      <input type="number" min="0" step="0.1" className={inputCls} value={rules.markup_percent} onChange={e => setRules({ ...rules, markup_percent: e.target.value })} />
                    </div>
                  )}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მინ. მარჟა %')}</label>
                    <input type="number" min="0" step="0.1" className={inputCls} value={rules.min_margin_percent} onChange={e => setRules({ ...rules, min_margin_percent: e.target.value })} />
                  </div>
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                  <input type="checkbox" checked={rules.approval_required} onChange={e => setRules({ ...rules, approval_required: e.target.checked })} className="rounded border-brandgray-300" />
                  {t('Approval, თუ ფასი მინიმალურ მარჟაზე დაბალია')}
                </label>
              </div>

              <div className="space-y-2">
                <div className="grid grid-cols-[1fr_90px_90px_80px_80px_28px] gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  <span>{t('პროდუქტი')}</span><span>{t('ფასი')}</span><span>{t('მინ. რაოდ.')}</span><span>{t('ვალუტა')}</span><span>{t('მარჟა %')}</span><span />
                </div>
                {items.map((it, idx) => (
                  <div key={idx} className="grid grid-cols-[1fr_90px_90px_80px_80px_28px] gap-2 items-center">
                    <select className={inputCls} value={it.product_id} onChange={e => { const nl = [...items]; nl[idx] = { ...it, product_id: e.target.value }; setItems(nl) }}>
                      <option value="">—</option>
                      {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.sku || p.code} — {p.name}</option>)}
                    </select>
                    <input type="number" step="0.01" className={inputCls} value={it.price} onChange={e => { const nl = [...items]; nl[idx] = { ...it, price: e.target.value }; setItems(nl) }} />
                    <input type="number" min="1" className={inputCls} value={it.min_quantity} onChange={e => { const nl = [...items]; nl[idx] = { ...it, min_quantity: e.target.value }; setItems(nl) }} />
                    <select className={inputCls} value={it.currency} onChange={e => { const nl = [...items]; nl[idx] = { ...it, currency: e.target.value }; setItems(nl) }}>
                      <option value="">—</option><option>GEL</option><option>USD</option><option>EUR</option>
                    </select>
                    <input type="number" min="0" step="0.1" className={inputCls} value={it.margin_percent} onChange={e => { const nl = [...items]; nl[idx] = { ...it, margin_percent: e.target.value }; setItems(nl) }} />
                    <button onClick={() => items.length > 1 && setItems(items.filter((_, i) => i !== idx))} className="text-gray-400 hover:text-red-600"><Trash2 size={15} /></button>
                  </div>
                ))}
                <button onClick={() => setItems([...items, { product_id: '', price: '', min_quantity: '1', currency: '', margin_percent: '' }])} className="text-sm text-primary-700 font-medium dark:text-primary-400">+ {t('სტრიქონის დამატება')}</button>
              </div>
            </>
          ) : (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დღეები')}</label>
                <input type="number" min="0" className={inputCls} value={form.days} onChange={e => setForm({ ...form, days: e.target.value })} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('აღწერა')}</label>
                <input className={inputCls} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
              </div>
            </>
          )}
          <button onClick={() => tab === 'pricelists' ? createList.mutate() : createTerm.mutate()}
            disabled={!form.name || (tab === 'pricelists' && items.some(i => !i.product_id || !i.price))}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
