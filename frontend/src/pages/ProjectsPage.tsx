import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Briefcase, Plus, Search, Calendar, User, DollarSign, ChevronDown, ChevronRight, Flag, TrendingUp, X } from 'lucide-react'

import Modal from '../components/ui/Modal'
import { api, projectsApi } from '../services/api'

interface Project {
  id: string; code: string; name: string; description: string | null
  manager_id: string | null; status: string
  start_date: string | null; end_date: string | null
  budget_amount: number; spent_amount: number; notes: string | null
  created_at: string
}

const statusColors: Record<string, string> = {
  draft: 'bg-gray-50 text-gray-600 dark:bg-dark-100 dark:text-gray-400',
  active: 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  on_hold: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  completed: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  cancelled: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400',
}
const statusLabels: Record<string, string> = { draft: 'მონახაზი', active: 'აქტიური', on_hold: 'შეჩერებული', completed: 'დასრულებული', cancelled: 'გაუქმებული' }
const money = (v: number) => new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)

export default function ProjectsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [detailFor, setDetailFor] = useState<Project | null>(null)
  const [milestoneForm, setMilestoneForm] = useState({ name: '', due_date: '', status: 'pending' })
  const [form, setForm] = useState({ code: '', name: '', description: '', manager_id: '', start_date: '', end_date: '', budget_amount: 0, notes: '' })
  const [error, setError] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['projects', search],
    queryFn: () => api.get('/projects/', { params: { search: search || undefined, page_size: 100 } }).then(r => r.data.data),
  })
  const projects: Project[] = data?.items || []

  const createMutation = useMutation({
    mutationFn: (d: any) => api.post('/projects/', d),
    onSuccess: () => { setShowModal(false); setForm({ code: '', name: '', description: '', manager_id: '', start_date: '', end_date: '', budget_amount: 0, notes: '' }); queryClient.invalidateQueries({ queryKey: ['projects'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  const { data: milestonesData, isLoading: milestonesLoading } = useQuery({
    queryKey: ['project-milestones', detailFor?.id],
    queryFn: () => detailFor ? projectsApi.milestones(detailFor.id).then(r => r.data.data) : [],
    enabled: !!detailFor,
  })
  const milestones: any[] = milestonesData || []

  const { data: progressData } = useQuery({
    queryKey: ['project-progress', detailFor?.id],
    queryFn: () => detailFor ? projectsApi.progress(detailFor.id).then(r => r.data.data) : null,
    enabled: !!detailFor,
  })

  const { data: profitData } = useQuery({
    queryKey: ['project-profit', detailFor?.id],
    queryFn: () => detailFor ? projectsApi.profitability(detailFor.id).then(r => r.data.data) : null,
    enabled: !!detailFor,
  })

  const createMilestone = useMutation({
    mutationFn: () => detailFor ? projectsApi.createMilestone(detailFor.id, milestoneForm) : Promise.reject(),
    onSuccess: () => { setMilestoneForm({ name: '', due_date: '', status: 'pending' }); queryClient.invalidateQueries({ queryKey: ['project-milestones'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  const completeMilestone = useMutation({
    mutationFn: (m: any) => detailFor ? projectsApi.updateMilestone(detailFor.id, m.id, { status: m.status === 'completed' ? 'pending' : 'completed' }) : Promise.reject(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['project-milestones'] }),
  })

  const totalBudget = projects.reduce((s, p) => s + p.budget_amount, 0)
  const totalSpent = projects.reduce((s, p) => s + p.spent_amount, 0)

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('პროექტები')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('პროექტების მართვა, განრიგი, ბიუჯეტი')}</p>
        </div>
        <button onClick={() => { setForm({ code: '', name: '', description: '', manager_id: '', start_date: '', end_date: '', budget_amount: 0, notes: '' }); setShowModal(true) }}
          className="btn btn-primary flex items-center gap-2"><Plus size={18} /> {t('ახალი პროექტი')}</button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <p className="text-xs text-gray-500 dark:text-gray-400">{t('პროექტების რაოდენობა')}</p>
          <p className="mt-2 text-xl font-bold text-brandgray-900 dark:text-gray-100">{projects.length}</p>
        </div>
        <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <p className="text-xs text-gray-500 dark:text-gray-400">{t('ჯამური ბიუჯეტი')}</p>
          <p className="mt-2 text-xl font-bold text-blue-700 dark:text-blue-400">{money(totalBudget)}</p>
        </div>
        <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <p className="text-xs text-gray-500 dark:text-gray-400">{t('დახარჯული')}</p>
          <p className="mt-2 text-xl font-bold text-amber-700 dark:text-amber-400">{money(totalSpent)}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative min-w-64 flex-1">
          <Search className="absolute left-3 top-2.5 text-gray-400 dark:text-gray-500" size={18} />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder={t('ძებნა...')}
            className="w-full rounded-lg border py-2 pl-10 pr-3 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('პროექტი')}</th>
                <th className="px-4 py-3">{t('სტატუსი')}</th>
                <th className="px-4 py-3">{t('თარიღი')}</th>
                <th className="px-4 py-3 text-right">{t('ბიუჯეტი')}</th>
                <th className="px-4 py-3 text-right">{t('დახარჯული')}</th>
                <th className="px-4 py-3 text-right">{t('დარჩენილი')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {isLoading ? (
                <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
              ) : projects.length === 0 ? (
                <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('პროექტები არ მოიძებნა')}</td></tr>
              ) : projects.map(p => (
                <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3">
                    <div className="font-medium text-brandgray-900 dark:text-gray-100">{p.name}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{p.code}{p.description ? ` · ${p.description}` : ''}</div>
                  </td>
                  <td className="px-4 py-3"><span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusColors[p.status] || ''}`}>{t(statusLabels[p.status] || p.status)}</span></td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{p.start_date || '—'} {p.end_date ? `→ ${p.end_date}` : ''}</td>
                  <td className="px-4 py-3 text-right dark:text-gray-200">{money(p.budget_amount)}</td>
                  <td className="px-4 py-3 text-right text-amber-700 dark:text-amber-400">{money(p.spent_amount)}</td>
                  <td className="px-4 py-3 text-right font-semibold text-green-700 dark:text-green-400">{money(p.budget_amount - p.spent_amount)}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => setDetailFor(p)} className="inline-flex items-center gap-1 text-primary-600 hover:underline text-xs dark:text-primary-400">
                      <Flag size={13} /> {t('დეტალები')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={showModal} onClose={() => setShowModal(false)} title={t('ახალი პროექტი')} size="lg">
        <form onSubmit={e => { e.preventDefault(); createMutation.mutate(form) }} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div><label className="block text-sm font-medium mb-1 dark:text-gray-300">{t('კოდი *')}</label><input required value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
            <div><label className="block text-sm font-medium mb-1 dark:text-gray-300">{t('სახელი *')}</label><input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
            <div className="md:col-span-2"><label className="block text-sm font-medium mb-1 dark:text-gray-300">{t('აღწერა')}</label><textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={2} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
            <div><label className="block text-sm font-medium mb-1 dark:text-gray-300">{t('დაწყების თარიღი')}</label><input type="date" value={form.start_date} onChange={e => setForm({ ...form, start_date: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
            <div><label className="block text-sm font-medium mb-1 dark:text-gray-300">{t('დასრულების თარიღი')}</label><input type="date" value={form.end_date} onChange={e => setForm({ ...form, end_date: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
            <div><label className="block text-sm font-medium mb-1 dark:text-gray-300">{t('ბიუჯეტი (₾)')}</label><input type="number" value={form.budget_amount || ''} onChange={e => setForm({ ...form, budget_amount: Number(e.target.value) })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" disabled={createMutation.isPending} className="w-full rounded-lg bg-primary-600 py-2 text-white disabled:opacity-50">{createMutation.isPending ? t('ინახება...') : t('პროექტის შექმნა')}</button>
        </form>
      </Modal>

      {/* ── Project Detail Modal ─────────────────────────────────────── */}
      <Modal open={!!detailFor} onClose={() => setDetailFor(null)} title={detailFor?.name || ''} size="lg">
        {detailFor && (
          <div className="space-y-5">
            {/* Progress + Profitability */}
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3">
                <p className="text-xs text-gray-500 dark:text-gray-400">{t('პროგრესი')}</p>
                <p className="mt-1 text-lg font-bold text-brandgray-900 dark:text-gray-100">{progressData?.completion_percent ?? 0}%</p>
                <div className="mt-2 h-1.5 rounded-full bg-brandgray-100 dark:bg-dark-100">
                  <div className="h-1.5 rounded-full bg-primary-600" style={{ width: `${progressData?.completion_percent ?? 0}%` }} />
                </div>
              </div>
              <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3">
                <p className="text-xs text-gray-500 dark:text-gray-400">{t('ბიუჯეტი')}</p>
                <p className="mt-1 text-lg font-bold text-blue-700 dark:text-blue-400">{money(profitData?.budget_amount ?? 0)}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">{t('დახარჯული')}: {money(profitData?.spent_amount ?? 0)}</p>
              </div>
              <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3">
                <p className="text-xs text-gray-500 dark:text-gray-400">{t('მომგებიანობა')}</p>
                <p className={`mt-1 text-lg font-bold ${(profitData?.profitability ?? 0) >= 0 ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>
                  {money(profitData?.profitability ?? 0)}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">{profitData?.profitability_percent ?? 0}%</p>
              </div>
            </div>

            {/* Milestones */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-brandgray-900 dark:text-gray-100">{t('Milestones')}</h3>
                <span className="text-xs text-gray-500 dark:text-gray-400">{milestones.filter((m: any) => m.status === 'completed').length}/{milestones.length}</span>
              </div>
              <div className="space-y-2">
                {milestonesLoading ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</p>
                ) : milestones.length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400">{t('Milestones არ არის')}</p>
                ) : milestones.map((m: any) => (
                  <div key={m.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <button onClick={() => completeMilestone.mutate(m)} title={t('სტატუსის შეცვლა')}
                        className={`w-4 h-4 rounded-full border-2 ${m.status === 'completed' ? 'bg-green-500 border-green-500' : 'border-gray-300 dark:border-gray-500'}`} />
                      <span className={`text-sm ${m.status === 'completed' ? 'line-through text-gray-400' : 'text-brandgray-900 dark:text-gray-100'}`}>{m.name}</span>
                    </div>
                    <span className="text-xs text-gray-500 dark:text-gray-400">{m.due_date ? new Date(m.due_date).toLocaleDateString('ka-GE') : '—'}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex gap-2">
                <input value={milestoneForm.name} onChange={e => setMilestoneForm({ ...milestoneForm, name: e.target.value })}
                  placeholder={t('ახალი milestone')} className="flex-1 rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
                <input type="date" value={milestoneForm.due_date} onChange={e => setMilestoneForm({ ...milestoneForm, due_date: e.target.value })}
                  className="rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
                <button onClick={() => createMilestone.mutate()} disabled={!milestoneForm.name || createMilestone.isPending}
                  className="rounded-lg bg-primary-600 px-3 py-2 text-sm text-white disabled:opacity-50">
                  <Plus size={15} />
                </button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
