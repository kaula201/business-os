import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { GitBranch, Plus, CheckCircle2, History } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { plmApi, productsApi } from '../services/api'

const lifecycleStages = ['concept', 'design', 'prototype', 'production', 'eol']

export default function PlmPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'versions' | 'eco'>('versions')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<Record<string, any>>({})
  const [selectedProduct, setSelectedProduct] = useState('')

  const { data: products } = useQuery({ queryKey: ['products'], queryFn: () => productsApi.list().then(r => r.data.data.items || r.data.data) })
  const { data: versions } = useQuery({
    queryKey: ['plm-versions', selectedProduct],
    queryFn: () => (selectedProduct ? plmApi.versions(selectedProduct).then(r => r.data.data) : []),
    enabled: !!selectedProduct,
  })
  const { data: lifecycle } = useQuery({
    queryKey: ['plm-lifecycle', selectedProduct],
    queryFn: () => (selectedProduct ? plmApi.lifecycle(selectedProduct).then(r => r.data.data) : null),
    enabled: !!selectedProduct,
  })
  const { data: ecos } = useQuery({ queryKey: ['plm-eco'], queryFn: () => plmApi.engineeringChanges().then(r => r.data.data) })

  const createVersion = useMutation({
    mutationFn: () => plmApi.createVersion(selectedProduct, { version: form.version, notes: form.notes }),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['plm-versions'] }) },
  })
  const createEco = useMutation({
    mutationFn: () => plmApi.createEco({ product_id: form.product_id, title: form.title, change_type: form.change_type, priority: form.priority, description: form.description }),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['plm-eco'] }) },
  })
  const approveEco = useMutation({
    mutationFn: (id: string) => plmApi.updateEco(id, { status: 'approved' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plm-eco'] }),
  })
  const setStage = useMutation({
    mutationFn: (stage: string) => plmApi.setLifecycle(selectedProduct, { stage }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plm-lifecycle'] }),
  })

  const productOptions = (products || []).map((p: any) => (
    <option key={p.id} value={p.id}>{p.name}</option>
  ))

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('PLM — პროდუქტის სასიცოცხლო ციკლი')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('ვერსიები, ინჟინერული ცვლილებები (ECO), ეტაპები')}</p>
        </div>
        <button onClick={() => setOpen(true)} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t('ახალი')}
        </button>
      </div>

      <div className="flex gap-2 border-b dark:border-dark-50">
        {([['versions', 'ვერსიები', History], ['eco', 'ECO ცვლილებები', GitBranch]] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)} className={`flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium ${tab === key ? 'border-primary-600 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'}`}>
            <Icon size={16} /> {t(label)}
          </button>
        ))}
      </div>

      {tab === 'versions' && (
        <div className="space-y-4">
          <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <FormField label={t('პროდუქტი')}>
              <select className="input" value={selectedProduct} onChange={e => setSelectedProduct(e.target.value)}>
                <option value="">{t('აირჩიეთ პროდუქტი')}</option>
                {productOptions}
              </select>
            </FormField>
            {lifecycle && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="text-sm text-gray-500 dark:text-gray-400">{t('ეტაპი')}:</span>
                {lifecycleStages.map(s => (
                  <button key={s} onClick={() => setStage.mutate(s)}
                    className={`rounded-full px-3 py-1 text-xs font-medium ${lifecycle.stage === s ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-dark-100 dark:text-gray-400'}`}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('ვერსია')}</th>
                  <th className="px-4 py-3">{t('რევიზია')}</th>
                  <th className="px-4 py-3">{t('შენიშვნები')}</th>
                  <th className="px-4 py-3">{t('მიმდინარე')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(versions || []).length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500">{t('ვერსიები არ არის')}</td></tr>
                ) : (versions || []).map((v: any) => (
                  <tr key={v.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{v.version}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{v.revision}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{v.notes || '—'}</td>
                    <td className="px-4 py-3">{v.is_current ? <span className="badge badge-success">{t('მიმდინარე')}</span> : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'eco' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('ნომერი')}</th>
                <th className="px-4 py-3">{t('სათაური')}</th>
                <th className="px-4 py-3">{t('ტიპი')}</th>
                <th className="px-4 py-3">{t('სტატუსი')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(ecos || []).length === 0 ? (
                <tr><td colSpan={5} className="p-8 text-center text-gray-500">{t('ECO არ არის')}</td></tr>
              ) : (ecos || []).map((e: any) => (
                <tr key={e.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{e.eco_number}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{e.title}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{e.change_type}</td>
                  <td className="px-4 py-3"><span className={`badge ${e.status === 'approved' ? 'badge-success' : 'badge-warning'}`}>{e.status}</span></td>
                  <td className="px-4 py-3">
                    {e.status !== 'approved' && (
                      <button onClick={() => approveEco.mutate(e.id)} className="btn btn-sm btn-success flex items-center gap-1">
                        <CheckCircle2 size={14} /> {t('დამტკიცება')}
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
          {tab === 'versions' ? (
            <>
              <FormField label={t('ვერსია')}><input className="input" value={form.version || ''} onChange={e => setForm({ ...form, version: e.target.value })} placeholder="v1.1" /></FormField>
              <FormField label={t('შენიშვნები')}><textarea className="input min-h-[80px]" value={form.notes || ''} onChange={e => setForm({ ...form, notes: e.target.value })} /></FormField>
            </>
          ) : (
            <>
              <FormField label={t('პროდუქტი')}>
                <select className="input" value={form.product_id || ''} onChange={e => setForm({ ...form, product_id: e.target.value })}>
                  <option value="">{t('აირჩიეთ პროდუქტი')}</option>
                  {productOptions}
                </select>
              </FormField>
              <FormField label={t('სათაური')}><input className="input" value={form.title || ''} onChange={e => setForm({ ...form, title: e.target.value })} /></FormField>
              <FormField label={t('ტიპი')}>
                <select className="input" value={form.change_type || 'design'} onChange={e => setForm({ ...form, change_type: e.target.value })}>
                  <option value="design">Design</option><option value="material">Material</option><option value="process">Process</option><option value="other">Other</option>
                </select>
              </FormField>
              <FormField label={t('აღწერა')}><textarea className="input min-h-[80px]" value={form.description || ''} onChange={e => setForm({ ...form, description: e.target.value })} /></FormField>
            </>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setOpen(false)}>{t('გაუქმება')}</button>
            <button className="btn btn-primary" onClick={() => (tab === 'versions' ? createVersion : createEco).mutate()}>{t('შექმნა')}</button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
