import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, ArrowRightLeft, PackagePlus, Trash2, ScanBarcode } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { productsApi, warehousesApi, wmsApi } from '../services/api'

interface Batch {
  id: string
  warehouse_id: string
  product_id: string
  batch_number: string
  production_date: string | null
  expiry_date: string | null
  quantity: number
  unit_cost: number | null
  notes: string | null
  created_at: string
}

interface Serial {
  id: string
  product_id: string
  batch_id: string | null
  serial_number: string
  status: string
  warehouse_id: string | null
  sold_at: string | null
  notes: string | null
  created_at: string
}

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function WmsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'batches' | 'serials'>('batches')
  const [open, setOpen] = useState(false)
  const [serialOpen, setSerialOpen] = useState(false)
  const [transferFor, setTransferFor] = useState<Batch | null>(null)
  const [form, setForm] = useState({
    warehouse_id: '', product_id: '', batch_number: '', production_date: '',
    expiry_date: '', quantity: '', unit_cost: '', notes: '',
  })
  const [serialForm, setSerialForm] = useState({
    product_id: '', batch_id: '', serial_number: '', warehouse_id: '', notes: '',
  })

  const { data: batchesData, isLoading: batchesLoading } = useQuery({
    queryKey: ['wms-batches'],
    queryFn: () => wmsApi.listBatches({ limit: 200 }).then(r => r.data.data),
  })
  const batches: Batch[] = batchesData || []

  const { data: serialsData, isLoading: serialsLoading } = useQuery({
    queryKey: ['wms-serials'],
    queryFn: () => wmsApi.listSerials({ limit: 200 }).then(r => r.data.data),
  })
  const serials: Serial[] = serialsData || []

  const { data: products } = useQuery({
    queryKey: ['products-all-wms'],
    queryFn: () => productsApi.list({ page_size: 200 }).then(r => r.data.data.items),
  })

  const { data: warehouses } = useQuery({
    queryKey: ['warehouses-all-wms'],
    queryFn: () => warehousesApi.list().then(r => r.data.data),
  })

  const productName = (id: string) => {
    const p = (products || []).find((x: any) => x.id === id)
    return p ? p.name : '—'
  }
  const warehouseName = (id: string | null) => {
    if (!id) return '—'
    const w = (warehouses || []).find((x: any) => x.id === id)
    return w ? w.name : '—'
  }

  const createBatch = useMutation({
    mutationFn: () => wmsApi.createBatch({
      warehouse_id: form.warehouse_id, product_id: form.product_id,
      batch_number: form.batch_number,
      production_date: form.production_date || null,
      expiry_date: form.expiry_date || null,
      quantity: Number(form.quantity), unit_cost: form.unit_cost ? Number(form.unit_cost) : null,
      notes: form.notes || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wms-batches'] })
      qc.invalidateQueries({ queryKey: ['inventory-balances'] })
      setOpen(false)
      setForm({ warehouse_id: '', product_id: '', batch_number: '', production_date: '', expiry_date: '', quantity: '', unit_cost: '', notes: '' })
    },
  })

  const receiveBatch = useMutation({
    mutationFn: ({ id, qty }: { id: string; qty: number }) => wmsApi.receiveBatch(id, qty),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wms-batches'] }); qc.invalidateQueries({ queryKey: ['inventory-balances'] }) },
  })

  const adjustBatch = useMutation({
    mutationFn: ({ id, delta, reason }: { id: string; delta: number; reason: string }) =>
      wmsApi.adjustBatch(id, { quantity_delta: delta, reason }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wms-batches'] }); qc.invalidateQueries({ queryKey: ['inventory-balances'] }) },
  })

  const transferBatch = useMutation({
    mutationFn: ({ id, dest }: { id: string; dest: string }) =>
      wmsApi.transferBatch(id, { destination_warehouse_id: dest, reason: 'batch_transfer' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wms-batches'] }); qc.invalidateQueries({ queryKey: ['wms-serials'] }); setTransferFor(null) },
  })

  const registerSerial = useMutation({
    mutationFn: () => wmsApi.registerSerial({
      product_id: serialForm.product_id, serial_number: serialForm.serial_number,
      batch_id: serialForm.batch_id || null, warehouse_id: serialForm.warehouse_id || null,
      notes: serialForm.notes || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wms-serials'] })
      setSerialOpen(false)
      setSerialForm({ product_id: '', batch_id: '', serial_number: '', warehouse_id: '', notes: '' })
    },
  })

  const updateSerialStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => wmsApi.updateSerialStatus(id, status),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wms-serials'] }); qc.invalidateQueries({ queryKey: ['wms-batches'] }) },
  })

  const statusBadge = (status: string) => {
    const map: Record<string, string> = {
      in_stock: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
      sold: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
      returned: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
      scrapped: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300',
    }
    const labels: Record<string, string> = {
      in_stock: t('მარაგშია'), sold: t('გაყიდულია'), returned: t('დაბრუნებულია'), scrapped: t('ჩამოწერილია'),
    }
    return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${map[status] || 'bg-gray-100 text-gray-500'}`}>{labels[status] || status}</span>
  }

  const batchColumns = [
    { key: 'batch_number', label: t('პარტია'), priority: true, render: (b: Batch) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100">{b.batch_number}</span>) },
    { key: 'product_id', label: t('პროდუქტი'), render: (b: Batch) => <span className="text-sm">{productName(b.product_id)}</span> },
    { key: 'warehouse_id', label: t('საწყობი'), render: (b: Batch) => <span className="text-sm">{warehouseName(b.warehouse_id)}</span> },
    { key: 'quantity', label: t('რაოდენობა'), render: (b: Batch) => <span className="font-mono font-semibold">{b.quantity}</span> },
    { key: 'expiry_date', label: t('ვადა'), render: (b: Batch) => b.expiry_date
      ? <span className={`font-mono text-sm ${new Date(b.expiry_date) < new Date() ? 'text-red-600 dark:text-red-400' : ''}`}>{new Date(b.expiry_date).toLocaleDateString('ka-GE')}</span> : '—' },
    { key: 'unit_cost', label: t('ღირებულება'), render: (b: Batch) => b.unit_cost ? <span className="font-mono text-sm">{b.unit_cost}</span> : '—' },
    { key: 'actions', label: '', render: (b: Batch) => (
      <div className="flex gap-1">
        <button onClick={() => { const q = prompt(t('რაოდენობა')); if (q && Number(q) > 0) receiveBatch.mutate({ id: b.id, qty: Number(q) }) }}
          className="p-1.5 rounded-md text-gray-400 hover:text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-900/30" title={t('მიღება')}>
          <PackagePlus size={15} />
        </button>
        <button onClick={() => { const d = prompt(t('ცვლილება (+/-)')); if (d && Number(d) !== 0) adjustBatch.mutate({ id: b.id, delta: Number(d), reason: 'manual_adjust' }) }}
          className="p-1.5 rounded-md text-gray-400 hover:text-amber-700 hover:bg-amber-50 dark:hover:bg-amber-900/30" title={t('კორექტირება')}>
          <ScanBarcode size={15} />
        </button>
        <button onClick={() => setTransferFor(b)}
          className="p-1.5 rounded-md text-gray-400 hover:text-primary-700 hover:bg-primary-50 dark:hover:bg-primary-900/30" title={t('გადატანა')}>
          <ArrowRightLeft size={15} />
        </button>
      </div>) },
  ]

  const serialColumns = [
    { key: 'serial_number', label: t('სერიული ნომერი'), priority: true, render: (s: Serial) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100 font-mono">{s.serial_number}</span>) },
    { key: 'product_id', label: t('პროდუქტი'), render: (s: Serial) => <span className="text-sm">{productName(s.product_id)}</span> },
    { key: 'batch_id', label: t('პარტია'), render: (s: Serial) => {
      const b = batches.find(x => x.id === s.batch_id)
      return <span className="text-sm">{b ? b.batch_number : '—'}</span>
    } },
    { key: 'warehouse_id', label: t('საწყობი'), render: (s: Serial) => <span className="text-sm">{warehouseName(s.warehouse_id)}</span> },
    { key: 'status', label: t('სტატუსი'), render: (s: Serial) => statusBadge(s.status) },
    { key: 'actions', label: '', render: (s: Serial) => (
      <div className="flex gap-1">
        {s.status === 'in_stock' && (
          <button onClick={() => updateSerialStatus.mutate({ id: s.id, status: 'sold' })}
            className="p-1.5 rounded-md text-gray-400 hover:text-blue-700 hover:bg-blue-50 dark:hover:bg-blue-900/30" title={t('გაყიდვა')}>
            <PackagePlus size={15} />
          </button>
        )}
        {s.status !== 'scrapped' && (
          <button onClick={() => updateSerialStatus.mutate({ id: s.id, status: 'scrapped' })}
            className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30" title={t('ჩამოწერა')}>
            <Trash2 size={15} />
          </button>
        )}
      </div>) },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('საწყობის მართვა (WMS)')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('პარტიები, სერიული ნომრები და ვადები')}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setTab('batches')}
            className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'batches' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            {t('პარტიები')}
          </button>
          <button onClick={() => setTab('serials')}
            className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'serials' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            {t('სერიული ნომრები')}
          </button>
          <button onClick={() => tab === 'batches' ? setOpen(true) : setSerialOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700">
            <Plus size={15} /> {tab === 'batches' ? t('ახალი პარტია') : t('ახალი სერიული ნომერი')}
          </button>
        </div>
      </div>

      {tab === 'batches' ? (
        <DataTable columns={batchColumns} data={batches} isLoading={batchesLoading} emptyMessage={t('პარტიები არ არის')} />
      ) : (
        <DataTable columns={serialColumns} data={serials} isLoading={serialsLoading} emptyMessage={t('სერიული ნომრები არ არის')} />
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი პარტია')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტი')}</label>
            <select className={inputCls} value={form.product_id} onChange={e => setForm({ ...form, product_id: e.target.value })}>
              <option value="">—</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('საწყობი')}</label>
            <select className={inputCls} value={form.warehouse_id} onChange={e => setForm({ ...form, warehouse_id: e.target.value })}>
              <option value="">—</option>
              {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პარტიის ნომერი')}</label>
            <input className={inputCls} value={form.batch_number} onChange={e => setForm({ ...form, batch_number: e.target.value })} placeholder="LOT-2026-001" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('წარმოების თარიღი')}</label>
              <input type="date" className={inputCls} value={form.production_date} onChange={e => setForm({ ...form, production_date: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ვადა')}</label>
              <input type="date" className={inputCls} value={form.expiry_date} onChange={e => setForm({ ...form, expiry_date: e.target.value })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('რაოდენობა')}</label>
              <input type="number" step="0.001" className={inputCls} value={form.quantity} onChange={e => setForm({ ...form, quantity: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ერთეულის ღირებულება')}</label>
              <input type="number" step="0.0001" className={inputCls} value={form.unit_cost} onChange={e => setForm({ ...form, unit_cost: e.target.value })} />
            </div>
          </div>
          <button onClick={() => createBatch.mutate()} disabled={createBatch.isPending || !form.product_id || !form.warehouse_id || !form.batch_number || !form.quantity}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={serialOpen} onClose={() => setSerialOpen(false)} title={t('ახალი სერიული ნომერი')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტი')}</label>
            <select className={inputCls} value={serialForm.product_id} onChange={e => setForm2(serialForm, e, setSerialForm, 'product_id')}>
              <option value="">—</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სერიული ნომერი')}</label>
            <input className={inputCls} value={serialForm.serial_number} onChange={e => setForm2(serialForm, e, setSerialForm, 'serial_number')} placeholder="SN-0001" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პარტია (არასავალდებულო)')}</label>
            <select className={inputCls} value={serialForm.batch_id} onChange={e => setForm2(serialForm, e, setSerialForm, 'batch_id')}>
              <option value="">—</option>
              {batches.filter(b => !serialForm.product_id || b.product_id === serialForm.product_id).map(b => (
                <option key={b.id} value={b.id}>{b.batch_number}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('საწყობი')}</label>
            <select className={inputCls} value={serialForm.warehouse_id} onChange={e => setForm2(serialForm, e, setSerialForm, 'warehouse_id')}>
              <option value="">—</option>
              {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </div>
          <button onClick={() => registerSerial.mutate()} disabled={registerSerial.isPending || !serialForm.product_id || !serialForm.serial_number}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={!!transferFor} onClose={() => setTransferFor(null)} title={t('პარტიის გადატანა')}>
        {transferFor && (
          <div className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              {t('პარტია')}: <span className="font-semibold">{transferFor.batch_number}</span> — {t('რაოდენობა')}: <span className="font-semibold">{transferFor.quantity}</span>
            </p>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დანიშნულების საწყობი')}</label>
              <select className={inputCls} defaultValue="" onChange={e => e.target.value && transferBatch.mutate({ id: transferFor.id, dest: e.target.value })}>
                <option value="">—</option>
                {(warehouses || []).filter((w: any) => w.id !== transferFor.warehouse_id).map((w: any) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </select>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

function setForm2<T>(form: T, e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>, setter: (v: T) => void, key: keyof T) {
  setter({ ...form, [key]: e.target.value })
}
