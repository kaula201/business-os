import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, Search, DollarSign, Target, TrendingDown, Calendar } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import { api } from '../services/api'
import type { BudgetPlan, BudgetPlanCreate, BudgetLine } from '../types'

const currentYear = new Date().getFullYear()

function money(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

function errorText(err: any) {
  return err?.response?.data?.detail || i18n.t('ოპერაცია ვერ შესრულდა')
}

export default function BudgetingPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)

  // Plan modal
  const [planModal, setPlanModal] = useState<'create' | 'edit' | null>(null)
  const [selectedPlan, setSelectedPlan] = useState<BudgetPlan | null>(null)
  const [planForm, setPlanForm] = useState<BudgetPlanCreate>({ name: '', fiscal_year: currentYear, period_type: 'monthly', notes: null })

  // ── Queries ──────────────────────────────────────────────────────

  const { data: plansData, isLoading } = useQuery({
    queryKey: ['budget-plans'],
    queryFn: () => api.get('/budgeting/plans').then((r) => r.data.data),
  })
  const plans: BudgetPlan[] = plansData || []

  const { data: linesData, isLoading: linesLoading } = useQuery({
    queryKey: ['budget-lines', selectedPlanId],
    queryFn: () => api.get(`/budgeting/plans/${selectedPlanId}/lines`).then((r) => r.data.data),
    enabled: !!selectedPlanId,
  })
  const lines: BudgetLine[] = linesData || []

  // ── Mutations ────────────────────────────────────────────────────

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['budget-plans'] })

  const createPlan = useMutation({
    mutationFn: () => api.post('/budgeting/plans', planForm),
    onSuccess: () => { setPlanModal(null); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })

  const deletePlan = useMutation({
    mutationFn: (id: string) => api.delete(`/budgeting/plans/${id}`),
    onSuccess: () => { setSelectedPlanId(null); refresh() },
    onError: (e) => setError(errorText(e)),
  })

  const visible = search.trim()
    ? plans.filter((p) => p.name.toLowerCase().includes(search.trim().toLowerCase()))
    : plans

  const totalPlanned = plans.reduce((s, p) => s + p.total_planned, 0)
  const totalActual = plans.reduce((s, p) => s + p.total_actual, 0)

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('ბიუჯეტირება')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('ბიუჯეტის დაგეგმვა, შესრულების მონიტორინგი')}</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => { setPlanForm({ name: '', fiscal_year: currentYear, period_type: 'monthly', notes: null }); setError(''); setPlanModal('create') }}>
          <Plus size={18} /> {t('ბიუჯეტი')}
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <Target className="text-primary-600" />
            <div>
              <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('დაგეგმილი')}</div>
              <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{money(totalPlanned)}</div>
            </div>
          </div>
        </div>
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <DollarSign className="text-accent-600" />
            <div>
              <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('ფაქტობრივი')}</div>
              <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{money(totalActual)}</div>
            </div>
          </div>
        </div>
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <TrendingDown className="text-amber-600" />
            <div>
              <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('გადახრა')}</div>
              <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{money(totalPlanned - totalActual)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('ძებნა...')} className="input pl-10" />
        </div>
      </div>

      {/* Plans Table */}
      <DataTable
        columns={[
          { key: 'name', label: 'სახელი', render: (p: BudgetPlan) => <span className="font-medium">{p.name}</span> },
          { key: 'fiscal_year', label: 'წელი' },
          { key: 'status', label: 'სტატუსი', render: (p: BudgetPlan) => {
            const cls = p.status === 'active' ? 'badge-green' : p.status === 'draft' ? 'badge-yellow' : 'badge-gray'
            const label = p.status === 'active' ? 'აქტიური' : p.status === 'draft' ? t('მონახაზი') : t('დახურული')
            return <span className={`badge ${cls}`}>{t(label)}</span>
          }},
          { key: 'total_planned', label: 'დაგეგმილი', render: (p: BudgetPlan) => money(p.total_planned) },
          { key: 'total_actual', label: 'ფაქტობრივი', render: (p: BudgetPlan) => money(p.total_actual) },
          {
            key: 'actions', label: '',
            render: (p: BudgetPlan) => (
              <div className="flex items-center gap-1">
                <button onClick={(e) => { e.stopPropagation(); setSelectedPlanId(p.id) }} className="p-1.5 hover:bg-primary-50 rounded-lg" title={t('ხაზები')}>
                  <Target size={16} className="text-primary-500" />
                </button>
                <button onClick={(e) => { e.stopPropagation(); if (confirm(t('წავშალოთ ბიუჯეტი?'))) deletePlan.mutate(p.id) }} className="p-1.5 hover:bg-red-50 rounded-lg">
                  <Trash2 size={18} className="text-red-400" />
                </button>
              </div>
            ),
          },
        ]}
        data={visible}
        clientPageSize={20}
        isLoading={isLoading}
        emptyMessage={t('ბიუჯეტები არ მოიძებნა')}
      />

      {/* Budget Lines Section */}
      {selectedPlanId && (
        <section className="card overflow-hidden p-0 dark:bg-dark-200 dark:border-dark-50">
          <div className="border-b border-brandgray-100 dark:border-dark-50 px-5 py-4 flex items-center justify-between">
            <h2 className="font-semibold text-brandgray-900 dark:text-gray-100">{t('ბიუჯეტის ხაზები')}</h2>
            <button onClick={() => setSelectedPlanId(null)} className="btn-secondary text-sm">{t('დახურვა')}</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-brandgray-50 dark:bg-dark-100">
                <tr>
                  <th className="px-4 py-3 text-left text-brandgray-600 dark:text-gray-400">{t('ანგარიში')}</th>
                  <th className="px-4 py-3 text-left text-brandgray-600 dark:text-gray-400">{t('პერიოდი')}</th>
                  <th className="px-4 py-3 text-right text-brandgray-600 dark:text-gray-400">{t('დაგეგმილი')}</th>
                  <th className="px-4 py-3 text-right text-brandgray-600 dark:text-gray-400">{t('ფაქტობრივი')}</th>
                  <th className="px-4 py-3 text-right text-brandgray-600 dark:text-gray-400">{t('გადახრა')}</th>
                  <th className="px-4 py-3 text-right text-brandgray-600 dark:text-gray-400">%</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brandgray-100 dark:divide-dark-50">
                {linesLoading && <tr><td className="px-4 py-8 text-center text-brandgray-500" colSpan={6}>{t('იტვირთება...')}</td></tr>}
                {!linesLoading && lines.length === 0 && <tr><td className="px-4 py-8 text-center text-brandgray-500" colSpan={6}>{t('ხაზები არ არის')}</td></tr>}
                {lines.map((l) => (
                  <tr key={l.id} className="hover:bg-brandgray-50/50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3"><span className="font-mono text-brandgray-600">{l.gl_account_code}</span> {l.gl_account_name}</td>
                    <td className="px-4 py-3">{l.period}</td>
                    <td className="px-4 py-3 text-right font-medium">{money(l.planned_amount)}</td>
                    <td className="px-4 py-3 text-right">{money(l.actual_amount)}</td>
                    <td className={`px-4 py-3 text-right font-semibold ${l.variance >= 0 ? 'text-green-600' : 'text-red-600'}`}>{money(l.variance)}</td>
                    <td className="px-4 py-3 text-right">
                      {l.variance_percent !== null ? (
                        <span className={`${l.variance_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {l.variance_percent >= 0 ? '+' : ''}{l.variance_percent}%
                        </span>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Create Modal */}
      <Modal open={planModal === 'create'} onClose={() => setPlanModal(null)} title={t('ახალი ბიუჯეტი')} size="md">
        <div className="space-y-4">
          <FormField label={t('სახელი')} required>
            <input value={planForm.name} onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })} placeholder={t('2026 წლის ბიუჯეტი')} className="input" />
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label={t('წელი')} required>
              <input type="number" min={2020} max={2100} value={planForm.fiscal_year} onChange={(e) => setPlanForm({ ...planForm, fiscal_year: Number(e.target.value) })} className="input" />
            </FormField>
            <FormField label={t('პერიოდის ტიპი')}>
              <Select value={planForm.period_type || 'monthly'} onChange={(e) => setPlanForm({ ...planForm, period_type: e.target.value })} options={[
                { value: 'monthly', label: 'თვიური' },
                { value: 'quarterly', label: 'კვარტალური' },
                { value: 'yearly', label: 'წლიური' },
              ]} />
            </FormField>
          </div>
          <FormField label={t('შენიშვნა')}>
            <textarea value={planForm.notes || ''} onChange={(e) => setPlanForm({ ...planForm, notes: e.target.value || null })} className="input" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setPlanModal(null)} className="btn-secondary">{t('გაუქმება')}</button>
            <button onClick={() => { if (!planForm.name.trim()) { setError(t('სახელი სავალდებულოა')); return }; createPlan.mutate() }} disabled={createPlan.isPending} className="btn-primary">
              {createPlan.isPending ? t('იქმნება...') : t('შექმნა')}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
