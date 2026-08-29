import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, RefreshCw, Trash2 } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { clientsApi, commApi } from '../services/api'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

interface Subscription {
  id: string
  client_id: string
  plan: string
  amount: number
  frequency: string
  start_date: string | null
  end_date: string | null
  next_billing_date: string | null
  status: string
}

function money(v: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)
}

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function SubscriptionsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ client_id: '', plan: '', amount: '', frequency: 'monthly', start_date: new Date().toISOString().slice(0, 10) })

  const { data, isLoading } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => commApi.listSubscriptions({ page_size: 100 }).then(r => r.data.data),
  })
  const items: Subscription[] = data?.items || []

  const { data: clients } = useQuery({
    queryKey: ['clients-all-sub'],
    queryFn: () => clientsApi.list({ page_size: 100 }).then(r => r.data.data.items),
  })

  const create = useMutation({
    mutationFn: () => commApi.createSubscription({
      client_id: form.client_id, plan: form.plan, amount: Number(form.amount),
      frequency: form.frequency, start_date: form.start_date, status: 'active',
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['subscriptions'] }); setOpen(false); setForm({ client_id: '', plan: '', amount: '', frequency: 'monthly', start_date: new Date().toISOString().slice(0, 10) }) },
  })

  const renew = useMutation({
    mutationFn: (id: string) => commApi.renewSubscription(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subscriptions'] }),
  })

  const remove = useMutation({
    mutationFn: (id: string) => commApi.deleteSubscription(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subscriptions'] }),
  })

  const freqLabels: Record<string, string> = { monthly: 'თვიური', yearly: 'წლიური', one_time: 'ერთჯერადი' }

  const columns = [
    { key: 'plan', label: 'გეგმა', priority: true, render: (s: Subscription) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100">{s.plan}</span>) },
    { key: 'amount', label: 'თანხა', render: (s: Subscription) => <span className="font-mono font-semibold">{money(s.amount)}</span> },
    { key: 'frequency', label: 'სიხშირე', render: (s: Subscription) => t(freqLabels[s.frequency] || s.frequency) },
    { key: 'next_billing_date', label: 'შემდეგი გადახდა', render: (s: Subscription) => s.next_billing_date
      ? <span className="font-mono text-sm">{fmtDate(new Date(s.next_billing_date))}</span> : '—' },
    { key: 'status', label: 'სტატუსი', render: (s: Subscription) => s.status === 'active'
      ? <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">{t('აქტიური')}</span>
      : <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 dark:bg-dark-100 dark:text-gray-400">{t(s.status)}</span> },
    { key: 'actions', label: '', render: (s: Subscription) => (
      <div className="flex gap-1">
        {s.status === 'active' && (
          <button onClick={() => renew.mutate(s.id)} className="p-1.5 rounded-md text-gray-400 hover:text-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900/30" title={t('განახლება')}>
            <RefreshCw size={15} />
          </button>
        )}
        <button onClick={() => remove.mutate(s.id)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30">
          <Trash2 size={15} />
        </button>
      </div>) },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('გამოწერები')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('რეკურენტული გადახდები — კლიენტის გამოწერები')}</p>
        </div>
        <button onClick={() => setOpen(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
          <Plus size={15} /> {t('ახალი გამოწერა')}
        </button>
      </div>

      <DataTable columns={columns} data={items} isLoading={isLoading} emptyMessage={t('გამოწერები არ არის')} />

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი გამოწერა')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('კლიენტი')}</label>
            <select className={inputCls} value={form.client_id} onChange={e => setForm({ ...form, client_id: e.target.value })}>
              <option value="">—</option>
              {(clients || []).map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('გეგმა')}</label>
            <input className={inputCls} value={form.plan} onChange={e => setForm({ ...form, plan: e.target.value })} placeholder="პრემიუმი" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('თანხა')}</label>
              <input type="number" step="0.01" className={inputCls} value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სიხშირე')}</label>
              <select className={inputCls} value={form.frequency} onChange={e => setForm({ ...form, frequency: e.target.value })}>
                <option value="monthly">თვიური</option>
                <option value="yearly">წლიური</option>
                <option value="one_time">ერთჯერადი</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დაწყების თარიღი')}</label>
            <input type="date" className={inputCls} value={form.start_date} onChange={e => setForm({ ...form, start_date: e.target.value })} />
          </div>
          <button onClick={() => create.mutate()} disabled={create.isPending || !form.client_id || !form.plan || !form.amount}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
