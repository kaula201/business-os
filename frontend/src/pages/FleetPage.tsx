import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Car,
  Fuel,
  Wrench,
  Users,
  Plus,
  Pencil,
  Trash2,
  Search,
  Gauge,
  Calendar,
  Phone,
  BadgeInfo,
  Ban,
  MapPinned,
} from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import GeorgiaFleetMap from '../components/GeorgiaFleetMap'
import { fleetApi } from '../services/api'
import type {
  Vehicle,
  VehicleCreate,
  VehicleUpdate,
  FuelLog,
  FuelLogCreate,
  ServiceRecord,
  ServiceRecordCreate,
  DriverAssignment,
  DriverAssignmentCreate,
  DriverAssignmentUpdate,
} from '../types'

const today = () => new Date().toISOString().slice(0, 10)

const fuelTypes = [
  { value: 'petrol', label: 'ბენზინი' },
  { value: 'diesel', label: 'დიზელი' },
  { value: 'gas', label: 'გაზი' },
  { value: 'electric', label: 'ელექტრო' },
  { value: 'hybrid', label: 'ჰიბრიდი' },
]

const serviceTypes = [
  { value: 'oil_change', label: 'ზეთის ცვლილება' },
  { value: 'repair', label: 'რემონტი' },
  { value: 'tire', label: 'საბურავები' },
  { value: 'inspection', label: 'ტექ. ინსპექცია' },
  { value: 'other', label: 'სხვა' },
]

const tabs = [
  { id: 'vehicles', label: 'ავტომობილები', icon: Car },
  { id: 'map', label: 'საქართველოს რუკა', icon: MapPinned },
  { id: 'fuel', label: 'საწვავი', icon: Fuel },
  { id: 'services', label: 'მომსახურება', icon: Wrench },
  { id: 'drivers', label: 'მძღოლები', icon: Users },
]

const georgiaLocations = [
  { value: '', label: 'აირჩიეთ ქალაქი', latitude: null, longitude: null },
  { value: 'თბილისი, საქართველო', label: 'თბილისი', latitude: 41.7151, longitude: 44.8271 },
  { value: 'ბათუმი, საქართველო', label: 'ბათუმი', latitude: 41.6168, longitude: 41.6367 },
  { value: 'ქუთაისი, საქართველო', label: 'ქუთაისი', latitude: 42.2679, longitude: 42.6946 },
  { value: 'რუსთავი, საქართველო', label: 'რუსთავი', latitude: 41.5495, longitude: 44.9932 },
  { value: 'გორი, საქართველო', label: 'გორი', latitude: 41.9842, longitude: 44.1158 },
  { value: 'ფოთი, საქართველო', label: 'ფოთი', latitude: 42.1462, longitude: 41.6719 },
  { value: 'ზუგდიდი, საქართველო', label: 'ზუგდიდი', latitude: 42.5088, longitude: 41.8709 },
  { value: 'თელავი, საქართველო', label: 'თელავი', latitude: 41.9198, longitude: 45.4732 },
]

// ── Helpers ──────────────────────────────────────────────────────────

