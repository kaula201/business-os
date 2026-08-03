import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowDownLeft,
  ArrowUpRight,
  Building2,
  FileUp,
  Landmark,
  Link2,
  Plus,
  RotateCcw,
} from 'lucide-react'

import FormField, { Select } from '../components/ui/FormField'
import Modal from '../components/ui/Modal'
import { bankingApi, supplierFinanceApi } from '../services/api'
import { useAuthStore } from '../store/authStore'
import type {
  BankAccount,
  BankReconciliation,
  BankTransaction,
  SupplierPayable,
} from '../types'

const inputClass = 'input w-full'

function money(value: number, currency = 'GEL') {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency }).format(value)
}

function errorText(error: any) {
  return error?.response?.data?.detail || 'ოპერაცია ვერ შესრულდა'
}

const transactionStatus: Record<string, { label: string; cls: string }> = {
  unmatched: { label: 'შეუჯერებელი', cls: 'badge-yellow' },
  partially_matched: { label: 'ნაწილობრივ შეჯერებული', cls: 'badge-blue' },
  matched: { label: 'შეჯერებული', cls: 'badge-green' },
}

export default function BankingPage() {
  const queryClient = useQueryClient()
  const user = useAuthStore((state) => state.user)
  const canManage = user?.role === 'admin' || user?.role === 'accountant'
  const [accountOpen, setAccountOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [reconcileTransaction, setReconcileTransaction] = useState<BankTransaction | null>(null)
  const [reversalRow, setReversalRow] = useState<BankReconciliation | null>(null)
  const [accountFilter, setAccountFilter] = useState('')
  const [directionFilter, setDirectionFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [error, setError] = useState('')
  const [accountForm, setAccountForm] = useState({
    bank_name: '', account_name: '', iban: '', currency: 'GEL',
  })
  const [importAccountId, setImportAccountId] = useState('')
  const [statementFile, setStatementFile] = useState<File | null>(null)
  const [reconcileForm, setReconcileForm] = useState({ payable_id: '', amount: 0, notes: '' })
  const [reversalReason, setReversalReason] = useState('')

  const { data: accounts = [], isLoading: accountsLoading } = useQuery<BankAccount[]>({
    queryKey: ['bank-accounts'],
    queryFn: () => bankingApi.listAccounts().then((response) => response.data.data),
  })
  const { data: transactionsData, isLoading: transactionsLoading } = useQuery({
    queryKey: ['bank-transactions', accountFilter, directionFilter, statusFilter],
    queryFn: () => bankingApi.listTransactions({
      page_size: 100,
      bank_account_id: accountFilter || undefined,
      direction: directionFilter || undefined,
      status: statusFilter || undefined,
    }).then((response) => response.data.data),
  })
  const { data: payablesData } = useQuery({
    queryKey: ['supplier-payables', 'banking'],
    queryFn: () => supplierFinanceApi.listPayables({ page_size: 100 }).then((response) => response.data.data),
  })
  const { data: reconciliationsData } = useQuery({
    queryKey: ['bank-reconciliations'],
    queryFn: () => bankingApi.listReconciliations({ page_size: 100 }).then((response) => response.data.data),
  })

  const transactions: BankTransaction[] = transactionsData?.items || []
  const payables: SupplierPayable[] = useMemo(
    () => (payablesData?.items || []).filter((row: SupplierPayable) => row.outstanding_amount > 0),
    [payablesData],
  )
  const reconciliations: BankReconciliation[] = reconciliationsData?.items || []
  const totalUnmatched = transactions.reduce((sum, row) => sum + row.unmatched_amount, 0)

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['bank-accounts'] }),
      queryClient.invalidateQueries({ queryKey: ['bank-transactions'] }),
      queryClient.invalidateQueries({ queryKey: ['bank-reconciliations'] }),
      queryClient.invalidateQueries({ queryKey: ['supplier-payables'] }),
    ])
  }

  const createAccount = useMutation({
    mutationFn: () => bankingApi.createAccount(accountForm),
    onSuccess: async () => {
      setAccountOpen(false)
      setAccountForm({ bank_name: '', account_name: '', iban: '', currency: 'GEL' })
      setError('')
      await refresh()
    },
    onError: (err) => setError(errorText(err)),
  })

  const importStatement = useMutation({
    mutationFn: async () => {
      if (!statementFile || !importAccountId) throw new Error('აირჩიეთ ანგარიში და CSV ფაილი')
      const csvContent = await statementFile.text()
      return bankingApi.importStatement(importAccountId, {
        idempotency_key: `statement-${crypto.randomUUID()}`,
        filename: statementFile.name,
        csv_content: csvContent,
      })
    },
    onSuccess: async () => {
      setImportOpen(false)
      setStatementFile(null)
      setError('')
      await refresh()
    },
    onError: (err) => setError(errorText(err) === 'ოპერაცია ვერ შესრულდა' && err instanceof Error ? err.message : errorText(err)),
  })

  const reconcile = useMutation({
    mutationFn: () => bankingApi.reconcile(reconcileTransaction!.id, {
      idempotency_key: `bank-match-${crypto.randomUUID()}`,
      supplier_payable_id: reconcileForm.payable_id,
      amount: reconcileForm.amount,
      notes: reconcileForm.notes || undefined,
    }),
    onSuccess: async () => {
      setReconcileTransaction(null)
      setReconcileForm({ payable_id: '', amount: 0, notes: '' })
      setError('')
      await refresh()
    },
    onError: (err) => setError(errorText(err)),
  })

  const reverse = useMutation({
    mutationFn: () => bankingApi.reverseReconciliation(reversalRow!.id, {
      idempotency_key: `bank-reversal-${crypto.randomUUID()}`,
      reason: reversalReason,
    }),
    onSuccess: async () => {
      setReversalRow(null)
      setReversalReason('')
      setError('')
      await refresh()
    },
    onError: (err) => setError(errorText(err)),
  })

  const openReconcile = (transaction: BankTransaction) => {
    setError('')
    setReconcileTransaction(transaction)
    setReconcileForm({ payable_id: '', amount: transaction.unmatched_amount, notes: '' })
  }

  const submitReconciliation = () => {
    const payable = payables.find((row) => row.id === reconcileForm.payable_id)
    if (!payable || !reconcileTransaction) return setError('აირჩიეთ payable')
    if (reconcileForm.amount <= 0) return setError('თანხა უნდა იყოს ნულზე მეტი')
    if (reconcileForm.amount > reconcileTransaction.unmatched_amount) return setError('თანხა transaction-ის დარჩენილ თანხას აჭარბებს')
    if (reconcileForm.amount > payable.outstanding_amount) return setError('თანხა payable-ის დარჩენილ თანხას აჭარბებს')
    reconcile.mutate()
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900">საბანკო ოპერაციები</h1>
          <p className="mt-1 text-sm text-brandgray-500">ამონაწერის იმპორტი და მომწოდებლის payable-ებთან შეჯერება</p>
        </div>
        {canManage && <div className="flex gap-2">
          <button className="btn-secondary flex items-center gap-2" onClick={() => { setError(''); setAccountOpen(true) }}>
            <Plus size={17} /> ანგარიში
          </button>
          <button className="btn-primary flex items-center gap-2" onClick={() => { setError(''); setImportAccountId(accounts[0]?.id || ''); setImportOpen(true) }} disabled={!accounts.length}>
            <FileUp size={17} /> CSV იმპორტი
          </button>
        </div>}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="card p-5"><div className="flex items-center gap-3"><Landmark className="text-primary-600" /><div><div className="text-sm text-brandgray-500">საბანკო ანგარიშები</div><div className="text-2xl font-semibold text-brandgray-900">{accounts.length}</div></div></div></div>
        <div className="card p-5"><div className="flex items-center gap-3"><Link2 className="text-accent-600" /><div><div className="text-sm text-brandgray-500">შეჯერებები</div><div className="text-2xl font-semibold text-brandgray-900">{reconciliations.filter((row) => row.status === 'active').length}</div></div></div></div>
        <div className="card p-5"><div className="flex items-center gap-3"><ArrowUpRight className="text-amber-600" /><div><div className="text-sm text-brandgray-500">დარჩენილი თანხა</div><div className="text-2xl font-semibold text-brandgray-900">{money(totalUnmatched)}</div></div></div></div>
      </div>

      <section className="card overflow-hidden">
        <div className="border-b border-brandgray-100 p-4">
          <div className="flex flex-wrap gap-3">
            <Select value={accountFilter} onChange={(event) => setAccountFilter(event.target.value)} options={accounts.map((row) => ({ value: row.id, label: row.account_name }))} placeholder="ყველა ანგარიში" />
            <Select value={directionFilter} onChange={(event) => setDirectionFilter(event.target.value)} options={[{ value: 'debit', label: 'გასავალი' }, { value: 'credit', label: 'შემოსავალი' }]} placeholder="ყველა მიმართულება" />
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} options={[{ value: 'unmatched', label: 'შეუჯერებელი' }, { value: 'partially_matched', label: 'ნაწილობრივი' }, { value: 'matched', label: 'შეჯერებული' }]} placeholder="ყველა სტატუსი" />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-brandgray-50 text-left text-brandgray-600"><tr><th className="px-4 py-3">თარიღი</th><th className="px-4 py-3">ანგარიში / reference</th><th className="px-4 py-3">კონტრაგენტი</th><th className="px-4 py-3 text-right">თანხა</th><th className="px-4 py-3 text-right">დარჩენილი</th><th className="px-4 py-3">სტატუსი</th><th className="px-4 py-3"></th></tr></thead>
            <tbody className="divide-y divide-brandgray-100">
              {(transactionsLoading || accountsLoading) && <tr><td className="px-4 py-8 text-center text-brandgray-500" colSpan={7}>იტვირთება...</td></tr>}
              {!transactionsLoading && !transactions.length && <tr><td className="px-4 py-10 text-center text-brandgray-500" colSpan={7}>transaction-ები ჯერ არ არის. ატვირთეთ CSV ამონაწერი.</td></tr>}
              {transactions.map((row) => {
                const status = transactionStatus[row.status]
                return <tr key={row.id} className="hover:bg-primary-50/30">
                  <td className="px-4 py-3">{row.transaction_date}</td>
                  <td className="px-4 py-3"><div className="font-medium text-brandgray-900">{row.bank_account_name}</div><div className="text-xs text-brandgray-500">{row.reference}</div></td>
                  <td className="px-4 py-3"><div>{row.counterparty || '—'}</div><div className="max-w-[260px] truncate text-xs text-brandgray-500">{row.description}</div></td>
                  <td className={`px-4 py-3 text-right font-semibold ${row.direction === 'debit' ? 'text-red-600' : 'text-accent-700'}`}><span className="inline-flex items-center gap-1">{row.direction === 'debit' ? <ArrowUpRight size={15} /> : <ArrowDownLeft size={15} />}{money(row.amount, row.currency)}</span></td>
                  <td className="px-4 py-3 text-right">{money(row.unmatched_amount, row.currency)}</td>
                  <td className="px-4 py-3"><span className={`badge ${status.cls}`}>{status.label}</span></td>
                  <td className="px-4 py-3 text-right">{canManage && row.direction === 'debit' && row.unmatched_amount > 0 && <button className="text-sm font-medium text-primary-700 hover:text-primary-900" onClick={() => openReconcile(row)}>შეჯერება</button>}</td>
                </tr>
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card overflow-hidden">
        <div className="border-b border-brandgray-100 px-5 py-4"><h2 className="font-semibold text-brandgray-900">Reconciliation history</h2></div>
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-brandgray-50 text-left text-brandgray-600"><tr><th className="px-4 py-3">reference</th><th className="px-4 py-3">მომწოდებელი / ინვოისი</th><th className="px-4 py-3 text-right">თანხა</th><th className="px-4 py-3">სტატუსი</th><th className="px-4 py-3"></th></tr></thead><tbody className="divide-y divide-brandgray-100">
          {!reconciliations.length && <tr><td colSpan={5} className="px-4 py-8 text-center text-brandgray-500">შეჯერების ისტორია ჯერ არ არის.</td></tr>}
          {reconciliations.map((row) => <tr key={row.id}><td className="px-4 py-3">{row.transaction_reference}</td><td className="px-4 py-3"><div>{row.supplier_name}</div><div className="text-xs text-brandgray-500">{row.supplier_invoice_number}</div></td><td className="px-4 py-3 text-right font-medium">{money(row.amount)}</td><td className="px-4 py-3"><span className={`badge ${row.status === 'active' ? 'badge-green' : 'badge-gray'}`}>{row.status === 'active' ? 'აქტიური' : 'გაუქმებული'}</span></td><td className="px-4 py-3 text-right">{canManage && row.status === 'active' && <button className="inline-flex items-center gap-1 text-sm font-medium text-red-600 hover:text-red-800" onClick={() => { setError(''); setReversalRow(row) }}><RotateCcw size={15} /> გაუქმება</button>}</td></tr>)}
        </tbody></table></div>
      </section>

      <Modal open={accountOpen} onClose={() => setAccountOpen(false)} title="საბანკო ანგარიშის დამატება">
        <div className="space-y-4">
          <FormField label="ბანკი" required><input className={inputClass} value={accountForm.bank_name} onChange={(e) => setAccountForm({ ...accountForm, bank_name: e.target.value })} /></FormField>
          <FormField label="ანგარიშის სახელი" required><input className={inputClass} value={accountForm.account_name} onChange={(e) => setAccountForm({ ...accountForm, account_name: e.target.value })} /></FormField>
          <FormField label="IBAN" required><input className={inputClass} value={accountForm.iban} onChange={(e) => setAccountForm({ ...accountForm, iban: e.target.value })} /></FormField>
          <FormField label="ვალუტა" required><Select value={accountForm.currency} onChange={(e) => setAccountForm({ ...accountForm, currency: e.target.value })} options={[{ value: 'GEL', label: 'GEL' }, { value: 'USD', label: 'USD' }, { value: 'EUR', label: 'EUR' }]} /></FormField>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setAccountOpen(false)}>დახურვა</button><button className="btn-primary" disabled={!accountForm.bank_name || !accountForm.account_name || !accountForm.iban || createAccount.isPending} onClick={() => createAccount.mutate()}>{createAccount.isPending ? 'ინახება...' : 'შენახვა'}</button></div>
        </div>
      </Modal>

      <Modal open={importOpen} onClose={() => setImportOpen(false)} title="CSV ამონაწერის იმპორტი" size="lg">
        <div className="space-y-4">
          <div className="rounded-lg border border-primary-100 bg-primary-50 p-3 text-sm text-primary-900">სავალდებულო სვეტები: <code>transaction_date, reference, description, counterparty, amount, direction, currency</code>. მიმართულება უნდა იყოს <code>debit</code> ან <code>credit</code>.</div>
          <FormField label="საბანკო ანგარიში" required><Select value={importAccountId} onChange={(e) => setImportAccountId(e.target.value)} options={accounts.map((row) => ({ value: row.id, label: `${row.account_name} — ${row.iban}` }))} /></FormField>
          <FormField label="CSV ფაილი" required><input className={inputClass} type="file" accept=".csv,text/csv" onChange={(e) => setStatementFile(e.target.files?.[0] || null)} /></FormField>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setImportOpen(false)}>დახურვა</button><button className="btn-primary" disabled={!statementFile || !importAccountId || importStatement.isPending} onClick={() => importStatement.mutate()}>{importStatement.isPending ? 'იტვირთება...' : 'იმპორტი'}</button></div>
        </div>
      </Modal>

      <Modal open={!!reconcileTransaction} onClose={() => setReconcileTransaction(null)} title="Supplier Payable-თან შეჯერება" size="lg">
        {reconcileTransaction && <div className="space-y-4">
          <div className="grid gap-3 rounded-lg bg-brandgray-50 p-4 sm:grid-cols-3"><div><div className="text-xs text-brandgray-500">reference</div><div className="font-medium">{reconcileTransaction.reference}</div></div><div><div className="text-xs text-brandgray-500">თანხა</div><div className="font-medium">{money(reconcileTransaction.amount)}</div></div><div><div className="text-xs text-brandgray-500">დარჩენილი</div><div className="font-medium">{money(reconcileTransaction.unmatched_amount)}</div></div></div>
          <FormField label="Supplier Payable" required><Select value={reconcileForm.payable_id} onChange={(e) => setReconcileForm({ ...reconcileForm, payable_id: e.target.value })} placeholder="აირჩიეთ payable" options={payables.map((row) => ({ value: row.id, label: `${row.supplier_name} — ${row.supplier_invoice_number} — ${money(row.outstanding_amount)}` }))} /></FormField>
          <FormField label="შეჯერების თანხა" required><input className={inputClass} type="number" min="0.01" step="0.01" max={reconcileTransaction.unmatched_amount} value={reconcileForm.amount || ''} onChange={(e) => setReconcileForm({ ...reconcileForm, amount: Number(e.target.value) })} /></FormField>
          <FormField label="შენიშვნა"><textarea className={inputClass} rows={3} value={reconcileForm.notes} onChange={(e) => setReconcileForm({ ...reconcileForm, notes: e.target.value })} /></FormField>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setReconcileTransaction(null)}>დახურვა</button><button className="btn-primary" disabled={!reconcileForm.payable_id || reconcile.isPending} onClick={submitReconciliation}>{reconcile.isPending ? 'მუშავდება...' : 'შეჯერება'}</button></div>
        </div>}
      </Modal>

      <Modal open={!!reversalRow} onClose={() => setReversalRow(null)} title="Reconciliation-ის გაუქმება">
        <div className="space-y-4"><div className="rounded-lg border border-red-100 bg-red-50 p-3 text-sm text-red-800">გაუქმება აღადგენს payable-ის დავალიანებას და bank transaction-ის შეუჯერებელ თანხას. ისტორია არ წაიშლება.</div><FormField label="მიზეზი" required><textarea className={inputClass} rows={4} value={reversalReason} onChange={(e) => setReversalReason(e.target.value)} /></FormField>{error && <p className="text-sm text-red-600">{error}</p>}<div className="flex justify-end gap-2"><button className="btn-secondary" onClick={() => setReversalRow(null)}>დახურვა</button><button className="btn-danger" disabled={!reversalReason.trim() || reverse.isPending} onClick={() => reverse.mutate()}>{reverse.isPending ? 'მუშავდება...' : 'გაუქმება'}</button></div></div>
      </Modal>
    </div>
  )
}
