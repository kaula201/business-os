import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Users, Target, Percent } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { salesOrgApi, usersApi } from '../services/api'

interface Team {
  id: string
  name: string
  manager_id: string | null
  description: string | null
  is_active: boolean
  member_count: number
}

interface Target {
  id: string
  period: string
  team_id: string | null
  owner_id: string | null
  target_amount: number
  achieved_amount: number
  progress_percent: number
}

interface Rule {
  id: string
  name: string
  rate_percent: number
  fixed_amount: number
  is_active: boolean
}

interface Accrual {
  id: string
  order_id: string
  base_amount: number
  commission_amount: number
  status: string
  paid_at: string | null
}

function money(v: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)
}

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function SalesTeamsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'teams' | 'targets' | 'rules' | 'accruals'>('teams')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', period: '2026-08', target_amount: '', rate_percent: '', fixed_amount: '' })

  const { data: teamsData, isLoading } = useQuery({
    queryKey: ['sales-teams'],
    queryFn: () => salesOrgApi.listTeams({ page_size: 100 }).then(r => r.data.data),
  })
  const teams: Team[] = teamsData?.items || []

  const { data: targetsData, isLoading: targetsLoading } = useQuery({
    queryKey: ['sales-targets'],
    queryFn: () => salesOrgApi.listTargets({ page_size: 100 }).then(r => r.data.data),
  })
  const targets: Target[] = targetsData?.items || []

  const { data: rulesData, isLoading: rulesLoading } = useQuery({
    queryKey: ['sales-rules'],
    queryFn: () => salesOrgApi.listRules({ page_size: 100 }).then(r => r.data.data),
  })
  const rules: Rule[] = rulesData?.items || []

  const { data: accrualsData, isLoading: accrualsLoading } = useQuery({
    queryKey: ['sales-commissions'],
    queryFn: () => salesOrgApi.listCommissions({ page_size: 100 }).then(r => r.data.data),
  })
  const accruals: Accrual[] = accrualsData?.items || []

  const { data: users } = useQuery({
    queryKey: ['users-all'],
    queryFn: () => usersApi.list({ page_size: 100 }).then(r => r.data.data.items),
  })

  const createTeam = useMutation({
    mutationFn: () => salesOrgApi.createTeam({ name: form.name, description: form.description || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sales-teams'] }); setOpen(false); setForm({ name: '', description: '', period: '2026-08', target_amount: '', rate_percent: '', fixed_amount: '' }) },
  })

  const createTarget = useMutation({
    mutationFn: () => salesOrgApi.createTarget({ period: form.period, target_amount: Number(form.target_amount) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sales-targets'] }); setOpen(false); setForm({ name: '', description: '', period: '2026-08', target_amount: '', rate_percent: '', fixed_amount: '' }) },
  })

  const createRule = useMutation({
    mutationFn: () => salesOrgApi.createRule({
      name: form.name,
      rate_percent: form.rate_percent ? Number(form.rate_percent) : 0,
      fixed_amount: form.fixed_amount ? Number(form.fixed_amount) : 0,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sales-rules'] }); setOpen(false); setForm({ name: '', description: '', period: '2026-08', target_amount: '', rate_percent: '', fixed_amount: '' }) },
  })

  const removeTeam = useMutation({
    mutationFn: (id: string) => salesOrgApi.deleteTeam(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sales-teams'] }),
  })
  const removeTarget = useMutation({
    mutationFn: (id: string) => salesOrgApi.deleteTarget(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sales-targets'] }),
  })
  const removeRule = useMutation({
    mutationFn: (id: string) => salesOrgApi.deleteRule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sales-rules'] }),
  })
  const markPaid = useMutation({
    mutationFn: (id: string) => salesOrgApi.markCommissionPaid(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sales-commissions'] }),
  })

  const teamColumns = [
    { key: 'name', label: 'დასახელება', priority: true, render: (tm: Team) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100">{tm.name}</span>) },
    { key: 'member_count', label: 'წევრები', render: (tm: Team) => (
      <span className="inline-flex items-center gap-1"><Users size={14} className="text-gray-400" />{tm.member_count}</span>) },
    { key: 'description', label: 'აღწერა', render: (tm: Team) => tm.description || '—' },
    { key: 'actions', label: '', render: (tm: Team) => (
      <button onClick={() => removeTeam.mutate(tm.id)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30"><Trash2 size={15} /></button>) },
  ]

  const targetColumns = [
    { key: 'period', label: 'პერიოდი', priority: true, render: (tg: Target) => (
      <span className="font-mono font-semibold text-gray-900 dark:text-gray-100">{tg.period}</span>) },
    { key: 'target_amount', label: 'მიზანი', render: (tg: Target) => money(tg.target_amount) },
    { key: 'achieved_amount', label: 'მიღწეულია', render: (tg: Target) => <span className="font-semibold text-emerald-600 dark:text-emerald-400">{money(tg.achieved_amount)}</span> },
    { key: 'progress_percent', label: 'პროგრესი', render: (tg: Target) => (
      <div className="flex items-center gap-2">
        <div className="w-24 h-1.5 rounded-full bg-gray-100 dark:bg-dark-100 overflow-hidden">
          <div className="h-full rounded-full bg-primary-500" style={{ width: `${Math.min(100, tg.progress_percent)}%` }} />
        </div>
        <span className="text-xs font-medium">{tg.progress_percent.toFixed(1)}%</span>
      </div>) },
    { key: 'actions', label: '', render: (tg: Target) => (
      <button onClick={() => removeTarget.mutate(tg.id)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30"><Trash2 size={15} /></button>) },
  ]

  const ruleColumns = [
    { key: 'name', label: 'დასახელება', priority: true, render: (r: Rule) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100">{r.name}</span>) },
    { key: 'rate_percent', label: 'პროცენტი', render: (r: Rule) => r.rate_percent > 0 ? `${r.rate_percent}%` : '—' },
    { key: 'fixed_amount', label: 'ფიქსირებული', render: (r: Rule) => r.fixed_amount > 0 ? money(r.fixed_amount) : '—' },
    { key: 'actions', label: '', render: (r: Rule) => (
      <button onClick={() => removeRule.mutate(r.id)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30"><Trash2 size={15} /></button>) },
  ]

  const accrualColumns = [
    { key: 'order_id', label: 'შეკვეთა', priority: true, render: (a: Accrual) => (
      <span className="font-mono text-xs text-gray-900 dark:text-gray-100">{a.order_id.slice(0, 8)}...</span>) },
    { key: 'base_amount', label: 'ბაზა', render: (a: Accrual) => money(a.base_amount) },
    { key: 'commission_amount', label: 'საკომისიო', render: (a: Accrual) => <span className="font-semibold text-primary-700 dark:text-primary-400">{money(a.commission_amount)}</span> },
    { key: 'status', label: 'სტატუსი', render: (a: Accrual) => a.status === 'paid'
      ? <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">{t('გადახდილი')}</span>
      : <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">{t('დარიცხული')}</span> },
    { key: 'actions', label: '', render: (a: Accrual) => a.status === 'accrued' && (
      <button onClick={() => markPaid.mutate(a.id)} className="text-xs font-medium text-primary-700 hover:text-primary-800 dark:text-primary-400">{t('გადახდა')}</button>) },
  ]

  const tabs = [
    { id: 'teams' as const, label: t('გუნდები'), icon: Users },
    { id: 'targets' as const, label: t('მიზნები'), icon: Target },
    { id: 'rules' as const, label: t('საკომისიო წესები'), icon: Percent },
    { id: 'accruals' as const, label: t('დარიცხვები'), icon: Percent },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('გაყიდვების გუნდები')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('გუნდები, მიზნები და საკომისიო სისტემა')}</p>
        </div>
        <button onClick={() => setOpen(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
          <Plus size={15} /> {tab === 'teams' ? t('ახალი გუნდი') : tab === 'targets' ? t('ახალი მიზანი') : t('ახალი წესი')}
        </button>
      </div>

      <div className="flex gap-1 rounded-lg bg-brandgray-100 p-1 w-fit dark:bg-dark-100">
        {tabs.map(tb => (
          <button key={tb.id} onClick={() => setTab(tb.id)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium ${tab === tb.id ? 'bg-white shadow-sm text-gray-900 dark:bg-dark-200 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'}`}>
            <tb.icon size={14} className="inline mr-1 -mt-0.5" />{tb.label}
          </button>
        ))}
      </div>

      {tab === 'teams' && <DataTable columns={teamColumns} data={teams} isLoading={isLoading} emptyMessage={t('გუნდები არ არის')} />}
      {tab === 'targets' && <DataTable columns={targetColumns} data={targets} isLoading={targetsLoading} emptyMessage={t('მიზნები არ არის')} />}
      {tab === 'rules' && <DataTable columns={ruleColumns} data={rules} isLoading={rulesLoading} emptyMessage={t('საკომისიო წესები არ არის')} />}
      {tab === 'accruals' && <DataTable columns={accrualColumns} data={accruals} isLoading={accrualsLoading} emptyMessage={t('დარიცხვები არ არის')} />}

      <Modal open={open} onClose={() => setOpen(false)} title={tab === 'teams' ? t('ახალი გუნდი') : tab === 'targets' ? t('ახალი მიზანი') : t('ახალი საკომისიო წესი')}>
        <div className="space-y-4">
          {tab === 'teams' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დასახელება')}</label>
                <input className={inputCls} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('აღწერა')}</label>
                <input className={inputCls} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
              </div>
            </>
          )}
          {tab === 'targets' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პერიოდი (YYYY-MM)')}</label>
                <input className={inputCls} value={form.period} onChange={e => setForm({ ...form, period: e.target.value })} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მიზნის თანხა')}</label>
                <input type="number" step="0.01" className={inputCls} value={form.target_amount} onChange={e => setForm({ ...form, target_amount: e.target.value })} />
              </div>
            </>
          )}
          {tab === 'rules' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დასახელება')}</label>
                <input className={inputCls} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროცენტი %')}</label>
                  <input type="number" step="0.01" className={inputCls} value={form.rate_percent} onChange={e => setForm({ ...form, rate_percent: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ფიქსირებული თანხა')}</label>
                  <input type="number" step="0.01" className={inputCls} value={form.fixed_amount} onChange={e => setForm({ ...form, fixed_amount: e.target.value })} />
                </div>
              </div>
            </>
          )}
          <button onClick={() => tab === 'teams' ? createTeam.mutate() : tab === 'targets' ? createTarget.mutate() : createRule.mutate()}
            disabled={!form.name && !(tab === 'targets' && form.period && form.target_amount)}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
