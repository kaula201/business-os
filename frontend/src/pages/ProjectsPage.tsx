import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Briefcase, Plus, Search, Calendar, User, DollarSign, ChevronDown, ChevronRight } from 'lucide-react'

import Modal from '../components/ui/Modal'
import { api } from '../services/api'

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
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {isLoading ? (
                <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
              ) : projects.length === 0 ? (
                <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('პროექტები არ მოიძებნა')}</td></tr>
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
    </div>
  )
}
