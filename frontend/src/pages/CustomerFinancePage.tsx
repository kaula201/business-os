import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Banknote, CreditCard, FileMinus2, RotateCcw, Search, X } from 'lucide-react'

import Modal from '../components/ui/Modal'
import { bankingApi, customerFinanceApi } from '../services/api'
import type { BankTransaction, CustomerBankReconciliation, CustomerCreditNoteCreate, CustomerPaymentCreate, CustomerReceivable } from '../types'

const today = () => new Date().toISOString().slice(0, 10)
const key = (prefix: string) => `${prefix}-${Date.now()}-${crypto.randomUUID()}`
const money = (value: number, currency = 'GEL') =>
  new Intl.NumberFormat('ka-GE', { style: 'currency', currency }).format(value)

const statuses: Record<string, { label: string; classes: string }> = {
  unpaid: { label: 'გადასახდელი', classes: 'bg-amber-50 text-amber-700' },
  partially_paid: { label: 'ნაწილობრივ გადახდილი', classes: 'bg-blue-50 text-blue-700' },
  paid: { label: 'გადახდილი', classes: 'bg-green-50 text-green-700' },
  overdue: { label: 'ვადაგადაცილებული', classes: 'bg-red-50 text-red-700' },
  credited: { label: 'Credit Note-ით დახურული', classes: 'bg-purple-50 text-purple-700' },
}

const paymentMethods = [
  ['bank_transfer', 'საბანკო გადარიცხვა'],
  ['cash', 'ნაღდი'],
  ['card', 'ბარათი'],
  ['other', 'სხვა'],
]

