import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ordersApi, clientsApi, productsApi, warehousesApi } from '../services/api'
import { ArrowRight, Eye, FileText, PackageCheck, Plus, Search, UserPlus, X } from 'lucide-react'
import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import { StatusBadge, orderStatusMap } from '../components/ui/Badges'
import type { Client, ClientCreate, InventoryReservation, Order, OrderCreate, OrderStatus, OrderStatusHistory, OrderSummary, Warehouse } from '../types'

const nextStatusActions: Partial<Record<OrderStatus, { status: OrderStatus; label: string; danger?: boolean }[]>> = {
  new: [
    { status: 'confirmed', label: 'შეკვეთის დადასტურება' },
    { status: 'cancelled', label: 'გაუქმება', danger: true },
  ],
  confirmed: [
    { status: 'preparing', label: 'მომზადების დაწყება' },
    { status: 'cancelled', label: 'გაუქმება', danger: true },
  ],
  preparing: [
    { status: 'shipping', label: 'მიწოდებაში გაშვება' },
    { status: 'cancelled', label: 'გაუქმება', danger: true },
  ],
  shipping: [{ status: 'completed', label: 'მიწოდების დასრულება' }],
  completed: [{ status: 'returned', label: 'სრული დაბრუნება', danger: true }],
}

const lifecycleStages: { status: OrderStatus; label: string }[] = [
  { status: 'new', label: 'ახალი' },
  { status: 'confirmed', label: 'დადასტურებული' },
  { status: 'preparing', label: 'მზადდება' },
  { status: 'shipping', label: 'მიწოდებაში' },
  { status: 'completed', label: 'დასრულებული' },
]

const reservationLabels: Record<string, string> = {
  active: 'დარეზერვებული',
  consumed: 'მარაგიდან გაცემული',
  released: 'რეზერვაცია მოხსნილი',
  returned: 'მარაგში დაბრუნებული',
}

