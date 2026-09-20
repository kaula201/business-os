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

  const planDelivery = useMutation({ mutationFn: (id: string) => fleetApi.planDelivery(id), onSuccess: invalidate })

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
    </div>
  )
}
