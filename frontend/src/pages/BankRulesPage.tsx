import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Play, Trash2 } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { bankingApi, glApi } from '../services/api'

interface Rule {
  id: string
  name: string
  rule_type: string
  action: string
  match_text: string | null
  match_amount: number | null
  date_window_days: number
  direction: string
  gl_account_id: string | null
  priority: number
  is_active: boolean
}

const ruleTypeLabels: Record<string, string> = {
  amount_date: 'თანხა + თარიღი',
  description_contains: 'აღწერა შეიცავს',
  counterparty_equals: 'კონტრაგენტი =',
  reference_equals: 'რეფერენსი =',
}
const actionLabels: Record<string, string> = { auto_reconcile: 'ავტო-შეჯერება', categorize: 'კატეგორიზაცია' }

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function BankRulesPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    name: '', rule_type: 'description_contains', action: 'categorize',
    match_text: '', match_amount: '', direction: 'any', date_window_days: '7',
    gl_account_id: '', priority: '100',
  })

  const { data, isLoading } = useQuery({
    queryKey: ['bank-rules'],
    queryFn: () => bankingApi.listRules({ page_size: 100 }).then(r => r.data),
  })
  const items: Rule[] = data?.items || []

  const { data: accounts } = useQuery({
    queryKey: ['gl-accounts-all-rules'],
    queryFn: () => glApi.listAccounts({ page_size: 200 }).then(r => r.data.data.items),
  })

  const create = useMutation({
    mutationFn: () => bankingApi.createRule({
      name: form.name, rule_type: form.rule_type, action: form.action,
      match_text: form.match_text || null,
      match_amount: form.match_amount ? Number(form.match_amount) : null,
      date_window_days: Number(form.date_window_days),
      direction: form.direction,
      gl_account_id: form.gl_account_id || null,
      priority: Number(form.priority),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['bank-rules'] }); setOpen(false) },
  })

  const apply = useMutation({
    mutationFn: () => bankingApi.applyRules(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['bank-rules'] }),
  })

  const remove = useMutation({
    mutationFn: (id: string) => bankingApi.deleteRule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['bank-rules'] }),
  })

  const columns = [
    { key: 'name', label: 'დასახელება', priority: true, render: (r: Rule) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100">{r.name}</span>) },
    { key: 'rule_type', label: 'ტიპი', render: (r: Rule) => ruleTypeLabels[r.rule_type] || r.rule_type },
    { key: 'action', label: 'მოქმედება', render: (r: Rule) => (
      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${r.action === 'auto_reconcile' ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300' : 'bg-brandgray-50 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
        {actionLabels[r.action] || r.action}
      </span>) },
    { key: 'priority', label: 'პრიორიტეტი', render: (r: Rule) => r.priority },
    { key: 'is_active', label: 'სტატუსი', render: (r: Rule) => r.is_active
      ? <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">{t('აქტიური')}</span>
      : <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 dark:bg-dark-100 dark:text-gray-400">{t('გაჩერებული')}</span> },
    { key: 'actions', label: '', render: (r: Rule) => (
      <button onClick={() => remove.mutate(r.id)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30" title={t('წაშლა')}>
        <Trash2 size={16} />
      </button>) },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('შეჯერების წესები')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('საბანკო ტრანზაქციების ავტომატური დამუშავება')}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => apply.mutate()} disabled={apply.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50">
            <Play size={15} /> {t('წესების გამოყენება')}
          </button>
          <button onClick={() => setOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
            <Plus size={15} /> {t('ახალი წესი')}
          </button>
        </div>
      </div>

      {apply.data?.data && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-800 dark:bg-emerald-900/20 dark:border-emerald-800/50 dark:text-emerald-300">
          {t('შეჯერებულია')}: {apply.data.data.matched} · {t('კატეგორიზებულია')}: {apply.data.data.categorized} · {t('გამოტოვებულია')}: {apply.data.data.skipped}
        </div>
      )}

      <DataTable columns={columns} data={items} isLoading={isLoading} emptyMessage={t('წესები არ არის')} />

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი წესი')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დასახელება')}</label>
            <input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="საბანკო საკომისიო" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ტიპი')}</label>
              <select className={inputCls} value={form.rule_type} onChange={(e) => setForm({ ...form, rule_type: e.target.value })}>
                {Object.entries(ruleTypeLabels).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მოქმედება')}</label>
              <select className={inputCls} value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })}>
                {Object.entries(actionLabels).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
          </div>
          {form.rule_type !== 'amount_date' ? (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მატჩის ტექსტი')}</label>
              <input className={inputCls} value={form.match_text} onChange={(e) => setForm({ ...form, match_text: e.target.value })} placeholder="საკომისიო, TBC, ..." />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('თანხა')}</label>
                <input type="number" step="0.01" className={inputCls} value={form.match_amount} onChange={(e) => setForm({ ...form, match_amount: e.target.value })} placeholder="-60.25 (debit) ან 125.10 (credit)" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('თარიღის ფანჯარა (დღე)')}</label>
                <input type="number" className={inputCls} value={form.date_window_days} onChange={(e) => setForm({ ...form, date_window_days: e.target.value })} />
              </div>
            </div>
          )}
          {form.action === 'categorize' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('GL ანგარიში')}</label>
              <select className={inputCls} value={form.gl_account_id} onChange={(e) => setForm({ ...form, gl_account_id: e.target.value })}>
                <option value="">—</option>
                {(accounts || []).map((a: any) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
              </select>
            </div>
          )}
          <button onClick={() => create.mutate()} disabled={create.isPending || !form.name}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
