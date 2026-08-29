import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BadgeCheck, Plus, CheckCircle2, AlertTriangle, ScanLine } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { qualityApi } from '../services/api'

export default function QualityPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'points' | 'alerts'>('points')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<Record<string, any>>({})
  const [barcode, setBarcode] = useState('')
  const [scanResult, setScanResult] = useState<string | null>(null)

  const { data: points } = useQuery({ queryKey: ['quality-points'], queryFn: () => qualityApi.controlPoints().then(r => r.data.data) })
  const { data: alerts } = useQuery({ queryKey: ['quality-alerts'], queryFn: () => qualityApi.alerts().then(r => r.data.data) })
  const { data: checks } = useQuery({ queryKey: ['quality-checks'], queryFn: () => qualityApi.checks().then(r => r.data.data.items) })

  const createPoint = useMutation({
    mutationFn: () => qualityApi.createControlPoint({ name: form.name, point_type: form.point_type }),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['quality-points'] }) },
  })
  const createAlert = useMutation({
    mutationFn: () => qualityApi.createAlert({ title: form.title, priority: form.priority, description: form.description }),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['quality-alerts'] }) },
  })
  const resolveAlert = useMutation({
    mutationFn: (id: string) => qualityApi.resolveAlert(id, { resolution: 'დახურულია' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quality-alerts'] }),
  })
  const scanBarcode = useMutation({
    mutationFn: () => qualityApi.scan(barcode),
    onSuccess: (r) => {
      setScanResult(`✅ ${r.data.data.product_name} — ${t('შემოწმება შეიქმნა')}`)
      setBarcode('')
      qc.invalidateQueries({ queryKey: ['quality-checks'] })
    },
    onError: (e: any) => setScanResult(`❌ ${e?.response?.data?.detail || t('შეცდომა')}`),
  })

  const submit = () => (tab === 'points' ? createPoint : createAlert).mutate()

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('ხარისხის კონტროლი')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('კონტროლის წერტილები, ტესტები, გაფრთხილებები')}</p>
        </div>
        <button onClick={() => setOpen(true)} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t('ახალი')}
        </button>
      </div>

      {/* Barcode scanner */}
      <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <ScanLine size={20} className="text-primary-600" />
          <input
            className="input flex-1"
            placeholder={t('ბარკოდის სკანირება (ან SKU/GTIN)')}
            value={barcode}
            onChange={e => setBarcode(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && barcode) scanBarcode.mutate() }}
          />
          <button onClick={() => scanBarcode.mutate()} disabled={!barcode || scanBarcode.isPending} className="btn btn-primary">
            {t('სკანირება')}
          </button>
        </div>
        {scanResult && <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">{scanResult}</p>}
      </div>

      <div className="flex gap-2 border-b dark:border-dark-50">
        {([['points', 'კონტროლის წერტილები', BadgeCheck], ['alerts', 'გაფრთხილებები', AlertTriangle]] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)} className={`flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium ${tab === key ? 'border-primary-600 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'}`}>
            <Icon size={16} /> {t(label)}
          </button>
        ))}
      </div>

      {tab === 'points' && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(points || []).map((p: any) => (
            <div key={p.id} className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-600 dark:bg-dark-100">
                  <BadgeCheck size={20} />
                </div>
                <div>
                  <h3 className="font-semibold text-brandgray-900 dark:text-gray-100">{p.name}</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{p.point_type}</p>
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <span className={`badge ${p.is_active ? 'badge-success' : 'badge'}`}>{p.is_active ? t('აქტიური') : t('გაჩერებული')}</span>
              </div>
            </div>
          ))}
          {(points || []).length === 0 && (
            <div className="col-span-full rounded-xl border border-dashed p-10 text-center text-gray-500 dark:text-gray-400">
              {t('კონტროლის წერტილები არ არის')}
            </div>
          )}
        </div>
      )}

      {tab === 'alerts' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('სათაური')}</th>
                <th className="px-4 py-3">{t('წყარო')}</th>
                <th className="px-4 py-3">{t('პრიორიტეტი')}</th>
                <th className="px-4 py-3">{t('სტატუსი')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(alerts || []).length === 0 ? (
                <tr><td colSpan={5} className="p-8 text-center text-gray-500">{t('გაფრთხილებები არ არის')}</td></tr>
              ) : (alerts || []).map((a: any) => (
                <tr key={a.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{a.title}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{a.source}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{a.priority}</td>
                  <td className="px-4 py-3"><span className={`badge ${a.status === 'done' ? 'badge-success' : 'badge-danger'}`}>{a.status}</span></td>
                  <td className="px-4 py-3">
                    {a.status !== 'done' && (
                      <button onClick={() => resolveAlert.mutate(a.id)} className="btn btn-sm btn-success flex items-center gap-1">
                        <CheckCircle2 size={14} /> {t('დახურვა')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი ჩანაწერი')}>
        <div className="space-y-4">
          {tab === 'points' ? (
            <>
              <FormField label={t('სახელი')}><input className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
              <FormField label={t('ტიპი')}>
                <select className="input" value={form.point_type || 'receipt'} onChange={e => setForm({ ...form, point_type: e.target.value })}>
                  <option value="receipt">Receipt</option><option value="production">Production</option><option value="delivery">Delivery</option><option value="operation">Operation</option>
                </select>
              </FormField>
            </>
          ) : (
            <>
              <FormField label={t('სათაური')}><input className="input" value={form.title || ''} onChange={e => setForm({ ...form, title: e.target.value })} /></FormField>
              <FormField label={t('პრიორიტეტი')}>
                <select className="input" value={form.priority || 'medium'} onChange={e => setForm({ ...form, priority: e.target.value })}>
                  <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option>
                </select>
              </FormField>
              <FormField label={t('აღწერა')}><textarea className="input min-h-[80px]" value={form.description || ''} onChange={e => setForm({ ...form, description: e.target.value })} /></FormField>
            </>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setOpen(false)}>{t('გაუქმება')}</button>
            <button className="btn btn-primary" onClick={submit}>{t('შექმნა')}</button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
