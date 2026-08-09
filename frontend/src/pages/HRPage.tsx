import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Users, DollarSign, Calendar, Clock, Building2, Briefcase, ChevronDown, ChevronRight } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { api } from '../services/api'
import type { ApiResponse, PaginatedResponse } from '../types'

// ── Types ─────────────────────────────────────────────────────────────

interface Department {
  id: string; code: string; name: string; is_active: boolean
}

interface Employee {
  id: string; personal_number: string; full_name: string; position: string
  department_id: string | null; department_name: string | null
  email: string | null; phone: string | null
  contract_type: string; status: string
  hire_date: string; termination_date: string | null
  base_salary: number; salary_currency: string
}

interface PayrollEntry {
  id: string; employee_id: string; employee_name: string | null
  period_year: number; period_month: number
  base_salary: number; gross_pay: number; additions: number
  deductions: number; income_tax: number; net_pay: number
  status: string; payment_date: string | null
}

const money = (v: number, c = 'GEL') => new Intl.NumberFormat('ka-GE', { style: 'currency', currency: c }).format(v)

const statusColors: Record<string, string> = {
  active: 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  on_leave: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  terminated: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400',
}

const contractLabels: Record<string, string> = {
  permanent: i18n.t('მუდმივი'), fixed_term: i18n.t('ვადიანი'), contract: i18n.t('ხელშეკრულება'),
}

const tabs = [
  { id: 'employees', label: i18n.t('თანამშრომლები'), icon: Users },
  { id: 'payroll', label: i18n.t('ხელფასები'), icon: DollarSign },
  { id: 'timesheets', label: 'Timesheets', icon: Clock },
]

