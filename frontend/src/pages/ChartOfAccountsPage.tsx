import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Plus, Search, X } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { glApi } from '../services/api'
import type { GLAccount, GLAccountCreate, GLAccountUpdate } from '../types'

const accountTypes: Record<string, string> = {
  asset: 'აქტივი',
  liability: 'ვალდებულება',
  equity: 'კაპიტალი',
  income: 'შემოსავალი',
  expense: 'ხარჯი',
}

export default function ChartOfAccountsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [page, setPage] = useState(1)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [form, setForm] = useState<GLAccountCreate>({
    code: '', name: '', account_type: 'asset', description: '',
  })

  useEffect(() => {
    const timer = setTimeout(() => { setSearch(searchInput); setPage(1) }, 400)
    return () => clearTimeout(timer)
  }, [searchInput])

  const { data, isLoading } = useQuery({
    queryKey: ['gl-accounts', search, page],
    queryFn: () => glApi.listAccounts({ page, page_size: 20, search: search || undefined }).then(r => r.data.data),
  })

  const accounts: GLAccount[] = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.max(1, Math.ceil(total / 20))

  function resetForm() {
    setForm({ code: '', name: '', account_type: 'asset', description: '' })
    setEditId(null)
    setError('')
  }

  const createMutation = useMutation({
    mutationFn: () => glApi.createAccount(form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['gl-accounts'] }); setShowForm(false); resetForm() },
    onError: (e: any) => setError(e.response?.data?.detail || t('შექმნა ვერ მოხერხდა')),
  })

  const updateMutation = useMutation({
    mutationFn: () => glApi.updateAccount(editId!, { name: form.name, description: form.description || undefined }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['gl-accounts'] }); setShowForm(false); resetForm() },
    onError: (e: any) => setError(e.response?.data?.detail || t('განახლება ვერ მოხერხდა')),
  })

  function openEdit(account: GLAccount) {
    setForm({ code: account.code, name: account.name, account_type: account.account_type, description: account.description })
    setEditId(account.id)
    setShowForm(true)
  }

  const columns = [
    { key: 'code', label: 'კოდი', render: (a: GLAccount) => <span className="font-mono font-semibold text-gray-900 dark:text-gray-100">{a.code}</span> },
    { key: 'name', label: 'სახელი', render: (a: GLAccount) => <span className="text-gray-900 dark:text-gray-100">{a.name}</span> },
    { key: 'account_type', label: 'ტიპი', render: (a: GLAccount) => (
      <span className="inline-flex items-center rounded-full bg-gray-100 dark:bg-dark-100 px-2.5 py-0.5 text-xs font-medium text-gray-700 dark:text-gray-300">{accountTypes[a.account_type] || a.account_type}</span>
    )},
    { key: 'is_active', label: 'სტატუსი', render: (a: GLAccount) => a.is_active
      ? <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400"><Check size={14} />{t('აქტიური')}</span>
      : <span className="inline-flex items-center gap-1 text-gray-400 dark:text-gray-500"><X size={14} />{t('არააქტიური')}</span>
    },
    { key: 'actions', label: '', render: (a: GLAccount) => (
      <button onClick={e => { e.stopPropagation(); openEdit(a) }} className="rounded px-3 py-1 text-sm text-primary-600 hover:bg-primary-50 dark:text-primary-400 dark:hover:bg-primary-900/30">{t('რედაქტირება')}</button>
    )},
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('ანგარიშთა გეგმა')}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('საბუღალტრო ანგარიშების სია — Chart of Accounts')}</p>
        </div>
        <button onClick={() => { resetForm(); setShowForm(true) }} className="btn-primary flex items-center gap-2">
          <Plus size={18} />{t('ახალი ანგარიში')}
        </button>
      </div>

      <div className="card">
        <div className="relative max-w-xl">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" size={18} />
          <input value={searchInput} onChange={e => setSearchInput(e.target.value)} className="input pl-10" placeholder={t('ძებნა კოდით ან სახელით...')} />
        </div>
      </div>

      {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">{error}</div>}
      <DataTable columns={columns} data={accounts} isLoading={isLoading} emptyMessage={t('ანგარიშები ჯერ არ არის შექმნილი')} page={page} totalPages={totalPages} total={total} onPageChange={setPage} />

      <Modal open={showForm} onClose={() => { setShowForm(false); resetForm() }} title={editId ? t('ანგარიშის რედაქტირება') : t('ახალი ანგარიში')}>
        <div className="space-y-4">
          <div>
            <label className="label">{t('კოდი')}</label>
            <input value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} className="input" placeholder={t('მაგ. 1100')} disabled={!!editId} />
          </div>
          <div>
            <label className="label">{t('სახელი')}</label>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="input" placeholder={t('ანგარიშის სახელი')} />
          </div>
          <div>
            <label className="label">{t('ტიპი')}</label>
            <select value={form.account_type} onChange={e => setForm({ ...form, account_type: e.target.value })} className="input" disabled={!!editId}>
              {Object.entries(accountTypes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div>
            <label className="label">{t('აღწერა')}</label>
            <textarea value={form.description || ''} onChange={e => setForm({ ...form, description: e.target.value })} className="input" rows={3} />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => { setShowForm(false); resetForm() }} className="btn-secondary">{t('გაუქმება')}</button>
            <button onClick={() => editId ? updateMutation.mutate() : createMutation.mutate()} className="btn-primary" disabled={!form.code || !form.name}>
              {editId ? t('შენახვა') : t('შექმნა')}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
