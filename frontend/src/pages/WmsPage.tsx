import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, ArrowRightLeft, PackagePlus, Trash2, ScanBarcode, ClipboardList, Boxes, Truck, History, Camera, Sparkles } from 'lucide-react'
import { useRef } from 'react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import Wms2Tab from '../components/wms/Wms2Tab'
import { productsApi, warehousesApi, wmsApi, wmsOpsApi } from '../services/api'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

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
  const [tab, setTab] = useState<'batches' | 'serials' | 'picking' | 'replenishment' | 'landed' | 'zones' | 'counts' | 'wms2'>('batches')
  const [open, setOpen] = useState(false)
  const [serialOpen, setSerialOpen] = useState(false)
  const [pickOpen, setPickOpen] = useState(false)
  const [replenishOpen, setReplenishOpen] = useState(false)
  const [landedOpen, setLandedOpen] = useState(false)
  const [traceFor, setTraceFor] = useState<Batch | null>(null)
  const [transferFor, setTransferFor] = useState<Batch | null>(null)
  const [allocOpen, setAllocOpen] = useState(false)
  const [barcode, setBarcode] = useState('')
  const [barcodeResult, setBarcodeResult] = useState<any | null>(null)
  const [cameraOpen, setCameraOpen] = useState(false)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const openCamera = async () => {
    setCameraOpen(true)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
    } catch {
      setCameraOpen(false)
    }
  }

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }
  const [allocForm, setAllocForm] = useState({ product_id: '', strategy: 'fefo', quantity: '' })
  const [allocResult, setAllocResult] = useState<any[] | null>(null)
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
    queryFn: () => productsApi.list({ page_size: 100 }).then(r => r.data.data.items),
  })

  const { data: warehouses } = useQuery({
    queryKey: ['warehouses-all-wms'],
    queryFn: () => warehousesApi.list().then(r => r.data.data),
  })

  const searchBarcode = useMutation({
    mutationFn: (code: string) => productsApi.list({ barcode: code, page_size: 1 }).then(r => r.data.data.items[0] || null),
    onSuccess: (res) => setBarcodeResult(res),
  })
  const barcodeBatches = useMemo(() => {
    if (!barcodeResult) return []
    return batches.filter((b: any) => b.product_id === barcodeResult.id)
  }, [barcodeResult, batches])

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

  // ── WMS operations: picking, replenishment, landed cost, trace ──
  const { data: pickListsData, isLoading: pickLoading } = useQuery({
    queryKey: ['wms-pick-lists'],
    queryFn: () => wmsOpsApi.listPickLists({ limit: 200 }).then(r => r.data.data),
  })
  const pickLists: any[] = pickListsData || []

  const { data: replenishData, isLoading: replenishLoading } = useQuery({
    queryKey: ['wms-replenish'],
    queryFn: () => wmsOpsApi.listReplenishmentRules().then(r => r.data.data),
  })
  const replenishRules: any[] = replenishData || []

  const { data: suggestionsData } = useQuery({
    queryKey: ['wms-suggestions'],
    queryFn: () => wmsOpsApi.replenishmentSuggestions().then(r => r.data.data),
  })
  const suggestions: any[] = suggestionsData || []

  const { data: landedData, isLoading: landedLoading } = useQuery({
    queryKey: ['wms-landed'],
    queryFn: () => wmsOpsApi.listLandedCosts().then(r => r.data.data),
  })
  const landedCosts: any[] = landedData || []

  const { data: traceData, isLoading: traceLoading } = useQuery({
    queryKey: ['wms-trace', traceFor?.id],
    queryFn: () => traceFor ? wmsOpsApi.batchTrace(traceFor.id).then(r => r.data.data) : Promise.resolve([]),
    enabled: !!traceFor,
  })
  const traceEvents: any[] = traceData || []

  const [pickForm, setPickForm] = useState({ warehouse_id: '', product_id: '', batch_id: '', quantity: '' })
  const [replenishForm, setReplenishForm] = useState({ warehouse_id: '', product_id: '', min_quantity: '', max_quantity: '', reorder_quantity: '' })
  const [landedForm, setLandedForm] = useState({ description: '', total_amount: '', currency: 'GEL' })

  const createPickList = useMutation({
    mutationFn: () => wmsOpsApi.createPickList({
      warehouse_id: pickForm.warehouse_id,
      items: [{ product_id: pickForm.product_id, batch_id: pickForm.batch_id || null, quantity: Number(pickForm.quantity) }],
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wms-pick-lists'] }); setPickOpen(false); setPickForm({ warehouse_id: '', product_id: '', batch_id: '', quantity: '' }) },
  })

  const pickItem = useMutation({
    mutationFn: ({ pickListId, itemId, qty }: { pickListId: string; itemId: string; qty: number }) =>
      wmsOpsApi.pickItem(pickListId, { item_id: itemId, quantity: qty }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wms-pick-lists'] }); qc.invalidateQueries({ queryKey: ['wms-batches'] }) },
  })

  const completePick = useMutation({
    mutationFn: (id: string) => wmsOpsApi.completePickList(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['wms-pick-lists'] }),
  })

  const createReplenish = useMutation({
    mutationFn: () => wmsOpsApi.createReplenishmentRule({
      warehouse_id: replenishForm.warehouse_id, product_id: replenishForm.product_id,
      min_quantity: Number(replenishForm.min_quantity), max_quantity: Number(replenishForm.max_quantity),
      reorder_quantity: replenishForm.reorder_quantity ? Number(replenishForm.reorder_quantity) : null,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wms-replenish'] }); qc.invalidateQueries({ queryKey: ['wms-suggestions'] }); setReplenishOpen(false); setReplenishForm({ warehouse_id: '', product_id: '', min_quantity: '', max_quantity: '', reorder_quantity: '' }) },
  })

  const createLanded = useMutation({
    mutationFn: () => wmsOpsApi.createLandedCost({
      description: landedForm.description, total_amount: Number(landedForm.total_amount), currency: landedForm.currency,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wms-landed'] }); setLandedOpen(false); setLandedForm({ description: '', total_amount: '', currency: 'GEL' }) },
  })

  const allocateLanded = useMutation({
    mutationFn: ({ id, batchId, amount }: { id: string; batchId: string; amount: number }) =>
      wmsOpsApi.allocateLandedCost(id, { allocations: [{ batch_id: batchId, amount }] }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wms-landed'] }); qc.invalidateQueries({ queryKey: ['wms-batches'] }) },
  })

  const runAllocation = useMutation({
    mutationFn: () => wmsOpsApi.allocationSuggestion(allocForm.product_id, allocForm.strategy as 'fifo' | 'fefo', Number(allocForm.quantity)).then(r => r.data.data),
    onSuccess: (d) => setAllocResult(d),
  })

  // ── Zones (locations/bins) and cycle counts ──
  const { data: zonesData, isLoading: zonesLoading } = useQuery({
    queryKey: ['wms-zones'],
    queryFn: () => warehousesApi.listZones({ include_inactive: true }).then(r => r.data.data),
  })
  const zones: any[] = zonesData || []

  const { data: countsData, isLoading: countsLoading } = useQuery({
    queryKey: ['wms-counts'],
    queryFn: () => warehousesApi.listCounts({ limit: 100 }).then(r => r.data.data),
  })
  const counts: any[] = countsData || []

  const [zoneForm, setZoneForm] = useState({ warehouse_id: '', code: '', name: '', zone_type: 'bin' })
  const [countForm, setCountForm] = useState({ warehouse_id: '', count_type: 'cycle', notes: '' })

  const createZone = useMutation({
    mutationFn: () => warehousesApi.createZone({
      warehouse_id: zoneForm.warehouse_id, code: zoneForm.code, name: zoneForm.name, zone_type: zoneForm.zone_type,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wms-zones'] }); setZoneForm({ warehouse_id: '', code: '', name: '', zone_type: 'bin' }) },
  })

  const createCount = useMutation({
    mutationFn: () => warehousesApi.createCount({
      warehouse_id: countForm.warehouse_id, count_type: countForm.count_type, notes: countForm.notes || null,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['wms-counts'] }); setCountForm({ warehouse_id: '', count_type: 'cycle', notes: '' }) },
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
      ? <span className={`font-mono text-sm ${new Date(b.expiry_date) < new Date() ? 'text-red-600 dark:text-red-400' : ''}`}>{fmtDate(new Date(b.expiry_date))}</span> : '—' },
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
        <button onClick={() => setTraceFor(b)}
          className="p-1.5 rounded-md text-gray-400 hover:text-indigo-700 hover:bg-indigo-50 dark:hover:bg-indigo-900/30" title={t('ისტორია')}>
          <History size={15} />
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
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setTab('batches')}
            className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'batches' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            {t('პარტიები')}
          </button>
          <button onClick={() => setTab('serials')}
            className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'serials' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            {t('სერიული ნომრები')}
          </button>
          <button onClick={() => setTab('picking')}
            className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'picking' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            <ClipboardList size={14} className="inline mr-1" /> {t('პიკინგი')}
          </button>
          <button onClick={() => setTab('replenishment')}
            className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'replenishment' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            <Boxes size={14} className="inline mr-1" /> {t('შევსება')}
          </button>
          <button onClick={() => setTab('landed')}
            className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'landed' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            <Truck size={14} className="inline mr-1" /> {t('ლენდედ ქოსთი')}
          </button>
          <button onClick={() => setTab('zones')}
            className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'zones' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            {t('ლოკაციები')}
          </button>
          <button onClick={() => setTab('counts')}
            className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'counts' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            {t('ინვენტარიზაცია')}
          </button>
          <button onClick={() => setTab('wms2')}
            className={`px-3 py-2 rounded-lg text-sm font-medium ${tab === 'wms2' ? 'bg-brandgray-800 text-white dark:bg-gray-100 dark:text-gray-900' : 'bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400'}`}>
            <Sparkles size={14} className="inline mr-1" /> {t('WMS 2.0')}
          </button>
          <button onClick={() => {
            if (tab === 'batches') setOpen(true)
            else if (tab === 'serials') setSerialOpen(true)
            else if (tab === 'picking') setPickOpen(true)
            else if (tab === 'replenishment') setReplenishOpen(true)
            else if (tab === 'landed') setLandedOpen(true)
            else if (tab === 'zones') setZoneForm({ warehouse_id: '', code: '', name: '', zone_type: 'bin' })
            else setCountForm({ warehouse_id: '', count_type: 'cycle', notes: '' })
          }}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700">
            <Plus size={15} /> {tab === 'batches' ? t('ახალი პარტია') : tab === 'serials' ? t('ახალი სერიული ნომერი') : tab === 'picking' ? t('ახალი პიკინგი') : tab === 'replenishment' ? t('ახალი წესი') : tab === 'landed' ? t('ახალი ლენდედ ქოსთი') : tab === 'zones' ? t('ახალი ლოკაცია') : t('ახალი ინვენტარიზაცია')}
          </button>
          <button onClick={() => { setAllocResult(null); setAllocOpen(true) }}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-100 text-brandgray-700 hover:bg-brandgray-200 dark:bg-dark-100 dark:text-gray-300">
            <ScanBarcode size={15} /> {t('FIFO/FEFO')}
          </button>
        </div>
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-72">
            <ScanBarcode size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-brandgray-400" />
            <input
              value={barcode}
              onChange={(e) => setBarcode(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { setBarcodeResult(null); searchBarcode.mutate(barcode.trim()) } }}
              placeholder={t('Barcode-ის სკანირება / ძიება')}
              className="w-full pl-9 pr-3 py-2 rounded-lg border border-brandgray-200 dark:border-dark-50 bg-white dark:bg-dark-100 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/40"
            />
          </div>
          <button onClick={() => { setBarcodeResult(null); searchBarcode.mutate(barcode.trim()) }}
            className="px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-100 text-brandgray-700 hover:bg-brandgray-200 dark:bg-dark-100 dark:text-gray-300">
            {t('ძიება')}
          </button>
          <button onClick={openCamera}
            className="px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700 flex items-center gap-1.5"
            title={t('კამერით სკანირება')}>
            <Camera size={15} />
          </button>
        </div>
      </div>

      {/* Camera barcode scanner */}
      <Modal open={cameraOpen} onClose={() => { setCameraOpen(false); stopCamera() }} title={t('კამერით სკანირება')}>
        <div className="space-y-4">
          <video ref={videoRef} className="w-full rounded-lg border border-gray-200 dark:border-dark-50 bg-black" playsInline muted />
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('მიიტანეთ შტრიხკოდი კამერასთან — ავტომატურად დაფიქსირდება')}</p>
          <div className="flex gap-2">
            <button onClick={() => { setCameraOpen(false); stopCamera() }} className="flex-1 rounded-lg border border-gray-200 dark:border-dark-50 py-2 text-sm font-medium">
              {t('დახურვა')}
            </button>
          </div>
        </div>
      </Modal>

      {barcodeResult && (
        <div className="rounded-lg border border-primary-200 dark:border-primary-900/40 bg-primary-50/50 dark:bg-primary-900/10 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold text-gray-900 dark:text-gray-100">{barcodeResult.name}</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-primary-100 text-primary-700 dark:bg-primary-900/40 dark:text-primary-300">{barcodeResult.barcode || '—'}</span>
          </div>
          <div className="text-sm text-brandgray-600 dark:text-gray-400">
            {t('მარაგი')}: <span className="font-mono font-semibold">{barcodeResult.stock_quantity ?? '—'}</span>
            {barcodeResult.sku && <span className="ml-3">SKU: <span className="font-mono">{barcodeResult.sku}</span></span>}
          </div>
          {barcodeBatches.length > 0 && (
            <div className="mt-3">
              <div className="text-xs font-medium uppercase tracking-wide text-brandgray-500 dark:text-gray-500 mb-2">{t('პარტიები')}</div>
              <div className="space-y-1.5">
                {barcodeBatches.map((b: any) => (
                  <div key={b.id} className="flex items-center justify-between text-sm rounded-md bg-white dark:bg-dark-100 px-3 py-2">
                    <span className="font-mono font-semibold text-gray-900 dark:text-gray-100">{b.batch_number}</span>
                    <span className="text-brandgray-500 dark:text-gray-400">{b.quantity} {t('ცალი')}</span>
                    <span className="text-xs text-brandgray-500 dark:text-gray-400">{b.expiry_date ? fmtDate(new Date(b.expiry_date)) : '—'}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'batches' && (
        <DataTable columns={batchColumns} data={batches} isLoading={batchesLoading} emptyMessage={t('პარტიები არ არის')} />
      )}
      {tab === 'serials' && (
        <DataTable columns={serialColumns} data={serials} isLoading={serialsLoading} emptyMessage={t('სერიული ნომრები არ არის')} />
      )}
      {tab === 'picking' && (
        <div className="space-y-4">
          {pickLists.length === 0 && !pickLoading ? (
            <div className="rounded-lg border border-dashed border-brandgray-200 dark:border-dark-50 p-8 text-center text-sm text-brandgray-500 dark:text-gray-400">
              {t('პიკინგის სიები არ არის')}
            </div>
          ) : (
            pickLists.map((pl: any) => (
              <div key={pl.id} className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="font-semibold text-gray-900 dark:text-gray-100">{pl.pick_number}</span>
                    <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400">{pl.status}</span>
                  </div>
                  <div className="flex gap-2">
                    {pl.status === 'draft' && (
                      <button onClick={() => completePick.mutate(pl.id)}
                        className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 text-white hover:bg-emerald-700">
                        {t('დასრულება')}
                      </button>
                    )}
                    {pl.status === 'picked' && (
                      <button onClick={() => wmsOpsApi.createPackingSlip({ pick_list_id: pl.id }).then(() => qc.invalidateQueries({ queryKey: ['wms-pick-lists'] }))}
                        className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-primary-600 text-white hover:bg-primary-700">
                        {t('შეფუთვა')}
                      </button>
                    )}
                  </div>
                </div>
                <div className="space-y-2">
                  {pl.items.map((it: any) => (
                    <div key={it.id} className="flex items-center justify-between rounded-lg bg-brandgray-50 dark:bg-dark-100 px-3 py-2 text-sm">
                      <span className="font-medium">{productName(it.product_id)}</span>
                      <span className="text-brandgray-500 dark:text-gray-400">{it.picked_quantity} / {it.quantity}</span>
                      {pl.status === 'draft' && it.status !== 'picked' && (
                        <button onClick={() => { const q = prompt(t('რაოდენობა')); if (q && Number(q) > 0) pickItem.mutate({ pickListId: pl.id, itemId: it.id, qty: Number(q) }) }}
                          className="px-2 py-1 rounded-md text-xs font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
                          {t('პიკინგი')}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      )}
      {tab === 'replenishment' && (
        <div className="space-y-4">
          {suggestions.length > 0 && (
            <div className="rounded-lg border border-amber-200 dark:border-amber-900/40 bg-amber-50 dark:bg-amber-900/10 p-4">
              <h3 className="text-sm font-semibold text-amber-800 dark:text-amber-300 mb-2">{t('შევსების რეკომენდაციები')}</h3>
              <div className="space-y-1.5">
                {suggestions.map((s: any, i: number) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="font-medium">{productName(s.product_id)}</span>
                    <span className="text-amber-700 dark:text-amber-300">{t('მარაგშია')}: {s.on_hand} → {t('რეკომენდებულია')}: {s.suggested_quantity}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <DataTable
            columns={[
              { key: 'product_id', label: t('პროდუქტი'), priority: true, render: (r: any) => <span className="font-semibold text-gray-900 dark:text-gray-100">{productName(r.product_id)}</span> },
              { key: 'warehouse_id', label: t('საწყობი'), render: (r: any) => <span className="text-sm">{warehouseName(r.warehouse_id)}</span> },
              { key: 'min_quantity', label: t('მინიმუმი'), render: (r: any) => <span className="font-mono">{r.min_quantity}</span> },
              { key: 'max_quantity', label: t('მაქსიმუმი'), render: (r: any) => <span className="font-mono">{r.max_quantity}</span> },
              { key: 'reorder_quantity', label: t('შევსების რაოდენობა'), render: (r: any) => <span className="font-mono">{r.reorder_quantity ?? '—'}</span> },
            ]}
            data={replenishRules} isLoading={replenishLoading} emptyMessage={t('შევსების წესები არ არის')} />
        </div>
      )}
      {tab === 'landed' && (
        <DataTable
          columns={[
            { key: 'description', label: t('აღწერა'), priority: true, render: (l: any) => <span className="font-semibold text-gray-900 dark:text-gray-100">{l.description}</span> },
            { key: 'total_amount', label: t('თანხა'), render: (l: any) => <span className="font-mono font-semibold">{l.total_amount} {l.currency}</span> },
            { key: 'allocated', label: t('სტატუსი'), render: (l: any) => l.allocated
              ? <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">{t('განაწილებულია')}</span>
              : <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">{t('განაწილებული არ არის')}</span> },
            { key: 'actions', label: '', render: (l: any) => !l.allocated && (
              <button onClick={() => { const b = prompt(t('პარტიის ID')); const a = prompt(t('თანხა')); if (b && a && Number(a) > 0) allocateLanded.mutate({ id: l.id, batchId: b, amount: Number(a) }) }}
                className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-primary-600 text-white hover:bg-primary-700">
                {t('განაწილება')}
              </button>
            ) },
          ]}
          data={landedCosts} isLoading={landedLoading} emptyMessage={t('ლენდედ ქოსთები არ არის')} />
      )}
      {tab === 'zones' && (
        <DataTable
          columns={[
            { key: 'code', label: t('კოდი'), priority: true, render: (z: any) => <span className="font-semibold text-gray-900 dark:text-gray-100 font-mono">{z.code}</span> },
            { key: 'name', label: t('სახელი'), render: (z: any) => <span className="text-sm">{z.name}</span> },
            { key: 'warehouse_id', label: t('საწყობი'), render: (z: any) => <span className="text-sm">{warehouseName(z.warehouse_id)}</span> },
            { key: 'zone_type', label: t('ტიპი'), render: (z: any) => <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400">{z.zone_type}</span> },
            { key: 'is_pickable', label: t('პიკაბელური'), render: (z: any) => z.is_pickable ? '✓' : '—' },
          ]}
          data={zones} isLoading={zonesLoading} emptyMessage={t('ლოკაციები არ არის')} />
      )}
      {tab === 'counts' && (
        <DataTable
          columns={[
            { key: 'count_number', label: t('ნომერი'), priority: true, render: (c: any) => <span className="font-semibold text-gray-900 dark:text-gray-100 font-mono">{c.count_number}</span> },
            { key: 'warehouse_id', label: t('საწყობი'), render: (c: any) => <span className="text-sm">{warehouseName(c.warehouse_id)}</span> },
            { key: 'count_type', label: t('ტიპი'), render: (c: any) => <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-brandgray-100 text-brandgray-600 dark:bg-dark-100 dark:text-gray-400">{c.count_type}</span> },
            { key: 'status', label: t('სტატუსი'), render: (c: any) => <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">{c.status}</span> },
            { key: 'created_at', label: t('თარიღი'), render: (c: any) => <span className="font-mono text-sm">{fmtDate(new Date(c.created_at))}</span> },
          ]}
          data={counts} isLoading={countsLoading} emptyMessage={t('ინვენტარიზაციები არ არის')} />
      )}

      {tab === 'wms2' && <Wms2Tab />}

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

      <Modal open={pickOpen} onClose={() => setPickOpen(false)} title={t('ახალი პიკინგი')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('საწყობი')}</label>
            <select className={inputCls} value={pickForm.warehouse_id} onChange={e => setForm2(pickForm, e, setPickForm, 'warehouse_id')}>
              <option value="">—</option>
              {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტი')}</label>
            <select className={inputCls} value={pickForm.product_id} onChange={e => setForm2(pickForm, e, setPickForm, 'product_id')}>
              <option value="">—</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პარტია (არასავალდებულო)')}</label>
            <select className={inputCls} value={pickForm.batch_id} onChange={e => setForm2(pickForm, e, setPickForm, 'batch_id')}>
              <option value="">—</option>
              {batches.filter(b => !pickForm.product_id || b.product_id === pickForm.product_id).map(b => (
                <option key={b.id} value={b.id}>{b.batch_number}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('რაოდენობა')}</label>
            <input type="number" step="0.001" className={inputCls} value={pickForm.quantity} onChange={e => setForm2(pickForm, e, setPickForm, 'quantity')} />
          </div>
          <button onClick={() => createPickList.mutate()} disabled={createPickList.isPending || !pickForm.warehouse_id || !pickForm.product_id || !pickForm.quantity}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={replenishOpen} onClose={() => setReplenishOpen(false)} title={t('ახალი შევსების წესი')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('საწყობი')}</label>
            <select className={inputCls} value={replenishForm.warehouse_id} onChange={e => setForm2(replenishForm, e, setReplenishForm, 'warehouse_id')}>
              <option value="">—</option>
              {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტი')}</label>
            <select className={inputCls} value={replenishForm.product_id} onChange={e => setForm2(replenishForm, e, setReplenishForm, 'product_id')}>
              <option value="">—</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მინიმუმი')}</label>
              <input type="number" step="0.001" className={inputCls} value={replenishForm.min_quantity} onChange={e => setForm2(replenishForm, e, setReplenishForm, 'min_quantity')} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('მაქსიმუმი')}</label>
              <input type="number" step="0.001" className={inputCls} value={replenishForm.max_quantity} onChange={e => setForm2(replenishForm, e, setReplenishForm, 'max_quantity')} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('შევსების რაოდენობა')}</label>
              <input type="number" step="0.001" className={inputCls} value={replenishForm.reorder_quantity} onChange={e => setForm2(replenishForm, e, setReplenishForm, 'reorder_quantity')} />
            </div>
          </div>
          <button onClick={() => createReplenish.mutate()} disabled={createReplenish.isPending || !replenishForm.warehouse_id || !replenishForm.product_id}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={landedOpen} onClose={() => setLandedOpen(false)} title={t('ახალი ლენდედ ქოსთი')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('აღწერა')}</label>
            <input className={inputCls} value={landedForm.description} onChange={e => setForm2(landedForm, e, setLandedForm, 'description')} placeholder={t('ტრანსპორტირება, საბაჟო, დაზღვევა')} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('თანხა')}</label>
              <input type="number" step="0.01" className={inputCls} value={landedForm.total_amount} onChange={e => setForm2(landedForm, e, setLandedForm, 'total_amount')} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ვალუტა')}</label>
              <select className={inputCls} value={landedForm.currency} onChange={e => setForm2(landedForm, e, setLandedForm, 'currency')}>
                <option value="GEL">GEL</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </select>
            </div>
          </div>
          <button onClick={() => createLanded.mutate()} disabled={createLanded.isPending || !landedForm.description || !landedForm.total_amount}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      <Modal open={!!traceFor} onClose={() => setTraceFor(null)} title={`${t('ისტორია')} — ${traceFor?.batch_number || ''}`}>
        {traceFor && (
          <div className="space-y-3">
            {traceLoading ? (
              <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('იტვირთება...')}</p>
            ) : traceEvents.length === 0 ? (
              <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('ისტორია არ არის')}</p>
            ) : (
              traceEvents.map((ev: any, i: number) => (
                <div key={i} className="flex items-start gap-3 rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">{ev.event_type}</span>
                  <div className="flex-1">
                    <div className="text-brandgray-600 dark:text-gray-300">
                      {ev.quantity != null && <span className="font-mono mr-2">{ev.quantity}</span>}
                      {ev.reference && <span className="text-brandgray-400 dark:text-gray-500">{ev.reference}</span>}
                    </div>
                    <div className="text-xs text-brandgray-400 dark:text-gray-500">{fmtDateTime(new Date(ev.created_at))}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </Modal>

      <Modal open={allocOpen} onClose={() => setAllocOpen(false)} title={t('FIFO/FEFO განაწილება')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტი')}</label>
            <select className={inputCls} value={allocForm.product_id} onChange={e => setForm2(allocForm, e, setAllocForm, 'product_id')}>
              <option value="">—</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სტრატეგია')}</label>
              <select className={inputCls} value={allocForm.strategy} onChange={e => setForm2(allocForm, e, setAllocForm, 'strategy')}>
                <option value="fefo">FEFO ({t('ვადის მიხედვით')})</option>
                <option value="fifo">FIFO ({t('მიღების მიხედვით')})</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('რაოდენობა')}</label>
              <input type="number" step="0.001" className={inputCls} value={allocForm.quantity} onChange={e => setForm2(allocForm, e, setAllocForm, 'quantity')} />
            </div>
          </div>
          <button onClick={() => runAllocation.mutate()} disabled={runAllocation.isPending || !allocForm.product_id || !allocForm.quantity}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('გამოთვლა')}
          </button>
          {allocResult && (
            <div className="space-y-2">
              {allocResult.length === 0 ? (
                <p className="text-sm text-amber-600 dark:text-amber-400">{t('საკმარისი მარაგი არ არის')}</p>
              ) : (
                allocResult.map((a: any, i: number) => (
                  <div key={i} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                    <span className="font-medium">{a.batch_number}</span>
                    <span className="font-mono font-semibold">{a.quantity}</span>
                    {a.expiry_date && <span className="text-xs text-brandgray-400 dark:text-gray-500">{fmtDate(new Date(a.expiry_date))}</span>}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}

function setForm2<T>(form: T, e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>, setter: (v: T) => void, key: keyof T) {
  setter({ ...form, [key]: e.target.value })
}
