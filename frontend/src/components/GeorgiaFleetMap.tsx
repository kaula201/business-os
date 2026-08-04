import { useEffect, useMemo, useState } from 'react'
import { divIcon, latLngBounds } from 'leaflet'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'

import type { Vehicle } from '../types'

const GEORGIA_CENTER: [number, number] = [42.1, 43.5]

const vehicleIcon = divIcon({
  className: '',
  html: '<div style="width:34px;height:34px;border-radius:12px;background:#1d4ed8;color:white;display:flex;align-items:center;justify-content:center;border:3px solid white;box-shadow:0 4px 12px rgba(15,23,42,.28);font-size:17px">●</div>',
  iconSize: [34, 34],
  iconAnchor: [17, 17],
  popupAnchor: [0, -20],
})

function FitVehicleBounds({ vehicles }: { vehicles: Vehicle[] }) {
  const map = useMap()

  useEffect(() => {
    if (!vehicles.length) {
      map.setView(GEORGIA_CENTER, 7)
      return
    }
    if (vehicles.length === 1) {
      map.setView([Number(vehicles[0].latitude), Number(vehicles[0].longitude)], 12)
      return
    }
    const bounds = latLngBounds(
      vehicles.map((vehicle) => [Number(vehicle.latitude), Number(vehicle.longitude)] as [number, number]),
    )
    map.fitBounds(bounds, { padding: [45, 45], maxZoom: 12 })
  }, [map, vehicles])

  return null
}

/** Follow the app-wide dark class so map tiles match the theme. */
function useDarkMode(): boolean {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setDark(document.documentElement.classList.contains('dark'))
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])

  return dark
}

/** Renders the correct tile set: light OSM by day, CartoDB dark_matter at night. */
function DarkModeTileLayer() {
  const dark = useDarkMode()
  if (dark) {
    return (
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
    )
  }
  return (
    <TileLayer
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    />
  )
}

interface GeorgiaFleetMapProps {
  vehicles: Vehicle[]
  onSelectVehicle: (vehicle: Vehicle) => void
}

export default function GeorgiaFleetMap({ vehicles, onSelectVehicle }: GeorgiaFleetMapProps) {
  const locatedVehicles = useMemo(
    () => vehicles.filter((vehicle) => vehicle.latitude != null && vehicle.longitude != null),
    [vehicles],
  )
  const missingLocations = vehicles.length - locatedVehicles.length

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 dark:border-blue-900/50 dark:bg-blue-900/20">
          <div className="text-sm text-blue-700 dark:text-blue-300">რუკაზე ნაჩვენები</div>
          <div className="mt-1 text-2xl font-bold text-blue-950 dark:text-blue-100">{locatedVehicles.length}</div>
        </div>
        <div className="rounded-xl border border-amber-100 bg-amber-50 p-4 dark:border-amber-900/50 dark:bg-amber-900/20">
          <div className="text-sm text-amber-700 dark:text-amber-300">მდებარეობის გარეშე</div>
          <div className="mt-1 text-2xl font-bold text-amber-950 dark:text-amber-100">{missingLocations}</div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-dark-50 dark:bg-dark-200">
          <div className="text-sm text-gray-500">მოქმედება</div>
          <div className="mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100">marker-ზე დაჭერით გახსენით მანქანის ბარათი</div>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <div className="border-b border-gray-200 p-4 dark:border-dark-50">
          <h2 className="font-semibold text-gray-900 dark:text-gray-100">ავტოპარკი საქართველოს რუკაზე</h2>
          <p className="mt-1 text-sm text-gray-500">OpenStreetMap — ქალაქები, გზები და ავტომობილების დაფიქსირებული მდებარეობები</p>
        </div>
        <MapContainer center={GEORGIA_CENTER} zoom={7} minZoom={6} maxZoom={18} scrollWheelZoom className="h-[560px] w-full">
          <DarkModeTileLayer />
          <FitVehicleBounds vehicles={locatedVehicles} />
          {locatedVehicles.map((vehicle) => (
            <Marker
              key={vehicle.id}
              position={[Number(vehicle.latitude), Number(vehicle.longitude)]}
              icon={vehicleIcon}
            >
              <Popup>
                <div className="min-w-48 space-y-2">
                  <div className="font-bold">{vehicle.plate_number}</div>
                  <div>{vehicle.brand} {vehicle.model}</div>
                  <div className="text-sm text-gray-600">{vehicle.location_name || 'მდებარეობა მითითებულია კოორდინატებით'}</div>
                  <button
                    type="button"
                    onClick={() => onSelectVehicle(vehicle)}
                    className="rounded-md bg-blue-700 px-3 py-1.5 text-sm font-semibold text-white"
                  >
                    ბარათის გახსნა
                  </button>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      {missingLocations > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-300">
          {missingLocations} ავტომობილის მდებარეობა ჯერ არ არის მითითებული. გახსენით ავტომობილის რედაქტირება და აირჩიეთ ქალაქი ან ჩაწერეთ კოორდინატები.
        </div>
      )}
    </div>
  )
}
