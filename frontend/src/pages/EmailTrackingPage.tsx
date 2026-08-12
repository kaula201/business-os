import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Mail, PenLine, Plus, Trash2 } from 'lucide-react'

import DataTable from '../components/ui/DataTable'
import Modal from '../components/ui/Modal'
import { commApi } from '../services/api'

interface EmailEvent {
  id: string
  campaign_id: string
  recipient_email: string
  event_type: string
  occurred_at: string
}

interface SignatureRequest {
  id: string
  document_name: string
  signer_name: string
  signer_email: string
  status: string
  signed_at: string | null
  created_at: string
}

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function EmailTrackingPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'events' | 'signatures'>('events')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ document_name: '', signer_name: '', signer_email: '' })

  const { data: eventsData, isLoading } = useQuery({
    queryKey: ['email-events'],
    queryFn: () => commApi.listEmailEvents({ page_size: 100 }).then(r => r.data.data),
  })
  const events: EmailEvent[] = eventsData?.items || []

  const { data: sigData, isLoading: sigLoading } = useQuery({
    queryKey: ['signature-requests'],
    queryFn: () => commApi.listSignatureRequests({ page_size: 100 }).then(r => r.data.data),
  })
  const signatures: SignatureRequest[] = sigData?.items || []

  const createSig = useMutation({
    mutationFn: () => commApi.createSignatureRequest({
      document_name: form.document_name, signer_name: form.signer_name, signer_email: form.signer_email,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['signature-requests'] }); setOpen(false); setForm({ document_name: '', signer_name: '', signer_email: '' }) },
  })

  const eventColumns = [
    { key: 'recipient_email', label: 'მიმღები', priority: true, render: (e: EmailEvent) => (
      <span className="font-medium text-gray-900 dark:text-gray-100">{e.recipient_email}</span>) },
    { key: 'event_type', label: 'მოვლენა', render: (e: EmailEvent) => {
      const map: Record<string, string> = { sent: 'გაგზავნილი', opened: 'გახსნილი', clicked: 'დაკლიკებული' }
      const colors: Record<string, string> = {
        sent: 'bg-gray-100 text-gray-600 dark:bg-dark-100 dark:text-gray-400',
        opened: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
        clicked: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
      }
      return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${colors[e.event_type]}`}>{t(map[e.event_type] || e.event_type)}</span>
    } },
    { key: 'occurred_at', label: 'დრო', render: (e: EmailEvent) => new Date(e.occurred_at).toLocaleString('ka-GE') },
  ]

  const sigColumns = [
    { key: 'document_name', label: 'დოკუმენტი', priority: true, render: (s: SignatureRequest) => (
      <span className="font-semibold text-gray-900 dark:text-gray-100">{s.document_name}</span>) },
    { key: 'signer_name', label: 'ხელმომწერი', render: (s: SignatureRequest) => s.signer_name },
    { key: 'signer_email', label: 'ელ.ფოსტა', render: (s: SignatureRequest) => s.signer_email },
    { key: 'status', label: 'სტატუსი', render: (s: SignatureRequest) => {
      const map: Record<string, { label: string; cls: string }> = {
        pending: { label: 'მოლოდინი', cls: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
        signed: { label: 'ხელმოწერილი', cls: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' },
        declined: { label: 'უარყოფილი', cls: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300' },
      }
      const st = map[s.status] || { label: s.status, cls: 'bg-gray-100 text-gray-600 dark:bg-dark-100 dark:text-gray-400' }
      return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${st.cls}`}>{t(st.label)}</span>
    } },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('ელ.ფოსტის თვალთვალი და ხელმოწერები')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('კამპანიის მოვლენები · ელექტრონული ხელმოწერა')}</p>
        </div>
        {tab === 'signatures' && (
          <button onClick={() => setOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-brandgray-800 text-white hover:bg-brandgray-900 dark:bg-gray-100 dark:text-gray-900">
            <Plus size={15} /> {t('ახალი ხელმოწერის მოთხოვნა')}
          </button>
        )}
      </div>

      <div className="flex gap-1 rounded-lg bg-brandgray-100 p-1 w-fit dark:bg-dark-100">
        <button onClick={() => setTab('events')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium ${tab === 'events' ? 'bg-white shadow-sm text-gray-900 dark:bg-dark-200 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'}`}>
          <Mail size={14} className="inline mr-1 -mt-0.5" />{t('ელ.ფოსტის მოვლენები')}
        </button>
        <button onClick={() => setTab('signatures')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium ${tab === 'signatures' ? 'bg-white shadow-sm text-gray-900 dark:bg-dark-200 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'}`}>
          <PenLine size={14} className="inline mr-1 -mt-0.5" />{t('ხელმოწერის მოთხოვნები')}
        </button>
      </div>

      {tab === 'events'
        ? <DataTable columns={eventColumns} data={events} isLoading={isLoading} emptyMessage={t('ელ.ფოსტის მოვლენები არ არის')} />
        : <DataTable columns={sigColumns} data={signatures} isLoading={sigLoading} emptyMessage={t('ხელმოწერის მოთხოვნები არ არის')} />}

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი ხელმოწერის მოთხოვნა')}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დოკუმენტი')}</label>
            <input className={inputCls} value={form.document_name} onChange={e => setForm({ ...form, document_name: e.target.value })} placeholder="კონტრაქტი #1" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ხელმომწერის სახელი')}</label>
            <input className={inputCls} value={form.signer_name} onChange={e => setForm({ ...form, signer_name: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ხელმომწერის ელ.ფოსტა')}</label>
            <input type="email" className={inputCls} value={form.signer_email} onChange={e => setForm({ ...form, signer_email: e.target.value })} placeholder="client@example.ge" />
          </div>
          <button onClick={() => createSig.mutate()} disabled={createSig.isPending || !form.document_name || !form.signer_name || !form.signer_email}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('გაგზავნა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