export default function HRPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState('employees')
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [payrollYear, setPayrollYear] = useState(new Date().getFullYear())
  const [payrollMonth, setPayrollMonth] = useState(new Date().getMonth() + 1)
  const [form, setForm] = useState({
    personal_number: '', full_name: '', position: '', department_id: '',
    email: '', phone: '', contract_type: 'permanent', hire_date: '',
    base_salary: 0, salary_currency: 'GEL', notes: '',
  })
  const [error, setError] = useState('')

  // ── Queries ──────────────────────────────────────────────────────

  const { data: empData, isLoading: empLoading } = useQuery({
    queryKey: ['hr-employees', search],
    queryFn: () => api.get('/hr/employees', { params: { search: search || undefined, page_size: 100 } }).then(r => r.data.data),
  })
  const { data: deptData } = useQuery({
    queryKey: ['hr-departments'],
    queryFn: () => api.get('/hr/departments').then(r => r.data.data),
  })
  const { data: payrollData, isLoading: payLoading } = useQuery({
    queryKey: ['hr-payroll', payrollYear, payrollMonth],
    queryFn: () => api.get('/hr/payroll', { params: { year: payrollYear, month: payrollMonth, page_size: 100 } }).then(r => r.data.data),
  })

  const employees: Employee[] = empData?.items || []
  const departments: Department[] = deptData || []
  const payrollEntries: PayrollEntry[] = payrollData?.items || []

  // ── Mutations ─────────────────────────────────────────────────────

  const createMutation = useMutation({
    mutationFn: (data: any) => editId
      ? api.patch(`/hr/employees/${editId}`, data)
      : api.post('/hr/employees', data),
    onSuccess: () => { setShowModal(false); setEditId(null); resetForm(); queryClient.invalidateQueries({ queryKey: ['hr-employees'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  const calcMutation = useMutation({
    mutationFn: () => api.post('/hr/payroll/calculate', { year: payrollYear, month: payrollMonth }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hr-payroll'] }),
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  function resetForm() {
    setForm({ personal_number: '', full_name: '', position: '', department_id: '', email: '', phone: '', contract_type: 'permanent', hire_date: '', base_salary: 0, salary_currency: 'GEL', notes: '' })
    setError('')
  }

  function openEdit(emp: Employee) {
    setEditId(emp.id)
    setForm({
      personal_number: emp.personal_number, full_name: emp.full_name, position: emp.position,
      department_id: emp.department_id || '', email: emp.email || '', phone: emp.phone || '',
      contract_type: emp.contract_type, hire_date: emp.hire_date,
      base_salary: emp.base_salary, salary_currency: emp.salary_currency, notes: '',
    })
    setShowModal(true)
  }

  function submit(e: React.FormEvent) {
    e.preventDefault()
    createMutation.mutate(form)
  }

  const totalGross = payrollEntries.reduce((s, e) => s + e.gross_pay, 0)
  const totalTax = payrollEntries.reduce((s, e) => s + e.income_tax, 0)
  const totalNet = payrollEntries.reduce((s, e) => s + e.net_pay, 0)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('HR / კადრები')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('თანამშრომლების რეესტრი, ხელფასები, timesheets')}</p>
        </div>
        {tab === 'employees' && (
          <button onClick={() => { setEditId(null); resetForm(); setShowModal(true) }} className="btn btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('თანამშრომლის დამატება')}
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-brandgray-100 dark:border-dark-50">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id
                ? 'border-primary-600 text-primary-700 dark:border-primary-400 dark:text-primary-300'
                : 'border-transparent text-brandgray-500 hover:text-brandgray-700 dark:text-gray-400'
            }`}
          >
            <t.icon size={18} /> {t.label}
          </button>
        ))}
      </div>

      {/* ── Employees Tab ──────────────────────────────────────────── */}
      {tab === 'employees' && (
        <>
          <div className="flex flex-wrap gap-3">
            <div className="relative min-w-64 flex-1">
              <Search className="absolute left-3 top-2.5 text-gray-400 dark:text-gray-500" size={18} />
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder={t('ძებნა სახელით, პოზიციით...')}
                className="w-full rounded-lg border py-2 pl-10 pr-3 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                  <tr>
                    <th className="px-4 py-3">{t('სახელი / პოზიცია')}</th>
                    <th className="px-4 py-3">{t('პირადი ნომერი')}</th>
                    <th className="px-4 py-3">{t('დეპარტამენტი')}</th>
                    <th className="px-4 py-3">{t('ხელშეკრულება')}</th>
                    <th className="px-4 py-3 text-right">{t('ხელფასი')}</th>
                    <th className="px-4 py-3">{t('სტატუსი')}</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y dark:divide-dark-50">
                  {empLoading ? (
                    <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
                  ) : employees.length === 0 ? (
                    <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('თანამშრომლები არ მოიძებნა')}</td></tr>
                  ) : employees.map(emp => (
                    <tr key={emp.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                      <td className="px-4 py-3">
                        <div className="font-medium text-brandgray-900 dark:text-gray-100">{emp.full_name}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">{emp.position}</div>
                      </td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{emp.personal_number}</td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{emp.department_name || '—'}</td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{contractLabels[emp.contract_type] || emp.contract_type}</td>
                      <td className="px-4 py-3 text-right font-medium dark:text-gray-100">{money(emp.base_salary, emp.salary_currency)}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusColors[emp.status] || ''}`}>
                          {emp.status === 'active' ? 'აქტიური' : emp.status === 'on_leave' ? t('შვებულება') : t('გათავისუფლებული')}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button onClick={() => openEdit(emp)} className="text-primary-600 hover:underline text-xs dark:text-primary-400">{t('რედაქტირება')}</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* ── Payroll Tab ─────────────────────────────────────────────── */}
      {tab === 'payroll' && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Calendar size={18} className="text-gray-400 dark:text-gray-500" />
              <select value={payrollYear} onChange={e => setPayrollYear(Number(e.target.value))} className="input w-28 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                {Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - 2 + i).map(y => <option key={y} value={y}>{y}</option>)}
              </select>
              <select value={payrollMonth} onChange={e => setPayrollMonth(Number(e.target.value))} className="input w-32 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                {Array.from({ length: 12 }, (_, i) => i + 1).map(m => <option key={m} value={m}>{m.toString().padStart(2, '0')}</option>)}
              </select>
            </div>
            <button onClick={() => calcMutation.mutate()} disabled={calcMutation.isPending}
              className="btn btn-primary text-sm flex items-center gap-2">
              <DollarSign size={16} /> {calcMutation.isPending ? t('მუშავდება...') : t('ხელფასების გაანგარიშება')}
            </button>
          </div>

          {/* Summary cards */}
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <p className="text-xs text-gray-500 dark:text-gray-400">{t('მთლიანი დარიცხვა')}</p>
              <p className="mt-2 text-xl font-bold text-brandgray-900 dark:text-gray-100">{money(totalGross)}</p>
            </div>
            <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <p className="text-xs text-gray-500 dark:text-gray-400">{t('საშემოსავლო გადასახადი (15%)')}</p>
              <p className="mt-2 text-xl font-bold text-amber-700 dark:text-amber-400">{money(totalTax)}</p>
            </div>
            <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <p className="text-xs text-gray-500 dark:text-gray-400">{t('გასაცემი ხელფასი')}</p>
              <p className="mt-2 text-xl font-bold text-green-700 dark:text-green-400">{money(totalNet)}</p>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                  <tr>
                    <th className="px-4 py-3">{t('თანამშრომელი')}</th>
                    <th className="px-4 py-3 text-right">{t('დარიცხვა')}</th>
                    <th className="px-4 py-3 text-right">{t('დამატებები')}</th>
                    <th className="px-4 py-3 text-right">{t('დაკავებები')}</th>
                    <th className="px-4 py-3 text-right">{t('გადასახადი')}</th>
                    <th className="px-4 py-3 text-right">{t('გასაცემი')}</th>
                    <th className="px-4 py-3">{t('სტატუსი')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y dark:divide-dark-50">
                  {payLoading ? (
                    <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
                  ) : payrollEntries.length === 0 ? (
                    <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">ამ პერიოდისთვის მონაცემები არ არის. დააჭირეთ "ხელფასების გაანგარიშება"</td></tr>
                  ) : payrollEntries.map(entry => (
                    <tr key={entry.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                      <td className="px-4 py-3 font-medium dark:text-gray-100">{entry.employee_name || '—'}</td>
                      <td className="px-4 py-3 text-right dark:text-gray-200">{money(entry.gross_pay)}</td>
                      <td className="px-4 py-3 text-right dark:text-gray-200">{money(entry.additions)}</td>
                      <td className="px-4 py-3 text-right dark:text-gray-200">{money(entry.deductions)}</td>
                      <td className="px-4 py-3 text-right text-amber-700 dark:text-amber-400">{money(entry.income_tax)}</td>
                      <td className="px-4 py-3 text-right font-semibold text-green-700 dark:text-green-400">{money(entry.net_pay)}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                          entry.status === 'paid' ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                          entry.status === 'approved' ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                          'bg-gray-50 text-gray-600 dark:bg-dark-100 dark:text-gray-400'
                        }`}>
                          {entry.status === 'paid' ? 'გადახდილი' : entry.status === 'approved' ? t('დამტკიცებული') : t('მონახაზი')}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* ── Timesheets Tab ──────────────────────────────────────────── */}
      {tab === 'timesheets' && (
        <div className="rounded-xl border bg-white p-8 text-center text-sm text-gray-500 dark:border-dark-50 dark:bg-dark-200 dark:text-gray-400">
          {t('Timesheets ფუნქციონალი API-ში მზადაა. Frontend UI მალე დაემატება.')}
        </div>
      )}

      {/* ── Employee Modal ─────────────────────────────────────────── */}
      <Modal open={showModal} onClose={() => setShowModal(false)} title={editId ? t('თანამშრომლის რედაქტირება') : t('ახალი თანამშრომელი')} size="lg">
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label={t('სრული სახელი')} required>
              <input required value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('პირადი ნომერი')} required>
              <input required value={form.personal_number} onChange={e => setForm({ ...form, personal_number: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('პოზიცია')} required>
              <input required value={form.position} onChange={e => setForm({ ...form, position: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('დეპარტამენტი')}>
              <select value={form.department_id} onChange={e => setForm({ ...form, department_id: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                <option value="">{t('აირჩიეთ')}</option>
                {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </FormField>
            <FormField label={t('ელ. ფოსტა')}>
              <input value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('ტელეფონი')}>
              <input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('ხელშეკრულების ტიპი')}>
              <select value={form.contract_type} onChange={e => setForm({ ...form, contract_type: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                <option value="permanent">{t('მუდმივი')}</option>
                <option value="fixed_term">{t('ვადიანი')}</option>
                <option value="contract">{t('ხელშეკრულება')}</option>
              </select>
            </FormField>
            <FormField label={t('დაქირავების თარიღი')} required>
              <input required type="date" value={form.hire_date} onChange={e => setForm({ ...form, hire_date: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('საბაზისო ხელფასი')}>
              <input type="number" value={form.base_salary || ''} onChange={e => setForm({ ...form, base_salary: Number(e.target.value) })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button type="submit" disabled={createMutation.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {createMutation.isPending ? 'ინახება...' : editId ? t('შენახვა') : t('თანამშრომლის დამატება')}
          </button>
        </form>
      </Modal>
    </div>
  )
}
