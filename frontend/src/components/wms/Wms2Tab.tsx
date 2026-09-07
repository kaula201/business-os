import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, ScanBarcode, Truck, Boxes, ShieldAlert, CalendarClock, Coins, GitBranch, ArrowRightLeft, Package } from 'lucide-react'

import Modal from '../ui/Modal'
import { wmsOpsApi, productsApi, warehousesApi, suppliersApi } from '../../services/api'

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

function Section({ title, icon, children }: { title: string; icon: any; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-brandgray-200 dark:border-dark-50 p-4">
      <h3 className="font-semibold flex items-center gap-2 mb-3">{icon} {title}</h3>
      {children}
    </div>
  )
}

export default function Wms2Tab() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [uomOpen, setUomOpen] = useState(false)
  const [uomForm, setUomForm] = useState({ code: '', name: '', category: 'unit', is_base: false })
  const [convForm, setConvForm] = useState({ from_uom_id: '', to_uom_id: '', factor: '' })
  const [reorderForm, setReorderForm] = useState({ warehouse_id: '', product_id: '', min_quantity: '', max_quantity: '', reorder_quantity: '', lead_time_days: '0' })
  const [putawayForm, setPutawayForm] = useState({ name: '', product_id: '', zone_id: '', priority: '100' })
  const [abcForm, setAbcForm] = useState({ product_id: '', abc_class: 'A', xyz_class: 'X', is_quarantine: false, quarantine_reason: '' })
  const [cycleForm, setCycleForm] = useState({ warehouse_id: '', abc_class: 'A', frequency_days: '30' })
  const [consignForm, setConsignForm] = useState({ warehouse_id: '', product_id: '', owner_id: '', quantity: '', unit_cost: '' })
  const [waveForm, setWaveForm] = useState({ warehouse_id: '', notes: '' })
  const [xdForm, setXdForm] = useState({ source_warehouse_id: '', destination_warehouse_id: '', product_id: '', quantity: '' })
  const [shipForm, setShipForm] = useState({ warehouse_id: '', carrier: '', tracking_number: '', product_id: '', quantity: '' })
  const [gs1Input, setGs1Input] = useState('')
  const [gs1Result, setGs1Result] = useState<any>(null)
  const [err, setErr] = useState('')

  const { data: uoms } = useQuery({ queryKey: ['wms2-uoms'], queryFn: () => wmsOpsApi.listUoms().then((r: any) => r.data.data) })
  const { data: conversions } = useQuery({ queryKey: ['wms2-conversions'], queryFn: () => wmsOpsApi.listUomConversions().then((r: any) => r.data.data) })
  const { data: reorderRules } = useQuery({ queryKey: ['wms2-reorder'], queryFn: () => wmsOpsApi.listReorderRules().then((r: any) => r.data.data) })
  const { data: reorderSugg } = useQuery({ queryKey: ['wms2-reorder-sugg'], queryFn: () => wmsOpsApi.reorderSuggestions().then((r: any) => r.data.data) })
  const { data: putaway } = useQuery({ queryKey: ['wms2-putaway'], queryFn: () => wmsOpsApi.listPutawayStrategies().then((r: any) => r.data.data) })
  const { data: cycles } = useQuery({ queryKey: ['wms2-cycles'], queryFn: () => wmsOpsApi.listCycleCountSchedules().then((r: any) => r.data.data) })
  const { data: consign } = useQuery({ queryKey: ['wms2-consign'], queryFn: () => wmsOpsApi.listConsignmentStock().then((r: any) => r.data.data) })
  const { data: aging } = useQuery({ queryKey: ['wms2-aging'], queryFn: () => wmsOpsApi.stockAging().then((r: any) => r.data.data) })
  const { data: expiry } = useQuery({ queryKey: ['wms2-expiry'], queryFn: () => wmsOpsApi.expiryAlerts().then((r: any) => r.data.data) })
  const { data: abcxyz } = useQuery({ queryKey: ['wms2-abcxyz'], queryFn: () => wmsOpsApi.listAbcXyz().then((r: any) => r.data.data) })
  const { data: waves } = useQuery({ queryKey: ['wms2-waves'], queryFn: () => wmsOpsApi.listWaves().then((r: any) => r.data.data) })
  const { data: xds } = useQuery({ queryKey: ['wms2-xd'], queryFn: () => wmsOpsApi.listCrossDockOrders().then((r: any) => r.data.data) })
  const { data: ships } = useQuery({ queryKey: ['wms2-ships'], queryFn: () => wmsOpsApi.listShipments().then((r: any) => r.data.data) })
  const { data: lotZones } = useQuery({ queryKey: ['wms2-lotzones'], queryFn: () => wmsOpsApi.listLotZoneBalances().then((r: any) => r.data.data) })
  const { data: products } = useQuery({ queryKey: ['wms2-products'], queryFn: () => productsApi.list({ page_size: 100 }).then((r: any) => r.data.data.items) })
  const { data: warehouses } = useQuery({ queryKey: ['wms2-wh'], queryFn: () => warehousesApi.list().then((r: any) => r.data.data) })
  const { data: suppliers } = useQuery({ queryKey: ['wms2-suppliers'], queryFn: () => suppliersApi.list({ page_size: 100 }).then((r: any) => r.data.data.items) })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['wms2-'] })
  }

  const uomMut = useMutation({ mutationFn: () => wmsOpsApi.createUom(uomForm), onSuccess: () => { setUomOpen(false); setUomForm({ code: '', name: '', category: 'unit', is_base: false }); invalidate() }, onError: (e: any) => setErr(e.response?.data?.detail || 'UoM ვერ შეიქმნა') })
  const convMut = useMutation({ mutationFn: () => wmsOpsApi.createUomConversion(convForm), onSuccess: () => { setConvForm({ from_uom_id: '', to_uom_id: '', factor: '' }); invalidate() }, onError: (e: any) => setErr(e.response?.data?.detail || 'კონვერტაცია ვერ შეიქმნა') })
  const reorderMut = useMutation({ mutationFn: () => wmsOpsApi.upsertReorderRule(reorderForm), onSuccess: () => { setReorderForm({ warehouse_id: '', product_id: '', min_quantity: '', max_quantity: '', reorder_quantity: '', lead_time_days: '0' }); invalidate() }, onError: (e: any) => setErr(e.response?.data?.detail || 'Reorder rule ვერ შეიქმნა') })
  const putawayMut = useMutation({ mutationFn: () => wmsOpsApi.createPutawayStrategy(putawayForm), onSuccess: () => { setPutawayForm({ name: '', product_id: '', zone_id: '', priority: '100' }); invalidate() }, onError: (e: any) => setErr(e.response?.data?.detail || 'Putaway ვერ შეიქმნა') })
  const abcMut = useMutation({ mutationFn: () => wmsOpsApi.setAbcXyz(abcForm), onSuccess: () => { setAbcForm({ product_id: '', abc_class: 'A', xyz_class: 'X', is_quarantine: false, quarantine_reason: '' }); invalidate() }, onError: (e: any) => setErr(e.response?.data?.detail || 'კლასიფიკაცია ვერ შეინახა') })
  const cycleMut = useMutation({ mutationFn: () => wmsOpsApi.createCycleCountSchedule(cycleForm), onSuccess: () => { setCycleForm({ warehouse_id: '', abc_class: 'A', frequency_days: '30' }); invalidate() }, onError: (e: any) => setErr(e.response?.data?.detail || 'Cycle count ვერ შეიქმნა') })
  const consignMut = useMutation({ mutationFn: () => wmsOpsApi.upsertConsignmentStock(consignForm), onSuccess: () => { setConsignForm({ warehouse_id: '', product_id: '', owner_id: '', quantity: '', unit_cost: '' }); invalidate() }, onError: (e: any) => setErr(e.response?.data?.detail || 'Consignment ვერ შეინახა') })
  const waveMut = useMutation({ mutationFn: () => wmsOpsApi.createWave(waveForm), onSuccess: () => { setWaveForm({ warehouse_id: '', notes: '' }); invalidate() }, onError: (e: any) => setErr(e.response?.data?.detail || 'Wave ვერ შეიქმნა') })
  const waveCompleteMut = useMutation({ mutationFn: (id: string) => wmsOpsApi.completeWave(id), onSuccess: () => invalidate(), onError: (e: any) => setErr(e.response?.data?.detail || 'Wave ვერ დასრულდა') })
  const xdMut = useMutation({ mutationFn: () => wmsOpsApi.createCrossDockOrder({ source_warehouse_id: xdForm.source_warehouse_id, destination_warehouse_id: xdForm.destination_warehouse_id, items: [{ product_id: xdForm.product_id, quantity: Number(xdForm.quantity) }] }), onSuccess: () => { setXdForm({ source_warehouse_id: '', destination_warehouse_id: '', product_id: '', quantity: '' }); invalidate() }, onError: (e: any) => setErr(e.response?.data?.detail || 'Cross-dock ვერ შეიქმნა') })
  const shipMut = useMutation({ mutationFn: () => wmsOpsApi.createShipment({ warehouse_id: shipForm.warehouse_id, carrier: shipForm.carrier || undefined, tracking_number: shipForm.tracking_number || undefined, items: [{ product_id: shipForm.product_id, quantity: Number(shipForm.quantity) }] }), onSuccess: () => { setShipForm({ warehouse_id: '', carrier: '', tracking_number: '', product_id: '', quantity: '' }); invalidate() }, onError: (e: any) => setErr(e.response?.data?.detail || 'Shipment ვერ შეიქმნა') })
  const shipShipMut = useMutation({ mutationFn: (id: string) => wmsOpsApi.shipShipment(id), onSuccess: () => invalidate(), onError: (e: any) => setErr(e.response?.data?.detail || 'Shipment ვერ გაიგზავნა') })

  const productName = (id: string) => (products || []).find((p: any) => p.id === id)?.name || '—'
  const whName = (id: string) => (warehouses || []).find((w: any) => w.id === id)?.name || '—'

  return (
    <div className="space-y-4">
      {err && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{err}</div>}

      <div className="grid md:grid-cols-2 gap-4">
        {/* UoM */}
        <Section title={t('UoM და კონვერტაციები')} icon={<Boxes size={16} />}>
          <div className="flex flex-wrap gap-2 mb-3">
            <button className="btn-primary text-sm" onClick={() => setUomOpen(true)}><Plus size={14} className="inline mr-1" /> {t('ახალი UoM')}</button>
            <div className="flex gap-1 items-center">
              <select className="input text-sm py-1" value={convForm.from_uom_id} onChange={e => setConvForm({ ...convForm, from_uom_id: e.target.value })}>
                <option value="">{t('დან')}</option>
                {(uoms || []).map((u: any) => <option key={u.id} value={u.id}>{u.code}</option>)}
              </select>
              <span>→</span>
              <select className="input text-sm py-1" value={convForm.to_uom_id} onChange={e => setConvForm({ ...convForm, to_uom_id: e.target.value })}>
                <option value="">{t('მდე')}</option>
                {(uoms || []).map((u: any) => <option key={u.id} value={u.id}>{u.code}</option>)}
              </select>
              <input className="input text-sm py-1 w-20" placeholder="x" value={convForm.factor} onChange={e => setConvForm({ ...convForm, factor: e.target.value })} />
              <button className="btn-secondary text-sm" onClick={() => convMut.mutate()} disabled={!convForm.from_uom_id || !convForm.to_uom_id || !convForm.factor}>OK</button>
            </div>
          </div>
          <div className="space-y-1 text-sm">
            {(uoms || []).map((u: any) => (
              <div key={u.id} className="flex justify-between p-1.5 border-b dark:border-dark-50">
                <span className="font-medium">{u.code} — {u.name}</span>
                <span className="text-gray-500">{u.category}{u.is_base ? ' · base' : ''}</span>
              </div>
            ))}
            {(conversions || []).length > 0 && (
              <div className="pt-2 text-xs text-gray-500">
                {(conversions || []).map((c: any) => (
                  <div key={c.id} className="flex justify-between">
                    <span>{uoms?.find((u: any) => u.id === c.from_uom_id)?.code} → {uoms?.find((u: any) => u.id === c.to_uom_id)?.code}</span>
                    <span className="font-mono">× {c.factor}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Section>

        {/* Reorder rules */}
        <Section title={t('Reorder rules (საწყობის მიხედვით)')} icon={<Package size={16} />}>
          <div className="grid grid-cols-2 gap-2 mb-2">
            <select className={inputCls} value={reorderForm.warehouse_id} onChange={e => setReorderForm({ ...reorderForm, warehouse_id: e.target.value })}>
              <option value="">{t('საწყობი')}</option>
              {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
            <select className={inputCls} value={reorderForm.product_id} onChange={e => setReorderForm({ ...reorderForm, product_id: e.target.value })}>
              <option value="">{t('პროდუქტი')}</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <input className={inputCls} placeholder={t('მინ')} type="number" value={reorderForm.min_quantity} onChange={e => setReorderForm({ ...reorderForm, min_quantity: e.target.value })} />
            <input className={inputCls} placeholder={t('მაქს')} type="number" value={reorderForm.max_quantity} onChange={e => setReorderForm({ ...reorderForm, max_quantity: e.target.value })} />
            <input className={inputCls} placeholder={t('შეკვეთის რაოდენობა')} type="number" value={reorderForm.reorder_quantity} onChange={e => setReorderForm({ ...reorderForm, reorder_quantity: e.target.value })} />
            <input className={inputCls} placeholder={t('Lead time (დღე)')} type="number" value={reorderForm.lead_time_days} onChange={e => setReorderForm({ ...reorderForm, lead_time_days: e.target.value })} />
          </div>
          <button className="btn-primary text-sm w-full" onClick={() => reorderMut.mutate()} disabled={!reorderForm.warehouse_id || !reorderForm.product_id}>{t('შენახვა')}</button>
          {reorderSugg?.length > 0 && (
            <div className="mt-3 space-y-1">
              <p className="text-xs font-semibold text-amber-600">{t('შევსების საჭიროება')}</p>
              {reorderSugg.map((s: any, i: number) => (
                <div key={i} className="flex justify-between text-xs p-2 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
                  <span>{productName(s.product_id)} ({whName(s.warehouse_id)})</span>
                  <span className="font-mono">{s.on_hand} / {s.min_quantity} → {s.suggested_order}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Putaway */}
        <Section title={t('Putaway strategy')} icon={<ArrowRightLeft size={16} />}>
          <div className="grid grid-cols-2 gap-2 mb-2">
            <input className={inputCls} placeholder={t('სახელი')} value={putawayForm.name} onChange={e => setPutawayForm({ ...putawayForm, name: e.target.value })} />
            <input className={inputCls} placeholder={t('პრიორიტეტი')} type="number" value={putawayForm.priority} onChange={e => setPutawayForm({ ...putawayForm, priority: e.target.value })} />
            <select className={inputCls} value={putawayForm.product_id} onChange={e => setPutawayForm({ ...putawayForm, product_id: e.target.value })}>
              <option value="">{t('პროდუქტი')}</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <select className={inputCls} value={putawayForm.zone_id} onChange={e => setPutawayForm({ ...putawayForm, zone_id: e.target.value })}>
              <option value="">{t('ზონა')}</option>
              {(warehouses || []).flatMap((w: any) => (w.zones || []).map((z: any) => <option key={z.id} value={z.id}>{w.name} / {z.code}</option>))}
            </select>
          </div>
          <button className="btn-primary text-sm w-full" onClick={() => putawayMut.mutate()} disabled={!putawayForm.name || !putawayForm.zone_id}>{t('შენახვა')}</button>
          {(putaway || []).length > 0 && (
            <div className="mt-2 space-y-1 text-xs">
              {(putaway || []).map((p: any) => (
                <div key={p.id} className="flex justify-between p-1.5 border-b dark:border-dark-50">
                  <span>{p.name}</span><span className="text-gray-500">P{p.priority}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* ABC/XYZ + quarantine */}
        <Section title={t('ABC/XYZ + Quarantine')} icon={<ShieldAlert size={16} />}>
          <div className="grid grid-cols-2 gap-2 mb-2">
            <select className={inputCls} value={abcForm.product_id} onChange={e => setAbcForm({ ...abcForm, product_id: e.target.value })}>
              <option value="">{t('პროდუქტი')}</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <div className="flex gap-1">
              <select className={inputCls} value={abcForm.abc_class} onChange={e => setAbcForm({ ...abcForm, abc_class: e.target.value })}>
                <option value="A">A</option><option value="B">B</option><option value="C">C</option>
              </select>
              <select className={inputCls} value={abcForm.xyz_class} onChange={e => setAbcForm({ ...abcForm, xyz_class: e.target.value })}>
                <option value="X">X</option><option value="Y">Y</option><option value="Z">Z</option>
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm col-span-2">
              <input type="checkbox" checked={abcForm.is_quarantine} onChange={e => setAbcForm({ ...abcForm, is_quarantine: e.target.checked })} /> {t('Quarantine')}
            </label>
            {abcForm.is_quarantine && (
              <input className={`${inputCls} col-span-2`} placeholder={t('მიზეზი')} value={abcForm.quarantine_reason} onChange={e => setAbcForm({ ...abcForm, quarantine_reason: e.target.value })} />
            )}
          </div>
          <button className="btn-primary text-sm w-full" onClick={() => abcMut.mutate()} disabled={!abcForm.product_id}>{t('შენახვა')}</button>
          {(abcxyz || []).filter((p: any) => p.abc_class || p.xyz_class || p.is_quarantine).length > 0 && (
            <div className="mt-2 space-y-1 text-xs">
              {(abcxyz || []).filter((p: any) => p.abc_class || p.xyz_class || p.is_quarantine).map((p: any) => (
                <div key={p.product_id} className="flex justify-between p-1.5 border-b dark:border-dark-50">
                  <span>{p.name}</span>
                  <span className="font-mono">{p.abc_class || '—'}/{p.xyz_class || '—'}{p.is_quarantine ? ' ⚠' : ''}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Cycle count */}
        <Section title={t('Cycle-count scheduler')} icon={<CalendarClock size={16} />}>
          <div className="grid grid-cols-3 gap-2 mb-2">
            <select className={inputCls} value={cycleForm.warehouse_id} onChange={e => setCycleForm({ ...cycleForm, warehouse_id: e.target.value })}>
              <option value="">{t('საწყობი')}</option>
              {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
            <select className={inputCls} value={cycleForm.abc_class} onChange={e => setCycleForm({ ...cycleForm, abc_class: e.target.value })}>
              <option value="A">A</option><option value="B">B</option><option value="C">C</option>
            </select>
            <input className={inputCls} placeholder={t('სიხშირე (დღე)')} type="number" value={cycleForm.frequency_days} onChange={e => setCycleForm({ ...cycleForm, frequency_days: e.target.value })} />
          </div>
          <button className="btn-primary text-sm w-full" onClick={() => cycleMut.mutate()} disabled={!cycleForm.warehouse_id}>{t('შენახვა')}</button>
          {(cycles || []).length > 0 && (
            <div className="mt-2 space-y-1 text-xs">
              {(cycles || []).map((c: any) => (
                <div key={c.id} className="flex justify-between p-1.5 border-b dark:border-dark-50">
                  <span>{whName(c.warehouse_id)} — {c.abc_class}</span>
                  <span className="text-gray-500">{c.frequency_days} დღე{c.next_run_date ? ` · ${c.next_run_date.slice(0, 10)}` : ''}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Consignment */}
        <Section title={t('Consignment stock')} icon={<Coins size={16} />}>
          <div className="grid grid-cols-2 gap-2 mb-2">
            <select className={inputCls} value={consignForm.warehouse_id} onChange={e => setConsignForm({ ...consignForm, warehouse_id: e.target.value })}>
              <option value="">{t('საწყობი')}</option>
              {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
            <select className={inputCls} value={consignForm.owner_id} onChange={e => setConsignForm({ ...consignForm, owner_id: e.target.value })}>
              <option value="">{t('მფლობელი')}</option>
              {(suppliers || []).map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <select className={inputCls} value={consignForm.product_id} onChange={e => setConsignForm({ ...consignForm, product_id: e.target.value })}>
              <option value="">{t('პროდუქტი')}</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <div className="flex gap-1">
              <input className={inputCls} placeholder={t('რაოდენობა')} type="number" value={consignForm.quantity} onChange={e => setConsignForm({ ...consignForm, quantity: e.target.value })} />
              <input className={inputCls} placeholder={t('ფასი')} type="number" value={consignForm.unit_cost} onChange={e => setConsignForm({ ...consignForm, unit_cost: e.target.value })} />
            </div>
          </div>
          <button className="btn-primary text-sm w-full" onClick={() => consignMut.mutate()} disabled={!consignForm.warehouse_id || !consignForm.product_id || !consignForm.owner_id}>{t('შენახვა')}</button>
          {(consign || []).length > 0 && (
            <div className="mt-2 space-y-1 text-xs">
              {(consign || []).map((c: any) => (
                <div key={c.id} className="flex justify-between p-1.5 border-b dark:border-dark-50">
                  <span>{productName(c.product_id)}</span>
                  <span className="font-mono">{c.quantity} @ {c.unit_cost || '—'}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Waves */}
        <Section title={t('Wave picking')} icon={<GitBranch size={16} />}>
          <div className="flex gap-2 mb-2">
            <select className={inputCls} value={waveForm.warehouse_id} onChange={e => setWaveForm({ ...waveForm, warehouse_id: e.target.value })}>
              <option value="">{t('საწყობი')}</option>
              {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
            <input className={inputCls} placeholder={t('შენიშვნა')} value={waveForm.notes} onChange={e => setWaveForm({ ...waveForm, notes: e.target.value })} />
            <button className="btn-primary text-sm" onClick={() => waveMut.mutate()} disabled={!waveForm.warehouse_id}><Plus size={14} /></button>
          </div>
          {(waves || []).length > 0 && (
            <div className="space-y-1 text-xs">
              {(waves || []).map((w: any) => (
                <div key={w.id} className="flex justify-between items-center p-1.5 border-b dark:border-dark-50">
                  <span className="font-mono font-semibold">{w.wave_number}</span>
                  <span className="text-gray-500">{w.status}</span>
                  {w.status === 'planned' && (
                    <button className="text-emerald-600 font-medium" onClick={() => waveCompleteMut.mutate(w.id)}>{t('დასრულება')}</button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Cross-dock */}
        <Section title={t('Cross-docking')} icon={<ArrowRightLeft size={16} />}>
          <div className="grid grid-cols-2 gap-2 mb-2">
            <select className={inputCls} value={xdForm.source_warehouse_id} onChange={e => setXdForm({ ...xdForm, source_warehouse_id: e.target.value })}>
              <option value="">{t('წყარო')}</option>
              {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
            <select className={inputCls} value={xdForm.destination_warehouse_id} onChange={e => setXdForm({ ...xdForm, destination_warehouse_id: e.target.value })}>
              <option value="">{t('დანიშნულება')}</option>
              {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
            <select className={inputCls} value={xdForm.product_id} onChange={e => setXdForm({ ...xdForm, product_id: e.target.value })}>
              <option value="">{t('პროდუქტი')}</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <input className={inputCls} placeholder={t('რაოდენობა')} type="number" value={xdForm.quantity} onChange={e => setXdForm({ ...xdForm, quantity: e.target.value })} />
          </div>
          <button className="btn-primary text-sm w-full" onClick={() => xdMut.mutate()} disabled={!xdForm.source_warehouse_id || !xdForm.destination_warehouse_id || !xdForm.product_id}>{t('შექმნა')}</button>
          {(xds || []).length > 0 && (
            <div className="mt-2 space-y-1 text-xs">
              {(xds || []).map((x: any) => (
                <div key={x.id} className="flex justify-between p-1.5 border-b dark:border-dark-50">
                  <span className="font-mono font-semibold">{x.cross_dock_number}</span>
                  <span className="text-gray-500">{x.status}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Shipments */}
        <Section title={t('Shipping / Carrier')} icon={<Truck size={16} />}>
          <div className="grid grid-cols-2 gap-2 mb-2">
            <select className={inputCls} value={shipForm.warehouse_id} onChange={e => setShipForm({ ...shipForm, warehouse_id: e.target.value })}>
              <option value="">{t('საწყობი')}</option>
              {(warehouses || []).map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
            <input className={inputCls} placeholder={t('Carrier')} value={shipForm.carrier} onChange={e => setShipForm({ ...shipForm, carrier: e.target.value })} />
            <input className={inputCls} placeholder={t('Tracking')} value={shipForm.tracking_number} onChange={e => setShipForm({ ...shipForm, tracking_number: e.target.value })} />
            <select className={inputCls} value={shipForm.product_id} onChange={e => setShipForm({ ...shipForm, product_id: e.target.value })}>
              <option value="">{t('პროდუქტი')}</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <input className={inputCls} placeholder={t('რაოდენობა')} type="number" value={shipForm.quantity} onChange={e => setShipForm({ ...shipForm, quantity: e.target.value })} />
          </div>
          <button className="btn-primary text-sm w-full" onClick={() => shipMut.mutate()} disabled={!shipForm.warehouse_id || !shipForm.product_id || !shipForm.quantity}>{t('შექმნა')}</button>
          {(ships || []).length > 0 && (
            <div className="mt-2 space-y-1 text-xs">
              {(ships || []).map((s: any) => (
                <div key={s.id} className="flex justify-between items-center p-1.5 border-b dark:border-dark-50">
                  <span className="font-mono font-semibold">{s.shipment_number}</span>
                  <span className="text-gray-500">{s.carrier || ''} {s.tracking_number ? `#${s.tracking_number}` : ''}</span>
                  <span className="text-gray-500">{s.status}</span>
                  {s.status === 'draft' && (
                    <button className="text-emerald-600 font-medium" onClick={() => shipShipMut.mutate(s.id)}>{t('გაგზავნა')}</button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* GS1 */}
        <Section title={t('GS1 barcode')} icon={<ScanBarcode size={16} />}>
          <div className="flex gap-2 mb-2">
            <input className={inputCls} placeholder="(01)...(10)...(17)..." value={gs1Input} onChange={e => setGs1Input(e.target.value)} />
            <button className="btn-primary text-sm" onClick={() => wmsOpsApi.parseGs1(gs1Input).then((r: any) => setGs1Result(r.data.data)).catch((e: any) => setErr(e.response?.data?.detail || 'GS1 ვერ გაშიფრდა'))}>{t('გაშიფვრა')}</button>
          </div>
          {gs1Result && (
            <div className="space-y-1 text-xs">
              {Object.entries(gs1Result).map(([k, v]) => (
                <div key={k} className="flex justify-between p-1.5 bg-gray-50 dark:bg-dark-100 rounded-lg">
                  <span className="font-mono font-semibold">({k})</span><span className="font-mono">{String(v)}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Aging + expiry + lot zones */}
        <Section title={t('Stock aging / Expiry / Lot zones')} icon={<CalendarClock size={16} />}>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <p className="font-semibold mb-1">{t('Aging')}</p>
              {(aging || []).length === 0 && <p className="text-gray-500">{t('არ არის')}</p>}
              {(aging || []).slice(0, 5).map((a: any, i: number) => (
                <div key={i} className="flex justify-between p-1 border-b dark:border-dark-50">
                  <span className="truncate">{productName(a.product_id)}</span>
                  <span className="font-mono">{a.last_movement_days ?? '—'} დღე</span>
                </div>
              ))}
            </div>
            <div>
              <p className="font-semibold mb-1 text-amber-600">{t('Expiry')}</p>
              {(expiry || []).length === 0 && <p className="text-gray-500">{t('არ არის')}</p>}
              {(expiry || []).map((e: any) => (
                <div key={e.batch_id} className="flex justify-between p-1 border-b dark:border-dark-50">
                  <span className="truncate">{e.batch_number}</span>
                  <span className="font-mono">{e.expiry_date?.slice(0, 10)}</span>
                </div>
              ))}
            </div>
            <div>
              <p className="font-semibold mb-1">{t('Lot zones')}</p>
              {(lotZones || []).length === 0 && <p className="text-gray-500">{t('არ არის')}</p>}
              {(lotZones || []).map((l: any) => (
                <div key={l.id} className="flex justify-between p-1 border-b dark:border-dark-50">
                  <span className="truncate">{l.batch_id.slice(0, 8)}</span>
                  <span className="font-mono">{l.quantity}</span>
                </div>
              ))}
            </div>
          </div>
        </Section>
      </div>

      <Modal open={uomOpen} onClose={() => setUomOpen(false)} title={t('ახალი UoM')}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">{t('კოდი')}</label>
              <input className={inputCls} value={uomForm.code} onChange={e => setUomForm({ ...uomForm, code: e.target.value })} placeholder="PCS" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">{t('სახელი')}</label>
              <input className={inputCls} value={uomForm.name} onChange={e => setUomForm({ ...uomForm, name: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">{t('კატეგორია')}</label>
            <select className={inputCls} value={uomForm.category} onChange={e => setUomForm({ ...uomForm, category: e.target.value })}>
              <option value="unit">unit</option><option value="weight">weight</option><option value="volume">volume</option><option value="length">length</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={uomForm.is_base} onChange={e => setUomForm({ ...uomForm, is_base: e.target.checked })} /> {t('ბაზის ერთეული')}
          </label>
          <button className="btn-primary w-full" onClick={() => uomMut.mutate()} disabled={!uomForm.code || !uomForm.name}>{t('შენახვა')}</button>
        </div>
      </Modal>
    </div>
  )
}
