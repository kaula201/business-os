import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Store, Plus, Download, Trash2, CheckCircle2 } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { marketplaceApi } from '../services/api'
import { fmtDate } from '../lib/format'

export default function MarketplacePage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: '', category: 'other', description: '' })

  const { data: catalog } = useQuery({
    queryKey: ['marketplace'],
    queryFn: () => marketplaceApi.apps().then(r => r.data.data),
  })
  const { data: myApps } = useQuery({
    queryKey: ['marketplace-my'],
    queryFn: () => marketplaceApi.myApps().then(r => r.data.data),
  })
  const { data: purchases } = useQuery({
    queryKey: ['marketplace-purchases'],
    queryFn: () => marketplaceApi.purchases().then(r => r.data.data),
  })

  const createApp = useMutation({
    mutationFn: () => marketplaceApi.create(form),
    onSuccess: () => { setOpen(false); setForm({ name: '', category: 'other', description: '' }); qc.invalidateQueries({ queryKey: ['marketplace'] }) },
  })
  const install = useMutation({
    mutationFn: (id: string) => marketplaceApi.install(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['marketplace'] }); qc.invalidateQueries({ queryKey: ['marketplace-my'] }) },
  })
  const uninstall = useMutation({
    mutationFn: (id: string) => marketplaceApi.uninstall(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['marketplace'] }); qc.invalidateQueries({ queryKey: ['marketplace-my'] }) },
  })
  const purchase = useMutation({
    mutationFn: (id: string) => marketplaceApi.purchase(id, { billing_mode: 'one_time' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['marketplace'] }); qc.invalidateQueries({ queryKey: ['marketplace-my'] }); qc.invalidateQueries({ queryKey: ['marketplace-purchases'] }) },
  })
  const trial = useMutation({
    mutationFn: (id: string) => marketplaceApi.trial(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['marketplace'] }); qc.invalidateQueries({ queryKey: ['marketplace-my'] }) },
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('Marketplace')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('აპების კატალოგი და დაყენებები')}</p>
        </div>
        <button onClick={() => setOpen(true)} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t('აპის გამოქვეყნება')}
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(catalog?.items || []).map((a: any) => (
          <div key={a.id} className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-600 dark:bg-dark-100">
                  <Store size={20} />
                </div>
                <div>
                  <h3 className="font-semibold text-brandgray-900 dark:text-gray-100">{a.name}</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{a.category} · v{a.version}</p>
                </div>
              </div>
              {a.installed && <CheckCircle2 size={18} className="text-green-600" />}
            </div>
            <p className="mt-2 line-clamp-2 text-sm text-gray-600 dark:text-gray-400">{a.description || '—'}</p>
            <div className="mt-3">
              {a.installed ? (
                <button onClick={() => uninstall.mutate(a.id)} className="btn btn-sm btn-outline w-full">
                  {t('მოხსნა')}
                </button>
              ) : a.price > 0 ? (
                <div className="flex gap-2">
                  <button onClick={() => purchase.mutate(a.id)} className="btn btn-sm btn-primary flex-1">
                    {t('ყიდვა')} — {a.price} ₾
                  </button>
                  <button onClick={() => trial.mutate(a.id)} className="btn btn-sm btn-outline flex-1">
                    {t('ტრიალი')}
                  </button>
                </div>
              ) : (
                <button onClick={() => install.mutate(a.id)} className="btn btn-sm btn-primary w-full flex items-center justify-center gap-1">
                  <Download size={14} /> {t('დაყენება')}
                </button>
              )}
            </div>
          </div>
        ))}
        {(catalog?.items || []).length === 0 && (
          <div className="col-span-full rounded-xl border border-dashed p-10 text-center text-gray-500 dark:text-gray-400">
            {t('აპები არ არის')}
          </div>
        )}
      </div>

      <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <h2 className="mb-3 font-semibold text-brandgray-900 dark:text-gray-100">{t('ჩემი აპები')}</h2>
        <div className="space-y-2">
          {(myApps || []).map((a: any) => (
            <div key={a.id} className="flex items-center justify-between rounded-lg border p-3 dark:border-dark-50">
              <div className="flex items-center gap-3">
                <Store size={18} className="text-primary-600" />
                <div>
                  <p className="font-medium text-brandgray-900 dark:text-gray-100">{a.name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{t('დაყენებულია')}: {fmtDate(new Date(a.installed_at))}</p>
                </div>
              </div>
              <button onClick={() => uninstall.mutate(a.id)} className="text-gray-400 hover:text-red-500">
                <Trash2 size={16} />
              </button>
            </div>
          ))}
          {(myApps || []).length === 0 && <p className="text-sm text-gray-500">{t('დაყენებული აპები არ არის')}</p>}
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={t('აპის გამოქვეყნება')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')}>
            <input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          </FormField>
          <FormField label={t('კატეგორია')}>
            <select className="input" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
              <option value="sales">Sales</option>
              <option value="finance">Finance</option>
              <option value="operations">Operations</option>
              <option value="hr">HR</option>
              <option value="crm">CRM</option>
              <option value="other">Other</option>
            </select>
          </FormField>
          <FormField label={t('აღწერა')}>
            <textarea className="input min-h-[80px]" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          </FormField>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setOpen(false)}>{t('გაუქმება')}</button>
            <button className="btn btn-primary" onClick={() => createApp.mutate()} disabled={!form.name}>{t('გამოქვეყნება')}</button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
