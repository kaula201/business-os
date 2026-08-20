import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Ticket, Inbox, Timer, Layers, TrendingUp, MessageSquare, BookOpen, Wrench, Mail, Users, GitBranch, X } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { helpdeskApi } from '../services/api'

const tabs = [
  { id: 'tickets', label: 'ტიკეტები', icon: Ticket },
  { id: 'teams', label: 'გუნდები', icon: Users },
  { id: 'pipelines', label: 'პაიპლაინები', icon: GitBranch },
  { id: 'queues', label: 'რიგები', icon: Layers },
  { id: 'slas', label: 'SLA', icon: Timer },
  { id: 'escalations', label: 'ესკალაციები', icon: TrendingUp },
  { id: 'canned', label: 'მზა პასუხები', icon: MessageSquare },
  { id: 'knowledge', label: 'ცოდნის ბაზა', icon: BookOpen },
  { id: 'field', label: 'საველე სამუშაო', icon: Wrench },
  { id: 'email', label: 'Email Intake', icon: Mail },
]

const statusColors: Record<string, string> = {
  new: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  open: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  in_progress: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  resolved: 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  closed: 'bg-gray-100 text-gray-600 dark:bg-dark-100 dark:text-gray-400',
}

export default function HelpdeskPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState('tickets')
  const [error, setError] = useState('')

  // Ticket form
  const [ticketForm, setTicketForm] = useState({ subject: '', description: '', priority: 'medium' })
  const [ticketOpen, setTicketOpen] = useState(false)
  // Queue form
  const [queueForm, setQueueForm] = useState({ name: '', description: '' })
  const [queueOpen, setQueueOpen] = useState(false)
  // SLA form
  const [slaForm, setSlaForm] = useState({ name: '', priority: 'medium', response_hours: 24, resolution_hours: 72 })
  const [slaOpen, setSlaOpen] = useState(false)
  // Canned form
  const [cannedForm, setCannedForm] = useState({ title: '', body: '', category: '' })
  const [cannedOpen, setCannedOpen] = useState(false)
  // KB form
  const [kbForm, setKbForm] = useState({ title: '', content: '', category: '' })
  const [kbOpen, setKbOpen] = useState(false)
  // Field service form
  const [fieldForm, setFieldForm] = useState({ status: 'scheduled', address: '', notes: '' })
  const [fieldOpen, setFieldOpen] = useState(false)
  // Email intake form
  const [emailForm, setEmailForm] = useState({ mailbox: '', priority: 'medium' })
  const [emailOpen, setEmailOpen] = useState(false)
  // Team form
  const [teamForm, setTeamForm] = useState({ name: '', description: '' })
  const [teamOpen, setTeamOpen] = useState(false)
  const [teams, setTeams] = useState<any[]>([])
  // Pipeline form
  const [pipelineForm, setPipelineForm] = useState({ name: '', description: '', stages: '' })
  const [pipelineOpen, setPipelineOpen] = useState(false)
  const [pipelines, setPipelines] = useState<any[]>([])

  const { data: ticketsData, isLoading: ticketsLoading } = useQuery({
    queryKey: ['hd-tickets'],
    queryFn: () => helpdeskApi.listTickets({ page_size: 100 }).then(r => r.data.data),
  })
  const tickets: any[] = ticketsData?.items || []

  const { data: queues } = useQuery({ queryKey: ['hd-queues'], queryFn: () => helpdeskApi.queues().then(r => r.data.data) })
  const { data: slas } = useQuery({ queryKey: ['hd-slas'], queryFn: () => helpdeskApi.slas().then(r => r.data.data) })
  const { data: escalations } = useQuery({ queryKey: ['hd-escalations'], queryFn: () => helpdeskApi.escalations().then(r => r.data.data) })
  const { data: canned } = useQuery({ queryKey: ['hd-canned'], queryFn: () => helpdeskApi.cannedReplies().then(r => r.data.data) })
  const { data: knowledge } = useQuery({ queryKey: ['hd-knowledge'], queryFn: () => helpdeskApi.knowledge().then(r => r.data.data) })
  const { data: fieldJobs } = useQuery({ queryKey: ['hd-field'], queryFn: () => helpdeskApi.fieldService().then(r => r.data.data) })
  const { data: emailRules } = useQuery({ queryKey: ['hd-email'], queryFn: () => helpdeskApi.emailIntake().then(r => r.data.data) })

  const createTicket = useMutation({
    mutationFn: () => helpdeskApi.createTicket(ticketForm),
    onSuccess: () => { setTicketOpen(false); setTicketForm({ subject: '', description: '', priority: 'medium' }); qc.invalidateQueries({ queryKey: ['hd-tickets'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const createQueue = useMutation({
    mutationFn: () => helpdeskApi.createQueue(queueForm),
    onSuccess: () => { setQueueOpen(false); setQueueForm({ name: '', description: '' }); qc.invalidateQueries({ queryKey: ['hd-queues'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const createSla = useMutation({
    mutationFn: () => helpdeskApi.createSla(slaForm),
    onSuccess: () => { setSlaOpen(false); setSlaForm({ name: '', priority: 'medium', response_hours: 24, resolution_hours: 72 }); qc.invalidateQueries({ queryKey: ['hd-slas'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const createCanned = useMutation({
    mutationFn: () => helpdeskApi.createCannedReply(cannedForm),
    onSuccess: () => { setCannedOpen(false); setCannedForm({ title: '', body: '', category: '' }); qc.invalidateQueries({ queryKey: ['hd-canned'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const createKb = useMutation({
    mutationFn: () => helpdeskApi.createKnowledge(kbForm),
    onSuccess: () => { setKbOpen(false); setKbForm({ title: '', content: '', category: '' }); qc.invalidateQueries({ queryKey: ['hd-knowledge'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const createField = useMutation({
    mutationFn: () => helpdeskApi.createFieldService(fieldForm),
    onSuccess: () => { setFieldOpen(false); setFieldForm({ status: 'scheduled', address: '', notes: '' }); qc.invalidateQueries({ queryKey: ['hd-field'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const createEmail = useMutation({
    mutationFn: () => helpdeskApi.createEmailIntake(emailForm),
    onSuccess: () => { setEmailOpen(false); setEmailForm({ mailbox: '', priority: 'medium' }); qc.invalidateQueries({ queryKey: ['hd-email'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })

  const openBtn = () => {
    if (tab === 'tickets') setTicketOpen(true)
    else if (tab === 'teams') setTeamOpen(true)
    else if (tab === 'pipelines') setPipelineOpen(true)
    else if (tab === 'queues') setQueueOpen(true)
    else if (tab === 'slas') setSlaOpen(true)
    else if (tab === 'canned') setCannedOpen(true)
    else if (tab === 'knowledge') setKbOpen(true)
    else if (tab === 'field') setFieldOpen(true)
    else if (tab === 'email') setEmailOpen(true)
  }

  const btnLabel = () => {
    const map: Record<string, string> = {
      tickets: 'ახალი ტიკეტი', teams: 'ახალი გუნდი', pipelines: 'ახალი პაიპლაინი', queues: 'ახალი რიგი', slas: 'ახალი SLA', canned: 'ახალი მზა პასუხი',
      knowledge: 'ახალი სტატია', field: 'ახალი საველე სამუშაო', email: 'ახალი წესი',
    }
    return map[tab] || ''
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('Helpdesk / მხარდაჭერა')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('ტიკეტები, SLA, ცოდნის ბაზა, საველე სამუშაო')}</p>
        </div>
        <button onClick={openBtn} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t(btnLabel())}
        </button>
      </div>

      <div className="flex gap-1 border-b border-brandgray-100 dark:border-dark-50 overflow-x-auto">
        {tabs.map(tabItem => (
          <button key={tabItem.id} onClick={() => setTab(tabItem.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              tab === tabItem.id
                ? 'border-primary-600 text-primary-700 dark:border-primary-400 dark:text-primary-300'
                : 'border-transparent text-brandgray-500 hover:text-brandgray-700 dark:text-gray-400'
            }`}>
            <tabItem.icon size={18} /> {t(tabItem.label)}
          </button>
        ))}
      </div>

      {tab === 'tickets' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სათაური')}</th>
                  <th className="px-4 py-3">{t('პრიორიტეტი')}</th>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3">{t('შექმნილია')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {ticketsLoading ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
                ) : tickets.length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('ტიკეტები არ არის')}</td></tr>
                ) : tickets.map((tk: any) => (
                  <tr key={tk.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{tk.subject}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{tk.priority}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusColors[tk.status] || ''}`}>{tk.status}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{new Date(tk.created_at).toLocaleDateString('ka-GE')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'teams' && (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {teams.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 col-span-full">{t('გუნდები არ არის')}</p>
          ) : teams.map((tm: any) => (
            <div key={tm.id} className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <div className="flex items-center justify-between">
                <div className="font-semibold text-brandgray-900 dark:text-gray-100">{tm.name}</div>
                <button onClick={() => helpdeskApi.removeTeam(tm.id).then(() => helpdeskApi.teams().then(r => setTeams(r.data.data)))}
                  className="text-gray-400 hover:text-red-600"><X size={15} /></button>
              </div>
              <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">{tm.description || '—'}</div>
              <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                {t('ლიდერი')}: {tm.lead_name || '—'} · {tm.member_count} {t('წევრი')}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'pipelines' && (
        <div className="grid gap-3 md:grid-cols-2">
          {pipelines.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 col-span-full">{t('პაიპლაინები არ არის')}</p>
          ) : pipelines.map((pl: any) => (
            <div key={pl.id} className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <div className="flex items-center justify-between">
                <div className="font-semibold text-brandgray-900 dark:text-gray-100">{pl.name}</div>
                <button onClick={() => helpdeskApi.removePipeline(pl.id).then(() => helpdeskApi.pipelines().then(r => setPipelines(r.data.data)))}
                  className="text-gray-400 hover:text-red-600"><X size={15} /></button>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(pl.stages || []).map((s: any, i: number) => (
                  <span key={s.id} className={`rounded-full px-2.5 py-1 text-xs font-medium ${s.is_done ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'}`}>
                    {i + 1}. {s.name}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'queues' && (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {(queues || []).length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 col-span-full">{t('რიგები არ არის')}</p>
          ) : (queues || []).map((q: any) => (
            <div key={q.id} className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <div className="font-semibold text-brandgray-900 dark:text-gray-100">{q.name}</div>
              <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">{q.description || '—'}</div>
            </div>
          ))}
        </div>
      )}

      {tab === 'slas' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სახელი')}</th>
                  <th className="px-4 py-3">{t('პრიორიტეტი')}</th>
                  <th className="px-4 py-3 text-right">{t('რეაგირება (სთ)')}</th>
                  <th className="px-4 py-3 text-right">{t('გადაწყვეტა (სთ)')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(slas || []).length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('SLA არ არის')}</td></tr>
                ) : (slas || []).map((s: any) => (
                  <tr key={s.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{s.name}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{s.priority}</td>
                    <td className="px-4 py-3 text-right font-mono">{s.response_hours}</td>
                    <td className="px-4 py-3 text-right font-mono">{s.resolution_hours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'escalations' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('ტიკეტი')}</th>
                  <th className="px-4 py-3">{t('დონე')}</th>
                  <th className="px-4 py-3">{t('მიზეზი')}</th>
                  <th className="px-4 py-3">{t('თარიღი')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(escalations || []).length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('ესკალაციები არ არის')}</td></tr>
                ) : (escalations || []).map((e: any) => (
                  <tr key={e.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono text-xs text-gray-600 dark:text-gray-400">{e.ticket_id?.slice(0, 8)}</td>
                    <td className="px-4 py-3"><span className="rounded-full bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400 px-2.5 py-1 text-xs font-medium">L{e.level}</span></td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{e.reason || '—'}</td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{new Date(e.created_at).toLocaleDateString('ka-GE')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'canned' && (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {(canned || []).length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 col-span-full">{t('მზა პასუხები არ არის')}</p>
          ) : (canned || []).map((c: any) => (
            <div key={c.id} className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <div className="font-semibold text-brandgray-900 dark:text-gray-100">{c.title}</div>
              <div className="mt-1 text-sm text-gray-500 dark:text-gray-400 line-clamp-3">{c.body}</div>
            </div>
          ))}
        </div>
      )}

      {tab === 'knowledge' && (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {(knowledge || []).length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 col-span-full">{t('სტატიები არ არის')}</p>
          ) : (knowledge || []).map((k: any) => (
            <div key={k.id} className="rounded-xl border bg-white p-4 shadow-sm dark:border-dark-50 dark:bg-dark-200">
              <div className="font-semibold text-brandgray-900 dark:text-gray-100">{k.title}</div>
              <div className="mt-1 text-sm text-gray-500 dark:text-gray-400 line-clamp-3">{k.content}</div>
              {k.category && <div className="mt-2 text-xs text-primary-600 dark:text-primary-400">{k.category}</div>}
            </div>
          ))}
        </div>
      )}

      {tab === 'field' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('სტატუსი')}</th>
                  <th className="px-4 py-3">{t('თარიღი')}</th>
                  <th className="px-4 py-3">{t('მისამართი')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(fieldJobs || []).length === 0 ? (
                  <tr><td colSpan={3} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('საველე სამუშაოები არ არის')}</td></tr>
                ) : (fieldJobs || []).map((f: any) => (
                  <tr key={f.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3"><span className="rounded-full bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400 px-2.5 py-1 text-xs font-medium">{f.status}</span></td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{f.scheduled_date ? new Date(f.scheduled_date).toLocaleDateString('ka-GE') : '—'}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{f.address || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'email' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('მეილბოქსი')}</th>
                  <th className="px-4 py-3">{t('პრიორიტეტი')}</th>
                  <th className="px-4 py-3">{t('აქტიური')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(emailRules || []).length === 0 ? (
                  <tr><td colSpan={3} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('წესები არ არის')}</td></tr>
                ) : (emailRules || []).map((r: any) => (
                  <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono text-gray-700 dark:text-gray-300">{r.mailbox}</td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.priority}</td>
                    <td className="px-4 py-3">{r.is_active ? '✓' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Ticket modal */}
      <Modal open={ticketOpen} onClose={() => setTicketOpen(false)} title={t('ახალი ტიკეტი')}>
        <div className="space-y-4">
          <FormField label={t('სათაური')} required>
            <input value={ticketForm.subject} onChange={e => setTicketForm({ ...ticketForm, subject: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('აღწერა')}>
            <textarea value={ticketForm.description} onChange={e => setTicketForm({ ...ticketForm, description: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" rows={3} />
          </FormField>
          <FormField label={t('პრიორიტეტი')}>
            <select value={ticketForm.priority} onChange={e => setTicketForm({ ...ticketForm, priority: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="low">{t('დაბალი')}</option>
              <option value="medium">{t('საშუალო')}</option>
              <option value="high">{t('მაღალი')}</option>
              <option value="urgent">{t('გადაუდებელი')}</option>
            </select>
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createTicket.mutate()} disabled={!ticketForm.subject || createTicket.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* Queue modal */}
      <Modal open={queueOpen} onClose={() => setQueueOpen(false)} title={t('ახალი რიგი')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')} required>
            <input value={queueForm.name} onChange={e => setQueueForm({ ...queueForm, name: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('აღწერა')}>
            <textarea value={queueForm.description} onChange={e => setQueueForm({ ...queueForm, description: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createQueue.mutate()} disabled={!queueForm.name || createQueue.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* SLA modal */}
      <Modal open={slaOpen} onClose={() => setSlaOpen(false)} title={t('ახალი SLA')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')} required>
            <input value={slaForm.name} onChange={e => setSlaForm({ ...slaForm, name: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('პრიორიტეტი')}>
            <select value={slaForm.priority} onChange={e => setSlaForm({ ...slaForm, priority: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="low">{t('დაბალი')}</option>
              <option value="medium">{t('საშუალო')}</option>
              <option value="high">{t('მაღალი')}</option>
            </select>
          </FormField>
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label={t('რეაგირება (სთ)')}>
              <input type="number" min={1} value={slaForm.response_hours} onChange={e => setSlaForm({ ...slaForm, response_hours: Number(e.target.value) })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
            <FormField label={t('გადაწყვეტა (სთ)')}>
              <input type="number" min={1} value={slaForm.resolution_hours} onChange={e => setSlaForm({ ...slaForm, resolution_hours: Number(e.target.value) })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createSla.mutate()} disabled={!slaForm.name || createSla.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* Canned modal */}
      <Modal open={cannedOpen} onClose={() => setCannedOpen(false)} title={t('ახალი მზა პასუხი')}>
        <div className="space-y-4">
          <FormField label={t('სათაური')} required>
            <input value={cannedForm.title} onChange={e => setCannedForm({ ...cannedForm, title: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('ტექსტი')} required>
            <textarea value={cannedForm.body} onChange={e => setCannedForm({ ...cannedForm, body: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" rows={3} />
          </FormField>
          <FormField label={t('კატეგორია')}>
            <input value={cannedForm.category} onChange={e => setCannedForm({ ...cannedForm, category: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createCanned.mutate()} disabled={!cannedForm.title || !cannedForm.body || createCanned.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* KB modal */}
      <Modal open={kbOpen} onClose={() => setKbOpen(false)} title={t('ახალი სტატია')}>
        <div className="space-y-4">
          <FormField label={t('სათაური')} required>
            <input value={kbForm.title} onChange={e => setKbForm({ ...kbForm, title: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('შინაარსი')} required>
            <textarea value={kbForm.content} onChange={e => setKbForm({ ...kbForm, content: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" rows={4} />
          </FormField>
          <FormField label={t('კატეგორია')}>
            <input value={kbForm.category} onChange={e => setKbForm({ ...kbForm, category: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createKb.mutate()} disabled={!kbForm.title || !kbForm.content || createKb.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* Field service modal */}
      <Modal open={fieldOpen} onClose={() => setFieldOpen(false)} title={t('ახალი საველე სამუშაო')}>
        <div className="space-y-4">
          <FormField label={t('სტატუსი')}>
            <select value={fieldForm.status} onChange={e => setFieldForm({ ...fieldForm, status: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="scheduled">{t('დაგეგმილი')}</option>
              <option value="in_progress">{t('პროცესში')}</option>
              <option value="completed">{t('დასრულებული')}</option>
            </select>
          </FormField>
          <FormField label={t('მისამართი')}>
            <input value={fieldForm.address} onChange={e => setFieldForm({ ...fieldForm, address: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('შენიშვნები')}>
            <textarea value={fieldForm.notes} onChange={e => setFieldForm({ ...fieldForm, notes: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createField.mutate()} disabled={createField.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* Email intake modal */}
      <Modal open={emailOpen} onClose={() => setEmailOpen(false)} title={t('ახალი წესი')}>
        <div className="space-y-4">
          <FormField label={t('მეილბოქსი')} required>
            <input value={emailForm.mailbox} onChange={e => setEmailForm({ ...emailForm, mailbox: e.target.value })}
              placeholder="support@company.ge" className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('პრიორიტეტი')}>
            <select value={emailForm.priority} onChange={e => setEmailForm({ ...emailForm, priority: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="low">{t('დაბალი')}</option>
              <option value="medium">{t('საშუალო')}</option>
              <option value="high">{t('მაღალი')}</option>
            </select>
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createEmail.mutate()} disabled={!emailForm.mailbox || createEmail.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* Team modal */}
      <Modal open={teamOpen} onClose={() => setTeamOpen(false)} title={t('ახალი გუნდი')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')} required>
            <input value={teamForm.name} onChange={e => setTeamForm({ ...teamForm, name: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('აღწერა')}>
            <textarea value={teamForm.description} onChange={e => setTeamForm({ ...teamForm, description: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" rows={2} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => helpdeskApi.createTeam(teamForm).then(() => {
            setTeamOpen(false); setTeamForm({ name: '', description: '' }); helpdeskApi.teams().then(r => setTeams(r.data.data))
          })} disabled={!teamForm.name}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>

      {/* Pipeline modal */}
      <Modal open={pipelineOpen} onClose={() => setPipelineOpen(false)} title={t('ახალი პაიპლაინი')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')} required>
            <input value={pipelineForm.name} onChange={e => setPipelineForm({ ...pipelineForm, name: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('აღწერა')}>
            <input value={pipelineForm.description} onChange={e => setPipelineForm({ ...pipelineForm, description: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('სტადიები (თითო ხაზზე)')} required>
            <textarea value={pipelineForm.stages} onChange={e => setPipelineForm({ ...pipelineForm, stages: e.target.value })}
              placeholder="New&#10;Triaged&#10;Done" className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" rows={3} />
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => {
            const stages = pipelineForm.stages.split('\n').map(s => s.trim()).filter(Boolean)
            helpdeskApi.createPipeline({ name: pipelineForm.name, description: pipelineForm.description, stages }).then(() => {
              setPipelineOpen(false); setPipelineForm({ name: '', description: '', stages: '' }); helpdeskApi.pipelines().then(r => setPipelines(r.data.data))
            })
          }} disabled={!pipelineForm.name || !pipelineForm.stages.trim()}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
