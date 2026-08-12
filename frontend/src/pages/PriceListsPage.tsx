import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Tags } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { productsApi, salesToolsApi } from '../services/api'

interface PriceList {
  id: string
  name: string
  currency: string
  is_default: boolean
  is_active: boolean
  description: string | null
  items: { id: string; product_id: string; price: number; min_quantity: number }[]
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
  const [items, setItems] = useState([{ product_id: '', price: '' }])

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

  const createList = useMutation({
    mutationFn: () => salesToolsApi.createPriceList({
      name: form.name, currency: form.currency,
      items: items.filter(i => i.product_id && i.price).map(i => ({
        product_id: i.product_id, price: Number(i.price), min_quantity: 1,
      })),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['price-lists'] }); setOpen(false); setItems([{ product_id: '', price: '' }]); setForm({ name: '', currency: 'GEL', days: '30', description: '' }) },
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

  const listColumns = [
    { key: 'name', label: 'დასახელება', priority: true, render: (l: PriceList) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100">{l.name}</span>) },
    { key: 'currency', label: 'ვალუტა', render: (l: PriceList) => <span className="font-mono">{l.currency}</span> },
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

      {tab === 'pricelists'
        ? <DataTable columns={listColumns} data={lists} isLoading={isLoading} emptyMessage={t('ფასების სიები არ არის')} />
        : <DataTable columns={termColumns} data={terms} isLoading={termsLoading} emptyMessage={t('გადახდის პირობები არ არის')} />}

      <Modal open={open} onClose={() => setOpen(false)} title={tab === 'pricelists' ? t('ახალი ფასების სია') : t('ახალი გადახდის პირობა')}>
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
              <div className="space-y-2">
                <div className="grid grid-cols-[1fr_100px_28px] gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  <span>{t('პროდუქტი')}</span><span>{t('ფასი')}</span><span />
                </div>
                {items.map((it, idx) => (
                  <div key={idx} className="grid grid-cols-[1fr_100px_28px] gap-2 items-center">
                    <select className={inputCls} value={it.product_id} onChange={e => { const nl = [...items]; nl[idx] = { ...it, product_id: e.target.value }; setItems(nl) }}>
                      <option value="">—</option>
                      {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.sku || p.code} — {p.name}</option>)}
                    </select>
                    <input type="number" step="0.01" className={inputCls} value={it.price} onChange={e => { const nl = [...items]; nl[idx] = { ...it, price: e.target.value }; setItems(nl) }} />
                    <button onClick={() => items.length > 1 && setItems(items.filter((_, i) => i !== idx))} className="text-gray-400 hover:text-red-600"><Trash2 size={15} /></button>
                  </div>
                ))}
                <button onClick={() => setItems([...items, { product_id: '', price: '' }])} className="text-sm text-primary-700 font-medium dark:text-primary-400">+ {t('სტრიქონის დამატება')}</button>
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
