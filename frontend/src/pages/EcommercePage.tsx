import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShoppingCart, Plus, Send, Trash2, Package } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { emailMarketingApi } from '../services/api'
import { fmtDate } from '../lib/format'

export default function EcommercePage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: '', subject: '', body: '', audience: '' })

  const { data: campaigns } = useQuery({
    queryKey: ['email-campaigns'],
    queryFn: () => emailMarketingApi.list().then(r => r.data.data.items),
  })

  const createCampaign = useMutation({
    mutationFn: () => emailMarketingApi.create({
      name: form.name,
      subject: form.subject,
      body: form.body,
      audience: { emails: form.audience.split(',').map((e: string) => e.trim()).filter(Boolean) },
    }),
    onSuccess: () => { setOpen(false); setForm({ name: '', subject: '', body: '', audience: '' }); qc.invalidateQueries({ queryKey: ['email-campaigns'] }) },
  })

  const sendCampaign = useMutation({
    mutationFn: (id: string) => emailMarketingApi.send(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['email-campaigns'] }),
  })

  const removeCampaign = useMutation({
    mutationFn: (id: string) => emailMarketingApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['email-campaigns'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('ელ. მარკეტინგი')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('კამპანიები: შექმნა, გაგზავნა, სტატისტიკა')}</p>
        </div>
        <button onClick={() => setOpen(true)} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t('ახალი კამპანია')}
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('სახელი')}</th>
                <th className="px-4 py-3">{t('თემა')}</th>
                <th className="px-4 py-3">{t('სტატუსი')}</th>
                <th className="px-4 py-3">{t('გაგზავნილია')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(campaigns || []).length === 0 ? (
                <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('კამპანიები არ არის')}</td></tr>
              ) : (campaigns || []).map((c: any) => (
                <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{c.name}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{c.subject}</td>
                  <td className="px-4 py-3">
                    <span className={`badge ${c.status === 'sent' ? 'badge-success' : 'badge-warning'}`}>{t(c.status === 'sent' ? 'გაგზავნილი' : 'მონახაზი')}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{c.sent_at ? fmtDate(new Date(c.sent_at)) : '—'}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {c.status !== 'sent' && (
                        <button onClick={() => sendCampaign.mutate(c.id)} className="btn btn-sm btn-primary flex items-center gap-1" title={t('გაგზავნა')}>
                          <Send size={14} />
                        </button>
                      )}
                      <button onClick={() => removeCampaign.mutate(c.id)} className="btn btn-sm btn-danger flex items-center gap-1" title={t('წაშლა')}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი კამპანია')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')}>
            <input className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          </FormField>
          <FormField label={t('თემა')}>
            <input className="input" value={form.subject} onChange={e => setForm({ ...form, subject: e.target.value })} />
          </FormField>
          <FormField label={t('შინაარსი')}>
            <textarea className="input min-h-[100px]" value={form.body} onChange={e => setForm({ ...form, body: e.target.value })} />
          </FormField>
          <FormField label={t('მიმღებები (ელფოსტები, მძიმით გამოყოფილი)')}>
            <input className="input" value={form.audience} onChange={e => setForm({ ...form, audience: e.target.value })} placeholder="a@test.ge, b@test.ge" />
          </FormField>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setOpen(false)}>{t('გაუქმება')}</button>
            <button className="btn btn-primary" onClick={() => createCampaign.mutate()} disabled={!form.name || !form.subject}>
              {t('შექმნა')}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
