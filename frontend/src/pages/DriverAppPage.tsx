import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Truck, MapPin, Phone, User, Navigation, CheckCircle2, XCircle, Camera } from 'lucide-react'
import { fleetApi } from '../services/api'

interface Stop {
  id: string
  sequence: number
  address: string
  contact_name?: string | null
  contact_phone?: string | null
  status: string
  arrived_at?: string | null
  delivered_qty?: string | null
  exception?: string | null
}

interface Trip {
  id: string
  trip_number: string
  status: string
  planned_start?: string | null
  stops?: Stop[]
  total_weight_kg: string
}

const statusBadge: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-600',
  arrived: 'bg-amber-100 text-amber-700',
  delivered: 'bg-green-100 text-green-700',
  partial: 'bg-orange-100 text-orange-700',
  failed: 'bg-red-100 text-red-700',
}

export default function DriverAppPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [activeTrip, setActiveTrip] = useState<Trip | null>(null)
  const [gps, setGps] = useState<{ lat: number; lng: number; ts: number } | null>(null)
  const [gpsErr, setGpsErr] = useState('')
  const [evidenceFor, setEvidenceFor] = useState<{ podId: string; kind: 'photo' | 'signature' } | null>(null)
  const gpsRef = useRef<{ lat: number; lng: number } | null>(null)
  const tripIdRef = useRef<string | null>(null)

  const telemetryTrip = useMutation({
    mutationFn: (payload: { trip_id: string; lat: number; lng: number; device_id?: string }) =>
      fleetApi.postTelemetry(payload.trip_id, { ...payload }),
  })

  useEffect(() => {
    if (!('geolocation' in navigator)) {
      setGpsErr('GPS არ არის ხელმისაწვდომი')
      return
    }
    const tick = () => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const point = { lat: pos.coords.latitude, lng: pos.coords.longitude }
          gpsRef.current = point
          setGps({ ...point, ts: Date.now() })
          const tid = tripIdRef.current
          if (tid) {
            telemetryTrip.mutate({ trip_id: tid, lat: point.lat, lng: point.lng, device_id: 'driver-web' })
          }
        },
        () => setGpsErr('GPS წვდომა ვერ მოხერხდა'),
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 5000 },
      )
    }
    tick()
    const iv = setInterval(tick, 10000)
    return () => clearInterval(iv)
  }, [])

  // ── my profile + trips (driver board, scoped to this driver account)
  const driverQuery = useQuery({
    queryKey: ['driver-me'],
    queryFn: () => fleetApi.driverMe(),
    retry: false,
  })
  const tripsQuery = useQuery({
    queryKey: ['driver-trips'],
    queryFn: () => fleetApi.listTrips('dispatched').then((r: any) => r.data.data as Trip[]),
    retry: false,
  })

  const openTrip = async (tripId: string) => {
    const res = await fleetApi.getTrip(tripId)
    setActiveTrip((res as any).data.data)
    tripIdRef.current = tripId
    // first GPS sync right away
    if (gpsRef.current) telemetryTrip.mutate({ trip_id: tripId, lat: gpsRef.current.lat, lng: gpsRef.current.lng, device_id: 'driver-web' })
  }

  const stopEvent = useMutation({
    mutationFn: ({ stopId, ev, qty }: { stopId: string; ev: string; qty?: number }) =>
      fleetApi.stopEvent(stopId, { event: ev, delivered_qty: qty, recipient_name: 'მძღოლი' }),
    onMutate: async (vars) => {
      // offline-first: enqueue first, flush after optimistic UI
      const online = typeof navigator !== 'undefined' ? navigator.onLine !== false : true
      if (!online) {
        const q = await loadQueue()
        q.push({ type: 'stop_event', ...vars, queued: Date.now() })
        await saveQueue(q)
        setOfflineCount((c) => c + 1)
      }
    },
    onSuccess: () => {
      if (activeTrip) openTrip(activeTrip.id)
      queryClient.invalidateQueries({ queryKey: ['driver-trips'] })
    },
  })

  // offline queue persistence (IndexedDB-style via localStorage for the PWA)
  const [offlineCount, setOfflineCount] = useState(0)
  const loadQueue = async (): Promise<any[]> => {
    try {
      return JSON.parse(localStorage.getItem('driver_offline_queue') || '[]')
    } catch {
      return []
    }
  }
  const saveQueue = async (q: any[]) => {
    localStorage.setItem('driver_offline_queue', JSON.stringify(q.filter((x, i) => i < 200)))
  }
  // flush queue when back online
  useEffect(() => {
    const flush = async () => {
      const q = await loadQueue()
      if (q.length === 0) return
      const online = navigator.onLine !== false
      if (!online) return
      const remaining: any[] = []
      for (const item of q) {
        try {
          if (item.type === 'stop_event') {
            await fleetApi.stopEvent(item.stopId, { event: item.ev, delivered_qty: item.qty, recipient_name: 'მძღოლი' })
          } else if (item.type === 'evidence') {
            await fleetApi.podEvidence(item.podId, { data: item.data, kind: item.kind })
          }
        } catch {
          remaining.push(item)
        }
      }
      await saveQueue(remaining)
      setOfflineCount(remaining.length)
      queryClient.invalidateQueries({ queryKey: ['driver-trips'] })
    }
    flush()
    window.addEventListener('online', flush)
    return () => window.removeEventListener('online', flush)
  }, [])

  const evidenceMutation = useMutation({
    mutationFn: ({ podId, data, kind }: { podId: string; data: string; kind: 'photo' | 'signature' }) =>
      fleetApi.podEvidence(podId, { data, kind }),
    onMutate: async (vars) => {
      if (typeof navigator !== 'undefined' && navigator.onLine === false) {
        const q = await loadQueue()
        q.push({ type: 'evidence', ...vars, queued: Date.now() })
        await saveQueue(q)
        setOfflineCount((c) => c + 1)
      }
    },
    onSuccess: () => setEvidenceFor(null),
  })

  // capture photo from device
  const capturePhoto = (podId: string) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    input.onchange = () => {
      const f = input.files?.[0]
      if (!f) return
      const reader = new FileReader()
      reader.onload = () => evidenceMutation.mutate({ podId, data: String(reader.result), kind: 'photo' })
      reader.readAsDataURL(f)
    }
    input.click()
  }

  const trips: Trip[] = tripsQuery.data || []
  const driver = (driverQuery.data as any)?.driver
  const activeTripId = activeTrip?.id

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <Truck className="h-5 w-5 text-blue-600" /> {t('მძღოლის აპი')}
          {driver?.name && <span className="text-sm font-normal text-gray-500">— {driver.name}</span>}
        </h1>
        <span className="flex items-center gap-1 rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">
          <Navigation className="h-3 w-3" />
          {gps ? `GPS: ${gps.lat.toFixed(4)}, ${gps.lng.toFixed(4)}` : (gpsErr || t('GPS-ის ლოდინი...'))}
        </span>
        {offlineCount > 0 && (
          <span className="rounded-full bg-amber-500 px-2 py-1 text-xs text-white" title={t('ოფლაინის რიგი')}>
            ⌛ {offlineCount} {t('ოფლაინი')}
          </span>
        )}
      </header>

      {/* Active trip live view */}
      {activeTrip ? (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold">{activeTrip.trip_number}</p>
              <p className="text-xs text-gray-500">{activeTrip.status}</p>
            </div>
            <button onClick={() => { setActiveTrip(null); tripIdRef.current = null }} className="rounded border border-blue-300 px-2 py-1 text-xs">
              ← {t('დახურვა')}
            </button>
          </div>
          {/* ordered stops */}
          <div className="mt-3 space-y-2">
            {(activeTrip.stops || []).map((stop: Stop, i: number) => (
              <div key={stop.id} className="rounded-lg border border-gray-200 bg-white p-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-xs text-white">{i + 1}</span>
                    <div>
                      <p className="text-sm font-medium">{stop.address}</p>
                      {(stop.contact_name || stop.contact_phone) && (
                        <p className="text-xs text-gray-500">
                          {stop.contact_name}
                          {stop.contact_phone && ` · ${stop.contact_phone}`}
                        </p>
                      )}
                    </div>
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${statusBadge[stop.status] || 'bg-gray-100 text-gray-600'}`}>{stop.status}</span>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {stop.status === 'pending' && (
                    <button onClick={() => stopEvent.mutate({ stopId: stop.id, ev: 'arrive' })} className="rounded bg-blue-600 px-3 py-1.5 text-xs text-white">
                      {t('ჩასვლა')}
                    </button>)}
                  {stop.status === 'arrived' && (
                    <>
                      <button onClick={() => stopEvent.mutate({ stopId: stop.id, ev: 'deliver', qty: 10 })} className="rounded bg-green-600 px-3 py-1.5 text-xs text-white">
                        <CheckCircle2 className="mr-1 inline h-3 w-3" />{t('მიწოდება')}
                      </button>
                      <button onClick={() => stopEvent.mutate({ stopId: stop.id, ev: 'fail', qty: 0 })} className="rounded bg-red-600 px-3 py-1.5 text-xs text-white">
                        <XCircle className="mr-1 inline h-3 w-3" />{t('ჩავარდენა')}
                      </button>
                      <button onClick={() => { setEvidenceFor({ podId: stop.id, kind: 'photo' }); capturePhoto(stop.id) }} className="rounded border border-gray-300 px-3 py-1.5 text-xs">
                        <Camera className="mr-1 inline h-3 w-3" />{t('ფოტო')}
                      </button>
                    </>)}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {driverQuery.isError && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-center text-sm text-amber-700">
              {t('ეს აქაუნთი მძღოლს არ უკავშირდება')}
            </div>
          )}
          {trips.length === 0 && (
            <div className="rounded-xl border border-gray-200 bg-white p-6 text-center text-sm text-gray-500">
              {t('აქტიური რეისები არ არის')}
            </div>
          )}
          {trips.map((tp) => (
            <button key={tp.id} onClick={() => openTrip(tp.id)} className="w-full rounded-xl border border-gray-200 bg-white p-4 text-left hover:border-blue-300">
              <div className="flex items-center justify-between">
                <span className="font-semibold">{tp.trip_number}</span>
                <span className="text-xs text-gray-500">{tp.status}</span>
              </div>
              <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
                <Navigation className="h-3 w-3" />
                {tp.planned_start ? new Date(tp.planned_start).toLocaleString('ka-GE', { dateStyle: 'short', timeStyle: 'short' }) : '—'}
                <span>·</span>
                {tp.total_weight_kg} kg
              </div>
            </button>
          ))}
        </div>
      )}

      {evidenceFor && (
        <div className="rounded-lg bg-gray-50 p-3 text-xs text-gray-500">
          {t('ფოტოს მიმაგრება...')} — {evidenceFor.kind}
        </div>
      )}
    </div>
  )
}
