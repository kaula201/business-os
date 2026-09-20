import { useEffect, useMemo } from 'react'
import { Circle, CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { divIcon, latLngBounds } from 'leaflet'
import { useTranslation } from 'react-i18next'

const GEORGIA_CENTER: [number, number] = [42.1, 43.5]

const stopIcon = divIcon({
  className: '',
  html: '<div style="width:26px;height:26px;border-radius:50%;background:#0ea5e9;color:white;display:flex;align-items:center;justify-content:center;border:3px solid white;box-shadow:0 3px 10px rgba(2,132,199,.35);font-size:12px;font-weight:700">●</div>',
  iconSize: [26, 26],
  iconAnchor: [13, 13],
})
const liveIcon = divIcon({
  className: '',
  html: '<div style="width:34px;height:34px;border-radius:50%;background:#dc2626;color:white;display:flex;align-items:center;justify-content:center;border:3px solid white;box-shadow:0 4px 12px rgba(220,38,38,.4);font-size:16px">🚚</div>',
  iconSize: [34, 34],
  iconAnchor: [17, 17],
})

function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (!points.length) { map.setView(GEORGIA_CENTER, 7); return }
    if (points.length === 1) { map.setView(points[0], 12); return }
    map.fitBounds(latLngBounds(points), { padding: [40, 40], maxZoom: 13 })
  }, [map, points])
  return null
}

/** Dark-mode aware tile layer (matches the rest of the app). */
function Tiles() {
  const { t } = useTranslation()
  const dark = typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
  if (dark) {
    return <TileLayer attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>' url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
  }
  return <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
}

export default function LiveRouteMap({ history }: { history: any }) {
  const track: [number, number][] = useMemo(
    () => (history.track || []).map((p: any) => [Number(p.lat), Number(p.lng)]),
    [history],
  )
  const stops = history.stops || []
  const fences = history.geofences || []
  const all: [number, number][] = useMemo(() => {
    const pts: [number, number][] = [...track]
    stops.forEach((s: any) => pts.push([Number(s.lat), Number(s.lng)]))
    fences.forEach((f: any) => pts.push([Number(f.lat), Number(f.lng)]))
    return pts
  }, [track, stops, fences])

  const last = track[track.length - 1]

  return (
    <MapContainer center={GEORGIA_CENTER} zoom={7} minZoom={6} maxZoom={18} scrollWheelZoom className="h-[460px] w-full">
      <Tiles />
      <FitBounds points={all} />

      {/* GPS track as a polyline */}
      {track.length > 0 && (
        <Polyline positions={track} pathOptions={{ color: '#2563eb', weight: 3, opacity: 0.8 }} />
      )}

      {/* live vehicle marker */}
      {last && <CircleMarker center={last} pathOptions={{ color: '#dc2626', weight: 2, fillColor: '#dc2626', fillOpacity: 1 }} radius={8} />}

      {/* stop geo-pins */}
      {stops.map((s: any, i: number) => (
        <CircleMarker
          key={s.stop_id || i}
          center={[Number(s.lat), Number(s.lng)]}
          pathOptions={{ color: s.status === 'delivered' ? '#16a34a' : '#0ea5e9', weight: 2, fillColor: s.status === 'delivered' ? '#16a34a' : '#0ea5e9', fillOpacity: 0.7 }}
          radius={9}
        >
          <Tooltip direction="top">{`${i + 1}. ${s.address} (${s.status})`}</Tooltip>
        </CircleMarker>
      ))}

      {/* geofence circles */}
      {fences.map((f: any) => (
        <Circle key={f.stop_id} center={[Number(f.lat), Number(f.lng)]} radius={f.radius_m} pathOptions={{ color: '#f59e0b', weight: 1.5, dashArray: '5 5', fillColor: '#f59e0b', fillOpacity: 0.06 }} />
      ))}
    </MapContainer>
  )
}