export default function OrdersPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [viewOrderId, setViewOrderId] = useState<string | null>(null)
  const [actionError, setActionError] = useState('')
  const [clientPanelOpen, setClientPanelOpen] = useState(false)
  const [clientError, setClientError] = useState('')
  const [clientForm, setClientForm] = useState<ClientCreate>({
    name: '', client_type: 'legal', identification_code: '', is_vat_payer: true,
    address: '', phone: '', email: '', notes: '',
  })

  const { data, isLoading } = useQuery({
    queryKey: ['orders', statusFilter, search],
    queryFn: () => ordersApi.list({ status: statusFilter || undefined, search: search || undefined, page_size: 50 }).then(r => r.data.data),
  })
  const { data: viewOrder, isLoading: isOrderDetailLoading } = useQuery<Order>({
    queryKey: ['order-detail', viewOrderId],
    queryFn: () => ordersApi.get(viewOrderId!).then(r => r.data.data),
    enabled: !!viewOrderId,
  })
  const { data: orderHistory = [] } = useQuery<OrderStatusHistory[]>({
    queryKey: ['order-history', viewOrderId],
    queryFn: () => ordersApi.history(viewOrderId!).then(r => r.data.data),
    enabled: !!viewOrderId,
  })
  const { data: reservations = [] } = useQuery<InventoryReservation[]>({
    queryKey: ['order-reservations', viewOrderId],
    queryFn: () => ordersApi.reservations(viewOrderId!).then(r => r.data.data),
    enabled: !!viewOrderId,
  })
  const { data: clientsData } = useQuery({ queryKey: ['clients-select'], queryFn: () => clientsApi.list({ page_size: 100 }).then(r => r.data.data) })
  const { data: productsData } = useQuery({ queryKey: ['products-select'], queryFn: () => productsApi.list({ page_size: 100 }).then(r => r.data.data) })
  const { data: warehousesData } = useQuery({ queryKey: ['warehouses-select'], queryFn: () => warehousesApi.list().then(r => r.data.data) })

  const items: OrderSummary[] = data?.items || []
  const clients = (clientsData?.items || []) as any[]
  const products = (productsData?.items || []) as any[]
  const warehouses = (warehousesData || []) as Warehouse[]

  // Order create form
  const [form, setForm] = useState<OrderCreate>({
    client_id: '', warehouse_id: '', items: [{ product_id: '', product_name: '', quantity: 1, unit_price: 0, discount_percent: 0 }],
    delivery_date: '', delivery_address: '', notes: '', is_vat_payer: true,
  })

  const createMutation = useMutation({
    mutationFn: (data: OrderCreate) => ordersApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      queryClient.invalidateQueries({ queryKey: ['customer-invoices'] })
      setModalOpen(false)
    },
  })

  const createClientMutation = useMutation({
    mutationFn: (data: ClientCreate) => clientsApi.create(data),
    onSuccess: (response) => {
      const client = response.data.data as Client
      queryClient.invalidateQueries({ queryKey: ['clients-select'] })
      queryClient.invalidateQueries({ queryKey: ['clients'] })
      setForm(current => ({
        ...current,
        client_id: client.id,
        is_vat_payer: client.is_vat_payer,
        delivery_address: current.delivery_address || client.address || '',
      }))
      setClientPanelOpen(false)
      setClientError('')
    },
    onError: (error: any) => setClientError(error.response?.data?.detail || 'კლიენტის დამატება ვერ შესრულდა'),
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: OrderStatus }) => ordersApi.changeStatus(id, { status }),
    onSuccess: () => {
      setActionError('')
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      queryClient.invalidateQueries({ queryKey: ['order-detail', viewOrderId] })
      queryClient.invalidateQueries({ queryKey: ['order-history', viewOrderId] })
      queryClient.invalidateQueries({ queryKey: ['order-reservations', viewOrderId] })
      queryClient.invalidateQueries({ queryKey: ['warehouse-balances'] })
      queryClient.invalidateQueries({ queryKey: ['products'] })
    },
    onError: (error: any) => setActionError(error.response?.data?.detail || 'სტატუსის შეცვლა ვერ შესრულდა'),
  })

  function openCreate() {
    const defaultWarehouse = warehouses.find(warehouse => warehouse.is_default) || warehouses[0]
    setForm({ client_id: '', warehouse_id: defaultWarehouse?.id || '', items: [{ product_id: '', product_name: '', quantity: 1, unit_price: 0, discount_percent: 0 }], delivery_date: '', delivery_address: '', notes: '', is_vat_payer: true })
    setClientPanelOpen(false)
    setClientError('')
    setClientForm({ name: '', client_type: 'legal', identification_code: '', is_vat_payer: true, address: '', phone: '', email: '', notes: '' })
    setModalOpen(true)
  }

  function changeStatus(status: OrderStatus, danger?: boolean) {
    if (!viewOrder) return
    if (danger && !window.confirm(status === 'returned' ? 'დადასტურების შემდეგ საქონელი საწყობში დაბრუნდება. გავაგრძელოთ?' : 'ნამდვილად გსურთ შეკვეთის გაუქმება?')) return
    statusMutation.mutate({ id: viewOrder.id, status })
  }

  function addItem() {
    setForm(f => ({ ...f, items: [...f.items, { product_id: '', product_name: '', quantity: 1, unit_price: 0, discount_percent: 0 }] }))
  }

  function removeItem(idx: number) {
    setForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }))
  }

  function updateItem(idx: number, field: string, value: any) {
    setForm(f => {
      const items = [...f.items]
      items[idx] = { ...items[idx], [field]: value }
      // Auto-fill from product selection
      if (field === 'product_id') {
        const prod = products.find((p: any) => p.id === value)
        if (prod) {
          items[idx] = { ...items[idx], product_name: prod.name, unit_price: prod.sale_price }
        }
      }
      return { ...f, items }
    })
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    createMutation.mutate(form)
  }

  const columns = [
    { key: 'order_number', label: 'შეკვეთა', render: (o: OrderSummary) => <span className="font-mono font-medium text-gray-900 dark:text-gray-100 dark:text-gray-200">{o.order_number}</span> },
    { key: 'client_name', label: 'კლიენტი', render: (o: OrderSummary) => o.client_name || '—', hideOnMobile: true },
    { key: 'status', label: 'სტატუსი', render: (o: OrderSummary) => <StatusBadge status={o.status} map={orderStatusMap} /> },
    { key: 'total', label: 'თანხა', render: (o: OrderSummary) => `${o.total?.toLocaleString()} ₾`, className: 'font-medium' },
    { key: 'created_at', label: 'თარიღი', render: (o: OrderSummary) => new Date(o.created_at).toLocaleDateString('ka-GE'), hideOnMobile: true },
    {
      key: 'actions', label: '',
      render: (o: OrderSummary) => (
        <button onClick={(e) => { e.stopPropagation(); setViewOrderId(o.id) }} className="p-1.5 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 rounded">
          <Eye size={16} className="text-gray-500 dark:text-gray-400 dark:text-gray-500" />
        </button>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 dark:text-gray-200">გაყიდვის შეკვეთები</h1><p className="mt-1 text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500">კლიენტის შეკვეთები, მარაგის რეზერვაცია და მიწოდების პროცესი</p></div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus size={18} /> ახალი გაყიდვის შეკვეთა
        </button>
      </div>

      <div className="card flex flex-wrap gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" size={18} />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="ძებნა ნომრით, კლიენტით..." className="input pl-10" />
        </div>
        <button onClick={() => setStatusFilter('')} className={`btn-secondary text-sm ${!statusFilter ? 'ring-2 ring-primary-500' : ''}`}>ყველა</button>
        {Object.entries(orderStatusMap).map(([key, { label }]) => (
          <button key={key} onClick={() => setStatusFilter(key)} className={`btn-secondary text-sm ${statusFilter === key ? 'ring-2 ring-primary-500' : ''}`}>{label}</button>
        ))}
      </div>

      <DataTable columns={columns} data={items} isLoading={isLoading} emptyMessage="გაყიდვის შეკვეთა არ მოიძებნა" onRowClick={(o) => setViewOrderId(o.id)} />

      {/* Create Order Modal */}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="ახალი გაყიდვის შეკვეთა" size="xl">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="mb-1.5 flex items-center justify-between gap-3">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-400">კლიენტი <span className="text-red-500">*</span></label>
                <button
                  type="button"
                  onClick={() => { setClientPanelOpen(!clientPanelOpen); setClientError('') }}
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-primary-700 hover:text-primary-800"
                >
                  <UserPlus size={15} /> {clientPanelOpen ? 'დახურვა' : 'ახალი კლიენტი'}
                </button>
              </div>
              <Select
                value={form.client_id}
                onChange={(e) => {
                  const client = clients.find((item: Client) => item.id === e.target.value)
                  setForm({
                    ...form,
                    client_id: e.target.value,
                    is_vat_payer: client?.is_vat_payer ?? form.is_vat_payer,
                    delivery_address: form.delivery_address || client?.address || '',
                  })
                }}
                placeholder="აირჩიეთ კლიენტი"
                options={clients.map((client: Client) => ({ value: client.id, label: `${client.name} — ${client.identification_code}` }))}
                required
              />
            </div>
            <FormField label="საწყობი" required>
              <Select value={form.warehouse_id || ''} onChange={(e) => setForm({ ...form, warehouse_id: e.target.value })} placeholder="აირჩიეთ საწყობი" options={warehouses.map(warehouse => ({ value: warehouse.id, label: `${warehouse.name} (${warehouse.code})` }))} required />
            </FormField>
            <FormField label="დღგ">
              <Select options={[{ value: 'true', label: 'დღგ-ს ჩათვლით (18%)' }, { value: 'false', label: 'დღგ-ს გარეშე' }]} value={String(form.is_vat_payer)} onChange={(e) => setForm({ ...form, is_vat_payer: e.target.value === 'true' })} />
            </FormField>
            <FormField label="მიწოდების თარიღი">
              <input type="date" value={form.delivery_date || ''} onChange={(e) => setForm({ ...form, delivery_date: e.target.value })} className="input" />
            </FormField>
            <FormField label="მიწოდების მისამართი">
              <input type="text" value={form.delivery_address || ''} onChange={(e) => setForm({ ...form, delivery_address: e.target.value })} className="input" />
            </FormField>
          </div>

          {clientPanelOpen && (
            <div className="rounded-xl border border-primary-200 bg-primary-50/60 p-4 dark:border-primary-900/50 dark:bg-primary-900/20">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <h3 className="flex items-center gap-2 font-semibold text-primary-900 dark:text-primary-200"><UserPlus size={18} /> ახალი კლიენტის სწრაფი დამატება</h3>
                  <p className="mt-1 text-sm text-primary-700 dark:text-primary-300">შენახვის შემდეგ კლიენტი ავტომატურად აირჩევა ამ შეკვეთაში.</p>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <FormField label="სახელი / კომპანიის დასახელება" required>
                  <input className="input" value={clientForm.name} onChange={e => setClientForm({ ...clientForm, name: e.target.value })} placeholder="მაგ. შპს ახალი კომპანია" />
                </FormField>
                <FormField label="საიდენტიფიკაციო კოდი" required>
                  <input className="input" value={clientForm.identification_code} onChange={e => setClientForm({ ...clientForm, identification_code: e.target.value })} />
                </FormField>
                <FormField label="ტიპი">
                  <Select options={[{ value: 'legal', label: 'იურიდიული პირი' }, { value: 'individual', label: 'ფიზიკური პირი' }]} value={clientForm.client_type} onChange={e => setClientForm({ ...clientForm, client_type: e.target.value as ClientCreate['client_type'] })} />
                </FormField>
                <FormField label="დღგ-ს გადამხდელი">
                  <Select options={[{ value: 'true', label: 'კი' }, { value: 'false', label: 'არა' }]} value={String(clientForm.is_vat_payer)} onChange={e => setClientForm({ ...clientForm, is_vat_payer: e.target.value === 'true' })} />
                </FormField>
                <FormField label="ტელეფონი">
                  <input type="tel" className="input" value={clientForm.phone || ''} onChange={e => setClientForm({ ...clientForm, phone: e.target.value })} placeholder="+995 5XX XXX XXX" />
                </FormField>
                <FormField label="ელფოსტა">
                  <input type="email" className="input" value={clientForm.email || ''} onChange={e => setClientForm({ ...clientForm, email: e.target.value })} placeholder="info@company.ge" />
                </FormField>
                <div className="md:col-span-2">
                  <FormField label="მისამართი">
                    <input className="input" value={clientForm.address || ''} onChange={e => setClientForm({ ...clientForm, address: e.target.value })} />
                  </FormField>
                </div>
              </div>
              {clientError && <div className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">{clientError}</div>}
              <div className="mt-4 flex justify-end gap-2">
                <button type="button" className="btn-secondary" onClick={() => { setClientPanelOpen(false); setClientError('') }}>გაუქმება</button>
                <button
                  type="button"
                  className="btn-primary flex items-center gap-2"
                  disabled={createClientMutation.isPending || clientForm.name.trim().length < 2 || !clientForm.identification_code.trim()}
                  onClick={() => createClientMutation.mutate(clientForm)}
                >
                  <UserPlus size={16} /> {createClientMutation.isPending ? 'ემატება...' : 'დამატება და არჩევა'}
                </button>
              </div>
            </div>
          )}

          {/* Order Items */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-400">პროდუქტები</label>
              <button type="button" onClick={addItem} className="text-sm text-primary-600 hover:underline">+ დამატება</button>
            </div>
            <div className="space-y-2">
              {form.items.map((item, idx) => (
                <div key={idx} className="flex gap-2 items-start p-3 bg-gray-50 dark:bg-dark-100 rounded-lg">
                  <div className="flex-1">
                    <Select
                      value={item.product_id || ''}
                      onChange={(e) => updateItem(idx, 'product_id', e.target.value)}
                      placeholder="აირჩიეთ პროდუქტი"
                      options={products.map((p: any) => ({ value: p.id, label: `${p.name} (${p.sku})` }))}
                    />
                  </div>
                  <div className="w-24">
                    <input type="text" placeholder="სახელი" value={item.product_name} onChange={(e) => updateItem(idx, 'product_name', e.target.value)} className="input text-sm" required />
                  </div>
                  <div className="w-20">
                    <input type="number" value={item.quantity} onChange={(e) => updateItem(idx, 'quantity', Number(e.target.value))} className="input text-sm" min={1} step="0.01" required />
                  </div>
                  <div className="w-24">
                    <input type="number" value={item.unit_price || ''} onChange={(e) => updateItem(idx, 'unit_price', Number(e.target.value))} className="input text-sm" min={0} step="0.01" required />
                  </div>
                  <div className="w-20">
                    <input type="number" value={item.discount_percent} onChange={(e) => updateItem(idx, 'discount_percent', Number(e.target.value))} className="input text-sm" min={0} max={100} />
                  </div>
                  <div className="w-16 pt-2 text-sm font-medium text-right">
                    {(item.quantity * item.unit_price * (1 - (item.discount_percent || 0) / 100)).toFixed(2)}
                  </div>
                  {form.items.length > 1 && (
                    <button type="button" onClick={() => removeItem(idx)} className="p-1.5 mt-1 hover:bg-red-100 rounded text-red-500">
                      <X size={16} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <FormField label="შენიშვნა">
            <textarea value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" rows={2} />
          </FormField>

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-dark-50">
            <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">გაუქმება</button>
            <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'იქმნება...' : 'შეკვეთის შექმნა'}
            </button>
          </div>
        </form>
      </Modal>

      {/* View Order Modal */}
      <Modal open={!!viewOrderId} onClose={() => setViewOrderId(null)} title="შეკვეთის დეტალები" size="xl">
        {isOrderDetailLoading && <div className="py-10 text-center text-gray-500 dark:text-gray-400 dark:text-gray-500">იტვირთება...</div>}
        {viewOrder && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 dark:text-gray-200 font-mono">{viewOrder.order_number}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500">{viewOrder.client_name} • {new Date(viewOrder.created_at).toLocaleDateString('ka-GE')}</p>
              </div>
              <StatusBadge status={viewOrder.status} map={orderStatusMap} />
            </div>

            {viewOrder.status !== 'cancelled' && viewOrder.status !== 'returned' ? (
              <div className="flex items-center gap-2 overflow-x-auto rounded-lg bg-gray-50 dark:bg-dark-100 p-3">
                {lifecycleStages.map((stage, index) => {
                  const currentIndex = lifecycleStages.findIndex(item => item.status === viewOrder.status)
                  const reached = index <= currentIndex
                  return (
                    <div key={stage.status} className="flex min-w-fit items-center gap-2">
                      <span className={`rounded-full px-3 py-1 text-xs font-medium ${reached ? 'bg-primary-600 text-white' : 'bg-white dark:bg-dark-200 text-gray-400 dark:text-gray-500'}`}>{stage.label}</span>
                      {index < lifecycleStages.length - 1 && <ArrowRight size={14} className="text-gray-300 dark:text-gray-400" />}
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
                შეკვეთა {viewOrder.status === 'cancelled' ? 'გაუქმებულია' : 'სრულად დაბრუნებულია'}.
              </div>
            )}

            {(viewOrder.warehouse_name || viewOrder.reservation_status) && (
              <div className="flex flex-wrap gap-3 rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm">
                {viewOrder.warehouse_name && <span><strong>საწყობი:</strong> {viewOrder.warehouse_name}</span>}
                {viewOrder.reservation_status && <span><strong>მარაგი:</strong> {reservationLabels[viewOrder.reservation_status]}</span>}
              </div>
            )}

            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-dark-100 border-y border-gray-200 dark:border-dark-50">
                <tr><th className="text-left px-4 py-2 font-medium text-gray-500 dark:text-gray-400 dark:text-gray-500">პროდუქტი</th><th className="text-right px-4 py-2 font-medium text-gray-500 dark:text-gray-400 dark:text-gray-500">რაოდ.</th><th className="text-right px-4 py-2 font-medium text-gray-500 dark:text-gray-400 dark:text-gray-500">ფასი</th><th className="text-right px-4 py-2 font-medium text-gray-500 dark:text-gray-400 dark:text-gray-500">ფასდ.</th><th className="text-right px-4 py-2 font-medium text-gray-500 dark:text-gray-400 dark:text-gray-500">ჯამი</th></tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-dark-50">
                {viewOrder.items.map((item, i) => (
                  <tr key={i}>
                    <td className="px-4 py-2">{item.product_name}</td>
                    <td className="px-4 py-2 text-right">{item.quantity}</td>
                    <td className="px-4 py-2 text-right">{item.unit_price?.toFixed(2)} ₾</td>
                    <td className="px-4 py-2 text-right">{item.discount_percent || 0}%</td>
                    <td className="px-4 py-2 text-right font-medium">{item.total?.toFixed(2)} ₾</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-gray-200 dark:border-dark-50">
                <tr><td colSpan={4} className="px-4 py-2 text-right text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500">ქვე-ჯამი</td><td className="px-4 py-2 text-right font-medium">{viewOrder.subtotal?.toFixed(2)} ₾</td></tr>
                <tr><td colSpan={4} className="px-4 py-2 text-right text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500">დღგ</td><td className="px-4 py-2 text-right font-medium">{viewOrder.vat_amount?.toFixed(2)} ₾</td></tr>
                <tr><td colSpan={4} className="px-4 py-2 text-right text-sm font-bold">სულ</td><td className="px-4 py-2 text-right font-bold text-lg">{viewOrder.total?.toFixed(2)} ₾</td></tr>
              </tfoot>
            </table>

            {viewOrder.delivery_address && (
              <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg text-sm"><span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">მიწოდება:</span> {viewOrder.delivery_address}</div>
            )}
            {viewOrder.notes && (
              <div className="p-3 bg-gray-50 dark:bg-dark-100 rounded-lg text-sm"><span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">შენიშვნა:</span> {viewOrder.notes}</div>
            )}

            {reservations.length > 0 && (
              <div className="rounded-lg border border-gray-200 dark:border-dark-50 p-4">
                <h4 className="mb-3 flex items-center gap-2 font-semibold text-gray-900 dark:text-gray-100 dark:text-gray-200"><PackageCheck size={17} /> მარაგის reservation</h4>
                <div className="space-y-2">
                  {reservations.map(reservation => (
                    <div key={reservation.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                      <span>{reservation.product_name} — {reservation.quantity} ერთ.</span>
                      <span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">{reservation.warehouse_name} • {reservationLabels[reservation.status]}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {orderHistory.length > 0 && (
              <div className="rounded-lg border border-gray-200 dark:border-dark-50 p-4">
                <h4 className="mb-3 font-semibold text-gray-900 dark:text-gray-100 dark:text-gray-200">ცვლილებების ისტორია</h4>
                <div className="space-y-3">
                  {orderHistory.map(entry => (
                    <div key={entry.id} className="flex gap-3 text-sm">
                      <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary-500" />
                      <div>
                        <StatusBadge status={entry.status} map={orderStatusMap} />
                        <span className="ml-2 text-gray-400 dark:text-gray-500">{new Date(entry.created_at).toLocaleString('ka-GE')}</span>
                        {entry.notes && <p className="mt-1 text-gray-600 dark:text-gray-400 dark:text-gray-500">{entry.notes}</p>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {actionError && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{actionError}</div>}

            <div className="flex flex-wrap justify-end gap-3 pt-4 border-t border-gray-200 dark:border-dark-50">
              {(nextStatusActions[viewOrder.status] || []).map(action => (
                <button
                  key={action.status}
                  onClick={() => changeStatus(action.status, action.danger)}
                  disabled={statusMutation.isPending}
                  className={action.danger ? 'btn-secondary border-red-200 text-red-600 hover:bg-red-50' : 'btn-secondary text-sm'}
                >
                  {action.label}
                </button>
              ))}
              {!['cancelled', 'returned'].includes(viewOrder.status) && (
                <button
                  onClick={() => {
                    setViewOrderId(null)
                    navigate(`/invoices?search=${encodeURIComponent(viewOrder.order_number)}`)
                  }}
                  className="btn-primary flex items-center gap-2 text-sm"
                >
                  <FileText size={16} /> ინვოისის გახსნა
                </button>
              )}
            </div>
          </div>
        )}
      </Modal>


    </div>
  )
}