function money(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

function errorText(err: any) {
  return err?.response?.data?.detail || 'ოპერაცია ვერ შესრულდა'
}

// ── Page ─────────────────────────────────────────────────────────────

export default function FleetPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState('vehicles')
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  // Vehicle state
  const [vehicleModal, setVehicleModal] = useState<'create' | 'edit' | null>(null)
  const [selectedVehicle, setSelectedVehicle] = useState<Vehicle | null>(null)
  const [vehicleForm, setVehicleForm] = useState<VehicleCreate>({
    plate_number: '', brand: '', model: '', year: null, vin: '', color: '',
    fuel_type: 'petrol', engine_capacity: null, initial_mileage: 0, current_mileage: 0,
    insurance_company: '', insurance_policy: '', insurance_valid_until: null,
    tech_inspection_until: null, location_name: '', latitude: null, longitude: null, notes: '',
  })
  const [vehicleEditForm, setVehicleEditForm] = useState<VehicleUpdate>({})

  // Fuel state
  const [fuelModal, setFuelModal] = useState(false)
  const [fuelVehicleId, setFuelVehicleId] = useState('')
  const [fuelForm, setFuelForm] = useState<FuelLogCreate>({
    vehicle_id: '', refuel_date: today(), liters: 0, price_per_liter: 0,
    total_amount: 0, mileage_at_refuel: 0, fuel_card: '', station: '',
    receipt_number: '', notes: '',
  })

  // Service state
  const [serviceModal, setServiceModal] = useState(false)
  const [serviceVehicleId, setServiceVehicleId] = useState('')
  const [serviceForm, setServiceForm] = useState<ServiceRecordCreate>({
    vehicle_id: '', service_date: today(), service_type: 'oil_change',
    description: '', mileage_at_service: 0, cost: 0, service_provider: '',
    invoice_number: '', next_service_mileage: null, next_service_date: null, notes: '',
  })

  // Driver state
  const [driverModal, setDriverModal] = useState<'create' | 'edit' | null>(null)
  const [driverVehicleId, setDriverVehicleId] = useState('')
  const [selectedDriver, setSelectedDriver] = useState<DriverAssignment | null>(null)
  const [driverForm, setDriverForm] = useState<DriverAssignmentCreate>({
    vehicle_id: '', driver_name: '', driver_phone: '', driver_license: '',
    assigned_from: today(), assigned_until: null, notes: '',
  })
  const [driverEditForm, setDriverEditForm] = useState<DriverAssignmentUpdate>({})

  // ── Queries ──────────────────────────────────────────────────────

  const { data: vehiclesData, isLoading: vehiclesLoading } = useQuery({
    queryKey: ['fleet-vehicles'],
    queryFn: () => fleetApi.listVehicles().then((r) => r.data.data),
  })
  const vehicles: Vehicle[] = vehiclesData || []

  const { data: fuelData, isLoading: fuelLoading } = useQuery({
    queryKey: ['fleet-fuel', fuelVehicleId],
    queryFn: () => fleetApi.listFuelLogs(fuelVehicleId),
    enabled: tab === 'fuel' && !!fuelVehicleId,
  })
  const fuelLogs: FuelLog[] = fuelData?.data?.data || []

  const { data: serviceData, isLoading: serviceLoading } = useQuery({
    queryKey: ['fleet-services', serviceVehicleId],
    queryFn: () => fleetApi.listServices(serviceVehicleId),
    enabled: tab === 'services' && !!serviceVehicleId,
  })
  const services: ServiceRecord[] = serviceData?.data?.data || []

  const { data: driverData, isLoading: driverLoading } = useQuery({
    queryKey: ['fleet-drivers', driverVehicleId],
    queryFn: () => fleetApi.listDrivers(driverVehicleId),
    enabled: tab === 'drivers' && !!driverVehicleId,
  })
  const drivers: DriverAssignment[] = driverData?.data?.data || []

  // ── Mutations ────────────────────────────────────────────────────

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['fleet-vehicles'] })
    queryClient.invalidateQueries({ queryKey: ['fleet-fuel'] })
    queryClient.invalidateQueries({ queryKey: ['fleet-services'] })
    queryClient.invalidateQueries({ queryKey: ['fleet-drivers'] })
  }

  const createVehicle = useMutation({
    mutationFn: (d: VehicleCreate) => fleetApi.createVehicle(d),
    onSuccess: () => { setVehicleModal(null); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })
  const updateVehicle = useMutation({
    mutationFn: ({ id, d }: { id: string; d: VehicleUpdate }) => fleetApi.updateVehicle(id, d),
    onSuccess: () => { setVehicleModal(null); setSelectedVehicle(null); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })
  const deleteVehicle = useMutation({
    mutationFn: (id: string) => fleetApi.deleteVehicle(id),
    onSuccess: () => refresh(),
    onError: (e) => setError(errorText(e)),
  })

  const createFuel = useMutation({
    mutationFn: ({ vid, d }: { vid: string; d: FuelLogCreate }) => fleetApi.createFuelLog(vid, d),
    onSuccess: () => { setFuelModal(false); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })
  const deleteFuel = useMutation({
    mutationFn: (id: string) => fleetApi.deleteFuelLog(id),
    onSuccess: () => refresh(),
    onError: (e) => setError(errorText(e)),
  })

  const createService = useMutation({
    mutationFn: ({ vid, d }: { vid: string; d: ServiceRecordCreate }) => fleetApi.createService(vid, d),
    onSuccess: () => { setServiceModal(false); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })
  const deleteService = useMutation({
    mutationFn: (id: string) => fleetApi.deleteService(id),
    onSuccess: () => refresh(),
    onError: (e) => setError(errorText(e)),
  })

  const createDriver = useMutation({
    mutationFn: ({ vid, d }: { vid: string; d: DriverAssignmentCreate }) => fleetApi.createDriver(vid, d),
    onSuccess: () => { setDriverModal(null); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })
  const updateDriver = useMutation({
    mutationFn: ({ id, d }: { id: string; d: DriverAssignmentUpdate }) => fleetApi.updateDriver(id, d),
    onSuccess: () => { setDriverModal(null); setSelectedDriver(null); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })
  const deleteDriver = useMutation({
    mutationFn: (id: string) => fleetApi.deleteDriver(id),
    onSuccess: () => refresh(),
    onError: (e) => setError(errorText(e)),
  })

  // ── Filtered data ────────────────────────────────────────────────

  const visibleVehicles = search.trim()
    ? vehicles.filter((v) =>
        `${v.plate_number} ${v.brand} ${v.model}`.toLowerCase().includes(search.trim().toLowerCase())
      )
    : vehicles

  const openVehicleEditor = (vehicle: Vehicle) => {
    setSelectedVehicle(vehicle)
    setVehicleEditForm({
      plate_number: vehicle.plate_number,
      brand: vehicle.brand,
      model: vehicle.model,
      year: vehicle.year,
      vin: vehicle.vin,
      color: vehicle.color,
      fuel_type: vehicle.fuel_type,
      engine_capacity: vehicle.engine_capacity,
      current_mileage: vehicle.current_mileage,
      insurance_company: vehicle.insurance_company,
      insurance_policy: vehicle.insurance_policy,
      insurance_valid_until: vehicle.insurance_valid_until,
      tech_inspection_until: vehicle.tech_inspection_until,
      location_name: vehicle.location_name,
      latitude: vehicle.latitude,
      longitude: vehicle.longitude,
      is_active: vehicle.is_active,
      notes: vehicle.notes,
    })
    setError('')
    setVehicleModal('edit')
  }

  const applyCreateLocation = (locationName: string) => {
    const location = georgiaLocations.find((item) => item.value === locationName)
    setVehicleForm({
      ...vehicleForm,
      location_name: locationName,
      latitude: location?.latitude ?? null,
      longitude: location?.longitude ?? null,
    })
  }

  const applyEditLocation = (locationName: string) => {
    const location = georgiaLocations.find((item) => item.value === locationName)
    setVehicleEditForm({
      ...vehicleEditForm,
      location_name: locationName,
      latitude: location?.latitude ?? null,
      longitude: location?.longitude ?? null,
    })
  }

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900">ავტოპარკი</h1>
          <p className="mt-1 text-sm text-brandgray-500">ავტომობილების, საწვავის, მომსახურებისა და მძღოლების მართვა</p>
        </div>
        <div className="flex gap-2">
          {tab === 'vehicles' && (
            <button
              className="btn-primary flex items-center gap-2"
              onClick={() => {
                setVehicleForm({
                  plate_number: '', brand: '', model: '', year: null, vin: '', color: '',
                  fuel_type: 'petrol', engine_capacity: null, initial_mileage: 0, current_mileage: 0,
                  insurance_company: '', insurance_policy: '', insurance_valid_until: null,
                  tech_inspection_until: null, location_name: '', latitude: null, longitude: null, notes: '',
                })
                setError('')
                setVehicleModal('create')
              }}
            >
              <Plus size={18} /> ავტომობილი
            </button>
          )}
          {tab === 'fuel' && (
            <button
              className="btn-primary flex items-center gap-2"
              onClick={() => {
                if (!fuelVehicleId) return
                setFuelForm({
                  vehicle_id: fuelVehicleId, refuel_date: today(), liters: 0, price_per_liter: 0,
                  total_amount: 0, mileage_at_refuel: 0, fuel_card: '', station: '',
                  receipt_number: '', notes: '',
                })
                setError('')
                setFuelModal(true)
              }}
              disabled={!fuelVehicleId}
            >
              <Plus size={18} /> საწვავი
            </button>
          )}
          {tab === 'services' && (
            <button
              className="btn-primary flex items-center gap-2"
              onClick={() => {
                if (!serviceVehicleId) return
                setServiceForm({
                  vehicle_id: serviceVehicleId, service_date: today(), service_type: 'oil_change',
                  description: '', mileage_at_service: 0, cost: 0, service_provider: '',
                  invoice_number: '', next_service_mileage: null, next_service_date: null, notes: '',
                })
                setError('')
                setServiceModal(true)
              }}
              disabled={!serviceVehicleId}
            >
              <Plus size={18} /> მომსახურება
            </button>
          )}
          {tab === 'drivers' && (
            <button
              className="btn-primary flex items-center gap-2"
              onClick={() => {
                if (!driverVehicleId) return
                setDriverForm({
                  vehicle_id: driverVehicleId, driver_name: '', driver_phone: '', driver_license: '',
                  assigned_from: today(), assigned_until: null, notes: '',
                })
                setError('')
                setDriverModal('create')
              }}
              disabled={!driverVehicleId}
            >
              <Plus size={18} /> მძღოლი
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div
        className="flex min-w-0 snap-x snap-mandatory gap-1 overflow-x-auto border-b border-brandgray-100 overscroll-x-contain"
        aria-label="ავტოპარკის განყოფილებები"
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex shrink-0 snap-start items-center gap-2 whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
              tab === t.id
                ? 'border-primary-600 text-primary-700'
                : 'border-transparent text-brandgray-500 hover:text-brandgray-700 hover:border-brandgray-300'
            }`}
          >
            <t.icon size={18} />
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Vehicles Tab ─────────────────────────────────────────── */}
      {tab === 'vehicles' && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 max-w-xs">
              <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="ძებნა ნომრით, ბრენდით ან მოდელით..."
                className="input pl-10"
              />
            </div>
          </div>

          <DataTable
            columns={[
              { key: 'plate_number', label: 'სახელმწ. ნომერი', className: 'font-mono font-semibold' },
              { key: 'brand', label: 'ბრენდი' },
              { key: 'model', label: 'მოდელი' },
              { key: 'year', label: 'წელი', render: (v: Vehicle) => v.year ?? '—' },
              { key: 'fuel_type', label: 'საწვავი', render: (v: Vehicle) => fuelTypes.find((f) => f.value === v.fuel_type)?.label || v.fuel_type },
              { key: 'current_mileage', label: 'გარბენი (კმ)', render: (v: Vehicle) => v.current_mileage.toLocaleString() },
              {
                key: 'is_active', label: 'სტატუსი',
                render: (v: Vehicle) => (
                  <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    v.is_active ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {v.is_active ? 'აქტიური' : 'არააქტიური'}
                  </span>
                ),
              },
              {
                key: 'actions', label: '',
                render: (v: Vehicle) => (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); openVehicleEditor(v) }}
                      className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                      <Pencil size={16} className="text-gray-400" />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); if (confirm('დარწმუნებული ხართ, რომ გსურთ ავტომობილის წაშლა?')) deleteVehicle.mutate(v.id) }}
                      className="p-1.5 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <Trash2 size={16} className="text-red-400" />
                    </button>
                  </div>
                ),
              },
            ]}
            data={visibleVehicles}
            isLoading={vehiclesLoading}
            emptyMessage="ავტომობილები არ მოიძებნა"
          />
        </>
      )}

      {/* ── Georgia Map Tab ───────────────────────────────────────── */}
      {tab === 'map' && (
        <GeorgiaFleetMap vehicles={vehicles} onSelectVehicle={openVehicleEditor} />
      )}

      {/* ── Fuel Tab ──────────────────────────────────────────────── */}
      {tab === 'fuel' && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Select
              value={fuelVehicleId}
              onChange={(e) => setFuelVehicleId(e.target.value)}
              options={vehicles.map((v) => ({ value: v.id, label: `${v.plate_number} — ${v.brand} ${v.model}` }))}
              placeholder="აირჩიეთ ავტომობილი"
              className="w-72"
            />
          </div>

          {!fuelVehicleId ? (
            <div className="card p-8 text-center text-brandgray-500">აირჩიეთ ავტომობილი საწვავის ჩანაწერების სანახავად</div>
          ) : (
            <DataTable
              columns={[
                { key: 'refuel_date', label: 'თარიღი' },
                { key: 'liters', label: 'ლიტრი', render: (f: FuelLog) => f.liters.toFixed(2) },
                { key: 'price_per_liter', label: 'ფასი/ლ', render: (f: FuelLog) => money(f.price_per_liter) },
                { key: 'total_amount', label: 'თანხა', render: (f: FuelLog) => money(f.total_amount) },
                { key: 'mileage_at_refuel', label: 'გარბენი (კმ)', render: (f: FuelLog) => f.mileage_at_refuel.toLocaleString() },
                { key: 'station', label: 'ბენზინგასამართი', render: (f: FuelLog) => f.station || '—' },
                {
                  key: 'actions', label: '',
                  render: (f: FuelLog) => (
                    <button
                      onClick={(e) => { e.stopPropagation(); if (confirm('წავშალოთ საწვავის ჩანაწერი?')) deleteFuel.mutate(f.id) }}
                      className="p-1.5 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <Trash2 size={16} className="text-red-400" />
                    </button>
                  ),
                },
              ]}
              data={fuelLogs}
              isLoading={fuelLoading}
              emptyMessage="საწვავის ჩანაწერები არ მოიძებნა"
            />
          )}
        </>
      )}

      {/* ── Services Tab ──────────────────────────────────────────── */}
      {tab === 'services' && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Select
              value={serviceVehicleId}
              onChange={(e) => setServiceVehicleId(e.target.value)}
              options={vehicles.map((v) => ({ value: v.id, label: `${v.plate_number} — ${v.brand} ${v.model}` }))}
              placeholder="აირჩიეთ ავტომობილი"
              className="w-72"
            />
          </div>

          {!serviceVehicleId ? (
            <div className="card p-8 text-center text-brandgray-500">აირჩიეთ ავტომობილი მომსახურების ჩანაწერების სანახავად</div>
          ) : (
            <DataTable
              columns={[
                { key: 'service_date', label: 'თარიღი' },
                { key: 'service_type', label: 'ტიპი', render: (s: ServiceRecord) => serviceTypes.find((t) => t.value === s.service_type)?.label || s.service_type },
                { key: 'description', label: 'აღწერა', render: (s: ServiceRecord) => (
                  <div className="max-w-[300px] truncate" title={s.description}>{s.description}</div>
                )},
                { key: 'mileage_at_service', label: 'გარბენი (კმ)', render: (s: ServiceRecord) => s.mileage_at_service.toLocaleString() },
                { key: 'cost', label: 'ღირებულება', render: (s: ServiceRecord) => money(s.cost) },
                { key: 'service_provider', label: 'სერვის ცენტრი', render: (s: ServiceRecord) => s.service_provider || '—' },
                {
                  key: 'actions', label: '',
                  render: (s: ServiceRecord) => (
                    <button
                      onClick={(e) => { e.stopPropagation(); if (confirm('წავშალოთ მომსახურების ჩანაწერი?')) deleteService.mutate(s.id) }}
                      className="p-1.5 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <Trash2 size={16} className="text-red-400" />
                    </button>
                  ),
                },
              ]}
              data={services}
              isLoading={serviceLoading}
              emptyMessage="მომსახურების ჩანაწერები არ მოიძებნა"
            />
          )}
        </>
      )}

      {/* ── Drivers Tab ───────────────────────────────────────────── */}
      {tab === 'drivers' && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Select
              value={driverVehicleId}
              onChange={(e) => setDriverVehicleId(e.target.value)}
              options={vehicles.map((v) => ({ value: v.id, label: `${v.plate_number} — ${v.brand} ${v.model}` }))}
              placeholder="აირჩიეთ ავტომობილი"
              className="w-72"
            />
          </div>

          {!driverVehicleId ? (
            <div className="card p-8 text-center text-brandgray-500">აირჩიეთ ავტომობილი მძღოლების სანახავად</div>
          ) : (
            <DataTable
              columns={[
                { key: 'driver_name', label: 'მძღოლი', render: (d: DriverAssignment) => (
                  <span className="font-medium">{d.driver_name}</span>
                )},
                { key: 'driver_phone', label: 'ტელეფონი', render: (d: DriverAssignment) => d.driver_phone || '—' },
                { key: 'driver_license', label: 'უფლება', render: (d: DriverAssignment) => d.driver_license || '—' },
                { key: 'assigned_from', label: 'მინიჭებული' },
                { key: 'assigned_until', label: 'მოქმედებს', render: (d: DriverAssignment) => d.assigned_until || '—' },
                {
                  key: 'is_active', label: 'სტატუსი',
                  render: (d: DriverAssignment) => (
                    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      d.is_active ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'
                    }`}>
                      {d.is_active ? 'აქტიური' : 'არააქტიური'}
                    </span>
                  ),
                },
                {
                  key: 'actions', label: '',
                  render: (d: DriverAssignment) => (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => { e.stopPropagation(); setSelectedDriver(d); setDriverEditForm({
                          driver_name: d.driver_name, driver_phone: d.driver_phone, driver_license: d.driver_license,
                          assigned_from: d.assigned_from, assigned_until: d.assigned_until, is_active: d.is_active, notes: d.notes,
                        }); setError(''); setDriverModal('edit') }}
                        className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                      >
                        <Pencil size={16} className="text-gray-400" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); if (confirm('წავშალოთ მძღოლის მინიჭება?')) deleteDriver.mutate(d.id) }}
                        className="p-1.5 hover:bg-red-50 rounded-lg transition-colors"
                      >
                        <Trash2 size={16} className="text-red-400" />
                      </button>
                    </div>
                  ),
                },
              ]}
              data={drivers}
              isLoading={driverLoading}
              emptyMessage="მძღოლები არ მოიძებნა"
            />
          )}
        </>
      )}

      {/* ── Vehicle Create Modal ─────────────────────────────────── */}
      <Modal open={vehicleModal === 'create'} onClose={() => setVehicleModal(null)} title="ახალი ავტომობილი" size="lg">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormField label="სახელმწ. ნომერი" required>
              <input value={vehicleForm.plate_number} onChange={(e) => setVehicleForm({ ...vehicleForm, plate_number: e.target.value })} placeholder="მაგ. AA-123-BB" className="input" />
            </FormField>
            <FormField label="საწვავის ტიპი">
              <Select value={vehicleForm.fuel_type} onChange={(e) => setVehicleForm({ ...vehicleForm, fuel_type: e.target.value })} options={fuelTypes} />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="ბრენდი" required>
              <input value={vehicleForm.brand} onChange={(e) => setVehicleForm({ ...vehicleForm, brand: e.target.value })} placeholder="Toyota" className="input" />
            </FormField>
            <FormField label="მოდელი" required>
              <input value={vehicleForm.model} onChange={(e) => setVehicleForm({ ...vehicleForm, model: e.target.value })} placeholder="Camry" className="input" />
            </FormField>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <FormField label="გამოშვების წელი">
              <input type="number" value={vehicleForm.year ?? ''} onChange={(e) => setVehicleForm({ ...vehicleForm, year: e.target.value ? Number(e.target.value) : null })} className="input" />
            </FormField>
            <FormField label="VIN კოდი">
              <input value={vehicleForm.vin || ''} onChange={(e) => setVehicleForm({ ...vehicleForm, vin: e.target.value })} className="input" />
            </FormField>
            <FormField label="ფერი">
              <input value={vehicleForm.color || ''} onChange={(e) => setVehicleForm({ ...vehicleForm, color: e.target.value })} className="input" />
            </FormField>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <FormField label="ძრავის მოცულობა (ლ)">
              <input type="number" step="0.1" value={vehicleForm.engine_capacity ?? ''} onChange={(e) => setVehicleForm({ ...vehicleForm, engine_capacity: e.target.value ? Number(e.target.value) : null })} className="input" />
            </FormField>
            <FormField label="საწყისი გარბენი (კმ)">
              <input type="number" value={vehicleForm.initial_mileage} onChange={(e) => setVehicleForm({ ...vehicleForm, initial_mileage: Number(e.target.value) })} className="input" />
            </FormField>
            <FormField label="მიმდ. გარბენი (კმ)">
              <input type="number" value={vehicleForm.current_mileage} onChange={(e) => setVehicleForm({ ...vehicleForm, current_mileage: Number(e.target.value) })} className="input" />
            </FormField>
          </div>
          <div className="border-t border-gray-100 pt-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">დაზღვევა</h3>
            <div className="grid grid-cols-3 gap-4">
              <FormField label="მზღვეველი კომპანია">
                <input value={vehicleForm.insurance_company || ''} onChange={(e) => setVehicleForm({ ...vehicleForm, insurance_company: e.target.value })} className="input" />
              </FormField>
              <FormField label="პოლისის ნომერი">
                <input value={vehicleForm.insurance_policy || ''} onChange={(e) => setVehicleForm({ ...vehicleForm, insurance_policy: e.target.value })} className="input" />
              </FormField>
              <FormField label="მოქმედებს">
                <input type="date" value={vehicleForm.insurance_valid_until || ''} onChange={(e) => setVehicleForm({ ...vehicleForm, insurance_valid_until: e.target.value || null })} className="input" />
              </FormField>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="ტექ. ინსპექცია">
              <input type="date" value={vehicleForm.tech_inspection_until || ''} onChange={(e) => setVehicleForm({ ...vehicleForm, tech_inspection_until: e.target.value || null })} className="input" />
            </FormField>
            <FormField label="შენიშვნა">
              <input value={vehicleForm.notes || ''} onChange={(e) => setVehicleForm({ ...vehicleForm, notes: e.target.value })} className="input" />
            </FormField>
          </div>
          <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-4 dark:border-blue-900/40 dark:bg-blue-900/10">
            <div className="mb-3 flex items-center gap-2 font-semibold text-blue-950 dark:text-blue-200"><MapPinned size={18} /> მდებარეობა საქართველოს რუკაზე</div>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="ქალაქის სწრაფი არჩევა">
                <Select value={georgiaLocations.some((item) => item.value === vehicleForm.location_name) ? vehicleForm.location_name || '' : ''} onChange={(e) => applyCreateLocation(e.target.value)} options={georgiaLocations} />
              </FormField>
              <FormField label="მისამართი / ობიექტი">
                <input value={vehicleForm.location_name || ''} onChange={(e) => setVehicleForm({ ...vehicleForm, location_name: e.target.value })} className="input" placeholder="მაგ. თბილისი, წერეთლის გამზირი" />
              </FormField>
              <FormField label="Latitude">
                <input type="number" min="-90" max="90" step="0.000001" value={vehicleForm.latitude ?? ''} onChange={(e) => setVehicleForm({ ...vehicleForm, latitude: e.target.value ? Number(e.target.value) : null })} className="input" placeholder="41.715100" />
              </FormField>
              <FormField label="Longitude">
                <input type="number" min="-180" max="180" step="0.000001" value={vehicleForm.longitude ?? ''} onChange={(e) => setVehicleForm({ ...vehicleForm, longitude: e.target.value ? Number(e.target.value) : null })} className="input" placeholder="44.827100" />
              </FormField>
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setVehicleModal(null)} className="btn-secondary">გაუქმება</button>
            <button
              onClick={() => {
                if (!vehicleForm.plate_number.trim() || !vehicleForm.brand.trim() || !vehicleForm.model.trim()) {
                  setError('ნომერი, ბრენდი და მოდელი სავალდებულოა')
                  return
                }
                createVehicle.mutate(vehicleForm)
              }}
              disabled={createVehicle.isPending}
              className="btn-primary"
            >
              {createVehicle.isPending ? 'იქმნება...' : 'შექმნა'}
            </button>
          </div>
        </div>
      </Modal>

      {/* ── Vehicle Edit Modal ───────────────────────────────────── */}
      <Modal open={vehicleModal === 'edit'} onClose={() => setVehicleModal(null)} title="ავტომობილის რედაქტირება" size="lg">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormField label="სახელმწ. ნომერი">
              <input value={vehicleEditForm.plate_number || ''} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, plate_number: e.target.value })} className="input" />
            </FormField>
            <FormField label="საწვავის ტიპი">
              <Select value={vehicleEditForm.fuel_type || 'petrol'} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, fuel_type: e.target.value })} options={fuelTypes} />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="ბრენდი">
              <input value={vehicleEditForm.brand || ''} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, brand: e.target.value })} className="input" />
            </FormField>
            <FormField label="მოდელი">
              <input value={vehicleEditForm.model || ''} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, model: e.target.value })} className="input" />
            </FormField>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <FormField label="წელი">
              <input type="number" value={vehicleEditForm.year ?? ''} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, year: e.target.value ? Number(e.target.value) : null })} className="input" />
            </FormField>
            <FormField label="VIN">
              <input value={vehicleEditForm.vin || ''} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, vin: e.target.value })} className="input" />
            </FormField>
            <FormField label="ფერი">
              <input value={vehicleEditForm.color || ''} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, color: e.target.value })} className="input" />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="მიმდ. გარბენი (კმ)">
              <input type="number" value={vehicleEditForm.current_mileage ?? ''} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, current_mileage: e.target.value ? Number(e.target.value) : null })} className="input" />
            </FormField>
            <FormField label="სტატუსი">
              <label className="flex items-center gap-2 mt-2">
                <input type="checkbox" checked={vehicleEditForm.is_active !== false} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, is_active: e.target.checked })} className="rounded" />
                <span className="text-sm text-gray-700">აქტიური</span>
              </label>
            </FormField>
          </div>
          <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-4 dark:border-blue-900/40 dark:bg-blue-900/10">
            <div className="mb-3 flex items-center gap-2 font-semibold text-blue-950 dark:text-blue-200"><MapPinned size={18} /> მდებარეობა საქართველოს რუკაზე</div>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="ქალაქის სწრაფი არჩევა">
                <Select value={georgiaLocations.some((item) => item.value === vehicleEditForm.location_name) ? vehicleEditForm.location_name || '' : ''} onChange={(e) => applyEditLocation(e.target.value)} options={georgiaLocations} />
              </FormField>
              <FormField label="მისამართი / ობიექტი">
                <input value={vehicleEditForm.location_name || ''} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, location_name: e.target.value })} className="input" placeholder="მაგ. ბათუმი, პორტის ტერიტორია" />
              </FormField>
              <FormField label="Latitude">
                <input type="number" min="-90" max="90" step="0.000001" value={vehicleEditForm.latitude ?? ''} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, latitude: e.target.value ? Number(e.target.value) : null })} className="input" />
              </FormField>
              <FormField label="Longitude">
                <input type="number" min="-180" max="180" step="0.000001" value={vehicleEditForm.longitude ?? ''} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, longitude: e.target.value ? Number(e.target.value) : null })} className="input" />
              </FormField>
            </div>
          </div>
          <FormField label="შენიშვნა">
            <textarea value={vehicleEditForm.notes || ''} onChange={(e) => setVehicleEditForm({ ...vehicleEditForm, notes: e.target.value })} className="input" rows={3} />
          </FormField>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setVehicleModal(null)} className="btn-secondary">გაუქმება</button>
            <button
              onClick={() => {
                if (!selectedVehicle) return
                updateVehicle.mutate({ id: selectedVehicle.id, d: vehicleEditForm })
              }}
              disabled={updateVehicle.isPending}
              className="btn-primary"
            >
              {updateVehicle.isPending ? 'ინახება...' : 'შენახვა'}
            </button>
          </div>
        </div>
      </Modal>

      {/* ── Fuel Create Modal ─────────────────────────────────────── */}
      <Modal open={fuelModal} onClose={() => setFuelModal(false)} title="საწვავის ჩანაწერი" size="md">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormField label="თარიღი" required>
              <input type="date" value={fuelForm.refuel_date} onChange={(e) => setFuelForm({ ...fuelForm, refuel_date: e.target.value })} className="input" />
            </FormField>
            <FormField label="ლიტრი" required>
              <input type="number" step="0.01" value={fuelForm.liters || ''} onChange={(e) => setFuelForm({ ...fuelForm, liters: Number(e.target.value) })} className="input" />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="ფასი ლიტრზე" required>
              <input type="number" step="0.01" value={fuelForm.price_per_liter || ''} onChange={(e) => setFuelForm({ ...fuelForm, price_per_liter: Number(e.target.value) })} className="input" />
            </FormField>
            <FormField label="ჯამი" required>
              <input type="number" step="0.01" value={fuelForm.total_amount || ''} onChange={(e) => setFuelForm({ ...fuelForm, total_amount: Number(e.target.value) })} className="input" />
            </FormField>
          </div>
          <FormField label="გარბენი საწვავის შევსებისას (კმ)" required>
            <input type="number" value={fuelForm.mileage_at_refuel || ''} onChange={(e) => setFuelForm({ ...fuelForm, mileage_at_refuel: Number(e.target.value) })} className="input" />
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="საწვავის ბარათი">
              <input value={fuelForm.fuel_card || ''} onChange={(e) => setFuelForm({ ...fuelForm, fuel_card: e.target.value })} className="input" />
            </FormField>
            <FormField label="ბენზინგასამართი">
              <input value={fuelForm.station || ''} onChange={(e) => setFuelForm({ ...fuelForm, station: e.target.value })} className="input" />
            </FormField>
          </div>
          <FormField label="შენიშვნა">
            <textarea value={fuelForm.notes || ''} onChange={(e) => setFuelForm({ ...fuelForm, notes: e.target.value })} className="input" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setFuelModal(false)} className="btn-secondary">გაუქმება</button>
            <button
              onClick={() => {
                if (!fuelForm.liters || !fuelForm.price_per_liter || !fuelForm.total_amount || !fuelForm.mileage_at_refuel) {
                  setError('შეავსეთ სავალდებულო ველები')
                  return
                }
                createFuel.mutate({ vid: fuelVehicleId, d: fuelForm })
              }}
              disabled={createFuel.isPending}
              className="btn-primary"
            >
              {createFuel.isPending ? 'ინახება...' : 'შენახვა'}
            </button>
          </div>
        </div>
      </Modal>

      {/* ── Service Create Modal ──────────────────────────────────── */}
      <Modal open={serviceModal} onClose={() => setServiceModal(false)} title="მომსახურების ჩანაწერი" size="md">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormField label="თარიღი" required>
              <input type="date" value={serviceForm.service_date} onChange={(e) => setServiceForm({ ...serviceForm, service_date: e.target.value })} className="input" />
            </FormField>
            <FormField label="ტიპი" required>
              <Select value={serviceForm.service_type} onChange={(e) => setServiceForm({ ...serviceForm, service_type: e.target.value })} options={serviceTypes} />
            </FormField>
          </div>
          <FormField label="აღწერა" required>
            <textarea value={serviceForm.description} onChange={(e) => setServiceForm({ ...serviceForm, description: e.target.value })} className="input" rows={3} placeholder="მომსახურების აღწერა" />
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="გარბენი (კმ)" required>
              <input type="number" value={serviceForm.mileage_at_service || ''} onChange={(e) => setServiceForm({ ...serviceForm, mileage_at_service: Number(e.target.value) })} className="input" />
            </FormField>
            <FormField label="ღირებულება">
              <input type="number" step="0.01" value={serviceForm.cost || ''} onChange={(e) => setServiceForm({ ...serviceForm, cost: Number(e.target.value) })} className="input" />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="სერვის ცენტრი">
              <input value={serviceForm.service_provider || ''} onChange={(e) => setServiceForm({ ...serviceForm, service_provider: e.target.value })} className="input" />
            </FormField>
            <FormField label="ინვოისის ნომერი">
              <input value={serviceForm.invoice_number || ''} onChange={(e) => setServiceForm({ ...serviceForm, invoice_number: e.target.value })} className="input" />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="შემდეგი მომსახურება (გარბენი)">
              <input type="number" value={serviceForm.next_service_mileage ?? ''} onChange={(e) => setServiceForm({ ...serviceForm, next_service_mileage: e.target.value ? Number(e.target.value) : null })} className="input" />
            </FormField>
            <FormField label="შემდეგი მომსახურება (თარიღი)">
              <input type="date" value={serviceForm.next_service_date || ''} onChange={(e) => setServiceForm({ ...serviceForm, next_service_date: e.target.value || null })} className="input" />
            </FormField>
          </div>
          <FormField label="შენიშვნა">
            <textarea value={serviceForm.notes || ''} onChange={(e) => setServiceForm({ ...serviceForm, notes: e.target.value })} className="input" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setServiceModal(false)} className="btn-secondary">გაუქმება</button>
            <button
              onClick={() => {
                if (!serviceForm.description.trim() || !serviceForm.mileage_at_service) {
                  setError('აღწერა და გარბენი სავალდებულოა')
                  return
                }
                createService.mutate({ vid: serviceVehicleId, d: serviceForm })
              }}
              disabled={createService.isPending}
              className="btn-primary"
            >
              {createService.isPending ? 'ინახება...' : 'შენახვა'}
            </button>
          </div>
        </div>
      </Modal>

      {/* ── Driver Create Modal ──────────────────────────────────── */}
      <Modal open={driverModal === 'create'} onClose={() => setDriverModal(null)} title="მძღოლის მინიჭება" size="md">
        <div className="space-y-4">
          <FormField label="მძღოლის სახელი" required>
            <input value={driverForm.driver_name} onChange={(e) => setDriverForm({ ...driverForm, driver_name: e.target.value })} className="input" />
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="ტელეფონი">
              <input value={driverForm.driver_phone || ''} onChange={(e) => setDriverForm({ ...driverForm, driver_phone: e.target.value })} className="input" />
            </FormField>
            <FormField label="მართვის მოწმობა">
              <input value={driverForm.driver_license || ''} onChange={(e) => setDriverForm({ ...driverForm, driver_license: e.target.value })} className="input" />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="მინიჭებული" required>
              <input type="date" value={driverForm.assigned_from} onChange={(e) => setDriverForm({ ...driverForm, assigned_from: e.target.value })} className="input" />
            </FormField>
            <FormField label="მოქმედებს">
              <input type="date" value={driverForm.assigned_until || ''} onChange={(e) => setDriverForm({ ...driverForm, assigned_until: e.target.value || null })} className="input" />
            </FormField>
          </div>
          <FormField label="შენიშვნა">
            <textarea value={driverForm.notes || ''} onChange={(e) => setDriverForm({ ...driverForm, notes: e.target.value })} className="input" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setDriverModal(null)} className="btn-secondary">გაუქმება</button>
            <button
              onClick={() => {
                if (!driverForm.driver_name.trim()) { setError('მძღოლის სახელი სავალდებულოა'); return }
                createDriver.mutate({ vid: driverVehicleId, d: driverForm })
              }}
              disabled={createDriver.isPending}
              className="btn-primary"
            >
              {createDriver.isPending ? 'ინახება...' : 'მინიჭება'}
            </button>
          </div>
        </div>
      </Modal>

      {/* ── Driver Edit Modal ─────────────────────────────────────── */}
      <Modal open={driverModal === 'edit'} onClose={() => setDriverModal(null)} title="მძღოლის რედაქტირება" size="md">
        <div className="space-y-4">
          <FormField label="მძღოლის სახელი">
            <input value={driverEditForm.driver_name || ''} onChange={(e) => setDriverEditForm({ ...driverEditForm, driver_name: e.target.value })} className="input" />
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="ტელეფონი">
              <input value={driverEditForm.driver_phone || ''} onChange={(e) => setDriverEditForm({ ...driverEditForm, driver_phone: e.target.value })} className="input" />
            </FormField>
            <FormField label="მართვის მოწმობა">
              <input value={driverEditForm.driver_license || ''} onChange={(e) => setDriverEditForm({ ...driverEditForm, driver_license: e.target.value })} className="input" />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="მინიჭებული">
              <input type="date" value={driverEditForm.assigned_from || ''} onChange={(e) => setDriverEditForm({ ...driverEditForm, assigned_from: e.target.value })} className="input" />
            </FormField>
            <FormField label="მოქმედებს">
              <input type="date" value={driverEditForm.assigned_until || ''} onChange={(e) => setDriverEditForm({ ...driverEditForm, assigned_until: e.target.value || null })} className="input" />
            </FormField>
          </div>
          <FormField label="სტატუსი">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={driverEditForm.is_active !== false} onChange={(e) => setDriverEditForm({ ...driverEditForm, is_active: e.target.checked })} className="rounded" />
              <span className="text-sm text-gray-700">აქტიური</span>
            </label>
          </FormField>
          <FormField label="შენიშვნა">
            <textarea value={driverEditForm.notes || ''} onChange={(e) => setDriverEditForm({ ...driverEditForm, notes: e.target.value })} className="input" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setDriverModal(null)} className="btn-secondary">გაუქმება</button>
            <button
              onClick={() => {
                if (!selectedDriver) return
                updateDriver.mutate({ id: selectedDriver.id, d: driverEditForm })
              }}
              disabled={updateDriver.isPending}
              className="btn-primary"
            >
              {updateDriver.isPending ? 'ინახება...' : 'შენახვა'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
