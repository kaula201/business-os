import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Users, DollarSign, Calendar, Clock, Building2, Briefcase, ChevronDown, ChevronRight, FileText, Plane, CheckCircle2, Star, UserPlus, SlidersHorizontal, Trash2, Calculator } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { api, payrollEngineApi } from '../services/api'
import type { ApiResponse, PaginatedResponse } from '../types'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

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
  { id: 'employees', label: 'თანამშრომლები', icon: Users },
  { id: 'contracts', label: 'კონტრაქტები', icon: FileText },
  { id: 'payroll', label: 'ხელფასები', icon: DollarSign },
  { id: 'payroll-rules', label: 'სტრუქტურები და წესები', icon: SlidersHorizontal },
  { id: 'payslips', label: 'Payslips', icon: FileText },
  { id: 'leave', label: 'შვებულება', icon: Plane },
  { id: 'attendance', label: 'დასწრება', icon: Calendar },
  { id: 'appraisal', label: 'შეფასება', icon: Star },
  { id: 'recruitment', label: 'რეკრუტირება', icon: UserPlus },
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
  const [attModal, setAttModal] = useState(false)
  const [leaveModal, setLeaveModal] = useState(false)
  const [jobModal, setJobModal] = useState(false)
  const [reviewModal, setReviewModal] = useState(false)
  const [attForm, setAttForm] = useState({ employee_id: '', date: new Date().toISOString().slice(0, 10), status: 'present' })
  const [leaveForm, setLeaveForm] = useState({ employee_id: '', leave_type_id: '', start_date: '', end_date: '', total_days: 1, reason: '' })
  const [jobForm, setJobForm] = useState({ title: '', department: '', status: 'open', deadline: '' })
  const [reviewForm, setReviewForm] = useState({ employee_id: '', review_period: '', overall_rating: 5 })
  const [tsModal, setTsModal] = useState(false)
  const [tsForm, setTsForm] = useState({ employee_id: '', work_date: new Date().toISOString().slice(0, 10), hours_worked: 8, overtime_hours: 0, description: '' })
  // Payroll engine (Odoo-depth)
  const [selStructure, setSelStructure] = useState<string | null>(null)
  const [structModal, setStructModal] = useState(false)
  const [structForm, setStructForm] = useState({ name: '', description: '' })
  const [ruleModal, setRuleModal] = useState(false)
  const [ruleForm, setRuleForm] = useState({ code: '', name: '', category: 'addition', amount_type: 'fixed', amount: 0, formula: '', basis: 'gross', sequence: 10 })
  const [paramModal, setParamModal] = useState(false)
  const [paramForm, setParamForm] = useState({ key: '', value: 0, description: '' })
  const [calcModal, setCalcModal] = useState(false)
  const [calcForm, setCalcForm] = useState({ employee_id: '', period_year: new Date().getFullYear(), period_month: new Date().getMonth() + 1, base_salary: 0, structure_id: '', additions: 0, deductions: 0 })
  const [calcResult, setCalcResult] = useState<any>(null)

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

  const { data: payslipData, isLoading: payslipLoading } = useQuery({
    queryKey: ['hr-payslips', payrollYear, payrollMonth],
    queryFn: () => api.get('/hr/payslips', { params: { year: payrollYear, month: payrollMonth } }).then(r => r.data.data),
  })
  // Payroll engine (Odoo-depth)
  const { data: structuresData } = useQuery({
    queryKey: ['payroll-structures'],
    queryFn: () => payrollEngineApi.structures(),
  })
  const { data: rulesData } = useQuery({
    queryKey: ['payroll-rules', selStructure],
    queryFn: () => selStructure ? payrollEngineApi.rules(selStructure) : [],
    enabled: !!selStructure,
  })
  const { data: paramsData } = useQuery({
    queryKey: ['payroll-params'],
    queryFn: () => payrollEngineApi.parameters(),
  })
  const { data: workEntriesData } = useQuery({
    queryKey: ['payroll-work-entries'],
    queryFn: () => payrollEngineApi.workEntries(),
  })
  const { data: leaveData, isLoading: leaveLoading } = useQuery({
    queryKey: ['hr-leave'],
    queryFn: () => api.get('/hr/leave-requests').then(r => r.data.data),
  })
  const { data: attendanceData, isLoading: attLoading } = useQuery({
    queryKey: ['hr-attendance'],
    queryFn: () => api.get('/hr/attendance').then(r => r.data.data),
  })
  const { data: reviewData, isLoading: reviewLoading } = useQuery({
    queryKey: ['hr-reviews'],
    queryFn: () => api.get('/hr/reviews').then(r => r.data.data),
  })
  const { data: jobData, isLoading: jobLoading } = useQuery({
    queryKey: ['hr-jobs'],
    queryFn: () => api.get('/recruitment/', { params: { page_size: 100 } }).then(r => r.data.data),
  })
  const { data: tsData, isLoading: tsLoading } = useQuery({
    queryKey: ['hr-timesheets'],
    queryFn: () => api.get('/hr/timesheets', { params: { page_size: 100 } }).then(r => r.data.data),
  })

  const employees: Employee[] = empData?.items || []
  const departments: Department[] = deptData || []
  const payrollEntries: PayrollEntry[] = payrollData?.items || []
  const payslips: any[] = payslipData || []
  const [explainPayslip, setExplainPayslip] = useState<any>(null)
  const leaveRequests: any[] = leaveData || []
  const attendanceRecords: any[] = attendanceData || []
  const reviews: any[] = reviewData || []
  const jobPostings: any[] = jobData?.items || []
  const timesheets: any[] = tsData?.items || tsData || []

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

  const genPayslips = useMutation({
    mutationFn: () => api.post('/hr/payslips/generate', null, { params: { year: payrollYear, month: payrollMonth } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hr-payslips'] }),
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  // Payroll engine mutations (Odoo-depth)
  const createStructure = useMutation({
    mutationFn: () => payrollEngineApi.createStructure(structForm),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['payroll-structures'] }); setStructModal(false); setStructForm({ name: '', description: '' }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const deleteStructure = useMutation({
    mutationFn: (id: string) => payrollEngineApi.deleteStructure(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['payroll-structures'] }); if (selStructure) setSelStructure(null) },
  })
  const createRule = useMutation({
    mutationFn: () => selStructure ? payrollEngineApi.createRule(selStructure, ruleForm) : Promise.reject(),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['payroll-rules'] }); setRuleModal(false); setRuleForm({ code: '', name: '', category: 'addition', amount_type: 'fixed', amount: 0, formula: '', basis: 'gross', sequence: 10 }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const deleteRule = useMutation({
    mutationFn: (id: string) => payrollEngineApi.deleteRule(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['payroll-rules'] }),
  })
  const setParameter = useMutation({
    mutationFn: () => payrollEngineApi.setParameter(paramForm),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['payroll-params'] }); setParamModal(false); setParamForm({ key: '', value: 0, description: '' }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const runCalc = useMutation({
    mutationFn: () => payrollEngineApi.calculate(calcForm),
    onSuccess: (d) => { setCalcResult(d); queryClient.invalidateQueries({ queryKey: ['hr-payroll'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  const approveLeave = useMutation({
    mutationFn: (id: string) => api.post(`/hr/leave-requests/${id}/approve`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hr-leave'] }),
  })

  const createAttendance = useMutation({
    mutationFn: () => api.post('/hr/attendance', attForm),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['hr-attendance'] }); setAttModal(false); setAttForm({ employee_id: '', date: new Date().toISOString().slice(0, 10), status: 'present' }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  const createLeave = useMutation({
    mutationFn: () => api.post('/hr/leave-requests', leaveForm),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['hr-leave'] }); setLeaveModal(false); setLeaveForm({ employee_id: '', leave_type_id: '', start_date: '', end_date: '', total_days: 1, reason: '' }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  const createJob = useMutation({
    mutationFn: () => api.post('/recruitment/', jobForm),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['hr-jobs'] }); setJobModal(false); setJobForm({ title: '', department: '', status: 'open', deadline: '' }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  const createTimesheet = useMutation({
    mutationFn: () => api.post('/hr/timesheets', tsForm),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['hr-timesheets'] }); setTsModal(false); setTsForm({ employee_id: '', work_date: new Date().toISOString().slice(0, 10), hours_worked: 8, overtime_hours: 0, description: '' }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  const createReview = useMutation({
    mutationFn: () => api.post('/hr/reviews', reviewForm),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['hr-reviews'] }); setReviewModal(false); setReviewForm({ employee_id: '', review_period: '', overall_rating: 5 }) },
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
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('HR / ადამიანური რესურსები')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('თანამშრომლების რეესტრი, ხელფასები, timesheets')}</p>
        </div>
        {tab === 'employees' && (
          <button onClick={() => { setEditId(null); resetForm(); setShowModal(true) }} className="btn btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('თანამშრომლის დამატება')}
          </button>
        )}
        {tab === 'attendance' && (
          <button onClick={() => setAttModal(true)} className="btn btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('დასწრების დაფიქსირება')}
          </button>
        )}
        {tab === 'leave' && (
          <button onClick={() => setLeaveModal(true)} className="btn btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('შვებულების მოთხოვნა')}
          </button>
        )}
        {tab === 'recruitment' && (
          <button onClick={() => setJobModal(true)} className="btn btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('ახალი ვაკანსია')}
          </button>
        )}
        {tab === 'appraisal' && (
          <button onClick={() => setReviewModal(true)} className="btn btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('ახალი შეფასება')}
          </button>
        )}
        {tab === 'timesheets' && (
          <button onClick={() => setTsModal(true)} className="btn btn-primary flex items-center gap-2">
            <Plus size={18} /> {t('ახალი ჩანაწერი')}
          </button>
        )}
        {tab === 'payroll-rules' && (
          <div className="flex gap-2">
            <button onClick={() => setStructModal(true)} className="btn btn-primary flex items-center gap-2">
              <Plus size={18} /> {t('ახალი სტრუქტურა')}
            </button>
            <button onClick={() => setParamModal(true)} className="btn btn-outline flex items-center gap-2">
              <SlidersHorizontal size={16} /> {t('პარამეტრები')}
            </button>
            <button onClick={() => { setCalcResult(null); setCalcModal(true) }} className="btn btn-outline flex items-center gap-2">
              <Calculator size={16} /> {t('გაანგარიშება წესებით')}
            </button>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-brandgray-100 dark:border-dark-50">
        {tabs.map(tabItem => (
          <button key={tabItem.id} onClick={() => setTab(tabItem.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === tabItem.id
                ? 'border-primary-600 text-primary-700 dark:border-primary-400 dark:text-primary-300'
                : 'border-transparent text-brandgray-500 hover:text-brandgray-700 dark:text-gray-400'
            }`}
          >
            <tabItem.icon size={18} /> {t(tabItem.label)}
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

      {/* ── Contracts Tab ───────────────────────────────────────────── */}
      {tab === 'contracts' && (
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
                    <th className="px-4 py-3">{t('თანამშრომელი')}</th>
                    <th className="px-4 py-3">{t('ხელშეკრულების ტიპი')}</th>
                    <th className="px-4 py-3">{t('დაქირავების თარიღი')}</th>
                    <th className="px-4 py-3 text-right">{t('ხელფასი')}</th>
                    <th className="px-4 py-3">{t('სტატუსი')}</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y dark:divide-dark-50">
                  {empLoading ? (
                    <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
                  ) : employees.length === 0 ? (
                    <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('კონტრაქტები არ მოიძებნა')}</td></tr>
                  ) : employees.map(emp => (
                    <tr key={emp.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                      <td className="px-4 py-3">
                        <div className="font-medium text-brandgray-900 dark:text-gray-100">{emp.full_name}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">{emp.position}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                          emp.contract_type === 'permanent' ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : emp.contract_type === 'fixed_term' ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                          : 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                        }`}>
                          {contractLabels[emp.contract_type] || emp.contract_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                        {emp.hire_date ? fmtDate(new Date(emp.hire_date)) : '—'}
                      </td>
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
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('თანამშრომელი')}</th>
                  <th className="px-4 py-3">{t('თარიღი')}</th>
                  <th className="px-4 py-3 text-right">{t('საათები')}</th>
                  <th className="px-4 py-3 text-right">{t('ზეგანაკვეთური')}</th>
                  <th className="px-4 py-3">{t('აღწერა')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {tsLoading ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
                ) : timesheets.length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('Timesheets ჩანაწერები არ არის')}</td></tr>
                ) : timesheets.map((ts: any) => (
                  <tr key={ts.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">
                      {employees.find(e => e.id === ts.employee_id)?.full_name || '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{fmtDate(new Date(ts.work_date))}</td>
                    <td className="px-4 py-3 text-right font-mono dark:text-gray-100">{ts.hours_worked}</td>
                    <td className="px-4 py-3 text-right font-mono text-amber-600 dark:text-amber-400">{ts.overtime_hours || 0}</td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{ts.description || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Payslips Tab ─────────────────────────────────────────────── */}
      {tab === 'payslips' && (
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
            <button onClick={() => genPayslips.mutate()} disabled={genPayslips.isPending}
              className="btn btn-primary text-sm flex items-center gap-2">
              <FileText size={16} /> {genPayslips.isPending ? t('მუშავდება...') : t('Payslips-ის გენერაცია')}
            </button>
          </div>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                  <tr>
                    <th className="px-4 py-3">{t('ნომერი')}</th>
                    <th className="px-4 py-3">{t('თანამშრომელი')}</th>
                    <th className="px-4 py-3">{t('პერიოდი')}</th>
                    <th className="px-4 py-3 text-right">{t('დარიცხვა')}</th>
                    <th className="px-4 py-3 text-right">{t('პენსია 2%')}</th>
                    <th className="px-4 py-3 text-right">{t('გადასახადი 15%')}</th>
                    <th className="px-4 py-3 text-right">{t('გასაცემი')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y dark:divide-dark-50">
                  {payslipLoading ? (
                    <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
                  ) : payslips.length === 0 ? (
                    <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('Payslips არ არის. ჯერ ხელფასები გამოთვალეთ, მერე გენერაცია გაუშვით.')}</td></tr>
                  ) : payslips.map(p => (
                    <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                      <td className="px-4 py-3 font-mono text-xs dark:text-gray-300">{p.payslip_number}</td>
                      <td className="px-4 py-3 font-medium dark:text-gray-100">{p.employee_name}</td>
                      <td className="px-4 py-3 dark:text-gray-300">{p.period}</td>
                      <td className="px-4 py-3 text-right dark:text-gray-200">{money(p.gross_pay)}</td>
                      <td className="px-4 py-3 text-right text-amber-700 dark:text-amber-400">{money(p.pension_contribution)}</td>
                      <td className="px-4 py-3 text-right text-amber-700 dark:text-amber-400">{money(p.income_tax)}</td>
                      <td className="px-4 py-3 text-right font-semibold text-green-700 dark:text-green-400">{money(p.net_pay)}</td>
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => setExplainPayslip(p)}
                          className="rounded-lg border border-gray-200 px-2 py-1 text-xs font-medium text-brandgray-600 hover:bg-gray-50 dark:border-dark-50 dark:text-gray-300 dark:hover:bg-dark-100">
                          {t('ახსნა')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {explainPayslip && explainPayslip.explanation && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setExplainPayslip(null)}>
              <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl dark:bg-dark-200" onClick={e => e.stopPropagation()}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-brandgray-900 dark:text-gray-100">{t('გადასახადის ახსნა')}</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400">{explainPayslip.payslip_number} — {explainPayslip.employee_name}</p>
                  </div>
                  <button onClick={() => setExplainPayslip(null)} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-100">✕</button>
                </div>
                <div className="mt-4 space-y-3">
                  {explainPayslip.explanation.lines?.map((line: any, i: number) => (
                    <div key={i} className="rounded-xl border border-gray-100 p-3 dark:border-dark-50">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-brandgray-900 dark:text-gray-100">{line.label_ka}</span>
                        <span className="rounded-full bg-primary-50 px-2 py-0.5 text-xs font-bold text-primary-700 dark:bg-primary-900/30 dark:text-primary-200">{line.rate}</span>
                      </div>
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{line.basis_ka}</p>
                      <p className="mt-1 text-xs text-gray-600 dark:text-gray-300">{line.note_ka}</p>
                      <p className="mt-1 text-right text-sm font-bold text-gray-900 dark:text-gray-100">{money(line.amount)}</p>
                    </div>
                  ))}
                  {explainPayslip.explanation.meta && (
                    <div className="rounded-xl bg-gray-50 p-3 text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                      <div className="flex justify-between"><span>{t('ზოგადი განაკვეთი')}:</span><span>{explainPayslip.explanation.meta.general_rate}</span></div>
                      <div className="mt-1 flex justify-between"><span>{t('მოქმედი განაკვეთი')}:</span><span>{explainPayslip.explanation.meta.applied_rate}</span></div>
                      <div className="mt-1 flex justify-between"><span>{t('სამართლებრივი საფუძველი')}:</span><span>{explainPayslip.explanation.meta.legal_basis_ka}</span></div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Payroll Rules Tab (Odoo-depth) ─────────────────────────────── */}
      {tab === 'payroll-rules' && (
        <div className="space-y-4">
          {/* Structures + rules */}
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">{t('სახელფასო სტრუქტურები')}</h3>
              {!structuresData || structuresData.length === 0 ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">{t('სტრუქტურები არ არის')}</p>
              ) : (
                <div className="space-y-2">
                  {structuresData.map((s: any) => (
                    <div key={s.id} className={`flex items-center justify-between rounded-lg border p-3 cursor-pointer ${selStructure === s.id ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20' : 'dark:border-dark-50'}`}
                      onClick={() => setSelStructure(selStructure === s.id ? null : s.id)}>
                      <div>
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{s.name}</p>
                        {s.description && <p className="text-xs text-gray-500 dark:text-gray-400">{s.description}</p>}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${s.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400' : 'bg-gray-100 text-gray-500'}`}>
                          {s.is_active ? t('აქტიური') : t('არააქტიური')}
                        </span>
                        <button onClick={(e) => { e.stopPropagation(); deleteStructure.mutate(s.id) }} className="text-gray-400 hover:text-red-500">
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{t('სახელფასო წესები')}</h3>
                {selStructure && (
                  <button onClick={() => setRuleModal(true)} className="btn btn-primary btn-sm flex items-center gap-1">
                    <Plus size={14} /> {t('ახალი წესი')}
                  </button>
                )}
              </div>
              {!selStructure ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">{t('აირჩიეთ სტრუქტურა')}</p>
              ) : !rulesData || rulesData.length === 0 ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">{t('წესები არ არის')}</p>
              ) : (
                <div className="space-y-2">
                  {rulesData.map((r: any) => (
                    <div key={r.id} className="flex items-center justify-between rounded-lg border p-3 dark:border-dark-50">
                      <div>
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
                          <span className="font-mono text-xs text-primary-600 dark:text-primary-400 mr-2">{r.code}</span>{r.name}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {r.category} · {r.amount_type}
                          {r.amount_type === 'fixed' && ` · ${r.amount} ₾`}
                          {r.amount_type === 'percentage' && ` · ${r.amount}% (${r.basis})`}
                          {r.amount_type === 'formula' && ` · ${r.formula}`}
                        </p>
                      </div>
                      <button onClick={() => deleteRule.mutate(r.id)} className="text-gray-400 hover:text-red-500">
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Parameters + work entries */}
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">{t('წესების პარამეტრები')}</h3>
              {paramsData && (
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(paramsData).filter(([k]) => !['pension_ceiling'].includes(k) || true).map(([k, v]) => (
                    <div key={k} className="rounded-lg border p-2 dark:border-dark-50">
                      <p className="text-xs text-gray-500 dark:text-gray-400">{k}</p>
                      <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">{typeof v === 'number' ? v : String(v)}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">{t('სამუშაო ჩანაწერები (Work Entries)')}</h3>
              {!workEntriesData || workEntriesData.length === 0 ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">{t('ჩანაწერები არ არის')}</p>
              ) : (
                <div className="space-y-2">
                  {workEntriesData.map((w: any) => (
                    <div key={w.id} className="flex items-center justify-between rounded-lg border p-3 dark:border-dark-50">
                      <div>
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{w.period_year}-{String(w.period_month).padStart(2, '0')}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{t('დღეები')}: {w.worked_days} · {t('საათები')}: {w.worked_hours} · {t('ზეგანაკვეთური')}: {w.overtime_hours}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Calc result */}
          {calcResult && (
            <div className="rounded-xl border border-primary-200 bg-primary-50 p-4 dark:border-primary-900/40 dark:bg-primary-900/20">
              <h3 className="mb-2 text-sm font-semibold text-primary-800 dark:text-primary-300">{t('გაანგარიშების შედეგი')}</h3>
              <div className="grid gap-2 md:grid-cols-5">
                <div><p className="text-xs text-gray-500">{t('მთლიანი დარიცხვა')}</p><p className="font-bold">{calcResult.gross_pay} ₾</p></div>
                <div><p className="text-xs text-gray-500">{t('დამატებები')}</p><p className="font-bold">{calcResult.additions} ₾</p></div>
                <div><p className="text-xs text-gray-500">{t('საპენსიო')}</p><p className="font-bold">{calcResult.pension_contribution} ₾</p></div>
                <div><p className="text-xs text-gray-500">{t('საშემოსავლო')}</p><p className="font-bold">{calcResult.income_tax} ₾</p></div>
                <div><p className="text-xs text-gray-500">{t('გასაცემი')}</p><p className="font-bold text-green-700 dark:text-green-400">{calcResult.net_pay} ₾</p></div>
              </div>
              {calcResult.lines && calcResult.lines.length > 0 && (
                <div className="mt-3 space-y-1">
                  {calcResult.lines.map((l: any, i: number) => (
                    <div key={i} className="flex items-center justify-between rounded bg-white/60 px-3 py-1.5 text-sm dark:bg-dark-200/60">
                      <span className="font-mono text-xs text-primary-600 dark:text-primary-400 mr-2">{l.code}</span>
                      <span className="flex-1 text-gray-700 dark:text-gray-300">{l.name}</span>
                      <span className="font-semibold">{l.amount} ₾</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Leave Tab ─────────────────────────────────────────────────── */}
      {tab === 'leave' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('თანამშრომელი')}</th>
                  <th className="px-4 py-3">{t('ტიპი')}</th>
                  <th className="px-4 py-3">{t('დაწყება')}</th>
                  <th className="px-4 py-3">{t('დასრულება')}</th>
                  <th className="px-4 py-3 text-right">{t('დღეები')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {leaveLoading ? (
                  <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
                ) : leaveRequests.length === 0 ? (
                  <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('შვებულების მოთხოვნები არ არის')}</td></tr>
                ) : leaveRequests.map(lr => (
                  <tr key={lr.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium dark:text-gray-100">{lr.employee_name}</td>
                    <td className="px-4 py-3 dark:text-gray-300">{lr.leave_type}</td>
                    <td className="px-4 py-3 dark:text-gray-300">{lr.start_date}</td>
                    <td className="px-4 py-3 dark:text-gray-300">{lr.end_date}</td>
                    <td className="px-4 py-3 text-right dark:text-gray-200">{lr.total_days}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        lr.status === 'approved' ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                        lr.status === 'rejected' ? 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                        'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                      }`}>
                        {lr.status === 'approved' ? t('დამტკიცებული') : lr.status === 'rejected' ? t('უარყოფილი') : t('მოლოდინში')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {lr.status === 'pending' && (
                        <button onClick={() => approveLeave.mutate(lr.id)} className="text-primary-600 hover:underline text-xs dark:text-primary-400">
                          <CheckCircle2 size={15} className="inline mr-1" />{t('დამტკიცება')}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Attendance Tab ───────────────────────────────────────────── */}
      {tab === 'attendance' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('თანამშრომელი')}</th>
                  <th className="px-4 py-3">{t('თარიღი')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3">{t('შესვლა')}</th>
                  <th className="px-4 py-3">{t('გასვლა')}</th>
                  <th className="px-4 py-3 text-right">{t('საათები')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {attLoading ? (
                  <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
                ) : attendanceRecords.length === 0 ? (
                  <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('დასწრების ჩანაწერები არ არის')}</td></tr>
                ) : attendanceRecords.map(a => (
                  <tr key={a.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium dark:text-gray-100">{a.employee_name}</td>
                    <td className="px-4 py-3 dark:text-gray-300">{a.date}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        a.status === 'present' ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                        a.status === 'absent' ? 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                        a.status === 'late' ? 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
                        'bg-gray-50 text-gray-600 dark:bg-dark-100 dark:text-gray-400'
                      }`}>
                        {a.status === 'present' ? t('დასწრება') : a.status === 'absent' ? t('არყოფნა') : a.status === 'late' ? t('დაგვიანება') : a.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 dark:text-gray-300">{a.clock_in ? fmtTime(new Date(a.clock_in)) : '—'}</td>
                    <td className="px-4 py-3 dark:text-gray-300">{a.clock_out ? fmtTime(new Date(a.clock_out)) : '—'}</td>
                    <td className="px-4 py-3 text-right dark:text-gray-200">{a.hours_worked ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Appraisal Tab ────────────────────────────────────────────── */}
      {tab === 'appraisal' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('თანამშრომელი')}</th>
                  <th className="px-4 py-3">{t('პერიოდი')}</th>
                  <th className="px-4 py-3 text-right">{t('რეიტინგი')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {reviewLoading ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
                ) : reviews.length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('შეფასებები არ არის')}</td></tr>
                ) : reviews.map(r => (
                  <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium dark:text-gray-100">{r.employee_name}</td>
                    <td className="px-4 py-3 dark:text-gray-300">{r.review_period}</td>
                    <td className="px-4 py-3 text-right">
                      {r.rating ? (
                        <span className="inline-flex items-center gap-1 font-semibold text-amber-600 dark:text-amber-400">
                          <Star size={14} className="fill-amber-400 text-amber-400" /> {r.rating}/5
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        r.status === 'completed' ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                        r.status === 'in_progress' ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                        'bg-gray-50 text-gray-600 dark:bg-dark-100 dark:text-gray-400'
                      }`}>
                        {r.status === 'completed' ? t('დასრულებული') : r.status === 'in_progress' ? t('მიმდინარე') : r.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Recruitment Tab ──────────────────────────────────────────── */}
      {tab === 'recruitment' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('პოზიცია')}</th>
                  <th className="px-4 py-3">{t('დეპარტამენტი')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3">{t('ბოლო ვადა')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {jobLoading ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
                ) : jobPostings.length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('ვაკანსიები არ არის')}</td></tr>
                ) : jobPostings.map(j => (
                  <tr key={j.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium dark:text-gray-100">{j.title}</td>
                    <td className="px-4 py-3 dark:text-gray-300">{j.department || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        j.status === 'open' ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                        j.status === 'closed' ? 'bg-gray-50 text-gray-600 dark:bg-dark-100 dark:text-gray-400' :
                        'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                      }`}>
                        {j.status === 'open' ? t('ღია') : j.status === 'closed' ? t('დახურული') : j.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 dark:text-gray-300">{j.deadline || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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

      {/* ── Attendance Modal ─────────────────────────────────────────── */}
      <Modal open={attModal} onClose={() => setAttModal(false)} title={t('დასწრების დაფიქსირება')}>
        <div className="space-y-4">
          <FormField label={t('თანამშრომელი')} required>
            <select value={attForm.employee_id} onChange={e => setAttForm({ ...attForm, employee_id: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="">{t('აირჩიეთ')}</option>
              {employees.map(e => <option key={e.id} value={e.id}>{e.full_name}</option>)}
            </select>
          </FormField>
          <FormField label={t('თარიღი')} required>
            <input type="date" value={attForm.date} onChange={e => setAttForm({ ...attForm, date: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('სტატუსი')}>
            <select value={attForm.status} onChange={e => setAttForm({ ...attForm, status: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="present">{t('დასწრება')}</option>
              <option value="absent">{t('არყოფნა')}</option>
              <option value="late">{t('დაგვიანება')}</option>
              <option value="half_day">Half day</option>
            </select>
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createAttendance.mutate()} disabled={createAttendance.isPending || !attForm.employee_id}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* ── Leave Modal ──────────────────────────────────────────────── */}
      <Modal open={leaveModal} onClose={() => setLeaveModal(false)} title={t('შვებულების მოთხოვნა')}>
        <div className="space-y-4">
          <FormField label={t('თანამშრომელი')} required>
            <select value={leaveForm.employee_id} onChange={e => setLeaveForm({ ...leaveForm, employee_id: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="">{t('აირჩიეთ')}</option>
              {employees.map(e => <option key={e.id} value={e.id}>{e.full_name}</option>)}
            </select>
          </FormField>
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label={t('დაწყება')} required>
              <input type="date" value={leaveForm.start_date} onChange={e => setLeaveForm({ ...leaveForm, start_date: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('დასრულება')} required>
              <input type="date" value={leaveForm.end_date} onChange={e => setLeaveForm({ ...leaveForm, end_date: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
          </div>
          <FormField label={t('დღეები')}>
            <input type="number" min={1} value={leaveForm.total_days} onChange={e => setLeaveForm({ ...leaveForm, total_days: Number(e.target.value) })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('მიზეზი')}>
            <textarea value={leaveForm.reason} onChange={e => setLeaveForm({ ...leaveForm, reason: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createLeave.mutate()} disabled={createLeave.isPending || !leaveForm.employee_id || !leaveForm.start_date}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* ── Job Posting Modal ────────────────────────────────────────── */}
      <Modal open={jobModal} onClose={() => setJobModal(false)} title={t('ახალი ვაკანსია')}>
        <div className="space-y-4">
          <FormField label={t('პოზიცია')} required>
            <input value={jobForm.title} onChange={e => setJobForm({ ...jobForm, title: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('დეპარტამენტი')}>
            <input value={jobForm.department} onChange={e => setJobForm({ ...jobForm, department: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('ბოლო ვადა')}>
            <input type="date" value={jobForm.deadline} onChange={e => setJobForm({ ...jobForm, deadline: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createJob.mutate()} disabled={createJob.isPending || !jobForm.title}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* ── Review Modal ─────────────────────────────────────────────── */}
      <Modal open={reviewModal} onClose={() => setReviewModal(false)} title={t('ახალი შეფასება')}>
        <div className="space-y-4">
          <FormField label={t('თანამშრომელი')} required>
            <select value={reviewForm.employee_id} onChange={e => setReviewForm({ ...reviewForm, employee_id: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="">{t('აირჩიეთ')}</option>
              {employees.map(e => <option key={e.id} value={e.id}>{e.full_name}</option>)}
            </select>
          </FormField>
          <FormField label={t('პერიოდი')} required>
            <input value={reviewForm.review_period} onChange={e => setReviewForm({ ...reviewForm, review_period: e.target.value })}
              placeholder="2026-Q3" className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('რეიტინგი')}>
            <select value={reviewForm.overall_rating} onChange={e => setReviewForm({ ...reviewForm, overall_rating: Number(e.target.value) })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              {[1, 2, 3, 4, 5].map(r => <option key={r} value={r}>{r} / 5</option>)}
            </select>
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createReview.mutate()} disabled={createReview.isPending || !reviewForm.employee_id || !reviewForm.review_period}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* ── Timesheet Modal ───────────────────────────────────────────── */}
      <Modal open={tsModal} onClose={() => setTsModal(false)} title={t('ახალი ჩანაწერი')}>
        <div className="space-y-4">
          <FormField label={t('თანამშრომელი')} required>
            <select value={tsForm.employee_id} onChange={e => setTsForm({ ...tsForm, employee_id: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="">{t('აირჩიეთ')}</option>
              {employees.map(e => <option key={e.id} value={e.id}>{e.full_name}</option>)}
            </select>
          </FormField>
          <FormField label={t('თარიღი')} required>
            <input type="date" value={tsForm.work_date} onChange={e => setTsForm({ ...tsForm, work_date: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label={t('საათები')}>
              <input type="number" min={0} max={24} value={tsForm.hours_worked} onChange={e => setTsForm({ ...tsForm, hours_worked: Number(e.target.value) })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('ზეგანაკვეთური')}>
              <input type="number" min={0} value={tsForm.overtime_hours} onChange={e => setTsForm({ ...tsForm, overtime_hours: Number(e.target.value) })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
          </div>
          <FormField label={t('აღწერა')}>
            <textarea value={tsForm.description} onChange={e => setTsForm({ ...tsForm, description: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createTimesheet.mutate()} disabled={createTimesheet.isPending || !tsForm.employee_id || !tsForm.work_date}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* ── Payroll engine modals (Odoo-depth) ─────────────────────────── */}
      <Modal open={structModal} onClose={() => setStructModal(false)} title={t('ახალი სტრუქტურა')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')} required>
            <input value={structForm.name} onChange={e => setStructForm({ ...structForm, name: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" placeholder="სტანდარტული თვიური" />
          </FormField>
          <FormField label={t('აღწერა')}>
            <textarea value={structForm.description} onChange={e => setStructForm({ ...structForm, description: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createStructure.mutate()} disabled={createStructure.isPending || !structForm.name}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={ruleModal} onClose={() => setRuleModal(false)} title={t('ახალი წესი')}>
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label={t('კოდი')} required>
              <input value={ruleForm.code} onChange={e => setRuleForm({ ...ruleForm, code: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" placeholder="PENSION" />
            </FormField>
            <FormField label={t('სახელი')} required>
              <input value={ruleForm.name} onChange={e => setRuleForm({ ...ruleForm, name: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label={t('კატეგორია')}>
              <select value={ruleForm.category} onChange={e => setRuleForm({ ...ruleForm, category: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                <option value="addition">addition</option>
                <option value="deduction">deduction</option>
                <option value="tax">tax</option>
                <option value="pension">pension</option>
              </select>
            </FormField>
            <FormField label={t('ტიპი')}>
              <select value={ruleForm.amount_type} onChange={e => setRuleForm({ ...ruleForm, amount_type: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                <option value="fixed">fixed</option>
                <option value="percentage">percentage</option>
                <option value="formula">formula</option>
              </select>
            </FormField>
          </div>
          {ruleForm.amount_type === 'fixed' && (
            <FormField label={t('თანხა (₾)')}>
              <input type="number" value={ruleForm.amount} onChange={e => setRuleForm({ ...ruleForm, amount: Number(e.target.value) })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
          )}
          {ruleForm.amount_type === 'percentage' && (
            <div className="grid gap-4 md:grid-cols-2">
              <FormField label={t('პროცენტი (%)')}>
                <input type="number" value={ruleForm.amount} onChange={e => setRuleForm({ ...ruleForm, amount: Number(e.target.value) })}
                  className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
              </FormField>
              <FormField label={t('ბაზა')}>
                <select value={ruleForm.basis} onChange={e => setRuleForm({ ...ruleForm, basis: e.target.value })}
                  className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                  <option value="gross">gross</option>
                  <option value="base">base</option>
                  <option value="net">net</option>
                </select>
              </FormField>
            </div>
          )}
          {ruleForm.amount_type === 'formula' && (
            <FormField label={t('ფორმულა')}>
              <textarea value={ruleForm.formula} onChange={e => setRuleForm({ ...ruleForm, formula: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm font-mono dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" rows={3}
                placeholder="round(gross * params['income_tax_rate'], 2)" />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">gross, base_salary, worked_days, worked_hours, params['key']</p>
            </FormField>
          )}
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createRule.mutate()} disabled={createRule.isPending || !ruleForm.code || !ruleForm.name}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={paramModal} onClose={() => setParamModal(false)} title={t('პარამეტრი')}>
        <div className="space-y-4">
          <FormField label={t('გასაღები')} required>
            <input value={paramForm.key} onChange={e => setParamForm({ ...paramForm, key: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" placeholder="income_tax_rate" />
          </FormField>
          <FormField label={t('მნიშვნელობა')} required>
            <input type="number" step="0.0001" value={paramForm.value} onChange={e => setParamForm({ ...paramForm, value: Number(e.target.value) })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('აღწერა')}>
            <input value={paramForm.description} onChange={e => setParamForm({ ...paramForm, description: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => setParameter.mutate()} disabled={setParameter.isPending || !paramForm.key}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={calcModal} onClose={() => setCalcModal(false)} title={t('გაანგარიშება წესებით')}>
        <div className="space-y-4">
          <FormField label={t('თანამშრომელი')} required>
            <select value={calcForm.employee_id} onChange={e => setCalcForm({ ...calcForm, employee_id: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="">{t('აირჩიეთ')}</option>
              {employees.map(e => <option key={e.id} value={e.id}>{e.full_name}</option>)}
            </select>
          </FormField>
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label={t('წელი')}>
              <input type="number" value={calcForm.period_year} onChange={e => setCalcForm({ ...calcForm, period_year: Number(e.target.value) })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('თვე')}>
              <input type="number" min={1} max={12} value={calcForm.period_month} onChange={e => setCalcForm({ ...calcForm, period_month: Number(e.target.value) })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label={t('საბაზო ხელფასი')}>
              <input type="number" value={calcForm.base_salary} onChange={e => setCalcForm({ ...calcForm, base_salary: Number(e.target.value) })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('სტრუქტურა')}>
              <select value={calcForm.structure_id} onChange={e => setCalcForm({ ...calcForm, structure_id: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                <option value="">{t('პირველი აქტიური')}</option>
                {structuresData?.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </FormField>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label={t('დამატებები')}>
              <input type="number" value={calcForm.additions} onChange={e => setCalcForm({ ...calcForm, additions: Number(e.target.value) })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('დაქვითვები')}>
              <input type="number" value={calcForm.deductions} onChange={e => setCalcForm({ ...calcForm, deductions: Number(e.target.value) })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => runCalc.mutate()} disabled={runCalc.isPending || !calcForm.employee_id}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {runCalc.isPending ? t('მუშავდება...') : t('გამოთვლა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
