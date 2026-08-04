import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Banknote, Check, FileCheck2, FileMinus2, Plus, ReceiptText, RotateCcw, Search, WalletCards, XCircle } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import ConfirmDialog from '../components/ui/ConfirmDialog'
import DataTable from '../components/ui/DataTable'
import FormField, { Select } from '../components/ui/FormField'
import Modal from '../components/ui/Modal'
import {
  invoiceMatchingStatusMap,
  StatusBadge,
  supplierInvoiceStatusMap,
  supplierPayableStatusMap,
} from '../components/ui/Badges'
import { purchaseOrdersApi, supplierFinanceApi, suppliersApi } from '../services/api'
import type {
  PurchaseOrder,
  Supplier,
  SupplierCreditNoteCreate,
  SupplierInvoice,
  SupplierInvoiceCreate,
  SupplierPayable,
  SupplierPayment,
  SupplierPaymentCreate,
  SupplierPaymentReversalCreate,
} from '../types'

function currency(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

function isoDate(date = new Date()) {
  return date.toISOString().slice(0, 10)
}

function plusDays(days: number) {
  const result = new Date()
  result.setDate(result.getDate() + days)
  return isoDate(result)
}

type InvoiceForm = SupplierInvoiceCreate

const emptyInvoiceForm = (): InvoiceForm => ({
  supplier_id: '',
  purchase_order_id: '',
  supplier_invoice_number: '',
  invoice_date: isoDate(),
  due_date: plusDays(30),
  notes: '',
  items: [],
})

const invoiceFilters = [
  { value: '', label: 'ყველა სტატუსი' },
  { value: 'draft', label: 'მონახაზი' },
  { value: 'approved', label: 'დამტკიცებული' },
  { value: 'cancelled', label: 'გაუქმებული' },
]

const payableFilters = [
  { value: '', label: 'ყველა სტატუსი' },
  { value: 'unpaid', label: 'გადასახდელი' },
  { value: 'partially_paid', label: 'ნაწილობრივ გადახდილი' },
  { value: 'overdue', label: 'ვადაგადაცილებული' },
  { value: 'paid', label: 'გადახდილი' },
]

const paymentMethods = [
  { value: 'bank_transfer', label: 'საბანკო გადარიცხვა' },
  { value: 'cash', label: 'ნაღდი' },
  { value: 'card', label: 'ბარათი' },
  { value: 'other', label: 'სხვა' },
]

export default function SupplierFinancePage() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [tab, setTab] = useState<'invoices' | 'payables'>('invoices')
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedInvoice, setSelectedInvoice] = useState<SupplierInvoice | null>(null)
  const [invoiceAction, setInvoiceAction] = useState<'approved' | 'cancelled' | null>(null)
  const [selectedPayable, setSelectedPayable] = useState<SupplierPayable | null>(null)
  const [paymentOpen, setPaymentOpen] = useState(false)
  const [creditOpen, setCreditOpen] = useState(false)
  const [reversalPayment, setReversalPayment] = useState<SupplierPayment | null>(null)
  const [error, setError] = useState('')
  const [paymentError, setPaymentError] = useState('')
  const [creditError, setCreditError] = useState('')
  const [reversalError, setReversalError] = useState('')
  const [preselectionHandled, setPreselectionHandled] = useState(false)
  const [form, setForm] = useState<InvoiceForm>(emptyInvoiceForm())
  const [payment, setPayment] = useState<SupplierPaymentCreate>({
    idempotency_key: '',
    amount: 0,
    payment_date: isoDate(),
    payment_method: 'bank_transfer',
    reference: '',
    notes: '',
  })
  const [credit, setCredit] = useState<SupplierCreditNoteCreate>({
    idempotency_key: '',
    supplier_credit_note_number: '',
    amount: 0,
    credit_date: isoDate(),
    reason: '',
  })
  const [reversal, setReversal] = useState<SupplierPaymentReversalCreate>({
    idempotency_key: '',
    reason: '',
  })

  const { data: invoicesData, isLoading: invoicesLoading } = useQuery({
    queryKey: ['supplier-invoices', status],
    queryFn: () => supplierFinanceApi.listInvoices({ status: status || undefined, page_size: 100 }).then((r) => r.data.data),
  })
  const { data: payablesData, isLoading: payablesLoading } = useQuery({
    queryKey: ['supplier-payables', status],
    queryFn: () => supplierFinanceApi.listPayables({ status: status || undefined, page_size: 100 }).then((r) => r.data.data),
  })
  const { data: purchasesData } = useQuery({
    queryKey: ['purchase-orders', 'finance-options'],
    queryFn: () => purchaseOrdersApi.list({ page_size: 100 }).then((r) => r.data.data),
  })
  const { data: suppliersData } = useQuery({
    queryKey: ['suppliers', 'finance-options'],
    queryFn: () => suppliersApi.list({ page_size: 100 }).then((r) => r.data.data),
  })

  const invoices: SupplierInvoice[] = invoicesData?.items || []
  const payables: SupplierPayable[] = payablesData?.items || []
  const purchaseOrders: PurchaseOrder[] = (purchasesData?.items || []).filter(
    (order: PurchaseOrder) => ['partially_received', 'received'].includes(order.status),
  )
  const suppliers: Supplier[] = suppliersData?.items || []

  const visibleInvoices = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return invoices
    return invoices.filter((invoice) =>
      [invoice.internal_invoice_number, invoice.supplier_invoice_number, invoice.supplier_name, invoice.purchase_order_number]
        .some((value) => value.toLowerCase().includes(term)),
    )
  }, [invoices, search])

  const visiblePayables = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return payables
    return payables.filter((payable) =>
      [payable.internal_invoice_number, payable.supplier_invoice_number, payable.supplier_name]
        .some((value) => value.toLowerCase().includes(term)),
    )
  }, [payables, search])

  const invoiceDraftTotal = useMemo(() => form.items.reduce((sum, item) => {
    const gross = item.quantity * item.unit_price
    const net = gross - gross * item.discount_percent / 100
    return sum + net + net * item.vat_rate / 100
  }, 0), [form.items])

  function selectPurchaseOrder(orderId: string) {
    const order = purchaseOrders.find((item) => item.id === orderId)
    if (!order) {
      setForm(emptyInvoiceForm())
      return
    }
    const supplier = suppliers.find((item) => item.id === order.supplier_id)
    setForm({
      supplier_id: order.supplier_id,
      purchase_order_id: order.id,
      supplier_invoice_number: '',
      invoice_date: isoDate(),
      due_date: plusDays(supplier?.payment_terms_days || 30),
      notes: '',
      items: order.items
        .filter((item) => item.received_quantity > 0)
        .map((item) => ({
          purchase_order_item_id: item.id,
          quantity: item.received_quantity,
          unit_price: item.unit_price,
          discount_percent: item.discount_percent,
          vat_rate: item.vat_rate,
        })),
    })
    setError('')
  }

  useEffect(() => {
    const purchaseOrderId = searchParams.get('purchase_order_id')
    if (!preselectionHandled && purchaseOrderId && purchaseOrders.length) {
      selectPurchaseOrder(purchaseOrderId)
      setCreateOpen(true)
      setPreselectionHandled(true)
      setSearchParams({}, { replace: true })
    }
  }, [preselectionHandled, purchaseOrders, searchParams, setSearchParams])

  function refreshFinance() {
    queryClient.invalidateQueries({ queryKey: ['supplier-invoices'] })
    queryClient.invalidateQueries({ queryKey: ['supplier-payables'] })
  }

  const createMutation = useMutation({
    mutationFn: (payload: SupplierInvoiceCreate) => supplierFinanceApi.createInvoice(payload),
    onSuccess: (response) => {
      refreshFinance()
      setCreateOpen(false)
      setForm(emptyInvoiceForm())
      setSelectedInvoice(response.data.data)
      setError('')
    },
    onError: (apiError: any) => setError(apiError.response?.data?.detail || 'მომწოდებლის ინვოისის შექმნა ვერ მოხერხდა'),
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, target }: { id: string; target: 'approved' | 'cancelled' }) =>
      supplierFinanceApi.changeInvoiceStatus(id, target),
    onSuccess: (response) => {
      refreshFinance()
      setSelectedInvoice(response.data.data)
      setInvoiceAction(null)
      setError('')
    },
    onError: (apiError: any) => {
      setError(apiError.response?.data?.detail || 'Invoice-ის სტატუსის შეცვლა ვერ მოხერხდა')
      setInvoiceAction(null)
    },
  })

  const paymentMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SupplierPaymentCreate }) =>
      supplierFinanceApi.postPayment(id, payload),
    onSuccess: (response) => {
      refreshFinance()
      setSelectedPayable(response.data.data)
      setPaymentOpen(false)
      setPaymentError('')
    },
    onError: (apiError: any) => setPaymentError(apiError.response?.data?.detail || 'გადახდა ვერ დაფიქსირდა'),
  })

  const creditMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SupplierCreditNoteCreate }) =>
      supplierFinanceApi.postCreditNote(id, payload),
    onSuccess: (response) => {
      refreshFinance()
      setSelectedPayable(response.data.data)
      setCreditOpen(false)
      setCreditError('')
    },
    onError: (apiError: any) => setCreditError(apiError.response?.data?.detail || 'Credit Note ვერ დაფიქსირდა'),
  })

  const reversalMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SupplierPaymentReversalCreate }) =>
      supplierFinanceApi.reversePayment(id, payload),
    onSuccess: (response) => {
      refreshFinance()
      setSelectedPayable(response.data.data)
      setReversalPayment(null)
      setReversalError('')
    },
    onError: (apiError: any) => setReversalError(apiError.response?.data?.detail || 'გადახდის გაუქმება ვერ მოხერხდა'),
  })

  function submitInvoice(event: React.FormEvent) {
    event.preventDefault()
    if (!form.purchase_order_id || !form.supplier_invoice_number.trim() || !form.items.length) {
      setError('აირჩიეთ შესყიდვის შეკვეთა და შეავსეთ ინვოისის ნომერი')
      return
    }
    if (form.items.some((item) => item.quantity <= 0)) {
      setError('ყველა invoice line-ის რაოდენობა დადებითი უნდა იყოს')
      return
    }
    createMutation.mutate(form)
  }

  function openPayment(payable: SupplierPayable) {
    setSelectedPayable(payable)
    setPayment({
      idempotency_key: crypto.randomUUID(),
      amount: payable.outstanding_amount,
      payment_date: isoDate(),
      payment_method: 'bank_transfer',
      reference: '',
      notes: '',
    })
    setPaymentError('')
    setPaymentOpen(true)
  }

  function submitPayment(event: React.FormEvent) {
    event.preventDefault()
    if (!selectedPayable || payment.amount <= 0 || payment.amount > selectedPayable.outstanding_amount) {
      setPaymentError('თანხა უნდა იყოს დადებითი და დარჩენილ დავალიანებას არ უნდა აჭარბებდეს')
      return
    }
    paymentMutation.mutate({ id: selectedPayable.id, payload: payment })
  }

  function openCreditNote(payable: SupplierPayable) {
    setSelectedPayable(payable)
    setCredit({
      idempotency_key: crypto.randomUUID(),
      supplier_credit_note_number: '',
      amount: payable.outstanding_amount,
      credit_date: isoDate(),
      reason: '',
    })
    setCreditError('')
    setCreditOpen(true)
  }

  function submitCreditNote(event: React.FormEvent) {
    event.preventDefault()
    if (!selectedPayable || !credit.supplier_credit_note_number.trim() || !credit.reason.trim()) {
      setCreditError('შეავსეთ Credit Note-ის ნომერი და მიზეზი')
      return
    }
    if (credit.amount <= 0 || credit.amount > selectedPayable.outstanding_amount) {
      setCreditError('თანხა უნდა იყოს დადებითი და დარჩენილ დავალიანებას არ უნდა აჭარბებდეს')
      return
    }
    creditMutation.mutate({ id: selectedPayable.id, payload: credit })
  }

  function openReversal(paymentItem: SupplierPayment) {
    setReversalPayment(paymentItem)
    setReversal({ idempotency_key: crypto.randomUUID(), reason: '' })
    setReversalError('')
  }

  function submitReversal(event: React.FormEvent) {
    event.preventDefault()
    if (!reversalPayment || !reversal.reason.trim()) {
      setReversalError('მიუთითეთ გადახდის გაუქმების მიზეზი')
      return
    }
    reversalMutation.mutate({ id: reversalPayment.id, payload: reversal })
  }

  const invoiceColumns = [
    { key: 'internal_invoice_number', label: 'შიდა ნომერი', render: (invoice: SupplierInvoice) => <div><p className="font-semibold">{invoice.internal_invoice_number}</p><p className="text-xs text-gray-500 dark:text-gray-400">{invoice.supplier_invoice_number}</p></div> },
    { key: 'supplier_name', label: 'მომწოდებელი' },
    { key: 'purchase_order_number', label: 'შესყიდვის შეკვეთა', hideOnMobile: true },
    { key: 'matching_status', label: 'შეჯერება', render: (invoice: SupplierInvoice) => <StatusBadge status={invoice.matching_status} map={invoiceMatchingStatusMap} /> },
    { key: 'status', label: 'სტატუსი', render: (invoice: SupplierInvoice) => <StatusBadge status={invoice.status} map={supplierInvoiceStatusMap} /> },
    { key: 'total', label: 'ჯამი', className: 'text-right font-semibold', render: (invoice: SupplierInvoice) => currency(invoice.total) },
  ]

  const payableColumns = [
    { key: 'internal_invoice_number', label: 'Invoice', render: (payable: SupplierPayable) => <div><p className="font-semibold">{payable.internal_invoice_number}</p><p className="text-xs text-gray-500 dark:text-gray-400">{payable.supplier_invoice_number}</p></div> },
    { key: 'supplier_name', label: 'მომწოდებელი' },
    { key: 'due_date', label: 'გადახდის ვადა', hideOnMobile: true, render: (payable: SupplierPayable) => <span className={payable.status === 'overdue' ? 'text-red-700 font-medium' : ''}>{new Date(payable.due_date).toLocaleDateString('ka-GE')}{payable.days_overdue > 0 && ` · ${payable.days_overdue} დღე`}</span> },
    { key: 'status', label: 'სტატუსი', render: (payable: SupplierPayable) => <StatusBadge status={payable.status} map={supplierPayableStatusMap} /> },
    { key: 'outstanding_amount', label: 'დარჩენილი', className: 'text-right font-semibold', render: (payable: SupplierPayable) => currency(payable.outstanding_amount) },
    { key: 'actions', label: '', render: (payable: SupplierPayable) => payable.status !== 'paid' ? <button className="btn-primary py-1.5 px-3 text-sm" onClick={(event) => { event.stopPropagation(); openPayment(payable) }}>გადახდა</button> : null },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">მომწოდებლის ფინანსები</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">მომწოდებლის ინვოისები, სამმხრივი შეჯერება და გადასახდელები</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => { setForm(emptyInvoiceForm()); setError(''); setCreateOpen(true) }}><Plus size={18} /> ახალი მომწოდებლის ინვოისი</button>
      </div>

      <div className="card p-1 flex gap-1 w-fit">
        <button className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 ${tab === 'invoices' ? 'bg-primary-600 text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-dark-100 dark:bg-dark-100'}`} onClick={() => { setTab('invoices'); setStatus('') }}><ReceiptText size={17} /> მომწოდებლის ინვოისები</button>
        <button className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 ${tab === 'payables' ? 'bg-primary-600 text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-dark-100 dark:bg-dark-100'}`} onClick={() => { setTab('payables'); setStatus('') }}><WalletCards size={17} /> დავალიანებები</button>
      </div>

      <div className="card flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1"><Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" /><input className="input pl-10" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="ნომერი ან მომწოდებელი" /></div>
        <Select className="sm:w-64" value={status} onChange={(e) => setStatus(e.target.value)} options={tab === 'invoices' ? invoiceFilters : payableFilters} />
      </div>

      {tab === 'invoices' ? (
        <DataTable columns={invoiceColumns} data={visibleInvoices} isLoading={invoicesLoading} onRowClick={setSelectedInvoice} emptyMessage="მომწოდებლის ინვოისი ჯერ არ არის შექმნილი" />
      ) : (
        <DataTable columns={payableColumns} data={visiblePayables} isLoading={payablesLoading} onRowClick={setSelectedPayable} emptyMessage="მომწოდებლის დავალიანება ჯერ არ არის" />
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="ახალი მომწოდებლის ინვოისი" size="xl">
        <form onSubmit={submitInvoice} className="space-y-5">
          {error && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{error}</div>}
          <div className="grid md:grid-cols-2 gap-4">
            <FormField label="მიღებული შესყიდვის შეკვეთა" required><Select required value={form.purchase_order_id} onChange={(e) => selectPurchaseOrder(e.target.value)} placeholder="აირჩიეთ" options={purchaseOrders.map((order) => ({ value: order.id, label: `${order.purchase_order_number} — ${order.supplier_name}` }))} /></FormField>
            <FormField label="მომწოდებლის invoice ნომერი" required><input required className="input" value={form.supplier_invoice_number} onChange={(e) => setForm({ ...form, supplier_invoice_number: e.target.value })} placeholder="მაგ. INV-2026-001" /></FormField>
            <FormField label="Invoice date" required><input required type="date" className="input" value={form.invoice_date} onChange={(e) => setForm({ ...form, invoice_date: e.target.value })} /></FormField>
            <FormField label="გადახდის ვადა" required><input required type="date" min={form.invoice_date} className="input" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></FormField>
          </div>

          {form.items.length > 0 && <div className="border rounded-xl overflow-x-auto"><table className="w-full text-sm"><thead className="bg-gray-50 dark:bg-dark-100"><tr><th className="p-3 text-left">პროდუქტი</th><th className="p-3 text-right">მიღებული / invoice</th><th className="p-3 text-right">ფასი</th><th className="p-3 text-right">დღგ</th><th className="p-3 text-right">ჯამი</th></tr></thead><tbody className="divide-y">{form.items.map((line, index) => {
            const order = purchaseOrders.find((item) => item.id === form.purchase_order_id)
            const poItem = order?.items.find((item) => item.id === line.purchase_order_item_id)
            const gross = line.quantity * line.unit_price * (1 - line.discount_percent / 100)
            return <tr key={line.purchase_order_item_id}><td className="p-3 font-medium">{poItem?.product_name}</td><td className="p-3"><div className="flex items-center justify-end gap-2"><span className="text-xs text-gray-500 dark:text-gray-400">{poItem?.received_quantity} /</span><input type="number" min="0.001" max={poItem?.received_quantity} step="0.001" className="input w-28 text-right" value={line.quantity} onChange={(e) => setForm({ ...form, items: form.items.map((item, itemIndex) => itemIndex === index ? { ...item, quantity: Number(e.target.value) } : item) })} /></div></td><td className="p-3 text-right">{currency(line.unit_price)}</td><td className="p-3 text-right">{line.vat_rate}%</td><td className="p-3 text-right font-medium">{currency(gross * (1 + line.vat_rate / 100))}</td></tr>
          })}</tbody></table></div>}

          {!form.purchase_order_id && <div className="p-4 bg-blue-50 rounded-xl text-sm text-blue-800"><FileCheck2 size={18} className="inline mr-2" />ჯერ აირჩიეთ მიღებული შესყიდვის შეკვეთა. პროდუქტები ავტომატურად ჩაიტვირთება.</div>}
          <FormField label="შენიშვნა"><textarea className="input min-h-20" value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></FormField>
          <div className="flex items-center justify-between pt-4 border-t"><div><p className="text-xs text-gray-500 dark:text-gray-400">Invoice ჯამი</p><p className="text-xl font-bold">{currency(invoiceDraftTotal)}</p></div><div className="flex gap-3"><button type="button" className="btn-secondary" onClick={() => setCreateOpen(false)}>გაუქმება</button><button className="btn-primary" disabled={createMutation.isPending}>{createMutation.isPending ? 'იქმნება...' : 'შექმნა და შეჯერება'}</button></div></div>
        </form>
      </Modal>

      <Modal open={Boolean(selectedInvoice)} onClose={() => { setSelectedInvoice(null); setError('') }} title={selectedInvoice?.internal_invoice_number || 'მომწოდებლის ინვოისი'} size="xl">
        {selectedInvoice && <div className="space-y-5">
          {error && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{error}</div>}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-xl"><p className="text-xs text-gray-500 dark:text-gray-400">მომწოდებელი</p><p className="font-medium mt-1">{selectedInvoice.supplier_name}</p></div>
            <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-xl"><p className="text-xs text-gray-500 dark:text-gray-400">შესყიდვის შეკვეთა</p><p className="font-medium mt-1">{selectedInvoice.purchase_order_number}</p></div>
            <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-xl"><p className="text-xs text-gray-500 dark:text-gray-400">შეჯერება</p><div className="mt-1"><StatusBadge status={selectedInvoice.matching_status} map={invoiceMatchingStatusMap} /></div></div>
            <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-xl"><p className="text-xs text-gray-500 dark:text-gray-400">სტატუსი</p><div className="mt-1"><StatusBadge status={selectedInvoice.status} map={supplierInvoiceStatusMap} /></div></div>
          </div>
          {selectedInvoice.match_issues.length > 0 && <div className="p-4 bg-amber-50 rounded-xl text-amber-900"><p className="font-medium flex items-center gap-2"><AlertTriangle size={18} /> შეუსაბამობები</p><ul className="mt-2 list-disc pl-5 text-sm space-y-1">{selectedInvoice.match_issues.map((issue) => <li key={issue}>{issue}</li>)}</ul></div>}
          <div className="border rounded-xl overflow-x-auto"><table className="w-full text-sm"><thead className="bg-gray-50 dark:bg-dark-100"><tr><th className="p-3 text-left">პროდუქტი</th><th className="p-3 text-right">რაოდენობა</th><th className="p-3 text-right">ფასი</th><th className="p-3 text-right">ჯამი</th><th className="p-3 text-right">შეჯერება</th></tr></thead><tbody className="divide-y">{selectedInvoice.items.map((item) => <tr key={item.id}><td className="p-3 font-medium">{item.product_name}</td><td className="p-3 text-right">{item.quantity}</td><td className="p-3 text-right">{currency(item.unit_price)}</td><td className="p-3 text-right font-medium">{currency(item.line_total)}</td><td className="p-3 text-right"><StatusBadge status={item.matching_status} map={invoiceMatchingStatusMap} /></td></tr>)}</tbody></table></div>
          <div className="grid md:grid-cols-3 gap-3"><div className="p-3 border rounded-xl"><p className="text-xs text-gray-500 dark:text-gray-400">ქვეჯამი</p><p className="font-semibold mt-1">{currency(selectedInvoice.subtotal)}</p></div><div className="p-3 border rounded-xl"><p className="text-xs text-gray-500 dark:text-gray-400">დღგ</p><p className="font-semibold mt-1">{currency(selectedInvoice.vat_amount)}</p></div><div className="p-3 bg-primary-50 rounded-xl"><p className="text-xs text-primary-700">სულ</p><p className="font-bold text-primary-900 mt-1">{currency(selectedInvoice.total)}</p></div></div>
          {selectedInvoice.payable && <div className="p-4 bg-green-50 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div><p className="font-medium text-green-900">დავალიანება შექმნილია</p><p className="text-sm text-green-800 mt-1">დარჩენილი: {currency(selectedInvoice.payable.outstanding_amount)} · ვადა: {new Date(selectedInvoice.payable.due_date).toLocaleDateString('ka-GE')}</p></div><StatusBadge status={selectedInvoice.payable.status} map={supplierPayableStatusMap} /></div>}
          {selectedInvoice.status === 'draft' && <div className="flex justify-end gap-3 pt-4 border-t"><button className="btn-secondary text-red-600" onClick={() => setInvoiceAction('cancelled')}><XCircle size={17} className="inline mr-2" />გაუქმება</button><button className="btn-primary" disabled={selectedInvoice.matching_status !== 'matched'} onClick={() => setInvoiceAction('approved')}><Check size={17} className="inline mr-2" />დამტკიცება და payable-ის შექმნა</button></div>}
        </div>}
      </Modal>

      <Modal open={Boolean(selectedPayable) && !paymentOpen && !creditOpen && !reversalPayment} onClose={() => setSelectedPayable(null)} title={selectedPayable?.internal_invoice_number || 'დავალიანება'} size="lg">
        {selectedPayable && <div className="space-y-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-xl"><p className="text-xs text-gray-500 dark:text-gray-400">საწყისი</p><p className="font-bold mt-1">{currency(selectedPayable.original_amount)}</p></div>
            <div className="p-3 bg-green-50 rounded-xl"><p className="text-xs text-green-700">გადახდილი</p><p className="font-bold text-green-900 mt-1">{currency(selectedPayable.paid_amount)}</p></div>
            <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-xl"><p className="text-xs text-gray-500 dark:text-gray-400">საკრედიტო ჩანაწერი</p><p className="font-bold mt-1">{currency(selectedPayable.credited_amount)}</p></div>
            <div className="p-3 bg-primary-50 rounded-xl"><p className="text-xs text-primary-700">დარჩენილი</p><p className="font-bold text-primary-900 mt-1">{currency(selectedPayable.outstanding_amount)}</p></div>
          </div>
          <div className="flex items-center justify-between"><div><p className="font-medium">{selectedPayable.supplier_name}</p><p className="text-sm text-gray-500 dark:text-gray-400">ვადა: {new Date(selectedPayable.due_date).toLocaleDateString('ka-GE')}</p></div><StatusBadge status={selectedPayable.status} map={supplierPayableStatusMap} /></div>
          <div><h3 className="font-semibold mb-3">გადახდების ისტორია</h3>{selectedPayable.payments.length ? <div className="space-y-2">{selectedPayable.payments.map((item) => <div key={item.id} className={`p-3 border rounded-lg flex items-center justify-between gap-3 ${item.is_reversed ? 'bg-gray-50 dark:bg-dark-100' : ''}`}><div><p className={`font-medium ${item.is_reversed ? 'line-through text-gray-500 dark:text-gray-400' : ''}`}>{item.reference || paymentMethods.find((method) => method.value === item.payment_method)?.label}</p><p className="text-xs text-gray-500 dark:text-gray-400">{new Date(item.payment_date).toLocaleDateString('ka-GE')}{item.is_reversed && ' · გაუქმებულია'}</p>{item.reversal && <p className="text-xs text-red-600 mt-1">მიზეზი: {item.reversal.reason}</p>}</div><div className="flex items-center gap-3"><p className={`font-semibold ${item.is_reversed ? 'text-gray-400 line-through' : 'text-green-700'}`}>{currency(item.amount)}</p>{!item.is_reversed && <button className="btn-secondary py-1.5 px-2.5 text-xs text-red-600" onClick={() => openReversal(item)}><RotateCcw size={14} className="inline mr-1" />გაუქმება</button>}</div></div>)}</div> : <p className="text-sm text-gray-500 dark:text-gray-400">გადახდა ჯერ არ არის</p>}</div>
          <div><h3 className="font-semibold mb-3">Credit Note-ების ისტორია</h3>{selectedPayable.credit_notes.length ? <div className="space-y-2">{selectedPayable.credit_notes.map((item) => <div key={item.id} className="p-3 border rounded-lg flex items-center justify-between gap-3"><div><p className="font-medium">{item.supplier_credit_note_number}</p><p className="text-xs text-gray-500 dark:text-gray-400">{new Date(item.credit_date).toLocaleDateString('ka-GE')} · {item.reason}</p></div><p className="font-semibold text-primary-700">−{currency(item.amount)}</p></div>)}</div> : <p className="text-sm text-gray-500 dark:text-gray-400">Credit Note ჯერ არ არის</p>}</div>
          {selectedPayable.outstanding_amount > 0 && <div className="flex flex-wrap justify-end gap-3 pt-4 border-t"><button className="btn-secondary" onClick={() => openCreditNote(selectedPayable)}><FileMinus2 size={17} className="inline mr-2" />საკრედიტო ჩანაწერი</button><button className="btn-primary" onClick={() => openPayment(selectedPayable)}><Banknote size={17} className="inline mr-2" />გადახდის დაფიქსირება</button></div>}
        </div>}
      </Modal>

      <Modal open={paymentOpen} onClose={() => setPaymentOpen(false)} title="მომწოდებლის გადახდა" size="lg">
        {selectedPayable && <form onSubmit={submitPayment} className="space-y-5">
          {paymentError && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{paymentError}</div>}
          <div className="p-4 bg-blue-50 rounded-xl text-blue-900"><p className="text-sm">დარჩენილი დავალიანება</p><p className="text-xl font-bold mt-1">{currency(selectedPayable.outstanding_amount)}</p></div>
          <div className="grid md:grid-cols-2 gap-4"><FormField label="თანხა" required><input required type="number" min="0.01" max={selectedPayable.outstanding_amount} step="0.01" className="input" value={payment.amount || ''} onChange={(e) => setPayment({ ...payment, amount: Number(e.target.value) })} /></FormField><FormField label="გადახდის თარიღი" required><input required type="date" className="input" value={payment.payment_date} onChange={(e) => setPayment({ ...payment, payment_date: e.target.value })} /></FormField><FormField label="მეთოდი" required><Select value={payment.payment_method} onChange={(e) => setPayment({ ...payment, payment_method: e.target.value as SupplierPaymentCreate['payment_method'] })} options={paymentMethods} /></FormField><FormField label="Reference"><input className="input" value={payment.reference || ''} onChange={(e) => setPayment({ ...payment, reference: e.target.value })} placeholder="ბანკის ტრანზაქციის ნომერი" /></FormField></div>
          <FormField label="შენიშვნა"><textarea className="input min-h-20" value={payment.notes || ''} onChange={(e) => setPayment({ ...payment, notes: e.target.value })} /></FormField>
          <div className="flex justify-end gap-3 pt-4 border-t"><button type="button" className="btn-secondary" onClick={() => setPaymentOpen(false)}>გაუქმება</button><button className="btn-primary" disabled={paymentMutation.isPending}>{paymentMutation.isPending ? 'ინახება...' : 'გადახდის დაფიქსირება'}</button></div>
        </form>}
      </Modal>

      <Modal open={creditOpen} onClose={() => setCreditOpen(false)} title="Supplier Credit Note" size="lg">
        {selectedPayable && <form onSubmit={submitCreditNote} className="space-y-5">
          {creditError && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{creditError}</div>}
          <div className="p-4 bg-primary-50 rounded-xl text-primary-900"><p className="text-sm">დარჩენილი დავალიანება</p><p className="text-xl font-bold mt-1">{currency(selectedPayable.outstanding_amount)}</p><p className="text-xs mt-2">Credit Note ამ თანხას შეამცირებს. მარაგი ავტომატურად არ შეიცვლება.</p></div>
          <div className="grid md:grid-cols-2 gap-4"><FormField label="Credit Note ნომერი" required><input required className="input" value={credit.supplier_credit_note_number} onChange={(e) => setCredit({ ...credit, supplier_credit_note_number: e.target.value })} placeholder="მაგ. CN-2026-001" /></FormField><FormField label="თარიღი" required><input required type="date" className="input" value={credit.credit_date} onChange={(e) => setCredit({ ...credit, credit_date: e.target.value })} /></FormField><FormField label="თანხა" required><input required type="number" min="0.01" max={selectedPayable.outstanding_amount} step="0.01" className="input" value={credit.amount || ''} onChange={(e) => setCredit({ ...credit, amount: Number(e.target.value) })} /></FormField></div>
          <FormField label="მიზეზი" required><textarea required className="input min-h-24" value={credit.reason} onChange={(e) => setCredit({ ...credit, reason: e.target.value })} placeholder="მაგ. ფასის კორექტირება ან მომწოდებლის ფასდაკლება" /></FormField>
          <div className="flex justify-end gap-3 pt-4 border-t"><button type="button" className="btn-secondary" onClick={() => setCreditOpen(false)}>გაუქმება</button><button className="btn-primary" disabled={creditMutation.isPending}>{creditMutation.isPending ? 'ინახება...' : 'Credit Note-ის დაფიქსირება'}</button></div>
        </form>}
      </Modal>

      <Modal open={Boolean(reversalPayment)} onClose={() => setReversalPayment(null)} title="გადახდის გაუქმება" size="lg">
        {reversalPayment && <form onSubmit={submitReversal} className="space-y-5">
          {reversalError && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{reversalError}</div>}
          <div className="p-4 bg-red-50 rounded-xl text-red-900"><p className="font-medium flex items-center gap-2"><RotateCcw size={18} /> გადახდა გაუქმდება</p><p className="text-xl font-bold mt-2">{currency(reversalPayment.amount)}</p><p className="text-sm mt-2">თანხა დაბრუნდება მომწოდებლის დავალიანებაში. ჩანაწერი ისტორიაში დარჩება.</p></div>
          <FormField label="გაუქმების მიზეზი" required><textarea required className="input min-h-24" value={reversal.reason} onChange={(e) => setReversal({ ...reversal, reason: e.target.value })} placeholder="მიუთითეთ, რატომ უქმდება გადახდა" /></FormField>
          <div className="flex justify-end gap-3 pt-4 border-t"><button type="button" className="btn-secondary" onClick={() => setReversalPayment(null)}>დახურვა</button><button className="btn-primary bg-red-600 hover:bg-red-700" disabled={reversalMutation.isPending}>{reversalMutation.isPending ? 'უქმდება...' : 'გადახდის გაუქმება'}</button></div>
        </form>}
      </Modal>

      <ConfirmDialog open={Boolean(invoiceAction && selectedInvoice)} onClose={() => setInvoiceAction(null)} onConfirm={() => selectedInvoice && invoiceAction && statusMutation.mutate({ id: selectedInvoice.id, target: invoiceAction })} title={invoiceAction === 'approved' ? 'მომწოდებლის ინვოისის დამტკიცება' : 'მომწოდებლის ინვოისის გაუქმება'} message={invoiceAction === 'approved' ? 'დამტკიცების შემდეგ ავტომატურად შეიქმნება მომწოდებლის დავალიანება. თანხისა და მიღების შეჯერება გავლილია.' : 'გაუქმებული invoice payable-ს აღარ შექმნის.'} confirmLabel={invoiceAction === 'approved' ? 'დამტკიცება' : 'გაუქმება'} variant={invoiceAction === 'approved' ? 'warning' : 'danger'} loading={statusMutation.isPending} />
    </div>
  )
}
