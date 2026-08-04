import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowRight,
  CalendarDays,
  Check,
  ClipboardList,
  FileText,
  PackageCheck,
  Plus,
  Search,
  Trash2,
  Truck,
  XCircle,
} from 'lucide-react'

import ConfirmDialog from '../components/ui/ConfirmDialog'
import DataTable from '../components/ui/DataTable'
import FormField, { Select } from '../components/ui/FormField'
import Modal from '../components/ui/Modal'
import { purchaseOrderStatusMap, StatusBadge } from '../components/ui/Badges'
import { productsApi, purchaseOrdersApi, suppliersApi, warehousesApi } from '../services/api'
import { useAuthStore } from '../store/authStore'
import type {
  GoodsReceipt,
  Product,
  PurchaseOrder,
  PurchaseOrderCreate,
  PurchaseOrderHistory,
  PurchaseOrderStatus,
  Supplier,
  Warehouse,
} from '../types'

type DraftLine = PurchaseOrderCreate['items'][number]

const emptyLine = (): DraftLine => ({
  product_id: '',
  quantity: 1,
  unit_price: 0,
  discount_percent: 0,
  vat_rate: 18,
})

const statusFilters = [
  { value: '', label: 'ყველა სტატუსი' },
  { value: 'draft', label: 'მონახაზი' },
  { value: 'approved', label: 'დამტკიცებული' },
  { value: 'partially_received', label: 'ნაწილობრივ მიღებული' },
  { value: 'received', label: 'სრულად მიღებული' },
  { value: 'cancelled', label: 'გაუქმებული' },
]

const lifecycle: { key: PurchaseOrderStatus; label: string }[] = [
  { key: 'draft', label: 'მონახაზი' },
  { key: 'approved', label: 'დამტკიცებული' },
  { key: 'partially_received', label: 'ნაწილობრივი მიღება' },
  { key: 'received', label: 'სრულად მიღებული' },
]

const lifecycleRank: Record<string, number> = {
  draft: 0,
  approved: 1,
  partially_received: 2,
  received: 3,
}

