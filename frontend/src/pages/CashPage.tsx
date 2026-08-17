import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Plus, Pencil, Trash2, Search, ArrowDownRight, ArrowUpRight, DollarSign, CalendarDays, Receipt, Building2
} from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import { api } from '../services/api'
import type { CashAccount, CashTransaction } from '../types'

const today = () => new Date().toISOString().slice(0, 10)

const categories = [
  { value: 'sale', label: 'გაყიდვა' },
  { value: 'expense', label: 'ხარჯი' },
  { value: 'transfer', label: 'ტრანსფერი' },
  { value: 'salary', label: 'ხელფასი' },
  { value: 'other', label: 'სხვა' },
]

function money(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

function errorText(err: any) {
  return err?.response?.data?.detail || i18n.t('ოპერაცია ვერ შესრულდა')
}

export default function CashPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  // Account modal
  const [accountModal, setAccountModal] = useState<'create' | 'edit' | null>(null)
  const [selectedAccount, setSelectedAccount] = useState<CashAccount | null>(null)
  const [accountForm, setAccountForm] = useState({ name: '', currency: 'GEL', notes: '' })
  const [accountEditForm, setAccountEditForm] = useState({ name: '', is_active: true, notes: '' })

  // Transaction modal
  const [txModal, setTxModal] = useState(false)
  const [txAccountId, setTxAccountId] = useState('')
  const [txForm, setTxForm] = useState({
    cash_account_id: '', transaction_date: today(), direction: 'inflow',
    amount: 0, category: 'sale', description: '', counterparty: '',
    receipt_number: '', notes: '',
  })

  // Daily report
  const [reportDate, setReportDate] = useState(today())
  const [reportAccountId, setReportAccountId] = useState('')

  // ── Queries ──────────────────────────────────────────────────────

  const { data: accountsData, isLoading: accountsLoading } = useQuery({
    queryKey: ['cash-accounts'],
    queryFn: () => api.get('/cash/accounts').then((r) => r.data.data),
  })
  const accounts: CashAccount[] = accountsData || []

  const { data: txData, isLoading: txLoading } = useQuery({
    queryKey: ['cash-transactions', txAccountId],
    queryFn: () => api.get(`/cash/accounts/${txAccountId}/transactions`).then((r) => r.data.data),
    enabled: !!txAccountId,
  })
  const transactions: CashTransaction[] = txData || []

  const { data: reportData } = useQuery({
    queryKey: ['cash-report', reportAccountId, reportDate],
    queryFn: () => api.get(`/cash/accounts/${reportAccountId}/daily-report`, { params: { report_date: reportDate } }).then((r) => r.data.data),
    enabled: !!reportAccountId,
  })

  // ── Mutations ────────────────────────────────────────────────────

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['cash-accounts'] })
    queryClient.invalidateQueries({ queryKey: ['cash-transactions'] })
    queryClient.invalidateQueries({ queryKey: ['cash-report'] })
  }

  const createAccount = useMutation({
    mutationFn: () => api.post('/cash/accounts', accountForm),
    onSuccess: () => { setAccountModal(null); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })
  const updateAccount = useMutation({
    mutationFn: () => api.put(`/cash/accounts/${selectedAccount!.id}`, accountEditForm),
    onSuccess: () => { setAccountModal(null); setSelectedAccount(null); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })
  const deleteAccount = useMutation({
    mutationFn: (id: string) => api.delete(`/cash/accounts/${id}`),
    onSuccess: () => refresh(),
    onError: (e) => setError(errorText(e)),
  })

  const createTx = useMutation({
    mutationFn: () => api.post(`/cash/accounts/${txAccountId}/transactions`, txForm),
    onSuccess: () => { setTxModal(false); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })

  // ── Filtered data ────────────────────────────────────────────────

  const visibleAccounts = search.trim()
    ? accounts.filter((a) => a.name.toLowerCase().includes(search.trim().toLowerCase()))
    : accounts

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('სალარო')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('ნაღდი ფულის მოძრაობის აღრიცხვა')}</p>
        </div>
        <div className="flex gap-2">
          <button
            className="btn-primary flex items-center gap-2"
            onClick={() => { setAccountForm({ name: '', currency: 'GEL', notes: '' }); setError(''); setAccountModal('create') }}
          >
            <Plus size={18} /> {t('სალაროს შექმნა')}
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <DollarSign className="text-primary-600" />
            <div>
              <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('სალაროები')}</div>
              <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{accounts.length}</div>
            </div>
          </div>
        </div>
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <ArrowUpRight className="text-accent-600" />
            <div>
              <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('ჯამური ბალანსი')}</div>
              <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">
                {money(accounts.reduce((s, a) => s + a.balance, 0))}
              </div>
            </div>
          </div>
        </div>
        {reportData && (
          <>
            <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
              <div className="flex items-center gap-3">
                <ArrowUpRight className="text-green-600" />
                <div>
                  <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('შემოსავალი')}</div>
                  <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{money(reportData.total_inflow)}</div>
                </div>
              </div>
            </div>
            <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
              <div className="flex items-center gap-3">
                <ArrowDownRight className="text-red-600" />
                <div>
                  <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('გასავალი')}</div>
                  <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{money(reportData.total_outflow)}</div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Accounts Table */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <input
            value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder={t('სალაროს ძებნა...')}
            className="input pl-10"
          />
        </div>
      </div>

      <DataTable
        columns={[
          { key: 'name', label: 'სახელი', render: (a: CashAccount) => <span className="font-medium">{a.name}</span> },
          { key: 'currency', label: 'ვალუტა' },
          { key: 'balance', label: 'ბალანსი', render: (a: CashAccount) => <span className="font-semibold">{money(a.balance)}</span> },
          {
            key: 'is_active', label: 'სტატუსი',
            render: (a: CashAccount) => (
              <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${a.is_active ? 'bg-green-50 text-green-700 dark:bg-green-900/50 dark:text-green-200' : 'bg-gray-100 text-gray-500 dark:bg-dark-50 dark:text-gray-400'}`}>
                {a.is_active ? t('აქტიური') : t('არააქტიური')}
              </span>
            ),
          },
          {
            key: 'actions', label: '',
            render: (a: CashAccount) => (
              <div className="flex items-center gap-1">
                <button
                  onClick={(e) => { e.stopPropagation(); setTxAccountId(a.id); setTxForm({
                    cash_account_id: a.id, transaction_date: today(), direction: 'inflow',
                    amount: 0, category: 'sale', description: '', counterparty: '',
                    receipt_number: '', notes: '',
                  }); setError(''); setTxModal(true) }}
                  className="p-1.5 hover:bg-primary-50 rounded-lg transition-colors"
                  title={t('ოპერაციის დამატება')}
                >
                  <Plus size={16} className="text-primary-500" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setSelectedAccount(a); setAccountEditForm({ name: a.name, is_active: a.is_active, notes: a.notes || '' }); setError(''); setAccountModal('edit') }}
                  className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors dark:hover:bg-dark-100"
                >
                  <Pencil size={18} className="text-gray-400 dark:text-gray-500" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); if (confirm(t('წავშალოთ სალარო?'))) deleteAccount.mutate(a.id) }}
                  className="p-1.5 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <Trash2 size={18} className="text-red-400" />
                </button>
              </div>
            ),
          },
        ]}
        data={visibleAccounts}
        clientPageSize={20}
        isLoading={accountsLoading}
        emptyMessage={t('სალაროები არ მოიძებნა')}
      />

      {/* Transactions Section */}
      {txAccountId && (
        <section className="card overflow-hidden p-0 dark:bg-dark-200 dark:border-dark-50">
          <div className="border-b border-brandgray-100 dark:border-dark-50 px-5 py-4 flex items-center justify-between">
            <h2 className="font-semibold text-brandgray-900 dark:text-gray-100">{t('ოპერაციები')}</h2>
            <button
              className="btn-primary text-sm flex items-center gap-1"
              onClick={() => { setTxForm({
                cash_account_id: txAccountId, transaction_date: today(), direction: 'inflow',
                amount: 0, category: 'sale', description: '', counterparty: '',
                receipt_number: '', notes: '',
              }); setError(''); setTxModal(true) }}
            >
              <Plus size={15} /> {t('ოპერაცია')}
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-brandgray-50 text-left text-brandgray-600 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('თარიღი')}</th>
                  <th className="px-4 py-3">{t('მიმართულება')}</th>
                  <th className="px-4 py-3 text-right">{t('თანხა')}</th>
                  <th className="px-4 py-3">{t('კატეგორია')}</th>
                  <th className="px-4 py-3">{t('აღწერა')}</th>
                  <th className="px-4 py-3">{t('კონტრაგენტი')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brandgray-100 dark:divide-dark-50">
                {txLoading && <tr><td className="px-4 py-8 text-center text-brandgray-500 dark:text-gray-400" colSpan={6}>{t('იტვირთება...')}</td></tr>}
                {!txLoading && transactions.length === 0 && <tr><td className="px-4 py-8 text-center text-brandgray-500 dark:text-gray-400" colSpan={6}>{t('ოპერაციები ჯერ არ არის')}</td></tr>}
                {transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-primary-50/30 dark:hover:bg-dark-100">
                    <td className="px-4 py-3">{tx.transaction_date}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                        tx.direction === 'inflow'
                          ? 'bg-green-50 text-green-700 dark:bg-green-900/40 dark:text-green-200'
                          : 'bg-red-50 text-red-700 dark:bg-red-900/40 dark:text-red-200'
                      }`}>
                        {tx.direction === 'inflow' ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                        {tx.direction === 'inflow' ? t('შემოსავალი') : t('გასავალი')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-semibold">{money(tx.amount)}</td>
                    <td className="px-4 py-3">{categories.find((c) => c.value === tx.category)?.label || tx.category}</td>
                    <td className="px-4 py-3 max-w-[200px] truncate">{tx.description || '—'}</td>
                    <td className="px-4 py-3">{tx.counterparty || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Daily Report */}
      <section className="card dark:bg-dark-200 dark:border-dark-50">
        <h2 className="font-semibold text-brandgray-900 dark:text-gray-100 mb-4">{t('დღიური ანგარიში')}</h2>
        <div className="flex flex-wrap gap-3 mb-4">
          <Select
            value={reportAccountId}
            onChange={(e) => setReportAccountId(e.target.value)}
            options={accounts.map((a) => ({ value: a.id, label: a.name }))}
            placeholder={t('აირჩიეთ სალარო')}
            className="w-60"
          />
          <input
            type="date"
            value={reportDate}
            onChange={(e) => setReportDate(e.target.value)}
            className="input w-44"
          />
        </div>
        {reportData && (
          <div className="grid gap-4 md:grid-cols-5">
            <div className="p-3 rounded-lg bg-brandgray-50 dark:bg-dark-100">
              <div className="text-xs text-brandgray-500 dark:text-gray-400">{t('საწყისი ბალანსი')}</div>
              <div className="text-lg font-semibold text-brandgray-900 dark:text-gray-100">{money(reportData.opening_balance)}</div>
            </div>
            <div className="p-3 rounded-lg bg-green-50 dark:bg-green-900/30">
              <div className="text-xs text-green-700 dark:text-green-300">{t('შემოსავალი')}</div>
              <div className="text-lg font-semibold text-green-800 dark:text-green-200">{money(reportData.total_inflow)}</div>
            </div>
            <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/30">
              <div className="text-xs text-red-700 dark:text-red-300">{t('გასავალი')}</div>
              <div className="text-lg font-semibold text-red-800 dark:text-red-200">{money(reportData.total_outflow)}</div>
            </div>
            <div className="p-3 rounded-lg bg-primary-50 dark:bg-primary-900/30">
              <div className="text-xs text-primary-700 dark:text-primary-300">{t('საბოლოო ბალანსი')}</div>
              <div className="text-lg font-semibold text-primary-800 dark:text-primary-200">{money(reportData.closing_balance)}</div>
            </div>
            <div className="p-3 rounded-lg bg-brandgray-50 dark:bg-dark-100">
              <div className="text-xs text-brandgray-500 dark:text-gray-400">{t('ტრანზაქციები')}</div>
              <div className="text-lg font-semibold text-brandgray-900 dark:text-gray-100">{reportData.transaction_count}</div>
            </div>
          </div>
        )}
      </section>

      {/* ── Account Create Modal ─────────────────────────────────── */}
      <Modal open={accountModal === 'create'} onClose={() => setAccountModal(null)} title={t('ახალი სალარო')} size="md">
        <div className="space-y-4">
          <FormField label={t('სახელი')} required>
            <input value={accountForm.name} onChange={(e) => setAccountForm({ ...accountForm, name: e.target.value })} placeholder={t('მთავარი სალარო')} className="input" />
          </FormField>
          <FormField label={t('ვალუტა')}>
            <Select value={accountForm.currency} onChange={(e) => setAccountForm({ ...accountForm, currency: e.target.value })} options={[{ value: 'GEL', label: 'GEL' }, { value: 'USD', label: 'USD' }, { value: 'EUR', label: 'EUR' }]} />
          </FormField>
          <FormField label={t('შენიშვნა')}>
            <textarea value={accountForm.notes} onChange={(e) => setAccountForm({ ...accountForm, notes: e.target.value })} className="input" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setAccountModal(null)} className="btn-secondary">{t('გაუქმება')}</button>
            <button onClick={() => createAccount.mutate()} disabled={!accountForm.name.trim() || createAccount.isPending} className="btn-primary">
              {createAccount.isPending ? t('იქმნება...') : t('შექმნა')}
            </button>
          </div>
        </div>
      </Modal>

      {/* ── Account Edit Modal ───────────────────────────────────── */}
      <Modal open={accountModal === 'edit'} onClose={() => setAccountModal(null)} title={t('სალაროს რედაქტირება')} size="md">
        <div className="space-y-4">
          <FormField label={t('სახელი')}>
            <input value={accountEditForm.name} onChange={(e) => setAccountEditForm({ ...accountEditForm, name: e.target.value })} className="input" />
          </FormField>
          <FormField label={t('სტატუსი')}>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={accountEditForm.is_active} onChange={(e) => setAccountEditForm({ ...accountEditForm, is_active: e.target.checked })} className="rounded" />
              <span className="text-sm text-gray-700 dark:text-gray-300">{t('აქტიური')}</span>
            </label>
          </FormField>
          <FormField label={t('შენიშვნა')}>
            <textarea value={accountEditForm.notes} onChange={(e) => setAccountEditForm({ ...accountEditForm, notes: e.target.value })} className="input" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setAccountModal(null)} className="btn-secondary">{t('გაუქმება')}</button>
            <button onClick={() => updateAccount.mutate()} disabled={updateAccount.isPending} className="btn-primary">
              {updateAccount.isPending ? t('ინახება...') : t('შენახვა')}
            </button>
          </div>
        </div>
      </Modal>

      {/* ── Transaction Create Modal ──────────────────────────────── */}
      <Modal open={txModal} onClose={() => setTxModal(false)} title={t('ახალი ოპერაცია')} size="md">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormField label={t('თარიღი')} required>
              <input type="date" value={txForm.transaction_date} onChange={(e) => setTxForm({ ...txForm, transaction_date: e.target.value })} className="input" />
            </FormField>
            <FormField label={t('მიმართულება')} required>
              <Select value={txForm.direction} onChange={(e) => setTxForm({ ...txForm, direction: e.target.value })} options={[
                { value: 'inflow', label: 'შემოსავალი' },
                { value: 'outflow', label: 'გასავალი' },
              ]} />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label={t('თანხა')} required>
              <input type="number" step="0.01" value={txForm.amount || ''} onChange={(e) => setTxForm({ ...txForm, amount: Number(e.target.value) })} className="input" />
            </FormField>
            <FormField label={t('კატეგორია')} required>
              <Select value={txForm.category} onChange={(e) => setTxForm({ ...txForm, category: e.target.value })} options={categories} />
            </FormField>
          </div>
          <FormField label={t('აღწერა')}>
            <textarea value={txForm.description} onChange={(e) => setTxForm({ ...txForm, description: e.target.value })} className="input" rows={2} placeholder={t('ოპერაციის აღწერა')} />
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label={t('კონტრაგენტი')}>
              <input value={txForm.counterparty} onChange={(e) => setTxForm({ ...txForm, counterparty: e.target.value })} className="input" />
            </FormField>
            <FormField label={t('ქვითრის ნომერი')}>
              <input value={txForm.receipt_number} onChange={(e) => setTxForm({ ...txForm, receipt_number: e.target.value })} className="input" />
            </FormField>
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setTxModal(false)} className="btn-secondary">{t('გაუქმება')}</button>
            <button
              onClick={() => {
                if (!txForm.amount || !txForm.transaction_date) { setError(t('შეავსეთ სავალდებულო ველები')); return }
                createTx.mutate()
              }}
              disabled={createTx.isPending}
              className="btn-primary"
            >
              {createTx.isPending ? t('ინახება...') : t('დაფიქსირება')}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
