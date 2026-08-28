import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Wrench, Play, CheckCircle2, MapPin, CalendarDays, Plus } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { fieldServiceApi } from '../services/api'

export default function FieldServicePage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ scheduled_date: '', priority: 'medium', address: '', notes: '' })
  const [completeFor, setCompleteFor] = useState<string | null>(null)
  const [summary, setSummary] = useState('')
  const [signature, setSignature] = useState('')

  const { data: jobs } = useQuery({
    queryKey: ['field-service'],
    queryFn: () => fieldServiceApi.list().then(r => r.data.data),
  })
  const { data: myJobs } = useQuery({
    queryKey: ['field-service-my'],
    queryFn: () => fieldServiceApi.myJobs().then(r => r.data.data),
  })

  const createJob = useMutation({
    mutationFn: () => fieldServiceApi.create(form),
    onSuccess: () => { setOpen(false); setForm({ scheduled_date: '', priority: 'medium', address: '', notes: '' }); qc.invalidateQueries({ queryKey: ['field-service'] }); qc.invalidateQueries({ queryKey: ['field-service-my'] }) },
  })
  const startJob = useMutation({
    mutationFn: (id: string) => fieldServiceApi.start(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['field-service'] }); qc.invalidateQueries({ queryKey: ['field-service-my'] }) },
  })
  const completeJob = useMutation({
    mutationFn: () => fieldServiceApi.complete(completeFor!, { work_summary: summary, client_signature: signature }),
    onSuccess: () => { setCompleteFor(null); setSummary(''); setSignature(''); qc.invalidateQueries({ queryKey: ['field-service'] }); qc.invalidateQueries({ queryKey: ['field-service-my'] }) },
  })

  const statusBadge = (s: string) => {
    const map: Record<string, string> = {
      scheduled: 'badge-warning',
      in_progress: 'badge-info',
      completed: 'badge-success',
      cancelled: 'badge-danger',
    }
    return map[s] || 'badge'
  }
  const statusLabel = (s: string) => {
    const map: Record<string, string> = {
      scheduled: t('დაგეგმილი'),
      in_progress: t('მიმდინარე'),
      completed: t('დასრულებული'),
      cancelled: t('გაუქმებული'),
    }
    return map[s] || s
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('საველე სამუშაოები')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('ტექნიკოსების დავალებები: დაგეგმვა, დაწყება, დასრულება')}</p>
        </div>
        <button onClick={() => setOpen(true)} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t('ახალი სამუშაო')}
        </button>
      </div>

      <div className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <h2 className="mb-3 font-semibold text-brandgray-900 dark:text-gray-100">{t('ჩემი დავალებები')}</h2>
        <div className="space-y-2">
          {(myJobs || []).map((j: any) => (
            <div key={j.id} className="flex items-center justify-between rounded-lg border p-3 dark:border-dark-50">
              <div className="flex items-center gap-3">
                <Wrench size={18} className="text-primary-600" />
                <div>
                  <p className="font-medium text-brandgray-900 dark:text-gray-100">{j.address || t('მისამართი არ არის')}</p>
                  <p className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                    <CalendarDays size={12} /> {j.scheduled_date || '—'}
                    <MapPin size={12} /> {j.priority}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`badge ${statusBadge(j.status)}`}>{statusLabel(j.status)}</span>
                {j.status === 'scheduled' && (
                  <button onClick={() => startJob.mutate(j.id)} className="btn btn-sm btn-primary flex items-center gap-1">
                    <Play size={14} /> {t('დაწყება')}
                  </button>
                )}
                {j.status === 'in_progress' && (
                  <button onClick={() => setCompleteFor(j.id)} className="btn btn-sm btn-success flex items-center gap-1">
                    <CheckCircle2 size={14} /> {t('დასრულება')}
                  </button>
                )}
              </div>
            </div>
          ))}
          {(myJobs || []).length === 0 && <p className="text-sm text-gray-500">{t('აქტიური დავალებები არ არის')}</p>}
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('მისამართი')}</th>
                <th className="px-4 py-3">{t('თარიღი')}</th>
                <th className="px-4 py-3">{t('პრიორიტეტი')}</th>
                <th className="px-4 py-3">{t('სტატუსი')}</th>
                <th className="px-4 py-3">{t('შედეგი')}</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(jobs || []).length === 0 ? (
                <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('სამუშაოები არ არის')}</td></tr>
              ) : (jobs || []).map((j: any) => (
                <tr key={j.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{j.address || '—'}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{j.scheduled_date || '—'}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{j.priority}</td>
                  <td className="px-4 py-3"><span className={`badge ${statusBadge(j.status)}`}>{statusLabel(j.status)}</span></td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{j.work_summary || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი სამუშაო')}>
        <div className="space-y-4">
          <FormField label={t('თარიღი')}>
            <input type="date" className="input" value={form.scheduled_date} onChange={e => setForm({ ...form, scheduled_date: e.target.value })} />
          </FormField>
          <FormField label={t('პრიორიტეტი')}>
            <select className="input" value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </FormField>
          <FormField label={t('მისამართი')}>
            <input className="input" value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} />
          </FormField>
          <FormField label={t('შენიშვნები')}>
            <textarea className="input min-h-[80px]" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
          </FormField>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setOpen(false)}>{t('გაუქმება')}</button>
            <button className="btn btn-primary" onClick={() => createJob.mutate()} disabled={!form.scheduled_date}>{t('შექმნა')}</button>
          </div>
        </div>
      </Modal>

      <Modal open={!!completeFor} onClose={() => setCompleteFor(null)} title={t('სამუშაოს დასრულება')}>
        <div className="space-y-4">
          <FormField label={t('შესრულებული სამუშაოს აღწერა')}>
            <textarea className="input min-h-[100px]" value={summary} onChange={e => setSummary(e.target.value)} />
          </FormField>
          <FormField label={t('კლიენტის ხელმოწერა (სახელი)')}>
            <input className="input" value={signature} onChange={e => setSignature(e.target.value)} />
          </FormField>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setCompleteFor(null)}>{t('გაუქმება')}</button>
            <button className="btn btn-success" onClick={() => completeJob.mutate()} disabled={!summary}>
              {t('დასრულება')}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
