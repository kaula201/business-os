import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Briefcase, Plus, Search, Calendar, User, DollarSign, ChevronDown, ChevronRight, Flag, TrendingUp, X, LayoutTemplate, Trash2 } from 'lucide-react'

import Modal from '../components/ui/Modal'
import { api, projectsApi, projectResourcesApi } from '../services/api'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

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
  const [templateOpen, setTemplateOpen] = useState(false)
  const [templates, setTemplates] = useState<any[]>([])
  const [templateForm, setTemplateForm] = useState({ name: '', description: '', default_budget: 0, milestones: '' })
  const [instantiateFor, setInstantiateFor] = useState<any | null>(null)
  const [instantiateForm, setInstantiateForm] = useState({ name: '', code: '', budget_amount: 0 })

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

  const { data: billingData } = useQuery({
    queryKey: ['project-billing', detailFor?.id],
    queryFn: () => detailFor ? projectResourcesApi.billingSummary(detailFor.id) : null,
    enabled: !!detailFor,
  })

  const { data: timesheetsData } = useQuery({
    queryKey: ['project-timesheets', detailFor?.id],
    queryFn: () => detailFor ? projectResourcesApi.timesheets(detailFor.id).then((r: any) => r.data.data?.items || r.data.data || []) : [],
    enabled: !!detailFor,
  })
  const [tsForm, setTsForm] = useState({ work_date: new Date().toISOString().slice(0, 10), hours: '', hourly_rate: '', billable: true })
  const addTimesheet = useMutation({
    mutationFn: () => detailFor ? projectResourcesApi.addTimesheet(detailFor.id, {
      work_date: tsForm.work_date, hours: Number(tsForm.hours),
      hourly_rate: Number(tsForm.hourly_rate) || undefined, billable: tsForm.billable,
    }) : Promise.reject(),
    onSuccess: () => {
      setTsForm({ work_date: new Date().toISOString().slice(0, 10), hours: '', hourly_rate: '', billable: true })
      queryClient.invalidateQueries({ queryKey: ['project-billing'] })
      queryClient.invalidateQueries({ queryKey: ['project-timesheets'] })
      queryClient.invalidateQueries({ queryKey: ['project-profit'] })
    },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const markBilled = useMutation({
    mutationFn: (entryId: string) => detailFor ? projectResourcesApi.markBilled(detailFor.id, entryId) : Promise.reject(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-billing'] })
      queryClient.invalidateQueries({ queryKey: ['project-timesheets'] })
    },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  // Resource capacity — members + utilization
  const { data: membersData } = useQuery({
    queryKey: ['project-members', detailFor?.id],
    queryFn: () => detailFor ? projectResourcesApi.members(detailFor.id).then((r: any) => r.data.data) : [],
    enabled: !!detailFor,
  })
  const { data: utilizationData } = useQuery({
    queryKey: ['project-utilization'],
    queryFn: () => projectResourcesApi.utilization().then((r: any) => r.data.data),
  })
  const [memberForm, setMemberForm] = useState({ user_id: '', role: 'member', allocation_percent: 100, hourly_rate: '' })
  const addMember = useMutation({
    mutationFn: () => detailFor ? projectResourcesApi.addMember(detailFor.id, {
      user_id: memberForm.user_id, role: memberForm.role,
      allocation_percent: Number(memberForm.allocation_percent) || 100,
      hourly_rate: Number(memberForm.hourly_rate) || undefined,
    }) : Promise.reject(),
    onSuccess: () => {
      setMemberForm({ user_id: '', role: 'member', allocation_percent: 100, hourly_rate: '' })
      queryClient.invalidateQueries({ queryKey: ['project-members'] })
      queryClient.invalidateQueries({ queryKey: ['project-utilization'] })
    },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const removeMember = useMutation({
    mutationFn: (id: string) => projectResourcesApi.removeMember(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-members'] })
      queryClient.invalidateQueries({ queryKey: ['project-utilization'] })
    },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const { data: usersData } = useQuery({
    queryKey: ['users-all'],
    queryFn: () => api.get('/users/', { params: { page_size: 100 } }).then((r: any) => r.data.data.items),
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
  const totalRevenue = projects.reduce((s, p) => s + (p as any).revenue_amount || 0, 0)

  const createTemplateMut = useMutation({
    mutationFn: (d: any) => {
      const milestones = (d.milestones || '').split('\n').map((l: string) => l.trim()).filter(Boolean)
        .map((name: string) => ({ name, tasks: [] }))
      return projectsApi.createTemplate({ name: d.name, description: d.description, default_budget: d.default_budget, milestones })
    },
    onSuccess: () => { setTemplateOpen(false); setTemplateForm({ name: '', description: '', default_budget: 0, milestones: '' }); projectsApi.listTemplates().then(r => setTemplates(r.data.data)) },
  })

  const instantiateMut = useMutation({
    mutationFn: ({ templateId, data }: { templateId: string; data: any }) => projectsApi.instantiateTemplate(templateId, data),
    onSuccess: () => { setInstantiateFor(null); queryClient.invalidateQueries({ queryKey: ['projects'] }) },
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('პროექტები')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('პროექტების მართვა, განრიგი, ბიუჯეტი')}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => { setTemplateOpen(true); projectsApi.listTemplates().then(r => setTemplates(r.data.data)) }}
            className="btn btn-secondary flex items-center gap-2"><LayoutTemplate size={18} /> {t('შაბლონები')}</button>
          <button onClick={() => { setForm({ code: '', name: '', description: '', manager_id: '', start_date: '', end_date: '', budget_amount: 0, notes: '' }); setShowModal(true) }}
            className="btn btn-primary flex items-center gap-2"><Plus size={18} /> {t('ახალი პროექტი')}</button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
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
        <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <p className="text-xs text-gray-500 dark:text-gray-400">{t('შემოსავალი')}</p>
          <p className="mt-2 text-xl font-bold text-emerald-700 dark:text-emerald-400">{money(totalRevenue)}</p>
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

            {/* Timesheet Billing */}
            <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-brandgray-900 dark:text-gray-100">{t('Timesheet Billing')}</h3>
                {billingData && (
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {t('გადასახდელი')}: <b className="text-emerald-600 dark:text-emerald-400">{money(billingData.unbilled_value)}</b> · {t('დაბილინგებული')}: {money(billingData.billed_value)}
                  </span>
                )}
              </div>
              <div className="grid gap-4 md:grid-cols-4 mb-3">
                <div><p className="text-xs text-gray-500">{t('სულ საათები')}</p><p className="font-semibold">{billingData?.total_hours ?? 0}</p></div>
                <div><p className="text-xs text-gray-500">{t('ბილინგის საათები')}</p><p className="font-semibold">{billingData?.billable_hours ?? 0}</p></div>
                <div><p className="text-xs text-gray-500">{t('შემოსავალი')}</p><p className="font-semibold">{money(billingData?.project_revenue ?? 0)}</p></div>
                <div><p className="text-xs text-gray-500">{t('ხარჯი')}</p><p className="font-semibold">{money(billingData?.project_spent ?? 0)}</p></div>
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto mb-3">
                {(timesheetsData || []).length === 0 ? (
                  <p className="text-sm text-gray-400">{t('დროის ჩანაწერები არ არის')}</p>
                ) : (timesheetsData || []).map((e: any) => (
                  <div key={e.id} className="flex items-center justify-between rounded border border-brandgray-100 dark:border-dark-50 px-3 py-1.5 text-sm">
                    <div>
                      <span className="text-gray-700 dark:text-gray-300">{e.work_date}</span>
                      <span className="ml-2 text-gray-500">{e.hours}h</span>
                      {e.description && <span className="ml-2 text-xs text-gray-400">{e.description}</span>}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-gray-600">{money(e.billed_amount)}</span>
                      {e.billable && !e.billed && (
                        <button onClick={() => markBilled.mutate(e.id)} className="text-xs text-primary-600 hover:text-primary-800">
                          {t('ბილინგი')}
                        </button>
                      )}
                      {e.billed && <span className="badge badge-green">{t('დაბილინგებული')}</span>}
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <input type="date" value={tsForm.work_date} onChange={e => setTsForm({ ...tsForm, work_date: e.target.value })}
                  className="rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
                <input type="number" placeholder={t('საათები')} min="0.25" step="0.25" value={tsForm.hours}
                  onChange={e => setTsForm({ ...tsForm, hours: e.target.value })}
                  className="w-20 rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
                <input type="number" placeholder={t('₾/სთ')} min="0" step="0.01" value={tsForm.hourly_rate}
                  onChange={e => setTsForm({ ...tsForm, hourly_rate: e.target.value })}
                  className="w-24 rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
                <label className="flex items-center gap-1 text-sm text-gray-600 dark:text-gray-300">
                  <input type="checkbox" checked={tsForm.billable} onChange={e => setTsForm({ ...tsForm, billable: e.target.checked })} />
                  {t('ბილინგადი')}
                </label>
                <button onClick={() => addTimesheet.mutate()} disabled={!tsForm.hours || addTimesheet.isPending}
                  className="rounded-lg bg-primary-600 px-3 py-2 text-sm text-white disabled:opacity-50">
                  <Plus size={15} /> {t('დროის დამატება')}
                </button>
              </div>
            </div>

            {/* Resource Capacity */}
            <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-brandgray-900 dark:text-gray-100">{t('რესურსების სიმძლავრე')}</h3>
                <span className="text-xs text-gray-500 dark:text-gray-400">{t('წევრები')}: {(membersData || []).length}</span>
              </div>
              <div className="space-y-2 mb-3">
                {(membersData || []).length === 0 ? (
                  <p className="text-sm text-gray-400">{t('წევრები არ არის')}</p>
                ) : (membersData || []).map((m: any) => (
                  <div key={m.id} className="flex items-center justify-between rounded border border-brandgray-100 dark:border-dark-50 px-3 py-1.5 text-sm">
                    <div>
                      <span className="text-gray-700 dark:text-gray-300">{m.user_name || m.user_id?.slice(0, 8)}</span>
                      <span className="ml-2 text-xs text-gray-400">{m.role}</span>
                      {m.hourly_rate > 0 && <span className="ml-2 text-xs text-gray-500">{money(m.hourly_rate)}/h</span>}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">{m.allocation_percent}%</span>
                      <button onClick={() => removeMember.mutate(m.id)} className="text-red-500 hover:text-red-700"><Trash2 size={14} /></button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <select value={memberForm.user_id} onChange={e => setMemberForm({ ...memberForm, user_id: e.target.value })}
                  className="rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                  <option value="">{t('აირჩიეთ მომხმარებელი')}</option>
                  {(usersData || []).map((u: any) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                </select>
                <select value={memberForm.role} onChange={e => setMemberForm({ ...memberForm, role: e.target.value })}
                  className="rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                  <option value="member">member</option>
                  <option value="lead">lead</option>
                  <option value="manager">manager</option>
                  <option value="consultant">consultant</option>
                </select>
                <input type="number" placeholder="% " min="1" max="100" value={memberForm.allocation_percent}
                  onChange={e => setMemberForm({ ...memberForm, allocation_percent: Number(e.target.value) })}
                  className="w-20 rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
                <input type="number" placeholder="₾/h" min="0" step="0.01" value={memberForm.hourly_rate}
                  onChange={e => setMemberForm({ ...memberForm, hourly_rate: e.target.value })}
                  className="w-24 rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
                <button onClick={() => addMember.mutate()} disabled={!memberForm.user_id || addMember.isPending}
                  className="rounded-lg bg-primary-600 px-3 py-2 text-sm text-white disabled:opacity-50">
                  <Plus size={15} /> {t('წევრის დამატება')}
                </button>
              </div>
              {utilizationData && utilizationData.length > 0 && (
                <div className="mt-3 border-t border-brandgray-100 dark:border-dark-50 pt-3">
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">{t('დატვირთვა (ყველა პროექტი)')}</p>
                  <div className="space-y-1.5">
                    {utilizationData.slice(0, 5).map((u: any) => (
                      <div key={u.user_id} className="flex items-center gap-2 text-xs">
                        <span className="w-32 truncate text-gray-600 dark:text-gray-300">{u.user_name}</span>
                        <div className="flex-1 h-1.5 rounded-full bg-brandgray-100 dark:bg-dark-100">
                          <div className="h-1.5 rounded-full bg-primary-600" style={{ width: `${Math.min(u.total_allocation, 100)}%` }} />
                        </div>
                        <span className="w-16 text-right text-gray-500">{u.total_allocation}% · {u.project_count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
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
                    <span className="text-xs text-gray-500 dark:text-gray-400">{m.due_date ? fmtDate(new Date(m.due_date)) : '—'}</span>
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

      {/* ── Templates Modal ──────────────────────────────────────────── */}
      <Modal open={templateOpen} onClose={() => setTemplateOpen(false)} title={t('შაბლონები')} size="lg">
        <div className="space-y-4">
          <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-3 space-y-2">
            <p className="text-sm font-semibold text-brandgray-900 dark:text-gray-100">{t('ახალი შაბლონი')}</p>
            <input value={templateForm.name} onChange={e => setTemplateForm({ ...templateForm, name: e.target.value })}
              placeholder={t('შაბლონის სახელი')} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            <input value={templateForm.description} onChange={e => setTemplateForm({ ...templateForm, description: e.target.value })}
              placeholder={t('აღწერა')} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            <input type="number" value={templateForm.default_budget || ''} onChange={e => setTemplateForm({ ...templateForm, default_budget: Number(e.target.value) || 0 })}
              placeholder={t('ნაგულისხმევი ბიუჯეტი')} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            <textarea value={templateForm.milestones} onChange={e => setTemplateForm({ ...templateForm, milestones: e.target.value })}
              placeholder={t('ეტაპები (თითო ხაზზე)')} rows={3} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            <button onClick={() => createTemplateMut.mutate(templateForm)} disabled={!templateForm.name || createTemplateMut.isPending}
              className="w-full rounded-lg bg-primary-600 px-3 py-2 text-sm text-white disabled:opacity-50">
              {t('შენახვა')}
            </button>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {templates.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-6">{t('შაბლონები არ არის')}</p>
            ) : templates.map((tmpl: any) => (
              <div key={tmpl.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2">
                <div>
                  <div className="font-medium text-brandgray-900 dark:text-gray-100">{tmpl.name}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {tmpl.milestones?.length || 0} {t('ეტაპი')} · {money(tmpl.default_budget)}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => { setInstantiateFor(tmpl); setInstantiateForm({ name: tmpl.name, code: '', budget_amount: tmpl.default_budget }) }}
                    className="rounded-lg bg-primary-600 px-3 py-1.5 text-xs text-white">
                    {t('პროექტის შექმნა')}
                  </button>
                  <button onClick={() => projectsApi.removeTemplate(tmpl.id).then(() => projectsApi.listTemplates().then(r => setTemplates(r.data.data)))}
                    className="rounded-lg bg-red-600 px-2 py-1.5 text-xs text-white">
                    <X size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Modal>

      {/* ── Instantiate Modal ─────────────────────────────────────────── */}
      <Modal open={!!instantiateFor} onClose={() => setInstantiateFor(null)} title={t('პროექტის შექმნა შაბლონიდან')}>
        {instantiateFor && (
          <div className="space-y-3">
            <p className="text-sm text-gray-500 dark:text-gray-400">{instantiateFor.name} — {instantiateFor.milestones?.length || 0} {t('ეტაპი')}</p>
            <input value={instantiateForm.name} onChange={e => setInstantiateForm({ ...instantiateForm, name: e.target.value })}
              placeholder={t('პროექტის სახელი')} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            <input value={instantiateForm.code} onChange={e => setInstantiateForm({ ...instantiateForm, code: e.target.value })}
              placeholder={t('კოდი')} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            <input type="number" value={instantiateForm.budget_amount || ''} onChange={e => setInstantiateForm({ ...instantiateForm, budget_amount: Number(e.target.value) || 0 })}
              placeholder={t('ბიუჯეტი')} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            <button onClick={() => instantiateMut.mutate({ templateId: instantiateFor.id, data: instantiateForm })} disabled={instantiateMut.isPending}
              className="w-full rounded-lg bg-primary-600 px-3 py-2 text-sm text-white disabled:opacity-50">
              {t('შექმნა')}
            </button>
          </div>
        )}
      </Modal>
    </div>
  )
}
