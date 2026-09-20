import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Truck,
  Package,
  Plus,
  Send,
  Play,
  CheckCircle2,
  XCircle,
  MapPin,
  Phone,
  User,
  Calendar,
  Route,
} from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import { fleetApi } from '../services/api'

interface DeliveryRequest {
  id: string
  request_number: string
  status: string
  dropoff_address: string
  pickup_address?: string | null
  contact_name?: string | null
  contact_phone?: string | null
  weight_kg?: string | null
  volume_m3?: string | null
  package_count?: number | null
  delivery_date?: string | null
  delivered_at?: string | null
  delivered_qty?: string | null
  exception?: string | null
}

interface Trip {
  id: string
  trip_number: string
  status: string
  vehicle_id?: string | null
  driver_id?: string | null
  planned_start?: string | null
  total_weight_kg: string
  total_volume_m3: string
}

const statusColor: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  planned: 'bg-blue-100 text-blue-700',
  dispatched: 'bg-yellow-100 text-yellow-700',
  in_progress: 'bg-indigo-100 text-indigo-700',
  completed: 'bg-green-100 text-green-700',
  closed: 'bg-gray-200 text-gray-600',
  cancelled: 'bg-red-100 text-red-700',
  delivered: 'bg-green-100 text-green-700',
  partial: 'bg-amber-100 text-amber-700',
  failed: 'bg-red-100 text-red-700',
}

const tripStatusLabels: Record<string, string> = {
  draft: 'ნახაზი',
  planned: 'დაგეგმილი',
  dispatched: 'გაგზავნილი',
  in_progress: 'მიმდინარე',
  completed: 'დასრულებული',
  closed: 'დახურული',
  cancelled: 'გაუქმებული',
}

const drStatusLabels: Record<string, string> = {
  draft: 'ნახაზი',
  planned: 'დაგეგმილი',
  assigned: 'მინიჭებული',
  in_progress: 'მიმდინარე',
  delivered: 'მიწოდებული',
  partial: 'ნაწილობრივი',
  failed: 'ჩავარდნილი',
  cancelled: 'გაუქმებული',
}

