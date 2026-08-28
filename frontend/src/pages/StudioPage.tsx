import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LayoutGrid, Plus, Trash2, FileText, Send } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { studioApi } from '../services/api'

export default function StudioPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [formOpen, setFormOpen] = useState<string | null>(null)
  const [appName, setAppName] = useState('')
  const [formName, setFormName] = useState('')
  const [fieldLabel, setFieldLabel] = useState('')
  const [fields, setFields] = useState<{ label: string; field_type: string; required: boolean }[]>([])
  const [selectedApp, setSelectedApp] = useState<string | null>(null)
  const [recordData, setRecordData] = useState('')

  const { data: apps } = useQuery({ queryKey: ['studio-apps'], queryFn: () => studioApi.apps().then(r => r.data.data) })
  const { data: forms } = useQuery({
    queryKey: ['studio-forms', selectedApp],
    queryFn: () => (selectedApp ? studioApi.forms(selectedApp).then(r => r.data.data) : []),
    enabled: !!selectedApp,
  })
  const { data: records } = useQuery({
    queryKey: ['studio-records', formOpen],
    queryFn: () => (formOpen ? studioApi.records(formOpen).then(r => r.data.data.items) : []),
    enabled: !!formOpen,
  })

  const createApp = useMutation({
    mutationFn: () => studioApi.createApp({ name: appName }),
    onSuccess: () => { setOpen(false); setAppName(''); qc.invalidateQueries({ queryKey: ['studio-apps'] }) },
  })
  const removeApp = useMutation({
    mutationFn: (id: string) => studioApi.removeApp(id),
    onSuccess: () => { setSelectedApp(null); qc.invalidateQueries({ queryKey: ['studio-apps'] }) },
  })
  const createForm = useMutation({
    mutationFn: () => studioApi.createForm(formOpen!, { name: formName, fields }),
    onSuccess: () => { setFormOpen(null); setFormName(''); setFields([]); qc.invalidateQueries({ queryKey: ['studio-forms'] }) },
  })
  const createRecord = useMutation({
    mutationFn: () => {
      let data: Record<string, unknown> = {}
      try { data = JSON.parse(recordData) } catch { data = { value: recordData } }
      return studioApi.createRecord(formOpen!, { data })
    },
    onSuccess: () => { setRecordData(''); qc.invalidateQueries({ queryKey: ['studio-records'] }) },
  })
  const removeRecord = useMutation({
    mutationFn: (id: string) => studioApi.removeRecord(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['studio-records'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('No-code Studio')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('საკუთარი აპები: ფორმები, ველები, მონაცემები')}</p>
        </div>
        <button onClick={() => setOpen(true)} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t('ახალი აპი')}
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(apps || []).map((a: any) => (
          <div key={a.id} className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-600 dark:bg-dark-100">
                  <LayoutGrid size={20} />
                </div>
                <div>
                  <h3 className="font-semibold text-brandgray-900 dark:text-gray-100">{a.name}</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{a.form_count} {t('ფორმა')}</p>
                </div>
              </div>
              <button onClick={() => removeApp.mutate(a.id)} className="text-gray-400 hover:text-red-500">
                <Trash2 size={16} />
              </button>
            </div>
            <div className="mt-3 flex gap-2">
              <button
                onClick={() => { setSelectedApp(a.id); setFormOpen(null) }}
                className="btn btn-sm btn-outline flex-1"
              >
                {t('ფორმები')}
              </button>
              <button
                onClick={() => { setFormOpen(a.id); setSelectedApp(null) }}
                className="btn btn-sm btn-outline flex-1"
              >
                {t('ახალი ფორმა')}
              </button>
            </div>
          </div>
        ))}
        {(apps || []).length === 0 && (
          <div className="col-span-full rounded-xl border border-dashed p-10 text-center text-gray-500 dark:text-gray-400">
            {t('აპები არ არის. შექმენით პირველი აპი.')}
          </div>
        )}
      </div>

      {selectedApp && (
        <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <h2 className="mb-3 font-semibold text-brandgray-900 dark:text-gray-100">{t('ფორმები')}</h2>
          <div className="space-y-2">
            {(forms || []).map((f: any) => (
              <div key={f.id} className="flex items-center justify-between rounded-lg border p-3 dark:border-dark-50">
                <div>
                  <p className="font-medium text-brandgray-900 dark:text-gray-100">{f.name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{f.fields.length} {t('ველი')}</p>
                </div>
                <button onClick={() => setFormOpen(f.id)} className="btn btn-sm btn-outline flex items-center gap-1">
                  <FileText size={14} /> {t('ჩანაწერები')}
                </button>
              </div>
            ))}
            {(forms || []).length === 0 && <p className="text-sm text-gray-500">{t('ფორმები არ არის')}</p>}
          </div>
        </div>
      )}

      {formOpen && (
        <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <h2 className="mb-3 font-semibold text-brandgray-900 dark:text-gray-100">{t('ჩანაწერები')}</h2>
          <div className="mb-3 flex gap-2">
            <input className="input flex-1" placeholder={t('JSON მონაცემი, მაგ: {"სახელი": "ნინო"}')} value={recordData} onChange={e => setRecordData(e.target.value)} />
            <button onClick={() => createRecord.mutate()} className="btn btn-primary flex items-center gap-1">
              <Plus size={16} /> {t('დამატება')}
            </button>
          </div>
          <div className="space-y-2">
            {(records || []).map((r: any) => (
              <div key={r.id} className="flex items-center justify-between rounded-lg border p-3 dark:border-dark-50">
                <pre className="text-sm text-gray-700 dark:text-gray-300">{JSON.stringify(r.data, null, 2)}</pre>
                <button onClick={() => removeRecord.mutate(r.id)} className="text-gray-400 hover:text-red-500">
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
            {(records || []).length === 0 && <p className="text-sm text-gray-500">{t('ჩანაწერები არ არის')}</p>}
          </div>
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი აპი')}>
        <div className="space-y-4">
          <FormField label={t('აპის სახელი')}>
            <input className="input" value={appName} onChange={e => setAppName(e.target.value)} />
          </FormField>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setOpen(false)}>{t('გაუქმება')}</button>
            <button className="btn btn-primary" onClick={() => createApp.mutate()} disabled={!appName}>{t('შექმნა')}</button>
          </div>
        </div>
      </Modal>

      <Modal open={!!formOpen && !selectedApp && !records} onClose={() => setFormOpen(null)} title={t('ახალი ფორმა')}>
        <div className="space-y-4">
          <FormField label={t('ფორმის სახელი')}>
            <input className="input" value={formName} onChange={e => setFormName(e.target.value)} />
          </FormField>
          <FormField label={t('ველის სახელი')}>
            <div className="flex gap-2">
              <input className="input flex-1" value={fieldLabel} onChange={e => setFieldLabel(e.target.value)} />
              <button
                className="btn btn-outline"
                onClick={() => { if (fieldLabel) { setFields([...fields, { label: fieldLabel, field_type: 'text', required: false }]); setFieldLabel('') } }}
              >
                <Plus size={16} />
              </button>
            </div>
          </FormField>
          <div className="space-y-1">
            {fields.map((f, i) => (
              <div key={i} className="flex items-center justify-between rounded border p-2 text-sm dark:border-dark-50">
                <span>{f.label}</span>
                <button onClick={() => setFields(fields.filter((_, j) => j !== i))} className="text-gray-400 hover:text-red-500">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setFormOpen(null)}>{t('გაუქმება')}</button>
            <button className="btn btn-primary" onClick={() => createForm.mutate()} disabled={!formName}>
              {t('შექმნა')}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
