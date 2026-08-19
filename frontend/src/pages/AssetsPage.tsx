import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Plus, Pencil, Trash2, Search, Building2, Calendar, CalendarDays, TrendingDown, Calculator, FileText, Wrench
} from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import { api } from '../services/api'
import type { FixedAsset, FixedAssetCreate, FixedAssetUpdate, DepreciationRunResult, AssetDepreciationEntry } from '../types'

const today = () => new Date().toISOString().slice(0, 10)

const assetTypes = [
  { value: 'building', label: 'შენობა/ნაგებობა' },
  { value: 'vehicle', label: 'ტრანსპორტი' },
  { value: 'equipment', label: 'დანადგარები' },
  { value: 'furniture', label: 'ავეჯი' },
  { value: 'computer', label: 'კომპიუტერი/ტექნიკა' },
  { value: 'other', label: 'სხვა' },
]

const depMethods = [
  { value: 'straight_line', label: 'ხაზოვანი' },
  { value: 'declining', label: 'აჩქარებული' },
]

const statuses: Record<string, { label: string; cls: string }> = {
  active: { label: 'აქტიური', cls: 'badge-green' },
  fully_depreciated: { label: 'სრულად ამორტიზებული', cls: 'badge-blue' },
  disposed: { label: 'ჩამოწერილი', cls: 'badge-gray' },
}

