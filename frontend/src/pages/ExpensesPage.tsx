import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Plus, Pencil, Search, DollarSign, CheckCircle, XCircle, Clock, User, Tag, FileText
} from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import { api } from '../services/api'
import type { Expense, ExpenseCreate, ExpenseCategory } from '../types'

const today = () => new Date().toISOString().slice(0, 10)

const statuses: Record<string, { label: string; cls: string }> = {
  pending: { label: 'მოლოდინში', cls: 'badge-yellow' },
  approved: { label: 'დამტკიცებული', cls: 'badge-green' },
  rejected: { label: 'უარყოფილი', cls: 'badge-red' },
  paid: { label: 'გადახდილი', cls: 'badge-blue' },
}

function money(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

function errorText(err: any) {
  return err?.response?.data?.detail || i18n.t('ოპერაცია ვერ შესრულდა')
}

export default function ExpensesPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [error, setError] = useState('')

  // Debounce: search იგზავნება server-ზე მხოლოდ აკრეფის შეწყვეტის შემდეგ
  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput); setPage(1) }, 400)
    return () => clearTimeout(t)
  }, [searchInput])

  // Modal
  const [modal, setModal] = useState<'create' | 'edit' | null>(null)
  const [selected, setSelected] = useState<Expense | null>(null)
  const [form, setForm] = useState<ExpenseCreate>({
    category_id: null, expense_date: today(), description: '', amount: 0, currency: 'GEL', notes: null,
  })
  const [editForm, setEditForm] = useState({ description: '', amount: 0, notes: '' })

  // ── Queries ──────────────────────────────────────────────────────

  const { data: expensesData, isLoading } = useQuery({
    queryKey: ['expenses', statusFilter, search, page],
    queryFn: () => api.get('/expenses/', { params: { status: statusFilter || undefined, search: search || undefined, page, page_size: 20 } }).then((r) => r.data.data),
  })
  const expenses: Expense[] = expensesData?.items || []
  const total = expensesData?.total || 0
  const totalPages = Math.max(1, Math.ceil(total / 20))

  const { data: categoriesData } = useQuery({
    queryKey: ['expense-categories'],
    queryFn: () => api.get('/expenses/categories').then((r) => r.data.data),
  })
  const categories: ExpenseCategory[] = categoriesData || []

  // ── Mutations ────────────────────────────────────────────────────

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['expenses'] })

  const createExpense = useMutation({
    mutationFn: () => api.post('/expenses/', form),
    onSuccess: () => { setModal(null); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })

  const updateExpense = useMutation({
    mutationFn: () => api.put(`/expenses/${selected!.id}`, editForm),
    onSuccess: () => { setModal(null); setSelected(null); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })

  const approveExpense = useMutation({
    mutationFn: (id: string) => api.post(`/expenses/${id}/approve`),
    onSuccess: () => refresh(),
    onError: (e) => setError(errorText(e)),
  })

  const rejectExpense = useMutation({
    mutationFn: (id: string) => api.post(`/expenses/${id}/reject`),
    onSuccess: () => refresh(),
    onError: (e) => setError(errorText(e)),
  })

  // ── Filtered data ────────────────────────────────────────────────
  // Search და pagination ხდება server-side-ზე (/expenses/?search=&page=)

  const visible = expenses

  const totalPending = expenses.filter((e) => e.status === 'pending').reduce((s, e) => s + e.amount, 0)
  const totalApproved = expenses.filter((e) => e.status === 'approved').reduce((s, e) => s + e.amount, 0)
  const totalAll = expenses.reduce((s, e) => s + e.amount, 0)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('ხარჯები')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('თანამშრომლების ხარჯების აღრიცხვა')}</p>
        </div>
        <button
          className="btn-primary flex items-center gap-2"
          onClick={() => {
            setForm({ category_id: null, expense_date: today(), description: '', amount: 0, currency: 'GEL', notes: null })
            setError('')
            setModal('create')
          }}
        >
          <Plus size={18} /> {t('ახალი ხარჯი')}
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <DollarSign className="text-primary-600" />
            <div>
              <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('ჯამური ხარჯები')}</div>
              <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{money(totalAll)}</div>
            </div>
          </div>
        </div>
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <Clock className="text-amber-600" />
            <div>
              <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('მოლოდინში')}</div>
              <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{money(totalPending)}</div>
            </div>
          </div>
        </div>
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <CheckCircle className="text-green-600" />
            <div>
              <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('დამტკიცებული')}</div>
              <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{money(totalApproved)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <input value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder={t('ძებნა...')} className="input pl-10" />
        </div>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} options={[
          { value: '', label: 'ყველა' },
          { value: 'pending', label: 'მოლოდინში' },
          { value: 'approved', label: 'დამტკიცებული' },
          { value: 'rejected', label: 'უარყოფილი' },
          { value: 'paid', label: 'გადახდილი' },
        ]} className="w-40" />
      </div>

      {/* Table */}
      <DataTable
        columns={[
          { key: 'expense_date', label: 'თარიღი' },
          { key: 'employee_name', label: 'თანამშრომელი', render: (e: Expense) => (
            <span className="flex items-center gap-1"><User size={14} />{e.employee_name}</span>
          )},
          { key: 'description', label: 'აღწერა', render: (e: Expense) => (
            <div className="max-w-[250px] truncate" title={e.description}>{e.description}</div>
          )},
          { key: 'category_name', label: 'კატეგორია', render: (e: Expense) => e.category_name || '—' },
          { key: 'amount', label: 'თანხა', render: (e: Expense) => <span className="font-semibold">{money(e.amount)}</span> },
          {
            key: 'status', label: 'სტატუსი',
            render: (e: Expense) => {
              const s = statuses[e.status] || statuses.pending
              return <span className={`badge ${s.cls}`}>{s.label}</span>
            },
          },
          {
            key: 'actions', label: '',
            render: (e: Expense) => (
              <div className="flex items-center gap-1">
                {e.status === 'pending' && (
                  <>
                    <button onClick={(e2) => { e2.stopPropagation(); approveExpense.mutate(e.id) }} className="p-1.5 hover:bg-green-50 rounded-lg" title={t('დამტკიცება')}>
                      <CheckCircle size={16} className="text-green-500" />
                    </button>
                    <button onClick={(e2) => { e2.stopPropagation(); rejectExpense.mutate(e.id) }} className="p-1.5 hover:bg-red-50 rounded-lg" title={t('უარყოფა')}>
                      <XCircle size={16} className="text-red-500" />
                    </button>
                  </>
                )}
                <button onClick={(e2) => { e2.stopPropagation(); setSelected(e); setEditForm({ description: e.description, amount: e.amount, notes: e.notes || '' }); setError(''); setModal('edit') }} className="p-1.5 hover:bg-gray-100 rounded-lg dark:hover:bg-dark-100">
                  <Pencil size={16} className="text-gray-400 dark:text-gray-500" />
                </button>
              </div>
            ),
          },
        ]}
        data={visible}
        isLoading={isLoading}
        emptyMessage={t('ხარჯები არ მოიძებნა')}
        page={page}
        totalPages={totalPages}
        total={total}
        onPageChange={setPage}
      />

      {/* Create Modal */}
      <Modal open={modal === 'create'} onClose={() => setModal(null)} title={t('ახალი ხარჯი')} size="md">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormField label={t('თარიღი')} required>
              <input type="date" value={form.expense_date} onChange={(e) => setForm({ ...form, expense_date: e.target.value })} className="input" />
            </FormField>
            <FormField label={t('კატეგორია')}>
              <Select value={form.category_id || ''} onChange={(e) => setForm({ ...form, category_id: e.target.value || null })} options={categories.map((c) => ({ value: c.id, label: c.name }))} placeholder={t('აირჩიეთ')} />
            </FormField>
          </div>
          <FormField label={t('აღწერა')} required>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={3} placeholder={t('ხარჯის აღწერა')} />
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label={t('თანხა')} required>
              <input type="number" step="0.01" value={form.amount || ''} onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })} className="input" />
            </FormField>
            <FormField label={t('ვალუტა')}>
              <Select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} options={[{ value: 'GEL', label: 'GEL' }, { value: 'USD', label: 'USD' }, { value: 'EUR', label: 'EUR' }]} />
            </FormField>
          </div>
          <FormField label={t('შენიშვნა')}>
            <textarea value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value || null })} className="input" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setModal(null)} className="btn-secondary">{t('გაუქმება')}</button>
            <button onClick={() => { if (!form.description.trim() || !form.amount) { setError(t('აღწერა და თანხა სავალდებულოა')); return }; createExpense.mutate() }} disabled={createExpense.isPending} className="btn-primary">
              {createExpense.isPending ? t('ინახება...') : t('დაფიქსირება')}
            </button>
          </div>
        </div>
      </Modal>

      {/* Edit Modal */}
      <Modal open={modal === 'edit'} onClose={() => setModal(null)} title={t('ხარჯის რედაქტირება')} size="md">
        <div className="space-y-4">
          <FormField label={t('აღწერა')}>
            <textarea value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} className="input" rows={3} />
          </FormField>
          <FormField label={t('თანხა')}>
            <input type="number" step="0.01" value={editForm.amount || ''} onChange={(e) => setEditForm({ ...editForm, amount: Number(e.target.value) })} className="input" />
          </FormField>
          <FormField label={t('შენიშვნა')}>
            <textarea value={editForm.notes} onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })} className="input" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setModal(null)} className="btn-secondary">{t('გაუქმება')}</button>
            <button onClick={() => updateExpense.mutate()} disabled={updateExpense.isPending} className="btn-primary">
              {updateExpense.isPending ? t('ინახება...') : t('შენახვა')}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
