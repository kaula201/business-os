import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, Plus, Play, Trash2 } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { glApi } from '../services/api'

interface RecurringEntry {
  id: string
  name: string
  description: string | null
  frequency: string
  interval: number
  day_of_week: number | null
  day_of_month: number | null
  start_date: string
  end_date: string | null
  next_run_date: string
  last_run_date: string | null
  entry_description: string
  is_active: boolean
  total_posted: number
  lines: { gl_account_id: string; debit_amount: number; credit_amount: number; description?: string | null }[]
}

const freqLabels: Record<string, string> = { daily: 'ყოველდღე', weekly: 'ყოველკვირა', monthly: 'ყოველთვე' }

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function RecurringEntriesPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    name: '', frequency: 'monthly', interval: 1, day_of_month: 1,
    start_date: new Date().toISOString().slice(0, 10), entry_description: '',
    debit_account: '', credit_account: '', amount: '',
  })

  const { data, isLoading } = useQuery({
    queryKey: ['gl-recurring'],
    queryFn: () => glApi.listRecurring({ page_size: 100 }).then(r => r.data.data),
  })
  const items: RecurringEntry[] = data?.items || []

  const { data: accounts } = useQuery({
    queryKey: ['gl-accounts-all'],
    queryFn: () => glApi.listAccounts({ page_size: 200 }).then(r => r.data.data.items),
  })

  const create = useMutation({
    mutationFn: () => glApi.createRecurring({
      name: form.name, frequency: form.frequency, interval: Number(form.interval),
      day_of_month: form.frequency === 'monthly' ? Number(form.day_of_month) : null,
      day_of_week: form.frequency === 'weekly' ? 1 : null,
      start_date: form.start_date, entry_description: form.entry_description,
      lines: [
        { gl_account_id: form.debit_account, debit_amount: Number(form.amount), credit_amount: 0 },
        { gl_account_id: form.credit_account, debit_amount: 0, credit_amount: Number(form.amount) },
      ],
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['gl-recurring'] }); setOpen(false) },
  })

  const run = useMutation({
    mutationFn: () => glApi.runRecurring(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gl-recurring'] }),
  })

  const remove = useMutation({
    mutationFn: (id: string) => glApi.deleteRecurring(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['gl-recurring'] }),
  })

  const columns = [
    { key: 'name', label: 'დასახელება', priority: true, render: (r: RecurringEntry) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100">{r.name}</span>) },
    { key: 'frequency', label: 'სიხშირე', render: (r: RecurringEntry) => freqLabels[r.frequency] || r.frequency },
    { key: 'next_run_date', label: 'შემდეგი გაშვება', render: (r: RecurringEntry) => new Date(r.next_run_date).toLocaleDateString('ka-GE') },
    { key: 'total_posted', label: 'გაშვებულია', render: (r: RecurringEntry) => `${r.total_posted} ×` },
    { key: 'is_active', label: 'სტატუსი', render: (r: RecurringEntry) => r.is_active
      ? <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">{t('აქტიური')}</span>
      : <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 dark:bg-dark-100 dark:text-gray-400">{t('გაჩერებული')}</span> },
    { key: 'actions', label: '', render: (r: RecurringEntry) => (
      <button onClick={() => remove.mutate(r.id)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30" title={t('წაშლა')}>
        <Trash2 size={16} />
      </button>) },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('განმეორებადი ჩანაწერები')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('ავტომატური ჟურნალ-ორდერები გრაფიკით')}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => run.mutate()} disabled={run.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50">
            <Play size={15} /> {t('გაუშვი დაგვიანებული')}
          </button>
          <button onClick={() => setOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
            <Plus size={15} /> {t('ახალი შაბლონი')}
          </button>
        </div>
      </div>

      <DataTable columns={columns} data={items} isLoading={isLoading} emptyMessage={t('განმეორებადი ჩანაწერები არ არის')} />

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი განმეორებადი ჩანაწერი')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დასახელება')}</label>
            <input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="ქირა" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('აღწერა')}</label>
            <input className={inputCls} value={form.entry_description} onChange={(e) => setForm({ ...form, entry_description: e.target.value })} placeholder="ოფისის ქირა" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სიხშირე')}</label>
              <select className={inputCls} value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value })}>
                <option value="daily">ყოველდღე</option>
                <option value="weekly">ყოველკვირა</option>
                <option value="monthly">ყოველთვე</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დაწყების თარიღი')}</label>
              <input type="date" className={inputCls} value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('Debit ანგარიში')}</label>
              <select className={inputCls} value={form.debit_account} onChange={(e) => setForm({ ...form, debit_account: e.target.value })}>
                <option value="">—</option>
                {(accounts || []).map((a: any) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('Credit ანგარიში')}</label>
              <select className={inputCls} value={form.credit_account} onChange={(e) => setForm({ ...form, credit_account: e.target.value })}>
                <option value="">—</option>
                {(accounts || []).map((a: any) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('თანხა')}</label>
            <input type="number" step="0.01" className={inputCls} value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} placeholder="500.00" />
          </div>
          <button onClick={() => create.mutate()} disabled={create.isPending || !form.name || !form.debit_account || !form.credit_account || !form.amount}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            <CalendarClock size={15} className="inline mr-1.5 -mt-0.5" />{t('შენახვა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
