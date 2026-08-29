import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PenLine, Plus, Send, CheckCircle2, XCircle } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { signatureApi } from '../services/api'
import { fmtDate } from '../lib/format'

const statusBadge = (s: string) => {
  const map: Record<string, string> = {
    pending: 'badge-warning', signed: 'badge-success', declined: 'badge-danger', expired: 'badge',
  }
  return map[s] || 'badge'
}

export default function SignPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ document_name: '', signer_name: '', signer_email: '', message: '', send_email: true })

  const { data: requests } = useQuery({
    queryKey: ['signature-requests'],
    queryFn: () => signatureApi.list().then(r => r.data.data.items),
  })

  const createReq = useMutation({
    mutationFn: () => signatureApi.create(form),
    onSuccess: () => { setOpen(false); setForm({ document_name: '', signer_name: '', signer_email: '', message: '', send_email: true }); qc.invalidateQueries({ queryKey: ['signature-requests'] }) },
  })
  const resend = useMutation({
    mutationFn: (id: string) => signatureApi.resend(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['signature-requests'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('ელექტრონული ხელმოწერა')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('მოწვევა, ხელმოწერა, სტატუსი')}</p>
        </div>
        <button onClick={() => setOpen(true)} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t('ახალი მოწვევა')}
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('დოკუმენტი')}</th>
                <th className="px-4 py-3">{t('ხელმომწერი')}</th>
                <th className="px-4 py-3">{t('ელფოსტა')}</th>
                <th className="px-4 py-3">{t('სტატუსი')}</th>
                <th className="px-4 py-3">{t('ხელმოწერილია')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(requests || []).length === 0 ? (
                <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('მოწვევები არ არის')}</td></tr>
              ) : (requests || []).map((r: any) => (
                <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{r.document_name}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.signer_name}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.signer_email}</td>
                  <td className="px-4 py-3"><span className={`badge ${statusBadge(r.status)}`}>{r.status}</span></td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {r.signed_at ? fmtDate(new Date(r.signed_at)) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {r.status === 'pending' && (
                      <button onClick={() => resend.mutate(r.id)} className="btn btn-sm btn-outline flex items-center gap-1" title={t('ხელახლა გაგზავნა')}>
                        <Send size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი მოწვევა')}>
        <div className="space-y-4">
          <FormField label={t('დოკუმენტი')}>
            <input className="input" value={form.document_name} onChange={e => setForm({ ...form, document_name: e.target.value })} />
          </FormField>
          <FormField label={t('ხელმომწერი')}>
            <input className="input" value={form.signer_name} onChange={e => setForm({ ...form, signer_name: e.target.value })} />
          </FormField>
          <FormField label={t('ელფოსტა')}>
            <input type="email" className="input" value={form.signer_email} onChange={e => setForm({ ...form, signer_email: e.target.value })} />
          </FormField>
          <FormField label={t('შეტყობინება')}>
            <textarea className="input min-h-[80px]" value={form.message} onChange={e => setForm({ ...form, message: e.target.value })} />
          </FormField>
          <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <input type="checkbox" checked={form.send_email} onChange={e => setForm({ ...form, send_email: e.target.checked })} />
            {t('მოწვევის გაგზავნა ელფოსტაზე')}
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setOpen(false)}>{t('გაუქმება')}</button>
            <button className="btn btn-primary" onClick={() => createReq.mutate()} disabled={!form.document_name || !form.signer_name || !form.signer_email}>
              {t('გაგზავნა')}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