export default function CustomerFinancePage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [selected, setSelected] = useState<CustomerReceivable | null>(null)
  const [action, setAction] = useState<'payment' | 'credit' | 'bank' | null>(null)
  const [error, setError] = useState('')
  const [payment, setPayment] = useState<CustomerPaymentCreate>({
    idempotency_key: key('payment'), amount: 0, payment_date: today(), payment_method: 'bank_transfer', reference: '', notes: '',
  })
  const [credit, setCredit] = useState<CustomerCreditNoteCreate>({
    idempotency_key: key('credit'), credit_note_number: '', amount: 0, credit_date: today(), reason: '',
  })
  const [bank, setBank] = useState({ transaction_id: '', idempotency_key: key('bank'), amount: 0, notes: '' })

  const { data, isLoading } = useQuery({
    queryKey: ['customer-receivables', status],
    queryFn: () => customerFinanceApi.listReceivables({ status: status || undefined, page_size: 100 }).then((r) => r.data.data),
  })
  const { data: bankData } = useQuery({
    queryKey: ['bank-transactions', 'customer-receipts'],
    queryFn: () => bankingApi.listTransactions({ direction: 'credit', page_size: 100 }).then((r) => r.data.data),
  })
  const { data: reconciliationData } = useQuery({
    queryKey: ['customer-bank-reconciliations', selected?.id],
    queryFn: () => customerFinanceApi.listBankReconciliations({ customer_receivable_id: selected!.id, page_size: 100 }).then((r) => r.data.data),
    enabled: Boolean(selected?.id),
  })

  const receivables: CustomerReceivable[] = data?.items || []
  const bankReconciliations: CustomerBankReconciliation[] = reconciliationData?.items || []
  const bankCredits: BankTransaction[] = (bankData?.items || []).filter((row: BankTransaction) => row.unmatched_amount > 0)
  const visible = useMemo(() => {
    const term = search.trim().toLowerCase()
    return term ? receivables.filter((row) => `${row.invoice_number} ${row.client_name}`.toLowerCase().includes(term)) : receivables
  }, [receivables, search])
  const totals = useMemo(() => receivables.reduce((sum, row) => ({
    original: sum.original + row.original_amount,
    paid: sum.paid + row.paid_amount,
    outstanding: sum.outstanding + row.outstanding_amount,
    overdue: sum.overdue + (row.status === 'overdue' ? row.outstanding_amount : 0),
  }), { original: 0, paid: 0, outstanding: 0, overdue: 0 }), [receivables])

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ['customer-receivables'] })
    queryClient.invalidateQueries({ queryKey: ['bank-transactions'] })
    queryClient.invalidateQueries({ queryKey: ['customer-bank-reconciliations'] })
  }
  function closeAction() { setAction(null); setError('') }
  function updateSelected(response: any) {
    setSelected(response.data.data.receivable)
    refresh()
    closeAction()
  }

  const paymentMutation = useMutation({
    mutationFn: () => customerFinanceApi.postPayment(selected!.id, payment),
    onSuccess: updateSelected,
    onError: (e: any) => setError(e.response?.data?.detail || 'გადახდის დაფიქსირება ვერ მოხერხდა'),
  })
  const creditMutation = useMutation({
    mutationFn: () => customerFinanceApi.postCreditNote(selected!.id, credit),
    onSuccess: updateSelected,
    onError: (e: any) => setError(e.response?.data?.detail || 'Credit Note-ის შექმნა ვერ მოხერხდა'),
  })
  const bankMutation = useMutation({
    mutationFn: () => customerFinanceApi.reconcileBankTransaction(bank.transaction_id, {
      idempotency_key: bank.idempotency_key,
      customer_receivable_id: selected!.id,
      amount: bank.amount,
      notes: bank.notes,
    }),
    onSuccess: updateSelected,
    onError: (e: any) => setError(e.response?.data?.detail || 'საბანკო შეჯერება ვერ მოხერხდა'),
  })
  const reversalMutation = useMutation({
    mutationFn: (paymentId: string) => customerFinanceApi.reversePayment(paymentId, {
      idempotency_key: key('reversal'), reason: 'მომხმარებლის მიერ გაუქმებული გადახდა',
    }),
    onSuccess: updateSelected,
    onError: (e: any) => setError(e.response?.data?.detail || 'გადახდის გაუქმება ვერ მოხერხდა'),
  })
  const bankReversalMutation = useMutation({
    mutationFn: (reconciliationId: string) => customerFinanceApi.reverseBankReconciliation(reconciliationId, {
      idempotency_key: key('bank-reversal'), reason: 'მომხმარებლის მიერ გაუქმებული საბანკო შეჯერება',
    }),
    onSuccess: updateSelected,
    onError: (e: any) => setError(e.response?.data?.detail || 'საბანკო შეჯერების გაუქმება ვერ მოხერხდა'),
  })

  function openPayment(row: CustomerReceivable) {
    setSelected(row)
    setPayment({ idempotency_key: key('payment'), amount: row.outstanding_amount, payment_date: today(), payment_method: 'bank_transfer', reference: '', notes: '' })
    setAction('payment')
  }
  function openCredit(row: CustomerReceivable) {
    setSelected(row)
    setCredit({ idempotency_key: key('credit'), credit_note_number: '', amount: row.outstanding_amount, credit_date: today(), reason: '' })
    setAction('credit')
  }
  function openBank(row: CustomerReceivable) {
    setSelected(row)
    setBank({ transaction_id: '', idempotency_key: key('bank'), amount: 0, notes: '' })
    setAction('bank')
  }
  function actionButtons(row: CustomerReceivable) {
    if (row.outstanding_amount <= 0) return null
    return <div className="flex gap-1">
      <button title="გადახდა" aria-label="გადახდის დაფიქსირება" onClick={() => openPayment(row)} className="rounded p-2 text-green-700 hover:bg-green-50"><Banknote size={17} /></button>
      <button title="Credit Note" aria-label="Credit Note-ის შექმნა" onClick={() => openCredit(row)} className="rounded p-2 text-purple-700 hover:bg-purple-50"><FileMinus2 size={17} /></button>
      <button title="საბანკო შეჯერება" aria-label="საბანკო ჩარიცხვის შეჯერება" onClick={() => openBank(row)} className="rounded p-2 text-blue-700 hover:bg-blue-50"><CreditCard size={17} /></button>
    </div>
  }

  return <div className="space-y-6">
    <div>
      <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">კლიენტის ფინანსები</h1>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">დებიტორული დავალიანებები, მიღებული გადახდები და საბანკო შეჯერება</p>
    </div>

    <div className="grid gap-4 md:grid-cols-4">
      {[
        ['ინვოისების ჯამი', totals.original, 'text-brandgray-900 dark:text-gray-100'],
        ['მიღებული თანხა', totals.paid, 'text-green-700 dark:text-green-400'],
        ['დარჩენილი დავალიანება', totals.outstanding, 'text-blue-700 dark:text-blue-400'],
        ['ვადაგადაცილებული', totals.overdue, 'text-red-700 dark:text-red-400'],
      ].map(([label, value, color]) => <div key={String(label)} className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p><p className={`mt-2 text-xl font-bold ${color}`}>{money(Number(value))}</p>
      </div>)}
    </div>

    <div className="flex flex-wrap gap-3 rounded-xl border bg-white p-4 dark:border-dark-50 dark:bg-dark-200">
      <div className="relative min-w-64 flex-1"><Search className="absolute left-3 top-2.5 text-gray-400 dark:text-gray-500" size={18} />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="კლიენტი ან ინვოისის ნომერი" className="w-full rounded-lg border py-2 pl-10 pr-3 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
      </div>
      <select value={status} onChange={(e) => setStatus(e.target.value)} className="w-full rounded-lg border px-3 py-2 text-sm sm:w-auto dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
        <option value="">ყველა სტატუსი</option><option value="unpaid">გადასახდელი</option><option value="partially_paid">ნაწილობრივ გადახდილი</option>
        <option value="overdue">ვადაგადაცილებული</option><option value="paid">გადახდილი</option><option value="credited">Credit Note-ით დახურული</option>
      </select>
    </div>

    <div className="space-y-3 md:hidden">
      {isLoading ? <div className="rounded-xl border bg-white p-8 text-center text-sm text-gray-500 dark:border-dark-50 dark:bg-dark-200 dark:text-gray-400">იტვირთება...</div> : visible.length === 0 ?
        <div className="rounded-xl border bg-white p-8 text-center text-sm text-gray-500 dark:border-dark-50 dark:bg-dark-200 dark:text-gray-400">დებიტორული დავალიანება არ მოიძებნა</div> : visible.map((row) => <div key={row.id} className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="flex items-start justify-between gap-3"><div><button onClick={() => setSelected(row)} className="text-left font-semibold text-primary-700 hover:underline dark:text-primary-400">{row.invoice_number}</button><p className="text-xs text-gray-500 dark:text-gray-400">{row.client_name}</p></div><span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${statuses[row.status]?.classes}`}>{statuses[row.status]?.label}</span></div>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><p className="text-xs text-gray-500 dark:text-gray-400">გადახდის ვადა</p><p className="mt-1 dark:text-gray-200">{row.due_date}</p>{row.overdue_days > 0 && <p className="text-xs text-red-600 dark:text-red-400">{row.overdue_days} დღე</p>}</div><div className="text-right"><p className="text-xs text-gray-500 dark:text-gray-400">დავალიანება</p><p className="mt-1 font-semibold dark:text-gray-100">{money(row.outstanding_amount, row.currency)}</p></div><div><p className="text-xs text-gray-500 dark:text-gray-400">ინვოისი</p><p className="mt-1 dark:text-gray-200">{money(row.original_amount, row.currency)}</p></div><div className="text-right"><p className="text-xs text-gray-500 dark:text-gray-400">მიღებული</p><p className="mt-1 text-green-700 dark:text-green-400">{money(row.paid_amount, row.currency)}</p></div></div>
          {row.outstanding_amount > 0 && <div className="mt-3 flex justify-end border-t pt-2 dark:border-dark-50">{actionButtons(row)}</div>}
        </div>)}
    </div>

    <div className="hidden overflow-hidden rounded-xl border bg-white shadow-sm md:block dark:border-dark-50 dark:bg-dark-200">
      <div className="overflow-x-auto"><table className="w-full text-sm">
        <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400"><tr>
          <th className="px-4 py-3">ინვოისი / კლიენტი</th><th className="px-4 py-3">გადახდის ვადა</th><th className="px-4 py-3 text-right">ინვოისი</th>
          <th className="px-4 py-3 text-right">მიღებული</th><th className="px-4 py-3 text-right">დავალიანება</th><th className="px-4 py-3">სტატუსი</th><th className="px-4 py-3">მოქმედებები</th>
        </tr></thead>
        <tbody className="divide-y dark:divide-dark-50">{isLoading ? <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">იტვირთება...</td></tr> : visible.length === 0 ?
          <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">დებიტორული დავალიანება არ მოიძებნა</td></tr> : visible.map((row) => <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
            <td className="px-4 py-3"><button onClick={() => setSelected(row)} className="text-left font-semibold text-primary-700 hover:underline">{row.invoice_number}</button><div className="text-xs text-gray-500">{row.client_name}</div></td>
            <td className="px-4 py-3">{row.due_date}{row.overdue_days > 0 && <div className="text-xs text-red-600">{row.overdue_days} დღე</div>}</td>
            <td className="px-4 py-3 text-right">{money(row.original_amount, row.currency)}</td><td className="px-4 py-3 text-right text-green-700">{money(row.paid_amount, row.currency)}</td>
            <td className="px-4 py-3 text-right font-semibold">{money(row.outstanding_amount, row.currency)}</td>
            <td className="px-4 py-3"><span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statuses[row.status]?.classes}`}>{statuses[row.status]?.label}</span></td>
            <td className="px-4 py-3">{actionButtons(row)}</td>
          </tr>)}</tbody>
      </table></div>
    </div>

    {selected && !action && <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={() => setSelected(null)}>
      <div className="h-full w-full max-w-xl overflow-y-auto bg-white p-6 shadow-xl dark:bg-dark-200" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between"><div><h2 className="text-xl font-bold dark:text-gray-100">{selected.invoice_number}</h2><p className="text-sm text-gray-500 dark:text-gray-400">{selected.client_name}</p></div><button aria-label="დეტალების დახურვა" onClick={() => setSelected(null)} className="dark:text-gray-400"><X /></button></div>
        <div className="mt-6 grid grid-cols-2 gap-3">{[
          ['ინვოისის თანხა', selected.original_amount], ['მიღებული', selected.paid_amount], ['Credit Note', selected.credited_amount], ['დავალიანება', selected.outstanding_amount],
        ].map(([label, value]) => <div key={String(label)} className="rounded-lg bg-gray-50 p-3 dark:bg-dark-100"><p className="text-xs text-gray-500 dark:text-gray-400">{label}</p><p className="mt-1 font-semibold dark:text-gray-200">{money(Number(value), selected.currency)}</p></div>)}</div>
        <h3 className="mt-6 font-semibold dark:text-gray-100">გადახდების ისტორია</h3><div className="mt-2 space-y-2">{selected.payments.length === 0 ? <p className="text-sm text-gray-500 dark:text-gray-400">გადახდა ჯერ არ დაფიქსირებულა</p> : selected.payments.map((p) => <div key={p.id} className="flex items-center justify-between rounded-lg border p-3 text-sm dark:border-dark-50">...
          <div><div className="flex items-center gap-2"><p className={p.status === 'reversed' ? 'line-through text-gray-400' : 'font-medium'}>{money(p.amount, selected.currency)} · {p.payment_date}</p>{p.status === 'reversed' && <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">გაუქმებული</span>}</div><p className="text-xs text-gray-500">{p.reference || p.payment_method}{p.reversal_reason ? ` · ${p.reversal_reason}` : ''}</p></div>
          {p.status === 'active' && <button aria-label="გადახდის გაუქმება" onClick={() => window.confirm('ნამდვილად გსურთ გადახდის გაუქმება?') && reversalMutation.mutate(p.id)} className="rounded p-2 text-red-600 hover:bg-red-50" title="გაუქმება"><RotateCcw size={17} /></button>}
        </div>)}</div>
        <h3 className="mt-6 font-semibold dark:text-gray-100">Credit Note-ები</h3><div className="mt-2 space-y-2">{selected.credit_notes.length === 0 ? <p className="text-sm text-gray-500 dark:text-gray-400">Credit Note არ არის</p> : selected.credit_notes.map((c) => <div key={c.id} className="rounded-lg border p-3 text-sm dark:border-dark-50"><p className="font-medium dark:text-gray-200">{c.credit_note_number} · {money(c.amount, selected.currency)}</p><p className="text-xs text-gray-500 dark:text-gray-400">{c.credit_date} · {c.reason}</p></div>)}</div>
        <h3 className="mt-6 font-semibold dark:text-gray-100">საბანკო შეჯერებები</h3><div className="mt-2 space-y-2">{bankReconciliations.length === 0 ? <p className="text-sm text-gray-500 dark:text-gray-400">საბანკო შეჯერება არ არის</p> : bankReconciliations.map((row) => <div key={row.id} className="flex items-center justify-between rounded-lg border p-3 text-sm dark:border-dark-50">
          <div><p className={row.status === 'reversed' ? 'line-through text-gray-400' : 'font-medium dark:text-gray-200'}>{money(row.amount, selected.currency)}</p><p className="text-xs text-gray-500 dark:text-gray-400">{new Date(row.created_at).toLocaleDateString('ka-GE')}{row.reversal_reason ? ` · ${row.reversal_reason}` : ''}</p></div>
          {row.status === 'active' && <button aria-label="საბანკო შეჯერების გაუქმება" onClick={() => window.confirm('ნამდვილად გსურთ საბანკო შეჯერების გაუქმება?') && bankReversalMutation.mutate(row.id)} className="rounded p-2 text-red-600 hover:bg-red-50" title="შეჯერების გაუქმება"><RotateCcw size={17} /></button>}
        </div>)}</div>
        {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-400">{error}</p>}
      </div>
    </div>}

    <Modal open={action === 'payment'} onClose={closeAction} title="კლიენტის გადახდის დაფიქსირება">
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); paymentMutation.mutate() }}>
        <label className="block text-sm">თანხა<input required min="0.01" step="0.01" type="number" value={payment.amount || ''} onChange={(e) => setPayment({ ...payment, amount: Number(e.target.value) })} className="mt-1 w-full rounded-lg border p-2" /></label>
        <label className="block text-sm">თარიღი<input required type="date" value={payment.payment_date} onChange={(e) => setPayment({ ...payment, payment_date: e.target.value })} className="mt-1 w-full rounded-lg border p-2" /></label>
        <label className="block text-sm">გადახდის მეთოდი<select value={payment.payment_method} onChange={(e) => setPayment({ ...payment, payment_method: e.target.value as CustomerPaymentCreate['payment_method'] })} className="mt-1 w-full rounded-lg border p-2">{paymentMethods.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label className="block text-sm">გადახდის მითითება<input value={payment.reference} onChange={(e) => setPayment({ ...payment, reference: e.target.value })} className="mt-1 w-full rounded-lg border p-2" /></label>
        {error && <p className="text-sm text-red-600">{error}</p>}<button disabled={paymentMutation.isPending} className="w-full rounded-lg bg-primary-600 py-2 text-white disabled:opacity-50">{paymentMutation.isPending ? 'ინახება...' : 'გადახდის შენახვა'}</button>
      </form>
    </Modal>

    <Modal open={action === 'credit'} onClose={closeAction} title="კლიენტის Credit Note">
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); creditMutation.mutate() }}>
        <label className="block text-sm">Credit Note-ის ნომერი<input required value={credit.credit_note_number} onChange={(e) => setCredit({ ...credit, credit_note_number: e.target.value })} className="mt-1 w-full rounded-lg border p-2" /></label>
        <label className="block text-sm">თანხა<input required min="0.01" step="0.01" type="number" value={credit.amount || ''} onChange={(e) => setCredit({ ...credit, amount: Number(e.target.value) })} className="mt-1 w-full rounded-lg border p-2" /></label>
        <label className="block text-sm">თარიღი<input required type="date" value={credit.credit_date} onChange={(e) => setCredit({ ...credit, credit_date: e.target.value })} className="mt-1 w-full rounded-lg border p-2" /></label>
        <label className="block text-sm">მიზეზი<textarea required value={credit.reason} onChange={(e) => setCredit({ ...credit, reason: e.target.value })} className="mt-1 w-full rounded-lg border p-2" /></label>
        {error && <p className="text-sm text-red-600">{error}</p>}<button disabled={creditMutation.isPending} className="w-full rounded-lg bg-purple-600 py-2 text-white disabled:opacity-50">{creditMutation.isPending ? 'იქმნება...' : 'Credit Note-ის შექმნა'}</button>
      </form>
    </Modal>

    <Modal open={action === 'bank'} onClose={closeAction} title="საბანკო ჩარიცხვის შეჯერება">
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); bankMutation.mutate() }}>
        <label className="block text-sm">საბანკო ჩარიცხვა<select required value={bank.transaction_id} onChange={(e) => { const t = bankCredits.find((x) => x.id === e.target.value); setBank({ ...bank, transaction_id: e.target.value, amount: Math.min(t?.unmatched_amount || 0, selected?.outstanding_amount || 0) }) }} className="mt-1 w-full rounded-lg border p-2"><option value="">აირჩიეთ ჩარიცხვა</option>{bankCredits.map((t) => <option key={t.id} value={t.id}>{t.transaction_date} · {t.counterparty} · {money(t.unmatched_amount, t.currency)}</option>)}</select></label>
        <label className="block text-sm">შესაჯერებელი თანხა<input required min="0.01" step="0.01" type="number" value={bank.amount || ''} onChange={(e) => setBank({ ...bank, amount: Number(e.target.value) })} className="mt-1 w-full rounded-lg border p-2" /></label>
        <label className="block text-sm">შენიშვნა<textarea value={bank.notes} onChange={(e) => setBank({ ...bank, notes: e.target.value })} className="mt-1 w-full rounded-lg border p-2" /></label>
        {bankCredits.length === 0 && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-700">შეუჯერებელი შემოსული საბანკო ტრანზაქცია არ არის.</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}<button disabled={bankMutation.isPending || !bank.transaction_id} className="w-full rounded-lg bg-blue-600 py-2 text-white disabled:opacity-50">{bankMutation.isPending ? 'მუშავდება...' : 'შეჯერება'}</button>
      </form>
    </Modal>
  </div>
}
