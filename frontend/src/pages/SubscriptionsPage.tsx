import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BarChart3, Pause, Play, Plus, RefreshCw, Trash2, XCircle, Zap } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { clientsApi, commApi } from '../services/api'
import { fmtDate } from '../lib/format'

interface Subscription {
  id: string
  client_id: string
  plan: string
  plan_id: string | null
  plan_version: number
  amount: number
  frequency: string
  start_date: string | null
  end_date: string | null
  next_billing_date: string | null
  status: string
  billing_attempts: number
  max_billing_attempts: number
  last_billing_error: string | null
  last_billed_at: string | null
  paused_at: string | null
  paused_reason: string | null
  cancelled_at: string | null
}

interface Plan {
  id: string
  code: string
  name: string
  version: number
  amount: number
  frequency: string
  is_active: boolean
}

function money(v: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)
}

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function SubscriptionsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [planOpen, setPlanOpen] = useState(false)
  const [form, setForm] = useState({ client_id: '', plan: '', amount: '', frequency: 'monthly', start_date: new Date().toISOString().slice(0, 10) })
  const [planForm, setPlanForm] = useState({ code: '', name: '', amount: '', frequency: 'monthly' })
  const [billingMsg, setBillingMsg] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => commApi.listSubscriptions({ page_size: 100 }).then(r => r.data.data),
  })
  const items: Subscription[] = data?.items || []

  const { data: plansData } = useQuery({
    queryKey: ['subscription-plans'],
    queryFn: () => commApi.listPlans({ page_size: 100 }).then(r => r.data.data),
  })
  const plans: Plan[] = plansData?.items || []

  const { data: analytics } = useQuery({
    queryKey: ['subscription-analytics'],
    queryFn: () => commApi.subscriptionAnalytics().then(r => r.data.data),
  })

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

  const createPlan = useMutation({
    mutationFn: () => commApi.createPlan({
      code: planForm.code, name: planForm.name, amount: Number(planForm.amount), frequency: planForm.frequency,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['subscription-plans'] }); setPlanOpen(false); setPlanForm({ code: '', name: '', amount: '', frequency: 'monthly' }) },
  })

  const renew = useMutation({
    mutationFn: (id: string) => commApi.renewSubscription(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subscriptions'] }),
  })
  const remove = useMutation({
    mutationFn: (id: string) => commApi.deleteSubscription(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subscriptions'] }),
  })
  // Subscriptions 2.0
  const runBilling = useMutation({
    mutationFn: () => commApi.runBilling().then(r => r.data.data),
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ['subscriptions'] }); setBillingMsg(`${t('დარიცხულია:')} ${d.billed}, ${t('შეცდომა:')} ${d.failed}`) },
  })
  const retry = useMutation({
    mutationFn: (id: string) => commApi.retryBilling(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subscriptions'] }),
  })
  const pause = useMutation({
    mutationFn: (id: string) => commApi.pauseSubscription(id, { reason: 'მომხმარებლის მოთხოვნით' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subscriptions'] }),
  })
  const resume = useMutation({
    mutationFn: (id: string) => commApi.resumeSubscription(id, { prorate: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subscriptions'] }),
  })
  const cancel = useMutation({
    mutationFn: (id: string) => commApi.cancelSubscription(id, { reason: 'გაუქმება' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subscriptions'] }),
  })
  const changePlan = useMutation({
    mutationFn: ({ id, plan_id }: { id: string; plan_id: string }) => commApi.changePlan(id, { plan_id, prorate: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['subscriptions'] }),
  })

  const freqLabels: Record<string, string> = { monthly: 'თვიური', yearly: 'წლიური', one_time: 'ერთჯერადი' }

  const statusBadge = (s: string) => {
    const map: Record<string, { label: string; cls: string }> = {
      active: { label: t('აქტიური'), cls: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' },
      paused: { label: t('პაუზირებული'), cls: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
      past_due: { label: t('ვადაგადაცილებული'), cls: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300' },
      cancelled: { label: t('გაუქმებული'), cls: 'bg-gray-100 text-gray-500 dark:bg-dark-100 dark:text-gray-400' },
      expired: { label: t('ვადაგასული'), cls: 'bg-gray-100 text-gray-500 dark:bg-dark-100 dark:text-gray-400' },
    }
    const b = map[s] || map.active
    return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${b.cls}`}>{b.label}</span>
  }

  const columns = [
    { key: 'plan', label: 'გეგმა', priority: true, render: (s: Subscription) => (
      <div>
        <span className="font-semibold text-gray-900 dark:text-gray-100">{s.plan}</span>
        {s.plan_version > 1 && <span className="ml-1.5 text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 dark:bg-dark-100 dark:text-gray-400">v{s.plan_version}</span>}
      </div>) },
    { key: 'amount', label: 'თანხა', render: (s: Subscription) => <span className="font-mono font-semibold">{money(s.amount)}</span> },
    { key: 'frequency', label: 'სიხშირე', render: (s: Subscription) => t(freqLabels[s.frequency] || s.frequency) },
    { key: 'next_billing_date', label: 'შემდეგი გადახდა', render: (s: Subscription) => s.next_billing_date
      ? <span className="font-mono text-sm">{fmtDate(new Date(s.next_billing_date))}</span> : '—' },
    { key: 'status', label: 'სტატუსი', render: (s: Subscription) => statusBadge(s.status) },
    { key: 'actions', label: '', render: (s: Subscription) => (
      <div className="flex gap-1">
        {s.status === 'active' && (
          <>
            <button onClick={() => renew.mutate(s.id)} className="p-1.5 rounded-md text-gray-400 hover:text-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900/30" title={t('განახლება')}><RefreshCw size={15} /></button>
            <button onClick={() => pause.mutate(s.id)} className="p-1.5 rounded-md text-gray-400 hover:text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-900/30" title={t('პაუზა')}><Pause size={15} /></button>
            <button onClick={() => cancel.mutate(s.id)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30" title={t('გაუქმება')}><XCircle size={15} /></button>
          </>
        )}
        {s.status === 'paused' && (
          <button onClick={() => resume.mutate(s.id)} className="p-1.5 rounded-md text-gray-400 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/30" title={t('განახლება (proration)')}><Play size={15} /></button>
        )}
        {s.status === 'past_due' && (
          <button onClick={() => retry.mutate(s.id)} className="p-1.5 rounded-md text-gray-400 hover:text-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900/30" title={t('გადახდის retry')}><Zap size={15} /></button>
        )}
        {s.status === 'active' && plans.length > 0 && (
          <select className="h-7 w-20 text-[11px] rounded-md border border-brandgray-200 dark:border-dark-50 bg-transparent" value="" onChange={e => e.target.value && changePlan.mutate({ id: s.id, plan_id: e.target.value })} title={t('პლანის შეცვლა')}>
            <option value="">{t('პლანი')}</option>
            {plans.map(p => <option key={p.id} value={p.id}>{p.name} v{p.version}</option>)}
          </select>
        )}
        <button onClick={() => remove.mutate(s.id)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30"><Trash2 size={15} /></button>
      </div>) },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('გამოწერები')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('რეკურენტული გადახდები — კლიენტის გამოწერები')}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => runBilling.mutate()} disabled={runBilling.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50">
            <Zap size={15} /> {t('ბილინგის გაშვება')}
          </button>
          <button onClick={() => setPlanOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
            <Plus size={15} /> {t('ახალი პლანი')}
          </button>
          <button onClick={() => setOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
            <Plus size={15} /> {t('ახალი გამოწერა')}
          </button>
        </div>
      </div>

      {billingMsg && <div className="rounded-lg border border-primary-200 bg-primary-50 p-2 text-sm text-primary-800 dark:border-primary-900/50 dark:bg-primary-900/20 dark:text-primary-300">{billingMsg}</div>}

      {/* Analytics */}
      {analytics && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { label: t('MRR'), value: money(analytics.mrr) },
            { label: t('ARR'), value: money(analytics.arr) },
            { label: t('აქტიური გამოწერები'), value: String(analytics.active_subscriptions) },
            { label: t('გაუქმებული'), value: String(analytics.churned_subscriptions) },
            { label: t('Churn rate'), value: `${analytics.churn_rate}%` },
            { label: t('კოჰორტები'), value: String((analytics.cohorts || []).length) },
          ].map(c => (
            <div key={c.label} className="rounded-xl border border-gray-200 dark:border-dark-50 p-3">
              <div className="text-[11px] font-medium uppercase tracking-wider text-gray-400">{c.label}</div>
              <div className="mt-1 text-lg font-bold text-gray-900 dark:text-gray-100">{c.value}</div>
            </div>
          ))}
        </div>
      )}

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

      <Modal open={planOpen} onClose={() => setPlanOpen(false)} title={t('ახალი პლანი (ვერსია)')}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('კოდი')}</label>
              <input className={inputCls} value={planForm.code} onChange={e => setPlanForm({ ...planForm, code: e.target.value })} placeholder="PRO" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დასახელება')}</label>
              <input className={inputCls} value={planForm.name} onChange={e => setPlanForm({ ...planForm, name: e.target.value })} placeholder="პრო" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('თანხა')}</label>
              <input type="number" step="0.01" className={inputCls} value={planForm.amount} onChange={e => setPlanForm({ ...planForm, amount: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სიხშირე')}</label>
              <select className={inputCls} value={planForm.frequency} onChange={e => setPlanForm({ ...planForm, frequency: e.target.value })}>
                <option value="monthly">თვიური</option>
                <option value="yearly">წლიური</option>
              </select>
            </div>
          </div>
          <p className="text-xs text-gray-400">{t('იგივე კოდით შექმნა ავტომატურად ქმნის ახალ ვერსიას (v2, v3...)')}</p>
          <button onClick={() => createPlan.mutate()} disabled={createPlan.isPending || !planForm.code || !planForm.name || !planForm.amount}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
