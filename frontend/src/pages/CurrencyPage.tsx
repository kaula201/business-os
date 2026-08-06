import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRightLeft, Calculator, Plus, RefreshCw, Search, Trash2 } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import FormField, { Select } from '../components/ui/FormField'
import { api } from '../services/api'
import type { CurrencyConversion, CurrencyRate, CurrencyRateCreate } from '../types'

const currencies = ['GEL', 'USD', 'EUR', 'GBP', 'TRY']
const today = new Date().toISOString().slice(0, 10)
const options = currencies.map((value) => ({ value, label: value }))

function errorText(error: any) {
  return error?.response?.data?.detail || 'ოპერაცია ვერ შესრულდა'
}

export default function CurrencyPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [rateModal, setRateModal] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [syncDate, setSyncDate] = useState(today)
  const [rateForm, setRateForm] = useState<CurrencyRateCreate>({
    from_currency: 'USD', to_currency: 'GEL', rate_date: today, rate: 0, source: 'manual',
  })
  const [conversionForm, setConversionForm] = useState({ amount: 1, from_currency: 'USD', to_currency: 'GEL', rate_date: today })
  const [conversion, setConversion] = useState<CurrencyConversion | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['currency-rates'],
    queryFn: () => api.get('/currency/rates').then((response) => response.data.data),
  })
  const rates: CurrencyRate[] = data || []
  const { data: nbgStatus } = useQuery({
    queryKey: ['nbg-sync-status'],
    queryFn: () => api.get('/currency/rates/nbg-status').then((response) => response.data.data),
  })

  const createRate = useMutation({
    mutationFn: () => api.post('/currency/rates', rateForm),
    onSuccess: () => {
      setRateModal(false)
      setError('')
      queryClient.invalidateQueries({ queryKey: ['currency-rates'] })
    },
    onError: (e) => setError(errorText(e)),
  })

  const deleteRate = useMutation({
    mutationFn: (id: string) => api.delete(`/currency/rates/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['currency-rates'] }),
    onError: (e) => setError(errorText(e)),
  })

  const syncNbg = useMutation({
    mutationFn: () => api.post(`/currency/rates/sync-nbg?rate_date=${syncDate}`),
    onSuccess: (response) => {
      const result = response.data.data
      setError('')
      setNotice(`ეროვნული ბანკის კურსები განახლებულია: ${result.rates_created} ახალი, ${result.rates_updated} განახლებული`)
      queryClient.invalidateQueries({ queryKey: ['currency-rates'] })
      queryClient.invalidateQueries({ queryKey: ['nbg-sync-status'] })
    },
    onError: (e) => { setNotice(''); setError(errorText(e)) },
  })

  const convert = useMutation({
    mutationFn: () => api.post('/currency/convert', conversionForm),
    onSuccess: (response) => { setConversion(response.data.data); setError('') },
    onError: (e) => { setConversion(null); setError(errorText(e)) },
  })

  const visible = rates.filter((rate) => {
    const q = search.trim().toUpperCase()
    return !q || `${rate.from_currency} ${rate.to_currency} ${rate.source}`.toUpperCase().includes(q)
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('ვალუტის კურსები')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('კურსების მართვა და თანხის გადაყვანა')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input aria-label={t('ეროვნული ბანკის კურსის თარიღი')} className="input w-auto" type="date" value={syncDate} onChange={(e) => setSyncDate(e.target.value)} />
          <button className="btn-secondary flex items-center gap-2" disabled={syncNbg.isPending} onClick={() => syncNbg.mutate()}>
            <RefreshCw size={18} className={syncNbg.isPending ? 'animate-spin' : ''} /> {syncNbg.isPending ? 'ახლდება...' : 'ეროვნული ბანკიდან განახლება'}
          </button>
          <button className="btn-primary flex items-center gap-2" onClick={() => { setError(''); setNotice(''); setRateModal(true) }}>
            <Plus size={18} /> {t('კურსის დამატება')}
          </button>
        </div>
      </div>

      {notice && <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800 dark:border-green-800 dark:bg-green-900/30 dark:text-green-200">{notice}</div>}

      <section className="rounded-xl border border-gray-200 bg-white px-5 py-4 dark:border-dark-50 dark:bg-dark-200">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-semibold text-gray-900 dark:text-gray-100">{t('ავტომატური განახლება')}</p>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {nbgStatus?.enabled ? `ყოველდღე ${nbgStatus.schedule}-ზე · თბილისის დრო` : 'გამორთულია'}
            </p>
          </div>
          <span className={`badge ${nbgStatus?.enabled ? 'badge-green' : 'badge-gray'}`}>
            {nbgStatus?.enabled ? 'ჩართულია' : 'გამორთულია'}
          </span>
        </div>
        {nbgStatus?.last_run_at && (
          <div className="mt-4 grid gap-3 border-t border-gray-100 pt-4 text-sm sm:grid-cols-3 dark:border-dark-50">
            <div><span className="text-gray-500 dark:text-gray-400">{t('ბოლო გაშვება')}</span><p className="mt-1 font-medium text-gray-900 dark:text-gray-200">{new Date(nbgStatus.last_run_at).toLocaleString('ka-GE')}</p></div>
            <div><span className="text-gray-500 dark:text-gray-400">{t('ტიპი')}</span><p className="mt-1 font-medium text-gray-900 dark:text-gray-200">{nbgStatus.trigger === 'scheduled' ? 'ავტომატური' : 'ხელით'}</p></div>
            <div><span className="text-gray-500 dark:text-gray-400">{t('შედეგი')}</span><p className={`mt-1 font-medium ${nbgStatus.status === 'success' ? 'text-green-600' : 'text-red-600'}`}>{nbgStatus.status === 'success' ? `წარმატებული · ${nbgStatus.effective_date}` : nbgStatus.error_message || 'შეცდომა'}</p></div>
          </div>
        )}
      </section>

      <section className="card p-5 dark:bg-dark-200 dark:border-dark-50">
        <div className="mb-4 flex items-center gap-2">
          <Calculator className="text-primary-600" size={22} />
          <h2 className="font-semibold text-brandgray-900 dark:text-gray-100">{t('ვალუტის გადაყვანა')}</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-5">
          <FormField label={t('თანხა')}>
            <input className="input" type="number" min="0.01" step="0.01" value={conversionForm.amount || ''} onChange={(e) => setConversionForm({ ...conversionForm, amount: Number(e.target.value) })} />
          </FormField>
          <FormField label={t('საწყისი ვალუტა')}><Select value={conversionForm.from_currency} options={options} onChange={(e) => setConversionForm({ ...conversionForm, from_currency: e.target.value })} /></FormField>
          <FormField label={t('მიზნობრივი ვალუტა')}><Select value={conversionForm.to_currency} options={options} onChange={(e) => setConversionForm({ ...conversionForm, to_currency: e.target.value })} /></FormField>
          <FormField label={t('თარიღი')}><input className="input" type="date" value={conversionForm.rate_date} onChange={(e) => setConversionForm({ ...conversionForm, rate_date: e.target.value })} /></FormField>
          <div className="flex items-end"><button className="btn-primary w-full flex items-center justify-center gap-2" disabled={convert.isPending} onClick={() => convert.mutate()}><ArrowRightLeft size={17} /> {t('გადაყვანა')}</button></div>
        </div>
        {conversion && (
          <div className="mt-5 rounded-xl bg-primary-50 p-4 text-primary-900 dark:bg-primary-900/30 dark:text-primary-100">
            <span className="font-semibold">{conversion.amount.toLocaleString('ka-GE')} {conversion.from_currency}</span>
            <ArrowRightLeft className="mx-3 inline" size={18} />
            <span className="text-xl font-bold">{conversion.converted_amount.toLocaleString('ka-GE')} {conversion.to_currency}</span>
            <span className="ml-3 text-sm opacity-75">კურსი: {conversion.rate} · {conversion.rate_date}</span>
          </div>
        )}
        {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      </section>

      <div className="relative max-w-xs">
        <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
        <input className="input pl-10" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('ვალუტის ძებნა...')} />
      </div>

      <DataTable
        columns={[
          { key: 'pair', label: 'წყვილი', render: (rate: CurrencyRate) => <span className="font-semibold">{rate.from_currency} → {rate.to_currency}</span> },
          { key: 'rate_date', label: 'თარიღი' },
          { key: 'rate', label: 'კურსი', render: (rate: CurrencyRate) => Number(rate.rate).toFixed(6) },
          { key: 'source', label: 'წყარო', render: (rate: CurrencyRate) => rate.source === 'manual' ? 'ხელით' : rate.source.toUpperCase() },
          { key: 'actions', label: '', render: (rate: CurrencyRate) => <button title={t('წაშლა')} className="rounded-lg p-1.5 hover:bg-red-50 dark:hover:bg-red-900/30" onClick={() => { if (confirm('წავშალოთ კურსი?')) deleteRate.mutate(rate.id) }}><Trash2 size={16} className="text-red-500" /></button> },
        ]}
        data={visible}
        clientPageSize={20}
        isLoading={isLoading}
        emptyMessage="ვალუტის კურსები არ არის"
      />

      <Modal open={rateModal} onClose={() => setRateModal(false)} title={t('ვალუტის კურსის დამატება')} size="md">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FormField label={t('საწყისი ვალუტა')} required><Select value={rateForm.from_currency} options={options} onChange={(e) => setRateForm({ ...rateForm, from_currency: e.target.value })} /></FormField>
            <FormField label={t('მიზნობრივი ვალუტა')} required><Select value={rateForm.to_currency} options={options} onChange={(e) => setRateForm({ ...rateForm, to_currency: e.target.value })} /></FormField>
          </div>
          <FormField label={t('თარიღი')} required><input className="input" type="date" value={rateForm.rate_date} onChange={(e) => setRateForm({ ...rateForm, rate_date: e.target.value })} /></FormField>
          <FormField label={t('კურსი')} required><input className="input" type="number" min="0.000001" step="0.000001" value={rateForm.rate || ''} onChange={(e) => setRateForm({ ...rateForm, rate: Number(e.target.value) })} /></FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setRateModal(false)}>{t('გაუქმება')}</button>
            <button className="btn-primary" disabled={createRate.isPending || rateForm.rate <= 0 || rateForm.from_currency === rateForm.to_currency} onClick={() => createRate.mutate()}>{createRate.isPending ? 'ინახება...' : 'შენახვა'}</button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
