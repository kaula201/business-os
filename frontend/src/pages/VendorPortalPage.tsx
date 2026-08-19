import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Eye, X } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { suppliersApi, vendorPortalApi } from '../services/api'

interface VendorPortalUser {
  id: string
  supplier_id: string
  email: string
  display_name: string
  status: string
  last_login_at: string | null
  created_at: string
}

interface VendorSummary {
  supplier_id: string
  rfqs: { id: string; rfq_number: string; title: string; status: string; required_date: string | null; line_count: number }[]
  purchase_orders: { id: string; purchase_order_number: string; status: string; total: number; expected_delivery_date: string | null }[]
  invoices: { id: string; supplier_invoice_number: string; status: string; total: number; invoice_date: string; due_date: string }[]
  price_lists: { id: string; product_id: string; price: number; currency: string; valid_from: string | null; valid_to: string | null }[]
  counts: { rfqs: number; purchase_orders: number; invoices: number; price_lists: number }
}

function money(v: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)
}

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function VendorPortalPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [summaryFor, setSummaryFor] = useState<VendorSummary | null>(null)
  const [form, setForm] = useState({ supplier_id: '', email: '', display_name: '', status: 'active' })

  const { data, isLoading } = useQuery({
    queryKey: ['vendor-portal-users'],
    queryFn: () => vendorPortalApi.list({ page_size: 100 }).then(r => r.data.data),
  })
  const items: VendorPortalUser[] = data?.items || []

  const { data: suppliers } = useQuery({
    queryKey: ['suppliers-all-vendor-portal'],
    queryFn: () => suppliersApi.list({ page_size: 100 }).then(r => r.data.data.items),
  })

  const create = useMutation({
    mutationFn: () => vendorPortalApi.create({
      supplier_id: form.supplier_id, email: form.email, display_name: form.display_name, status: form.status,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['vendor-portal-users'] }); setOpen(false); setForm({ supplier_id: '', email: '', display_name: '', status: 'active' }) },
  })

  const remove = useMutation({
    mutationFn: (id: string) => vendorPortalApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vendor-portal-users'] }),
  })

  const showSummary = useMutation({
    mutationFn: (supplierId: string) => vendorPortalApi.supplierSummary(supplierId).then(r => r.data.data),
    onSuccess: (d) => setSummaryFor(d),
  })

  const columns = [
    { key: 'display_name', label: t('სახელი'), priority: true, render: (u: VendorPortalUser) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100">{u.display_name}</span>) },
    { key: 'email', label: t('ელ.ფოსტა'), render: (u: VendorPortalUser) => <span className="text-sm">{u.email}</span> },
    { key: 'status', label: t('სტატუსი'), render: (u: VendorPortalUser) => u.status === 'active'
      ? <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">{t('აქტიური')}</span>
      : <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 dark:bg-dark-100 dark:text-gray-400">{t('გათიშული')}</span> },
    { key: 'last_login_at', label: t('ბოლო შესვლა'), render: (u: VendorPortalUser) => u.last_login_at
      ? <span className="font-mono text-sm">{new Date(u.last_login_at).toLocaleDateString('ka-GE')}</span> : '—' },
    { key: 'actions', label: '', render: (u: VendorPortalUser) => (
      <div className="flex gap-1">
        <button onClick={() => showSummary.mutate(u.supplier_id)} className="p-1.5 rounded-md text-gray-400 hover:text-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900/30" title={t('მომწოდებლის მიმოხილვა')}>
          <Eye size={15} />
        </button>
        <button onClick={() => remove.mutate(u.id)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30">
          <Trash2 size={15} />
        </button>
      </div>) },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('მომწოდებლის პორტალი')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('პორტალის მომხმარებლები — მომწოდებლის წვდომა RFQ-ებზე, შეკვეთებსა და ინვოისებზე')}</p>
        </div>
        <button onClick={() => setOpen(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
          <Plus size={15} /> {t('ახალი პორტალის მომხმარებელი')}
        </button>
      </div>

      <DataTable columns={columns} data={items} isLoading={isLoading} emptyMessage={t('პორტალის მომხმარებლები არ არის')} />

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი პორტალის მომხმარებელი')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მომწოდებელი')}</label>
            <select className={inputCls} value={form.supplier_id} onChange={e => setForm({ ...form, supplier_id: e.target.value })}>
              <option value="">—</option>
              {(suppliers || []).map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სახელი')}</label>
            <input className={inputCls} value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ელ.ფოსტა')}</label>
            <input type="email" className={inputCls} value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სტატუსი')}</label>
            <select className={inputCls} value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>
              <option value="active">{t('აქტიური')}</option>
              <option value="disabled">{t('გათიშული')}</option>
            </select>
          </div>
          <button onClick={() => create.mutate()} disabled={create.isPending || !form.supplier_id || !form.email || !form.display_name}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={!!summaryFor} onClose={() => setSummaryFor(null)} title={t('მომწოდებლის მიმოხილვა')}>
        {summaryFor && (
          <div className="space-y-5">
            <div className="grid grid-cols-4 gap-3">
              <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3">
                <div className="text-xs text-brandgray-500 dark:text-gray-400">{t('RFQ')}</div>
                <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{summaryFor.counts.rfqs}</div>
              </div>
              <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3">
                <div className="text-xs text-brandgray-500 dark:text-gray-400">{t('შეკვეთები')}</div>
                <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{summaryFor.counts.purchase_orders}</div>
              </div>
              <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3">
                <div className="text-xs text-brandgray-500 dark:text-gray-400">{t('ინვოისები')}</div>
                <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{summaryFor.counts.invoices}</div>
              </div>
              <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3">
                <div className="text-xs text-brandgray-500 dark:text-gray-400">{t('ფასების სია')}</div>
                <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{summaryFor.counts.price_lists}</div>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">{t('RFQ-ები')}</h3>
              {summaryFor.rfqs.length === 0 ? (
                <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('RFQ არ არის')}</p>
              ) : (
                <div className="space-y-1.5">
                  {summaryFor.rfqs.map(r => (
                    <div key={r.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                      <span className="font-medium font-mono">{r.rfq_number}</span>
                      <span className="text-brandgray-500 dark:text-gray-400">{r.title}</span>
                      <span className="font-mono font-semibold">{r.line_count} {t('ხაზი')}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">{t('შეკვეთები')}</h3>
              {summaryFor.purchase_orders.length === 0 ? (
                <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('შეკვეთები არ არის')}</p>
              ) : (
                <div className="space-y-1.5">
                  {summaryFor.purchase_orders.map(o => (
                    <div key={o.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                      <span className="font-medium font-mono">{o.purchase_order_number}</span>
                      <span className="text-brandgray-500 dark:text-gray-400">{o.status}</span>
                      <span className="font-mono font-semibold">{money(o.total)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">{t('ინვოისები')}</h3>
              {summaryFor.invoices.length === 0 ? (
                <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('ინვოისები არ არის')}</p>
              ) : (
                <div className="space-y-1.5">
                  {summaryFor.invoices.map(inv => (
                    <div key={inv.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                      <span className="font-medium font-mono">{inv.supplier_invoice_number}</span>
                      <span className="text-brandgray-500 dark:text-gray-400">{new Date(inv.invoice_date).toLocaleDateString('ka-GE')}</span>
                      <span className="font-mono font-semibold">{money(inv.total)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">{t('ფასების სია')}</h3>
              {summaryFor.price_lists.length === 0 ? (
                <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('ფასები არ არის')}</p>
              ) : (
                <div className="space-y-1.5">
                  {summaryFor.price_lists.map(pl => (
                    <div key={pl.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                      <span className="font-medium">{pl.product_id.slice(0, 8)}</span>
                      <span className="font-mono font-semibold">{pl.price} {pl.currency}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