function badge(status: string) {
  const label = Object.keys(statusColor).includes(status)
    ? (tripStatusLabels[status] || drStatusLabels[status] || status)
    : status
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor[status] || 'bg-gray-100 text-gray-600'}`}>
      {label}
    </span>
  )
}

export default function TmsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'deliveries' | 'trips'>('deliveries')

  // ── Delivery requests ──
  const [drModal, setDrModal] = useState(false)
  const [drForm, setDrForm] = useState<Record<string, unknown>>({
    request_number: '', dropoff_address: '', pickup_address: '', contact_name: '',
    contact_phone: '', weight_kg: '', volume_m3: '', package_count: 0, delivery_date: '',
  })

  // ── Trips ──
  const [tripModal, setTripModal] = useState(false)
  const [tripForm, setTripForm] = useState<Record<string, unknown>>({
    trip_number: '', planned_start: '', notes: '',
  })
  // REQ-TMS-04 driver board: selected trip + its ordered stops
  const [selectedTrip, setSelectedTrip] = useState<any | null>(null)

  const drQuery = useQuery({
    queryKey: ['tms-deliveries'],
    queryFn: () => fleetApi.listDeliveryRequests().then((r: any) => r.data.data as DeliveryRequest[]),
  })
  const tripQuery = useQuery({
    queryKey: ['tms-trips'],
    queryFn: () => fleetApi.listTrips().then((r: any) => r.data.data as Trip[]),
  })
  const vehicleQuery = useQuery({
    queryKey: ['fleet-vehicles'],
    queryFn: () => fleetApi.listVehicles().then((r: any) => r.data.data),
  })
  // TMS commercial analytics (OTIF / cost / fleet utilization)
  const analyticsQuery = useQuery({
    queryKey: ['tms-analytics'],
    queryFn: () => fleetApi.analytics().then((r: any) => r.data.data),
  })
  const analytics: any = analyticsQuery.data || {}

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['tms-deliveries'] })
    queryClient.invalidateQueries({ queryKey: ['tms-trips'] })
  }

  const createDr = useMutation({
    mutationFn: (d: Record<string, unknown>) => fleetApi.createDeliveryRequest(d),
    onSuccess: () => { setDrModal(false); invalidate() },
  })
  const createTrip = useMutation({
    mutationFn: (d: Record<string, unknown>) => fleetApi.createTrip(d),
    onSuccess: () => { setTripModal(false); invalidate() },
  })
  const dispatchTrip = useMutation({
    mutationFn: (id: string) => fleetApi.dispatchTrip(id, {}),
    onSuccess: invalidate,
  })
  const startTrip = useMutation({ mutationFn: (id: string) => fleetApi.startTrip(id), onSuccess: invalidate })
  const completeTrip = useMutation({ mutationFn: (id: string) => fleetApi.completeTrip(id), onSuccess: invalidate })
  const closeTrip = useMutation({ mutationFn: (id: string) => fleetApi.closeTrip(id), onSuccess: invalidate })

  // TMS commercial: route planning + freight billing
  const routePlanTrip = useMutation({
    mutationFn: (id: string) => fleetApi.routePlan(id).then((r: any) => r.data.data),
    onSuccess: (data: any) => {
      if (data?.suggested && data?.trip_id) {
        fleetApi.applyPlan(data.trip_id, data.suggested).then(() => invalidate())
      }
    },
  })
  const freightTrip = useMutation({
    mutationFn: (id: string) => fleetApi.freight(id).then((r: any) => r.data.data),
    onSuccess: (data: any) => {
      setFreightData(data || null)
    },
  })
  const [freightData, setFreightData] = useState<any | null>(null)

  const planDelivery = useMutation({ mutationFn: (id: string) => fleetApi.planDelivery(id), onSuccess: invalidate })

  // REQ-TMS-04: load a trip's ordered stops into the driver-board modal
  const openTrip = async (tripId: string) => {
    const res = await fleetApi.getTrip(tripId)
    setSelectedTrip((res as any).data.data)
  }

  // REQ-TMS-05/06: driver stop event (arrive/depart/deliver/fail) → POD
  const driverEvent = useMutation({
    mutationFn: ({ stopId, ev, qty }: { stopId: string; ev: string; qty?: number }) =>
      fleetApi.stopEvent(stopId, { event: ev, delivered_qty: qty, recipient_name: 'მძღოლი' }),
    onSuccess: (_: any, vars: any) => {
      if (selectedTrip) openTrip(selectedTrip.id)
      invalidate()
    },
  })

  const deliveries = drQuery.data || []
  const trips = tripQuery.data || []
  const vehicles = vehicleQuery.data || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Truck className="h-5 w-5 text-blue-600" />
            {t('ტრანსპორტირება (TMS)')}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {t('რეისი და მიწოდება — დაგეგმვიდან POD-მდე')}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setDrModal(true) }}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" /> {t('მიწოდების მოთხოვნა')}
          </button>
          <button
            onClick={() => { setTripModal(true) }}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <Route className="h-4 w-4" /> {t('რეისის შექმნა')}
          </button>
        </div>
      </div>

      {/* TMS analytics (commercial value) */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-gray-200 bg-white p-3">
          <p className="text-xs text-gray-500">{t('დროული მიწოდება (OTIF)')}</p>
          <p className="mt-1 text-xl font-semibold text-green-600">{analytics.on_time_rate != null ? `${analytics.on_time_rate}%` : '—'}</p>
          <p className="text-xs text-gray-400">{analytics.delivered ?? 0} {t('მიწოდებული')}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-3">
          <p className="text-xs text-gray-500">{t('ხარჯი მიწოდებაზე')}</p>
          <p className="mt-1 text-xl font-semibold">{analytics.cost_per_delivery != null ? `${analytics.cost_per_delivery} ₾` : '—'}</p>
          <p className="text-xs text-gray-400">{t('ჯამური')}: {analytics.total_freight_cost != null ? `${analytics.total_freight_cost} ₾` : '—'}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-3">
          <p className="text-xs text-gray-500">{t('POD-ები')}</p>
          <p className="mt-1 text-xl font-semibold">{analytics.pods_recorded ?? 0}</p>
          <p className="text-xs text-gray-400">{t('ჩაწერილი')}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-3">
          <p className="text-xs text-gray-500">{t('ღია რეისები')}</p>
          <p className="mt-1 text-xl font-semibold">{analytics.fleet_utilization?.open_trips ?? 0}</p>
          <p className="text-xs text-gray-400">{t('ავტომობილით')}: {analytics.fleet_utilization?.with_vehicle ?? 0}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-1">
          <button
            onClick={() => setTab('deliveries')}
            className={`inline-flex items-center gap-2 rounded-t-lg px-4 py-2 text-sm font-medium ${
              tab === 'deliveries' ? 'border-b-2 border-blue-600 text-blue-700' : 'text-gray-500 hover:text-gray-800'
            }`}
          >
            <Package className="h-4 w-4" /> {t('მიწოდების მოთხოვნები')}
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs">{deliveries.length}</span>
          </button>
          <button
            onClick={() => setTab('trips')}
            className={`inline-flex items-center gap-2 rounded-t-lg px-4 py-2 text-sm font-medium ${
              tab === 'trips' ? 'border-b-2 border-blue-600 text-blue-700' : 'text-gray-500 hover:text-gray-800'
            }`}
          >
            <Truck className="h-4 w-4" /> {t('რეისები')}
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs">{trips.length}</span>
          </button>
        </nav>
      </div>

      {tab === 'deliveries' ? (
        <DataTable
          columns={[
            { key: 'request_number', label: t('ნომერი') },
            { key: 'status', label: t('სტატუსი'), render: (r: any) => badge(r.status) },
            { key: 'dropoff_address', label: t('მისამართი'), render: (r: any) => (
              <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3 text-gray-400" />{r.dropoff_address}</span>
            )},
            { key: 'contact_name', label: t('კონტაქტი'), render: (r: any) => (
              <span className="flex flex-col text-xs">
                {r.contact_name && <span className="inline-flex items-center gap-1"><User className="h-3 w-3 text-gray-400" />{r.contact_name}</span>}
                {r.contact_phone && <span className="inline-flex items-center gap-1 text-gray-500"><Phone className="h-3 w-3" />{r.contact_phone}</span>}
              </span>
            )},
            { key: 'weight_kg', label: t('წონა (კგ)') },
            { key: 'volume_m3', label: t('მოცულობა (მ³)') },
            { key: 'delivery_date', label: t('მიწოდების თარიღი'), render: (r: any) => r.delivery_date || '—' },
          ]}
          data={deliveries}
        />
      ) : (
        <DataTable
          columns={[
            { key: 'trip_number', label: t('რეისის ნომერი') },
            { key: 'status', label: t('სტატუსი'), render: (r: Trip) => (
              <div className="flex items-center gap-2">
                {badge(r.status)}
                <div className="flex gap-0.5">
                  {['draft', 'planned'].includes(r.status) && (
                    <button onClick={() => dispatchTrip.mutate(r.id)} className="rounded p-1 text-yellow-600 hover:bg-yellow-50" title={t('გაგზავნა')}><Send className="h-4 w-4" /></button>)}
                  {r.status === 'dispatched' && (
                    <button onClick={() => startTrip.mutate(r.id)} className="rounded p-1 text-blue-600 hover:bg-blue-50" title={t('დაწყება')}><Play className="h-4 w-4" /></button>)}
                  {r.status === 'in_progress' && (
                    <button onClick={() => completeTrip.mutate(r.id)} className="rounded p-1 text-green-600 hover:bg-green-50" title={t('დასრულება')}><CheckCircle2 className="h-4 w-4" /></button>)}
                  {r.status === 'completed' && (
                    <button onClick={() => closeTrip.mutate(r.id)} className="rounded p-1 text-gray-600 hover:bg-gray-50" title={t('დახურვა')}><XCircle className="h-4 w-4" /></button>)}
                  <button onClick={() => routePlanTrip.mutate(r.id)} className="rounded p-1 text-orange-600 hover:bg-orange-50" title={t('მარშრუტის დაგეგმვა')}><Route className="h-4 w-4" /></button>
                  {r.vehicle_id && <button onClick={() => freightTrip.mutate(r.id)} className="rounded p-1 text-purple-600 hover:bg-purple-50" title={t('ფრეიტ-ბილინგი')}><CheckCircle2 className="h-4 w-4" /></button>}
                </div>
              </div>
            )},
            { key: 'vehicle_id', label: t('მანქანა'), render: (r: Trip) => {
              const v = vehicles.find((x: any) => x.id === r.vehicle_id)
              return v ? <span className="inline-flex items-center gap-1"><Truck className="h-3 w-3 text-gray-400" />{v.plate_number}</span> : '—'
            }},
            { key: 'planned_start', label: t('დაგეგმილი დაწყება'), render: (r: any) => {
              const d = r.planned_start ? new Date(r.planned_start).toLocaleString('ka-GE', { dateStyle: 'short', timeStyle: 'short' }) : '—'
              return <span className="inline-flex items-center gap-1"><Calendar className="h-3 w-3 text-gray-400" />{d}</span>
            }},
            { key: 'total_weight_kg', label: t('წონა (კგ)') },
            { key: 'total_volume_m3', label: t('მოცულობა (მ³)') },
          ]}
          data={trips}
          onRowClick={(r: any) => openTrip(r.id)}
        />
      )}

      {/* New delivery request modal */}
      <Modal open={drModal} onClose={() => setDrModal(false)} title={t('მიწოდების მოთხოვნა')}>
        <div className="space-y-3">
          <FormField label={t('ნომერი')}>
            <input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" value={drForm.request_number as string}
              onChange={(e) => setDrForm({ ...drForm, request_number: e.target.value })} />
          </FormField>
          <FormField label={t('მიმღების მისამართი')}>
            <input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" value={drForm.dropoff_address as string}
              onChange={(e) => setDrForm({ ...drForm, dropoff_address: e.target.value })} />
          </FormField>
          <FormField label={t('კონტაქტი')}>
            <div className="grid grid-cols-2 gap-2">
              <input placeholder={t('სახელი')} className="rounded-lg border border-gray-300 px-3 py-2 text-sm" value={drForm.contact_name as string}
                onChange={(e) => setDrForm({ ...drForm, contact_name: e.target.value })} />
              <input placeholder={t('ტელეფონი')} className="rounded-lg border border-gray-300 px-3 py-2 text-sm" value={drForm.contact_phone as string}
                onChange={(e) => setDrForm({ ...drForm, contact_phone: e.target.value })} />
            </div>
          </FormField>
          <FormField label={t('წონა/მოცულობა')}>
            <div className="grid grid-cols-3 gap-2">
              <input placeholder={t('წონა (კგ)')} className="rounded-lg border border-gray-300 px-3 py-2 text-sm" value={drForm.weight_kg as string}
                onChange={(e) => setDrForm({ ...drForm, weight_kg: e.target.value })} />
              <input placeholder={t('მოცულობა (მ³)')} className="rounded-lg border border-gray-300 px-3 py-2 text-sm" value={drForm.volume_m3 as string}
                onChange={(e) => setDrForm({ ...drForm, volume_m3: e.target.value })} />
              <input placeholder={t('პაკეტები')} type="number" className="rounded-lg border border-gray-300 px-3 py-2 text-sm" value={drForm.package_count as number}
                onChange={(e) => setDrForm({ ...drForm, package_count: Number(e.target.value) })} />
            </div>
          </FormField>
          <FormField label={t('მიწოდების თარიღი')}>
            <input type="date" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" value={drForm.delivery_date as string}
              onChange={(e) => setDrForm({ ...drForm, delivery_date: e.target.value })} />
          </FormField>
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setDrModal(false)} className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700">{t('გაუქმება')}</button>
            <button onClick={() => createDr.mutate(drForm)} className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white">{t('შექმნა')}</button>
          </div>
        </div>
      </Modal>

      {/* New trip modal */}
      <Modal open={tripModal} onClose={() => setTripModal(false)} title={t('რეისის შექმნა')}>
        <div className="space-y-3">
          <FormField label={t('რეისის ნომერი')}>
            <input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" value={tripForm.trip_number as string}
              onChange={(e) => setTripForm({ ...tripForm, trip_number: e.target.value })} />
          </FormField>
          <FormField label={t('დაგეგმილი დაწყება')}>
            <input type="datetime-local" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" value={tripForm.planned_start as string}
              onChange={(e) => setTripForm({ ...tripForm, planned_start: e.target.value })} />
          </FormField>
          <FormField label={t('შენიშვნები')}>
            <textarea className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" value={tripForm.notes as string}
              onChange={(e) => setTripForm({ ...tripForm, notes: e.target.value })} />
          </FormField>
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setTripModal(false)} className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700">{t('გაუქმება')}</button>
            <button onClick={() => createTrip.mutate(tripForm)} className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white">{t('შექმნა')}</button>
          </div>
        </div>
      </Modal>

      {/* REQ-TMS-04: driver board — trip detail with ordered stops */}
      {selectedTrip !== null && (
        <Modal open={selectedTrip !== null} onClose={() => setSelectedTrip(null)} title={`${t('რეისი')} ${selectedTrip.trip_number}`}>
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-gray-100 px-2 py-1">{selectedTrip.status}</span>
              <span className="inline-flex items-center gap-1 text-gray-600"><Calendar className="h-3 w-3" />
                {selectedTrip.planned_start ? new Date(selectedTrip.planned_start).toLocaleString('ka-GE', { dateStyle: 'short', timeStyle: 'short' }) : '—'}</span>
              <span className="text-gray-600">{t('წონა')}: {selectedTrip.total_weight_kg} kg</span>
            </div>
            <div className="space-y-2">
              {selectedTrip.stops && selectedTrip.stops.length > 0 ? (
                selectedTrip.stops.map((stop: any, idx: number) => (
                  <div key={stop.id} className="rounded-lg border border-gray-200 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2 text-sm font-medium">
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700">{idx + 1}</span>
                          <span>{stop.address}</span>
                        </div>
                        {stop.contact_name && (
                          <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
                            <User className="h-3 w-3" />{stop.contact_name}
                            {stop.contact_phone && <Phone className="ml-1 h-3 w-3" />}
                            {stop.contact_phone}
                          </div>
                        )}
                      </div>
                      <span className={`rounded-full px-2 py-0.5 text-xs ${statusColor[stop.status] || 'bg-gray-100 text-gray-600'}`}>{stop.status}</span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {stop.status === 'pending' && (
                        <button onClick={() => driverEvent.mutate({ stopId: stop.id, ev: 'arrive' })} className="rounded bg-blue-600 px-2 py-1 text-xs text-white">{t('ჩასვლა')}</button>)}
                      {stop.status === 'arrived' && (
                        <>
                          <button onClick={() => driverEvent.mutate({ stopId: stop.id, ev: 'depart' })} className="rounded bg-indigo-600 px-2 py-1 text-xs text-white">{t('გამგზავრება')}</button>
                          <button onClick={() => driverEvent.mutate({ stopId: stop.id, ev: 'deliver', qty: 10 })} className="rounded bg-green-600 px-2 py-1 text-xs text-white">{t('მიწოდება')}</button>
                          <button onClick={() => driverEvent.mutate({ stopId: stop.id, ev: 'fail', qty: 0 })} className="rounded bg-red-600 px-2 py-1 text-xs text-white">{t('ჩავარდენა')}</button>
                        </>)}
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-gray-500">{t('გაჩერებები არ არის')}</p>
              )}
            </div>
          </div>
        </Modal>
      )}

      {/* TMS freight billing modal */}
      {freightData !== null && (
        <Modal open={freightData !== null} onClose={() => setFreightData(null)} title={`${t('ფრეიტ-ბილინგი')} — ${freightData.trip_number || ''}`}>
          <div className="space-y-3">
            <div className="rounded-lg border border-gray-200 p-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Subtotal</span>
                <span className="font-medium">{freightData.subtotal} ₾</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Carrier</span>
                <span className="font-medium">{freightData.carrier_rate} ₾</span>
              </div>
              <div className="flex justify-between border-t border-gray-200 pt-1 text-sm font-semibold">
                <span>Margin</span>
                <span className="text-green-600">{freightData.margin} ₾</span>
              </div>
            </div>
            {(freightData.lines || []).map((line: any, i: number) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-gray-100 p-2 text-sm">
                <span>{line.request_number}</span>
                <span>{line.basis} kg × {line.rate} = <b>{line.freight_charge} ₾</b></span>
              </div>
            ))}
          </div>
        </Modal>
      )}
    </div>
  )
}
