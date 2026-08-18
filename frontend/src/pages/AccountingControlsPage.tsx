import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { BookOpenCheck, Building2, ArrowRightLeft, Plus } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { accountingControlsApi } from '../services/api'

const today = new Date().toISOString().slice(0, 10)

export default function AccountingControlsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'fiscal' | 'mapping' | 'fx'>('fiscal')
  const [open, setOpen] = useState(false)
  const [fiscal, setFiscal] = useState({ code: 'GE-VAT-18', name: 'საქართველო — სტანდარტული დღგ', vat_rate: '18', tax_type: 'vat_standard', applies_to: 'both', is_default: true })
  const [mapping, setMapping] = useState({ source_account_code: '', target_account_code: '', target_name: '', target_account_type: 'expense' })
  const [fx, setFx] = useState({ target_currency: 'GEL', rate_date: today, rate: '', method: 'closing', source: 'manual', is_locked: true })

  const { data: fiscals = [] } = useQuery({ queryKey: ['fiscal-positions'], queryFn: () => accountingControlsApi.fiscalPositions().then(r => r.data.data) })
  const { data: mappings = [] } = useQuery({ queryKey: ['consolidation-mappings'], queryFn: () => accountingControlsApi.mappings().then(r => r.data.data) })
  const { data: fxRates = [] } = useQuery({ queryKey: ['fx-translation-rates'], queryFn: () => accountingControlsApi.fxRates().then(r => r.data.data) })

  const create = useMutation({
    mutationFn: () => tab === 'fiscal' ? accountingControlsApi.createFiscalPosition({ ...fiscal, vat_rate: Number(fiscal.vat_rate) })
      : tab === 'mapping' ? accountingControlsApi.createMapping(mapping)
      : accountingControlsApi.createFxRate({ ...fx, rate: Number(fx.rate) }),
    onSuccess: () => { setOpen(false); qc.invalidateQueries({ queryKey: [tab === 'fiscal' ? 'fiscal-positions' : tab === 'mapping' ? 'consolidation-mappings' : 'fx-translation-rates'] }) },
  })

  const tabs = [
    { id: 'fiscal' as const, label: 'ფისკალური პოზიციები', icon: BookOpenCheck },
    { id: 'mapping' as const, label: 'კონსოლიდაციის Mapping', icon: Building2 },
    { id: 'fx' as const, label: 'FX Translation', icon: ArrowRightLeft },
  ]
  const rows = tab === 'fiscal' ? fiscals : tab === 'mapping' ? mappings : fxRates

  return <div className="space-y-6">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div><h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('ბუღალტრული კონტროლები')}</h1><p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{t('ფისკალური ლოკალიზაცია, ჯგუფური ანგარიშები და FX translation')}</p></div>
      <button className="btn-primary flex items-center gap-2" onClick={() => setOpen(true)}><Plus size={18} />{t('ახალი ჩანაწერი')}</button>
    </div>
    <div className="flex flex-wrap gap-2 border-b border-gray-100 pb-3 dark:border-dark-50">{tabs.map(x => <button key={x.id} onClick={() => setTab(x.id)} className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium ${tab === x.id ? 'bg-primary-600 text-white' : 'bg-gray-50 text-gray-600 dark:bg-dark-100 dark:text-gray-400'}`}><x.icon size={16}/>{t(x.label)}</button>)}</div>
    <div className="overflow-x-auto rounded-xl border border-gray-100 bg-white dark:border-dark-50 dark:bg-dark-200"><table className="w-full text-sm"><thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400"><tr>{tab === 'fiscal' ? <><th className="p-3">{t('კოდი')}</th><th className="p-3">{t('სახელი')}</th><th className="p-3">დღგ</th><th className="p-3">{t('სტატუსი')}</th></> : tab === 'mapping' ? <><th className="p-3">Source</th><th className="p-3">Target</th><th className="p-3">{t('სახელი')}</th><th className="p-3">Type</th></> : <><th className="p-3">Currency</th><th className="p-3">{t('თარიღი')}</th><th className="p-3">Rate</th><th className="p-3">Method</th></>}</tr></thead><tbody className="divide-y divide-gray-100 dark:divide-dark-50">{rows.length === 0 ? <tr><td colSpan={4} className="p-8 text-center text-gray-500">{t('მონაცემები არ არის')}</td></tr> : rows.map((r: any) => tab === 'fiscal' ? <tr key={r.id}><td className="p-3 font-mono">{r.code}</td><td className="p-3">{r.name}</td><td className="p-3">{r.vat_rate}%</td><td className="p-3">{r.is_active ? t('აქტიური') : t('გამორთულია')}</td></tr> : tab === 'mapping' ? <tr key={r.id}><td className="p-3 font-mono">{r.source_account_code}</td><td className="p-3 font-mono">{r.target_account_code}</td><td className="p-3">{r.target_name}</td><td className="p-3">{r.target_account_type}</td></tr> : <tr key={r.id}><td className="p-3">{r.target_currency}</td><td className="p-3">{r.rate_date}</td><td className="p-3">{r.rate}</td><td className="p-3">{r.method}{r.is_locked ? ' · 🔒' : ''}</td></tr>)}</tbody></table></div>
    <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი ჩანაწერი')}><div className="space-y-4">{tab === 'fiscal' ? <><FormField label={t('კოდი')}><input className="input" value={fiscal.code} onChange={e => setFiscal({...fiscal,code:e.target.value})}/></FormField><FormField label={t('სახელი')}><input className="input" value={fiscal.name} onChange={e => setFiscal({...fiscal,name:e.target.value})}/></FormField><FormField label="დღგ %"><input className="input" type="number" value={fiscal.vat_rate} onChange={e => setFiscal({...fiscal,vat_rate:e.target.value})}/></FormField></> : tab === 'mapping' ? <><FormField label="Source account"><input className="input" value={mapping.source_account_code} onChange={e => setMapping({...mapping,source_account_code:e.target.value})}/></FormField><FormField label="Target account"><input className="input" value={mapping.target_account_code} onChange={e => setMapping({...mapping,target_account_code:e.target.value})}/></FormField><FormField label={t('სახელი')}><input className="input" value={mapping.target_name} onChange={e => setMapping({...mapping,target_name:e.target.value})}/></FormField></> : <><FormField label="Target currency"><input className="input" value={fx.target_currency} onChange={e => setFx({...fx,target_currency:e.target.value.toUpperCase()})}/></FormField><FormField label={t('თარიღი')}><input className="input" type="date" value={fx.rate_date} onChange={e => setFx({...fx,rate_date:e.target.value})}/></FormField><FormField label="Rate"><input className="input" type="number" step="0.000001" value={fx.rate} onChange={e => setFx({...fx,rate:e.target.value})}/></FormField></>}<button disabled={create.isPending} onClick={() => create.mutate()} className="btn-primary w-full">{t('შენახვა')}</button></div></Modal>
  </div>
}
