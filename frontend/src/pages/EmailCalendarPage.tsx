import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Mail, Calendar, Plus, Trash2 } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { emailCalendarApi } from '../services/api'

const tabs = [
  { id: 'emails', label: 'ელ.ფოსტა', icon: Mail },
  { id: 'calendar', label: 'კალენდარი', icon: Calendar },
]

export default function EmailCalendarPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState('emails')
  const [error, setError] = useState('')
  const [emailForm, setEmailForm] = useState({ to_email: '', subject: '', body: '' })
  const [emailOpen, setEmailOpen] = useState(false)
  const [eventForm, setEventForm] = useState({ title: '', event_date: '', event_type: 'meeting' })
  const [eventOpen, setEventOpen] = useState(false)

  const { data: emails } = useQuery({ queryKey: ['ec-emails'], queryFn: () => emailCalendarApi.emails().then(r => r.data.data) })
  const { data: events } = useQuery({ queryKey: ['ec-events'], queryFn: () => emailCalendarApi.events().then(r => r.data.data) })

  const sendEmail = useMutation({
    mutationFn: () => emailCalendarApi.sendEmail(emailForm),
    onSuccess: () => { setEmailOpen(false); setEmailForm({ to_email: '', subject: '', body: '' }); qc.invalidateQueries({ queryKey: ['ec-emails'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const createEvent = useMutation({
    mutationFn: () => emailCalendarApi.createEvent({ ...eventForm, event_date: new Date(eventForm.event_date).toISOString() }),
    onSuccess: () => { setEventOpen(false); setEventForm({ title: '', event_date: '', event_type: 'meeting' }); qc.invalidateQueries({ queryKey: ['ec-events'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const removeEvent = useMutation({
    mutationFn: (id: string) => emailCalendarApi.removeEvent(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ec-events'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('ელ.ფოსტა და კალენდარი')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('Email გაგზავნა, კალენდრის ღონისძიებები')}</p>
        </div>
        <button onClick={() => tab === 'emails' ? setEmailOpen(true) : setEventOpen(true)} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {tab === 'emails' ? t('ახალი ელ.ფოსტა') : t('ახალი ღონისძიება')}
        </button>
      </div>

      <div className="flex gap-1 border-b border-brandgray-100 dark:border-dark-50">
        {tabs.map(tabItem => (
          <button key={tabItem.id} onClick={() => setTab(tabItem.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === tabItem.id ? 'border-primary-600 text-primary-700 dark:border-primary-400 dark:text-primary-300' : 'border-transparent text-brandgray-500 hover:text-brandgray-700 dark:text-gray-400'
            }`}>
            <tabItem.icon size={18} /> {t(tabItem.label)}
          </button>
        ))}
      </div>

      {tab === 'emails' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('მიმღები')}</th>
                  <th className="px-4 py-3">{t('სათაური')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3">{t('თარიღი')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(emails || []).length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('ელ.ფოსტები არ არის')}</td></tr>
                ) : (emails || []).map((m: any) => (
                  <tr key={m.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono text-xs text-gray-700 dark:text-gray-300">{m.to_email}</td>
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{m.subject}</td>
                    <td className="px-4 py-3"><span className="rounded-full bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400 px-2.5 py-1 text-xs font-medium">{m.status}</span></td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{new Date(m.created_at).toLocaleDateString('ka-GE')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'calendar' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სათაური')}</th>
                  <th className="px-4 py-3">{t('ტიპი')}</th>
                  <th className="px-4 py-3">{t('თარიღი')}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(events || []).length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('ღონისძიებები არ არის')}</td></tr>
                ) : (events || []).map((e: any) => (
                  <tr key={e.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{e.title}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{e.event_type}</td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{new Date(e.event_date).toLocaleDateString('ka-GE')}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => removeEvent.mutate(e.id)} className="text-red-500 hover:text-red-700"><Trash2 size={16} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Modal open={emailOpen} onClose={() => setEmailOpen(false)} title={t('ახალი ელ.ფოსტა')}>
        <div className="space-y-4">
          <FormField label={t('მიმღები')} required>
            <input value={emailForm.to_email} onChange={e => setEmailForm({ ...emailForm, to_email: e.target.value })}
              placeholder="client@company.ge" className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('სათაური')} required>
            <input value={emailForm.subject} onChange={e => setEmailForm({ ...emailForm, subject: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('ტექსტი')}>
            <textarea value={emailForm.body} onChange={e => setEmailForm({ ...emailForm, body: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" rows={3} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => sendEmail.mutate()} disabled={!emailForm.to_email || !emailForm.subject || sendEmail.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('გაგზავნა')}
          </button>
        </div>
      </Modal>

      <Modal open={eventOpen} onClose={() => setEventOpen(false)} title={t('ახალი ღონისძიება')}>
        <div className="space-y-4">
          <FormField label={t('სათაური')} required>
            <input value={eventForm.title} onChange={e => setEventForm({ ...eventForm, title: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('ტიპი')}>
            <select value={eventForm.event_type} onChange={e => setEventForm({ ...eventForm, event_type: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="meeting">{t('შეხვედრა')}</option>
              <option value="call">{t('ზარი')}</option>
              <option value="reminder">{t('შეხსენება')}</option>
              <option value="deadline">{t('ვადა')}</option>
            </select>
          </FormField>
          <FormField label={t('თარიღი')} required>
            <input type="datetime-local" value={eventForm.event_date} onChange={e => setEventForm({ ...eventForm, event_date: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createEvent.mutate()} disabled={!eventForm.title || !eventForm.event_date || createEvent.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შექმნა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