function currency(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

export default function PurchasesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [receiptOpen, setReceiptOpen] = useState(false)
  const [action, setAction] = useState<'approved' | 'cancelled' | null>(null)
  const [formError, setFormError] = useState('')
  const [receiptError, setReceiptError] = useState('')
  const [receiptNotes, setReceiptNotes] = useState('')
  const [receiptQuantities, setReceiptQuantities] = useState<Record<string, number>>({})
  const [form, setForm] = useState<PurchaseOrderCreate>({
    supplier_id: '',
    warehouse_id: '',
    expected_delivery_date: '',
    notes: '',
    items: [emptyLine()],
  })

  const { data, isLoading } = useQuery({
    queryKey: ['purchase-orders', search, status],
    queryFn: () => purchaseOrdersApi.list({ search: search || undefined, status: status || undefined, page_size: 100 }).then((r) => r.data.data),
  })
  const { data: suppliersData } = useQuery({
    queryKey: ['suppliers', 'active'],
    queryFn: () => suppliersApi.list({ page_size: 100 }).then((r) => r.data.data),
  })
  const { data: warehousesData } = useQuery({
    queryKey: ['warehouses'],
    queryFn: () => warehousesApi.list().then((r) => r.data.data),
  })
  const { data: productsData } = useQuery({
    queryKey: ['products', 'purchase-options'],
    queryFn: () => productsApi.list({ page_size: 100 }).then((r) => r.data.data),
  })
  const { data: selectedData } = useQuery({
    queryKey: ['purchase-order', selectedId],
    queryFn: () => purchaseOrdersApi.get(selectedId!).then((r) => r.data.data),
    enabled: Boolean(selectedId),
  })
  const { data: historyData } = useQuery({
    queryKey: ['purchase-order-history', selectedId],
    queryFn: () => purchaseOrdersApi.history(selectedId!).then((r) => r.data.data),
    enabled: Boolean(selectedId),
  })
  const { data: receiptsData } = useQuery({
    queryKey: ['purchase-order-receipts', selectedId],
    queryFn: () => purchaseOrdersApi.receipts(selectedId!).then((r) => r.data.data),
    enabled: Boolean(selectedId),
  })

  const orders: PurchaseOrder[] = data?.items || []
  const suppliers: Supplier[] = suppliersData?.items || []
  const warehouses: Warehouse[] = warehousesData || []
  const products: Product[] = productsData?.items || []
  const selected: PurchaseOrder | undefined = selectedData
  const history: PurchaseOrderHistory[] = historyData || []
  const receipts: GoodsReceipt[] = receiptsData || []
  const canApproveSelected = Boolean(selected && (
    user?.role === 'admin' ||
    (user?.role === 'manager' && selected.required_approval_role === 'manager')
  ))

  const draftTotal = useMemo(() => form.items.reduce((total, line) => {
    const gross = line.quantity * line.unit_price
    const net = gross - gross * line.discount_percent / 100
    return total + net + net * line.vat_rate / 100
  }, 0), [form.items])

  function refreshPurchases() {
    queryClient.invalidateQueries({ queryKey: ['purchase-orders'] })
    if (selectedId) {
      queryClient.invalidateQueries({ queryKey: ['purchase-order', selectedId] })
      queryClient.invalidateQueries({ queryKey: ['purchase-order-history', selectedId] })
      queryClient.invalidateQueries({ queryKey: ['purchase-order-receipts', selectedId] })
    }
  }

  const createMutation = useMutation({
    mutationFn: (payload: PurchaseOrderCreate) => purchaseOrdersApi.create(payload),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] })
      setCreateOpen(false)
      setForm({ supplier_id: '', warehouse_id: '', expected_delivery_date: '', notes: '', items: [emptyLine()] })
      setSelectedId(response.data.data.id)
      setFormError('')
    },
    onError: (error: any) => setFormError(error.response?.data?.detail || 'შესყიდვის შეკვეთის შექმნა ვერ მოხერხდა'),
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, target }: { id: string; target: string }) => purchaseOrdersApi.changeStatus(id, target),
    onSuccess: () => {
      refreshPurchases()
      setAction(null)
      setFormError('')
    },
    onError: (error: any) => {
      setFormError(error.response?.data?.detail || 'სტატუსის შეცვლა ვერ მოხერხდა')
      setAction(null)
    },
  })

  const receiptMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: any }) => purchaseOrdersApi.receive(id, payload),
    onSuccess: () => {
      refreshPurchases()
      queryClient.invalidateQueries({ queryKey: ['products'] })
      queryClient.invalidateQueries({ queryKey: ['warehouse-balances'] })
      setReceiptOpen(false)
      setReceiptNotes('')
      setReceiptQuantities({})
      setReceiptError('')
    },
    onError: (error: any) => setReceiptError(error.response?.data?.detail || 'საქონლის მიღება ვერ შესრულდა'),
  })

  function openCreate() {
    const defaultWarehouse = warehouses.find((warehouse) => warehouse.is_default && warehouse.is_active)
    setForm({
      supplier_id: '',
      warehouse_id: defaultWarehouse?.id || '',
      expected_delivery_date: '',
      notes: '',
      items: [emptyLine()],
    })
    setFormError('')
    setCreateOpen(true)
  }

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setForm((current) => ({
      ...current,
      items: current.items.map((line, lineIndex) => lineIndex === index ? { ...line, ...patch } : line),
    }))
  }

  function selectProduct(index: number, productId: string) {
    const product = products.find((item) => item.id === productId)
    updateLine(index, { product_id: productId, unit_price: product?.purchase_price || 0 })
  }

  function submitPurchaseOrder(event: React.FormEvent) {
    event.preventDefault()
    setFormError('')
    if (!form.supplier_id || !form.warehouse_id || form.items.some((item) => !item.product_id)) {
      setFormError('შეავსეთ მომწოდებელი, საწყობი და ყველა პროდუქტი')
      return
    }
    if (new Set(form.items.map((item) => item.product_id)).size !== form.items.length) {
      setFormError('ერთი პროდუქტი შესყიდვის შეკვეთაში მხოლოდ ერთხელ შეიძლება იყოს')
      return
    }
    createMutation.mutate({ ...form, expected_delivery_date: form.expected_delivery_date || undefined })
  }

  function openReceipt() {
    if (!selected) return
    setReceiptQuantities(Object.fromEntries(selected.items.filter((item) => item.remaining_quantity > 0).map((item) => [item.id, item.remaining_quantity])))
    setReceiptNotes('')
    setReceiptError('')
    setReceiptOpen(true)
  }

  function submitReceipt(event: React.FormEvent) {
    event.preventDefault()
    if (!selected) return
    const items = selected.items
      .map((item) => ({ purchase_order_item_id: item.id, quantity: Number(receiptQuantities[item.id] || 0) }))
      .filter((item) => item.quantity > 0)
    if (!items.length) {
      setReceiptError('მიუთითეთ მინიმუმ ერთი მისაღები რაოდენობა')
      return
    }
    receiptMutation.mutate({
      id: selected.id,
      payload: { idempotency_key: crypto.randomUUID(), notes: receiptNotes || undefined, items },
    })
  }

  const columns = [
    { key: 'purchase_order_number', label: 'დოკუმენტი', render: (order: PurchaseOrder) => (
      <div><p className="font-semibold text-gray-900 dark:text-gray-100">{order.purchase_order_number}</p><p className="text-xs text-gray-500 dark:text-gray-400">{new Date(order.created_at).toLocaleDateString('ka-GE')}</p></div>
    ) },
    { key: 'supplier_name', label: 'მომწოდებელი' },
    { key: 'warehouse_name', label: 'საწყობი', hideOnMobile: true },
    { key: 'status', label: 'სტატუსი', render: (order: PurchaseOrder) => <StatusBadge status={order.status} map={purchaseOrderStatusMap} /> },
    { key: 'total', label: 'ჯამი', className: 'text-right font-semibold', render: (order: PurchaseOrder) => currency(order.total) },
    { key: 'progress', label: 'მიღება', hideOnMobile: true, render: (order: PurchaseOrder) => {
      const ordered = order.items.reduce((sum, item) => sum + item.quantity, 0)
      const received = order.items.reduce((sum, item) => sum + item.received_quantity, 0)
      return <span className="text-gray-600 dark:text-gray-400">{received} / {ordered}</span>
    } },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">შესყიდვები</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">შესყიდვის შეკვეთები, საქონლის მიღება და საწყობის შემოსავალი</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={openCreate}><Plus size={18} /> ახალი შესყიდვის შეკვეთა</button>
      </div>

      {formError && !createOpen && !selectedId && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{formError}</div>}

      <div className="card flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <input className="input pl-10" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="შესყიდვის შეკვეთის ნომერი" />
        </div>
        <Select className="sm:w-60" value={status} onChange={(e) => setStatus(e.target.value)} options={statusFilters} />
      </div>

      <DataTable columns={columns} data={orders} isLoading={isLoading} onRowClick={(order) => { setFormError(''); setSelectedId(order.id) }} emptyMessage="შესყიდვის შეკვეთა ჯერ არ არის შექმნილი" />

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="ახალი შესყიდვის შეკვეთა" size="xl">
        <form onSubmit={submitPurchaseOrder} className="space-y-5">
          {formError && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{formError}</div>}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <FormField label="მომწოდებელი" required><Select required value={form.supplier_id} onChange={(e) => setForm({ ...form, supplier_id: e.target.value })} placeholder="აირჩიეთ" options={suppliers.map((item) => ({ value: item.id, label: `${item.code} — ${item.name}` }))} /></FormField>
            <FormField label="მიმღები საწყობი" required><Select required value={form.warehouse_id} onChange={(e) => setForm({ ...form, warehouse_id: e.target.value })} placeholder="აირჩიეთ" options={warehouses.filter((item) => item.is_active).map((item) => ({ value: item.id, label: item.name }))} /></FormField>
            <FormField label="მოსალოდნელი მიღება"><input type="date" className="input" value={form.expected_delivery_date || ''} onChange={(e) => setForm({ ...form, expected_delivery_date: e.target.value })} /></FormField>
          </div>

          <div className="border rounded-xl overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 dark:bg-dark-100 border-b flex items-center justify-between"><h3 className="font-medium text-gray-900 dark:text-gray-100">პროდუქტები</h3><button type="button" className="text-sm text-primary-600 flex items-center gap-1" onClick={() => setForm({ ...form, items: [...form.items, emptyLine()] })}><Plus size={15} /> ხაზის დამატება</button></div>
            <div className="divide-y">
              {form.items.map((line, index) => (
                <div key={index} className="p-4 grid grid-cols-12 gap-3 items-end">
                  <div className="col-span-12 md:col-span-4"><FormField label="პროდუქტი" required><Select required value={line.product_id} onChange={(e) => selectProduct(index, e.target.value)} placeholder="აირჩიეთ" options={products.map((product) => ({ value: product.id, label: `${product.sku} — ${product.name}` }))} /></FormField></div>
                  <div className="col-span-4 md:col-span-2"><FormField label="რაოდენობა"><input type="number" min="0.001" step="0.001" className="input" value={line.quantity} onChange={(e) => updateLine(index, { quantity: Number(e.target.value) })} /></FormField></div>
                  <div className="col-span-4 md:col-span-2"><FormField label="ფასი"><input type="number" min="0" step="0.01" className="input" value={line.unit_price || ''} onChange={(e) => updateLine(index, { unit_price: Number(e.target.value) })} /></FormField></div>
                  <div className="col-span-4 md:col-span-1"><FormField label="ფასდ. %"><input type="number" min="0" max="100" step="0.01" className="input" value={line.discount_percent} onChange={(e) => updateLine(index, { discount_percent: Number(e.target.value) })} /></FormField></div>
                  <div className="col-span-4 md:col-span-1"><FormField label="დღგ %"><input type="number" min="0" max="100" step="0.01" className="input" value={line.vat_rate} onChange={(e) => updateLine(index, { vat_rate: Number(e.target.value) })} /></FormField></div>
                  <div className="col-span-6 md:col-span-1 text-right pb-2 font-medium">{currency((line.quantity * line.unit_price * (1 - line.discount_percent / 100)) * (1 + line.vat_rate / 100))}</div>
                  <div className="col-span-2 md:col-span-1 pb-1 text-right"><button type="button" className="p-2 text-red-500 hover:bg-red-50 rounded-lg disabled:opacity-30" disabled={form.items.length === 1} onClick={() => setForm({ ...form, items: form.items.filter((_, itemIndex) => itemIndex !== index) })}><Trash2 size={17} /></button></div>
                </div>
              ))}
            </div>
          </div>
          <FormField label="შენიშვნა"><textarea className="input min-h-20" value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></FormField>
          <div className="flex items-center justify-between pt-4 border-t"><div><p className="text-xs text-gray-500 dark:text-gray-400">სავარაუდო ჯამი დღგ-ის ჩათვლით</p><p className="text-xl font-bold text-gray-900 dark:text-gray-100">{currency(draftTotal)}</p></div><div className="flex gap-3"><button type="button" className="btn-secondary" onClick={() => setCreateOpen(false)}>გაუქმება</button><button className="btn-primary" disabled={createMutation.isPending}>{createMutation.isPending ? 'იქმნება...' : 'შესყიდვის შეკვეთის შექმნა'}</button></div></div>
        </form>
      </Modal>

      <Modal open={Boolean(selectedId)} onClose={() => { setSelectedId(null); setFormError('') }} title={selected?.purchase_order_number || 'შესყიდვის შეკვეთა'} size="xl">
        {selected && (
          <div className="space-y-6">
            {formError && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{formError}</div>}
            {selected.status === 'cancelled' ? <div className="p-4 bg-red-50 rounded-xl flex items-center gap-3 text-red-700"><XCircle size={22} /> შესყიდვის შეკვეთა გაუქმებულია</div> : (
              <div className="flex items-start justify-between gap-2">
                {lifecycle.map((step, index) => {
                  const active = lifecycleRank[selected.status] >= index
                  return <div key={step.key} className="flex-1 flex items-center last:flex-none"><div className="flex flex-col items-center min-w-20"><div className={`w-9 h-9 rounded-full flex items-center justify-center ${active ? 'bg-primary-600 text-white' : 'bg-gray-100 dark:bg-dark-100 text-gray-400'}`}>{active ? <Check size={18} /> : index + 1}</div><span className={`text-xs mt-2 text-center ${active ? 'text-gray-900 dark:text-gray-100 font-medium' : 'text-gray-400'}`}>{step.label}</span></div>{index < lifecycle.length - 1 && <div className={`h-0.5 flex-1 mt-[-18px] ${lifecycleRank[selected.status] > index ? 'bg-primary-600' : 'bg-gray-200'}`} />}</div>
                })}
              </div>
            )}

            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="p-4 bg-gray-50 dark:bg-dark-100 rounded-xl"><p className="text-xs text-gray-500 dark:text-gray-400">მომწოდებელი</p><p className="font-medium mt-1">{selected.supplier_name}</p></div>
              <div className="p-4 bg-gray-50 dark:bg-dark-100 rounded-xl"><p className="text-xs text-gray-500 dark:text-gray-400">საწყობი</p><p className="font-medium mt-1">{selected.warehouse_name}</p></div>
              <div className="p-4 bg-gray-50 dark:bg-dark-100 rounded-xl"><p className="text-xs text-gray-500 dark:text-gray-400">სტატუსი</p><div className="mt-1"><StatusBadge status={selected.status} map={purchaseOrderStatusMap} /></div></div>
              <div className="p-4 bg-gray-50 dark:bg-dark-100 rounded-xl"><p className="text-xs text-gray-500 dark:text-gray-400">ჯამი</p><p className="font-bold mt-1">{currency(selected.total)}</p></div>
              <div className={`p-4 rounded-xl ${selected.required_approval_role === 'admin' ? 'bg-purple-50' : 'bg-blue-50'}`}>
                <p className="text-xs text-gray-500 dark:text-gray-400">საჭირო დამმტკიცებელი</p>
                <p className={`font-semibold mt-1 ${selected.required_approval_role === 'admin' ? 'text-purple-700' : 'text-blue-700'}`}>
                  {selected.required_approval_role === 'admin' ? 'ადმინისტრატორი' : 'მენეჯერი / ადმინისტრატორი'}
                </p>
              </div>
            </div>

            <div className="border rounded-xl overflow-x-auto"><table className="w-full text-sm"><thead className="bg-gray-50 dark:bg-dark-100"><tr><th className="text-left p-3">პროდუქტი</th><th className="text-right p-3">შეკვეთილი</th><th className="text-right p-3">მიღებული</th><th className="text-right p-3">დარჩენილი</th><th className="text-right p-3">ფასი</th><th className="text-right p-3">ჯამი</th></tr></thead><tbody className="divide-y">{selected.items.map((item) => <tr key={item.id}><td className="p-3 font-medium">{item.product_name}</td><td className="p-3 text-right">{item.quantity}</td><td className="p-3 text-right text-green-700">{item.received_quantity}</td><td className="p-3 text-right">{item.remaining_quantity}</td><td className="p-3 text-right">{currency(item.unit_price)}</td><td className="p-3 text-right font-medium">{currency(item.line_total)}</td></tr>)}</tbody></table></div>

            <div className="grid md:grid-cols-2 gap-5">
              <div><h3 className="font-semibold flex items-center gap-2 mb-3"><ClipboardList size={18} /> სტატუსის ისტორია</h3><div className="space-y-3">{history.map((item) => <div key={item.id} className="flex gap-3"><div className="w-2 h-2 rounded-full bg-primary-500 mt-2" /><div><StatusBadge status={item.status} map={purchaseOrderStatusMap} /><p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{new Date(item.created_at).toLocaleString('ka-GE')}</p>{item.notes && <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{item.notes}</p>}</div></div>)}</div></div>
              <div><h3 className="font-semibold flex items-center gap-2 mb-3"><PackageCheck size={18} /> მიღებები</h3>{receipts.length ? <div className="space-y-2">{receipts.map((receipt) => <div key={receipt.id} className="p-3 border rounded-lg flex justify-between"><div><p className="font-medium">{receipt.receipt_number}</p><p className="text-xs text-gray-500 dark:text-gray-400">{new Date(receipt.received_at).toLocaleString('ka-GE')}</p></div><p className="text-sm text-gray-600 dark:text-gray-400">{receipt.items.reduce((sum, item) => sum + item.quantity, 0)} ერთ.</p></div>)}</div> : <p className="text-sm text-gray-500 dark:text-gray-400">მიღება ჯერ არ დაფიქსირებულა</p>}</div>
            </div>

            {selected.status === 'draft' && !canApproveSelected && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                ამ შესყიდვის შეკვეთის დამტკიცება შეუძლია {selected.required_approval_role === 'admin' ? 'მხოლოდ ადმინისტრატორს' : 'მენეჯერს ან ადმინისტრატორს'}.
              </div>
            )}

            <div className="flex flex-wrap justify-end gap-3 pt-4 border-t">
              {selected.status === 'draft' && <>
                <button className="btn-secondary text-red-600" onClick={() => setAction('cancelled')}><XCircle size={17} className="inline mr-2" />გაუქმება</button>
                {canApproveSelected && <button className="btn-primary" onClick={() => setAction('approved')}><Check size={17} className="inline mr-2" />დამტკიცება</button>}
              </>}
              {selected.status === 'approved' && <><button className="btn-secondary text-red-600" onClick={() => setAction('cancelled')}>გაუქმება</button><button className="btn-primary" onClick={openReceipt}><Truck size={17} className="inline mr-2" />საქონლის მიღება</button></>}
              {selected.status === 'partially_received' && <button className="btn-primary" onClick={openReceipt}><ArrowRight size={17} className="inline mr-2" />მიღების გაგრძელება</button>}
              {['partially_received', 'received'].includes(selected.status) && <button className="btn-secondary" onClick={() => navigate(`/supplier-finance?purchase_order_id=${selected.id}`)}><FileText size={17} className="inline mr-2" />მომწოდებლის ინვოისი</button>}
            </div>
          </div>
        )}
      </Modal>

      <Modal open={receiptOpen} onClose={() => setReceiptOpen(false)} title="საქონლის მიღება" size="lg">
        {selected && <form onSubmit={submitReceipt} className="space-y-5">
          {receiptError && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{receiptError}</div>}
          <div className="p-3 bg-blue-50 rounded-lg text-sm text-blue-800"><CalendarDays size={17} className="inline mr-2" />მარაგი დაემატება საწყობში: <strong>{selected.warehouse_name}</strong></div>
          <div className="space-y-3">{selected.items.filter((item) => item.remaining_quantity > 0).map((item) => <div key={item.id} className="grid grid-cols-3 gap-3 items-center p-3 border rounded-lg"><div className="col-span-2"><p className="font-medium">{item.product_name}</p><p className="text-xs text-gray-500 dark:text-gray-400">დარჩენილი: {item.remaining_quantity}</p></div><input type="number" min="0" max={item.remaining_quantity} step="0.001" className="input text-right" value={receiptQuantities[item.id] || 0} onChange={(e) => setReceiptQuantities({ ...receiptQuantities, [item.id]: Number(e.target.value) })} /></div>)}</div>
          <FormField label="შენიშვნა"><textarea className="input min-h-20" value={receiptNotes} onChange={(e) => setReceiptNotes(e.target.value)} placeholder="ზედნადების ნომერი ან სხვა ინფორმაცია" /></FormField>
          <div className="flex justify-end gap-3 pt-4 border-t"><button type="button" className="btn-secondary" onClick={() => setReceiptOpen(false)}>გაუქმება</button><button className="btn-primary" disabled={receiptMutation.isPending}>{receiptMutation.isPending ? 'მიღება მუშავდება...' : 'მიღების დაფიქსირება'}</button></div>
        </form>}
      </Modal>

      <ConfirmDialog open={Boolean(action && selected)} onClose={() => setAction(null)} onConfirm={() => selected && action && statusMutation.mutate({ id: selected.id, target: action })} title={action === 'approved' ? 'შესყიდვის შეკვეთის დამტკიცება' : 'შესყიდვის შეკვეთის გაუქმება'} message={action === 'approved' ? 'დამტკიცების შემდეგ შესაძლებელი გახდება საქონლის მიღება. მარაგი ამ ეტაპზე ჯერ არ შეიცვლება.' : 'გაუქმებული შესყიდვის შეკვეთის აღდგენა შეუძლებელი იქნება.'} confirmLabel={action === 'approved' ? 'დამტკიცება' : 'გაუქმება'} variant={action === 'approved' ? 'warning' : 'danger'} loading={statusMutation.isPending} />
    </div>
  )
}