function money(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

function errorText(err: any) {
  return err?.response?.data?.detail || i18n.t('ოპერაცია ვერ შესრულდა')
}

export default function AssetsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  // Asset modal
  const [assetModal, setAssetModal] = useState<'create' | 'edit' | null>(null)
  const [selectedAsset, setSelectedAsset] = useState<FixedAsset | null>(null)
  const [assetForm, setAssetForm] = useState<FixedAssetCreate>({
    name: '', asset_type: 'equipment', purchase_date: today(), purchase_cost: 0,
    useful_life_years: 5, depreciation_method: 'straight_line', salvage_value: 0,
    serial_number: null, location: null, notes: null,
  })
  const [assetEditForm, setAssetEditForm] = useState<FixedAssetUpdate>({})

  // Depreciation
  const [depAssetId, setDepAssetId] = useState<string | null>(null)
  const [depResult, setDepResult] = useState<DepreciationRunResult | null>(null)
  const [depHistory, setDepHistory] = useState<AssetDepreciationEntry[]>([])

  // Schedule + bulk run
  const [scheduleFor, setScheduleFor] = useState<string | null>(null)
  const [scheduleRows, setScheduleRows] = useState<{ period: string; amount: number; accumulated_after: number }[]>([])
  const [runAllResult, setRunAllResult] = useState<{ period: string; processed: number; items: { asset_name: string; amount: number; skipped: boolean }[] } | null>(null)

  // ── Queries ──────────────────────────────────────────────────────

  const { data: assetsData, isLoading } = useQuery({
    queryKey: ['fixed-assets'],
    queryFn: () => api.get('/assets/').then((r) => r.data.data),
  })
  const assets: FixedAsset[] = assetsData || []

  const visible = search.trim()
    ? assets.filter((a) => a.name.toLowerCase().includes(search.trim().toLowerCase()) || a.asset_type.includes(search.trim().toLowerCase()))
    : assets

  // ── Mutations ────────────────────────────────────────────────────

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['fixed-assets'] })
  }

  const createAsset = useMutation({
    mutationFn: () => api.post('/assets/', assetForm),
    onSuccess: () => { setAssetModal(null); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })
  const updateAsset = useMutation({
    mutationFn: () => api.put(`/assets/${selectedAsset!.id}`, assetEditForm),
    onSuccess: () => { setAssetModal(null); setSelectedAsset(null); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })
  const deleteAsset = useMutation({
    mutationFn: (id: string) => api.delete(`/assets/${id}`),
    onSuccess: () => refresh(),
    onError: (e) => setError(errorText(e)),
  })

  const runDep = useMutation({
    mutationFn: (id: string) => api.post(`/assets/${id}/run-depreciation`),
    onSuccess: (res) => {
      setDepResult(res.data.data)
      setError('')
      refresh()
    },
    onError: (e) => setError(errorText(e)),
  })

  const loadDepHistory = useMutation({
    mutationFn: (id: string) => api.get(`/assets/${id}/depreciation-history`).then((r) => r.data.data),
    onSuccess: (data) => setDepHistory(data),
    onError: (e) => setError(errorText(e)),
  })

  const loadSchedule = useMutation({
    mutationFn: (id: string) => api.get(`/assets/${id}/schedule`).then((r) => r.data.data),
    onSuccess: (data) => setScheduleRows(data),
    onError: (e) => setError(errorText(e)),
  })

  const runAllDep = useMutation({
    mutationFn: () => api.post('/assets/run-all-depreciation').then((r) => r.data.data),
    onSuccess: (data) => { setRunAllResult(data); setError(''); refresh() },
    onError: (e) => setError(errorText(e)),
  })

  // ── Summary ──────────────────────────────────────────────────────

  const totalCost = assets.reduce((s, a) => s + a.purchase_cost, 0)
  const totalDep = assets.reduce((s, a) => s + a.accumulated_depreciation, 0)
  const totalBook = assets.reduce((s, a) => s + a.book_value, 0)
  const activeCount = assets.filter((a) => a.status === 'active').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('ძირითადი საშუალებები')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('აქტივების რეგისტრი, ამორტიზაცია, ჩამოწერა')}</p>
        </div>
        <button
          className="btn-primary flex items-center gap-2"
          onClick={() => {
            setAssetForm({
              name: '', asset_type: 'equipment', purchase_date: today(), purchase_cost: 0,
              useful_life_years: 5, depreciation_method: 'straight_line', salvage_value: 0,
              serial_number: null, location: null, notes: null,
            })
            setError('')
            setAssetModal('create')
          }}
        >
          <Plus size={18} /> {t('აქტივის დამატება')}
        </button>
        <button
          onClick={() => { if (confirm(t('ყველა აქტივის ამორტიზაცია დავარიცხოთ მიმდინარე პერიოდისთვის?'))) runAllDep.mutate() }}
          disabled={runAllDep.isPending}
          className="btn-secondary flex items-center gap-2"
        >
          <Calculator size={16} /> {runAllDep.isPending ? t('ირიცხება...') : t('ყველას დარიცხვა')}
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <Building2 className="text-primary-600" />
            <div>
              <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('აქტიური აქტივები')}</div>
              <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{activeCount}</div>
            </div>
          </div>
        </div>
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <Calculator className="text-accent-600" />
            <div>
              <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('საწყისი ღირებულება')}</div>
              <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{money(totalCost)}</div>
            </div>
          </div>
        </div>
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <TrendingDown className="text-amber-600" />
            <div>
              <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('ამორტიზაცია')}</div>
              <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{money(totalDep)}</div>
            </div>
          </div>
        </div>
        <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <FileText className="text-primary-600" />
            <div>
              <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('ნარჩენი ღირებულება')}</div>
              <div className="text-2xl font-semibold text-brandgray-900 dark:text-gray-100">{money(totalBook)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <input
            value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder={t('ძებნა სახელით...')}
            className="input pl-10"
          />
        </div>
      </div>

      {/* Table */}
      <DataTable
        columns={[
          { key: 'name', label: 'სახელი', render: (a: FixedAsset) => <span className="font-medium">{a.name}</span> },
          { key: 'asset_type', label: 'ტიპი', render: (a: FixedAsset) => assetTypes.find((t) => t.value === a.asset_type)?.label || a.asset_type },
          { key: 'purchase_date', label: 'შეძენის თარიღი' },
          { key: 'purchase_cost', label: 'ღირებულება', render: (a: FixedAsset) => money(a.purchase_cost) },
          { key: 'book_value', label: 'ნარჩენი', render: (a: FixedAsset) => <span className="font-semibold">{money(a.book_value)}</span> },
          { key: 'accumulated_depreciation', label: 'ამორტიზაცია', render: (a: FixedAsset) => money(a.accumulated_depreciation) },
          {
            key: 'status', label: 'სტატუსი',
            render: (a: FixedAsset) => {
              const s = statuses[a.status] || statuses.active
              return <span className={`badge ${s.cls}`}>{s.label}</span>
            },
          },
          {
            key: 'actions', label: '',
            render: (a: FixedAsset) => (
              <div className="flex items-center gap-1">
                {a.status === 'active' && (
                  <button
                    onClick={(e) => { e.stopPropagation(); setDepResult(null); runDep.mutate(a.id) }}
                    className="p-1.5 hover:bg-accent-50 rounded-lg transition-colors"
                    title={t('ამორტიზაციის დათვლა')}
                  >
                    <Calculator size={16} className="text-accent-500" />
                  </button>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); setDepAssetId(a.id); loadDepHistory.mutate(a.id) }}
                  className="p-1.5 hover:bg-primary-50 rounded-lg transition-colors"
                  title={t('ამორტიზაციის ისტორია')}
                >
                  <TrendingDown size={16} className="text-primary-500" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setScheduleFor(a.id); loadSchedule.mutate(a.id) }}
                  className="p-1.5 hover:bg-amber-50 rounded-lg transition-colors"
                  title={t('ამორტიზაციის გრაფიკი')}
                >
                  <CalendarDays size={16} className="text-amber-500" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setSelectedAsset(a); setAssetEditForm({ name: a.name, status: a.status, location: a.location, notes: a.notes, serial_number: a.serial_number }); setError(''); setAssetModal('edit') }}
                  className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors dark:hover:bg-dark-100"
                >
                  <Pencil size={18} className="text-gray-400 dark:text-gray-500" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); if (confirm(t('წავშალოთ აქტივი?'))) deleteAsset.mutate(a.id) }}
                  className="p-1.5 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <Trash2 size={18} className="text-red-400" />
                </button>
              </div>
            ),
          },
        ]}
        data={visible}
        clientPageSize={20}
        isLoading={isLoading}
        emptyMessage={t('ძირითადი საშუალებები არ მოიძებნა')}
      />

      {/* Depreciation Result */}
      {depResult && (
        <div className="card border-accent-200 bg-accent-50/50 dark:bg-accent-900/20 dark:border-accent-800/30">
          <div className="flex items-center gap-3">
            <Calculator size={24} className="text-accent-600" />
            <div className="flex-1">
              <p className="font-medium text-accent-800 dark:text-accent-200">{t('ამორტიზაცია დაფიქსირებულია')}</p>
              <p className="text-sm text-accent-700 dark:text-accent-300">
                {depResult.asset_name} — {money(depResult.depreciation_amount)} / {depResult.is_fully_depreciated ? '✅ სრულად ამორტიზებული' : `📉 ნარჩენი: ${money(depResult.new_book_value)}`}
              </p>
            </div>
            <button onClick={() => setDepResult(null)} className="btn-secondary text-sm">{t('დახურვა')}</button>
          </div>
        </div>
      )}

      {/* Run-all Depreciation Result */}
      {runAllResult && (
        <div className="card border-emerald-200 bg-emerald-50/50 dark:bg-emerald-900/20 dark:border-emerald-800/30">
          <div className="flex items-center gap-3">
            <Calculator size={24} className="text-emerald-600" />
            <div className="flex-1">
              <p className="font-medium text-emerald-800 dark:text-emerald-200">
                {t('ამორტიზაცია დარიცხულია')}: {runAllResult.period} — {runAllResult.processed} {t('აქტივი')}
              </p>
              <div className="mt-1 space-y-0.5 text-sm text-emerald-700 dark:text-emerald-300">
                {runAllResult.items.map((it, i) => (
                  <div key={i} className="flex justify-between">
                    <span>{it.asset_name}</span>
                    <span className="font-mono">{it.skipped ? '✓ ' + t('უკვე დარიცხული') : `${money(it.amount)} ₾`}</span>
                  </div>
                ))}
              </div>
            </div>
            <button onClick={() => setRunAllResult(null)} className="btn-secondary text-sm">{t('დახურვა')}</button>
          </div>
        </div>
      )}

      {/* Depreciation History Modal */}
      <Modal open={!!depAssetId} onClose={() => { setDepAssetId(null); setDepHistory([]) }} title={t('ამორტიზაციის ისტორია')} size="md">
        {depHistory.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">{t('ამორტიზაციის ისტორია ცარიელია')}</p>
        ) : (
          <div className="space-y-2">
            {depHistory.map((d) => (
              <div key={d.id} className="flex items-center justify-between p-3 rounded-lg bg-brandgray-50 dark:bg-dark-100">
                <div>
                  <span className="text-sm font-medium text-brandgray-900 dark:text-gray-100">{d.period_label}</span>
                  <span className="text-xs text-brandgray-500 dark:text-gray-400 ml-3">{d.depreciation_date}</span>
                </div>
                <span className="font-semibold text-accent-700 dark:text-accent-300">{money(d.amount)}</span>
              </div>
            ))}
          </div>
        )}
      </Modal>

      {/* Depreciation Schedule Modal */}
      <Modal open={!!scheduleFor} onClose={() => { setScheduleFor(null); setScheduleRows([]) }} title={t('ამორტიზაციის გრაფიკი')} size="md">
        {scheduleRows.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">{t('გრაფიკი ცარიელია')}</p>
        ) : (
          <div className="max-h-96 overflow-y-auto space-y-1.5">
            {scheduleRows.map((r) => (
              <div key={r.period} className="flex items-center justify-between p-2.5 rounded-lg bg-brandgray-50 dark:bg-dark-100">
                <span className="text-sm font-medium text-brandgray-900 dark:text-gray-100 font-mono">{r.period}</span>
                <span className="text-sm font-semibold text-accent-700 dark:text-accent-300">{money(r.amount)}</span>
                <span className="text-xs text-brandgray-500 dark:text-gray-400">{t('დაგროვებით')}: {money(r.accumulated_after)}</span>
              </div>
            ))}
          </div>
        )}
      </Modal>

      {/* ── Create Modal ──────────────────────────────────────────── */}
      <Modal open={assetModal === 'create'} onClose={() => setAssetModal(null)} title={t('ახალი ძირითადი საშუალება')} size="lg">
        <div className="space-y-4">
          <FormField label={t('სახელი')} required>
            <input value={assetForm.name} onChange={(e) => setAssetForm({ ...assetForm, name: e.target.value })} placeholder={t('მაგ. საწარმოო დანადგარი')} className="input" />
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label={t('ტიპი')} required>
              <Select value={assetForm.asset_type} onChange={(e) => setAssetForm({ ...assetForm, asset_type: e.target.value })} options={assetTypes} />
            </FormField>
            <FormField label={t('შეძენის თარიღი')} required>
              <input type="date" value={assetForm.purchase_date} onChange={(e) => setAssetForm({ ...assetForm, purchase_date: e.target.value })} className="input" />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label={t('შეძენის ღირებულება')} required>
              <input type="number" step="0.01" value={assetForm.purchase_cost || ''} onChange={(e) => setAssetForm({ ...assetForm, purchase_cost: Number(e.target.value) })} className="input" />
            </FormField>
            <FormField label={t('სასარგებლო ვადა (წელი)')} required>
              <input type="number" min="1" value={assetForm.useful_life_years} onChange={(e) => setAssetForm({ ...assetForm, useful_life_years: Number(e.target.value) })} className="input" />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label={t('ამორტიზაციის მეთოდი')}>
              <Select value={assetForm.depreciation_method || 'straight_line'} onChange={(e) => setAssetForm({ ...assetForm, depreciation_method: e.target.value })} options={depMethods} />
            </FormField>
            <FormField label={t('სალიკვიდაციო ღირებულება')}>
              <input type="number" step="0.01" value={assetForm.salvage_value || ''} onChange={(e) => setAssetForm({ ...assetForm, salvage_value: Number(e.target.value) })} className="input" />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <FormField label={t('სერიული ნომერი')}>
              <input value={assetForm.serial_number || ''} onChange={(e) => setAssetForm({ ...assetForm, serial_number: e.target.value || null })} className="input" />
            </FormField>
            <FormField label={t('მდებარეობა')}>
              <input value={assetForm.location || ''} onChange={(e) => setAssetForm({ ...assetForm, location: e.target.value || null })} className="input" />
            </FormField>
          </div>
          <FormField label={t('შენიშვნა')}>
            <textarea value={assetForm.notes || ''} onChange={(e) => setAssetForm({ ...assetForm, notes: e.target.value || null })} className="input" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setAssetModal(null)} className="btn-secondary">{t('გაუქმება')}</button>
            <button
              onClick={() => {
                if (!assetForm.name.trim() || !assetForm.purchase_cost || !assetForm.useful_life_years) {
                  setError(t('სახელი, ღირებულება და ვადა სავალდებულოა'))
                  return
                }
                createAsset.mutate()
              }}
              disabled={createAsset.isPending}
              className="btn-primary"
            >
              {createAsset.isPending ? t('იქმნება...') : t('შექმნა')}
            </button>
          </div>
        </div>
      </Modal>

      {/* ── Edit Modal ────────────────────────────────────────────── */}
      <Modal open={assetModal === 'edit'} onClose={() => setAssetModal(null)} title={t('აქტივის რედაქტირება')} size="md">
        <div className="space-y-4">
          <FormField label={t('სახელი')}>
            <input value={assetEditForm.name || ''} onChange={(e) => setAssetEditForm({ ...assetEditForm, name: e.target.value })} className="input" />
          </FormField>
          <FormField label={t('სტატუსი')}>
            <Select value={assetEditForm.status || 'active'} onChange={(e) => setAssetEditForm({ ...assetEditForm, status: e.target.value })} options={[
              { value: 'active', label: 'აქტიური' },
              { value: 'fully_depreciated', label: 'სრულად ამორტიზებული' },
              { value: 'disposed', label: 'ჩამოწერილი' },
            ]} />
          </FormField>
          <FormField label={t('მდებარეობა')}>
            <input value={assetEditForm.location || ''} onChange={(e) => setAssetEditForm({ ...assetEditForm, location: e.target.value || null })} className="input" />
          </FormField>
          <FormField label={t('შენიშვნა')}>
            <textarea value={assetEditForm.notes || ''} onChange={(e) => setAssetEditForm({ ...assetEditForm, notes: e.target.value || null })} className="input" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setAssetModal(null)} className="btn-secondary">{t('გაუქმება')}</button>
            <button onClick={() => updateAsset.mutate()} disabled={updateAsset.isPending} className="btn-primary">
              {updateAsset.isPending ? t('ინახება...') : t('შენახვა')}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
