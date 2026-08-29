import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Eye, X } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { clientsApi, commApi } from '../services/api'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

interface PortalUser {
  id: string
  client_id: string
  email: string
  display_name: string
  status: string
  last_login_at: string | null
  created_at: string
}

interface PortalSummary {
  client_id: string
  outstanding_balance: number
  open_invoices: number
  total_orders: number
  invoices: { id: string; number: string; date: string; due_date: string; total: number; status: string }[]
  orders: { id: string; number: string; date: string; total: number; status: string }[]
}

function money(v: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)
}

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function PortalPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [summaryFor, setSummaryFor] = useState<PortalSummary | null>(null)
  const [form, setForm] = useState({ client_id: '', email: '', display_name: '', status: 'active' })

  const { data, isLoading } = useQuery({
    queryKey: ['portal-users'],
    queryFn: () => commApi.listPortalUsers({ page_size: 100 }).then(r => r.data.data),
  })
  const items: PortalUser[] = data?.items || []

  const { data: clients } = useQuery({
    queryKey: ['clients-all-portal'],
    queryFn: () => clientsApi.list({ page_size: 100 }).then(r => r.data.data.items),
  })

  const create = useMutation({
    mutationFn: () => commApi.createPortalUser({
      client_id: form.client_id, email: form.email, display_name: form.display_name, status: form.status,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['portal-users'] }); setOpen(false); setForm({ client_id: '', email: '', display_name: '', status: 'active' }) },
  })

  const remove = useMutation({
    mutationFn: (id: string) => commApi.deletePortalUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-users'] }),
  })

  const showSummary = useMutation({
    mutationFn: (clientId: string) => commApi.portalSummary(clientId).then(r => r.data.data),
    onSuccess: (d) => setSummaryFor(d),
  })

  const columns = [
    { key: 'display_name', label: t('სახელი'), priority: true, render: (u: PortalUser) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100">{u.display_name}</span>) },
    { key: 'email', label: t('ელ.ფოსტა'), render: (u: PortalUser) => <span className="text-sm">{u.email}</span> },
    { key: 'status', label: t('სტატუსი'), render: (u: PortalUser) => u.status === 'active'
      ? <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">{t('აქტიური')}</span>
      : <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 dark:bg-dark-100 dark:text-gray-400">{t('გათიშული')}</span> },
    { key: 'last_login_at', label: t('ბოლო შესვლა'), render: (u: PortalUser) => u.last_login_at
      ? <span className="font-mono text-sm">{fmtDate(new Date(u.last_login_at))}</span> : '—' },
    { key: 'actions', label: '', render: (u: PortalUser) => (
      <div className="flex gap-1">
        <button onClick={() => showSummary.mutate(u.client_id)} className="p-1.5 rounded-md text-gray-400 hover:text-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900/30" title={t('კლიენტის მიმოხილვა')}>
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
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('კლიენტის პორტალი')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('პორტალის მომხმარებლები — კლიენტის წვდომა ინვოისებსა და შეკვეთებზე')}</p>
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
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('კლიენტი')}</label>
            <select className={inputCls} value={form.client_id} onChange={e => setForm({ ...form, client_id: e.target.value })}>
              <option value="">—</option>
              {(clients || []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
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
          <button onClick={() => create.mutate()} disabled={create.isPending || !form.client_id || !form.email || !form.display_name}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={!!summaryFor} onClose={() => setSummaryFor(null)} title={t('კლიენტის მიმოხილვა')}>
        {summaryFor && (
          <div className="space-y-5">
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3">
                <div className="text-xs text-brandgray-500 dark:text-gray-400">{t('დავალიანება')}</div>
                <div className="text-lg font-bold text-red-600 dark:text-red-400">{money(summaryFor.outstanding_balance)}</div>
              </div>
              <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3">
                <div className="text-xs text-brandgray-500 dark:text-gray-400">{t('ღია ინვოისები')}</div>
                <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{summaryFor.open_invoices}</div>
              </div>
              <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3">
                <div className="text-xs text-brandgray-500 dark:text-gray-400">{t('შეკვეთები')}</div>
                <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{summaryFor.total_orders}</div>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">{t('ინვოისები')}</h3>
              {summaryFor.invoices.length === 0 ? (
                <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('ინვოისები არ არის')}</p>
              ) : (
                <div className="space-y-1.5">
                  {summaryFor.invoices.map(inv => (
                    <div key={inv.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                      <span className="font-medium">{inv.number}</span>
                      <span className="text-brandgray-500 dark:text-gray-400">{fmtDate(new Date(inv.date))}</span>
                      <span className="font-mono font-semibold">{money(inv.total)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">{t('შეკვეთები')}</h3>
              {summaryFor.orders.length === 0 ? (
                <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('შეკვეთები არ არის')}</p>
              ) : (
                <div className="space-y-1.5">
                  {summaryFor.orders.map(o => (
                    <div key={o.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                      <span className="font-medium">{o.number}</span>
                      <span className="text-brandgray-500 dark:text-gray-400">{fmtDate(new Date(o.date))}</span>
                      <span className="font-mono font-semibold">{money(o.total)}</span>
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
