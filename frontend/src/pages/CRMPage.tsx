import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '../i18n'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  BriefcaseBusiness,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  CircleDollarSign,
  Mail,
  Phone,
  Plus,
  Search,
  Settings2,
  Target,
  UserPlus,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import Modal from '../components/ui/Modal'
import CrmEnterpriseView from '../components/crm/CrmEnterpriseView'
import { authApi, crmApi, salesOrgApi } from '../services/api'
import type {
  CRMActivity,
  CRMActivityType,
  CRMLead,
  CRMLeadCreate,
  CRMLeadSource,
  CRMLeadStatus,
  CRMOpportunity,
  CRMOpportunityStage,
  CRMPipelineStage,
} from '../types'

type CRMView = 'overview' | 'leads' | 'pipeline' | 'activities' | 'enterprise'

const leadStatusLabels: Record<CRMLeadStatus, string> = {
  new: 'ახალი',
  contacted: 'დაკავშირებული',
  qualified: 'კვალიფიცირებული',
  unqualified: 'არაკვალიფიცირებული',
  converted: 'კლიენტად გადაყვანილი',
}

const sourceLabels: Record<CRMLeadSource, string> = {
  website: 'ვებსაიტი',
  referral: 'რეკომენდაცია',
  campaign: 'კამპანია / სოციალური ქსელი',
  phone: 'შემომავალი ზარი',
  email: 'ელფოსტა',
  other: 'სხვა',
}

const activityLabels: Record<CRMActivityType, string> = {
  call: 'ზარი',
  meeting: 'შეხვედრა',
  email: 'ელფოსტა',
  task: 'დავალება',
  note: 'ჩანაწერი',
}

const emptyLead: CRMLeadCreate = {
  company_name: '',
  contact_name: '',
  email: '',
  phone: '',
  source: 'other',
  estimated_value: 0,
  notes: '',
  team_id: '',
}

const money = (value: number | string | undefined) =>
  new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL', maximumFractionDigits: 2 }).format(Number(value || 0))

const dateTime = (value?: string) => value
  ? new Intl.DateTimeFormat('ka-GE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
  : i18n.t('ვადა არ არის მითითებული')

function errorMessage(error: any) {
  return error?.response?.data?.detail || i18n.t('მოქმედება ვერ შესრულდა. გადაამოწმეთ მონაცემები.')
}

export default function CRMPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedView = searchParams.get('view') as CRMView | null
  const [view, setView] = useState<CRMView>(requestedView || 'overview')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [message, setMessage] = useState('')
  const [newLeadOpen, setNewLeadOpen] = useState(false)
  const [selectedLead, setSelectedLead] = useState<CRMLead | null>(null)
  const [opportunityOpen, setOpportunityOpen] = useState(false)
  const [activityOpen, setActivityOpen] = useState(false)
  const [convertOpen, setConvertOpen] = useState(false)
  const [leadForm, setLeadForm] = useState<CRMLeadCreate>(emptyLead)
  const [opportunityForm, setOpportunityForm] = useState({ name: '', amount: 0, probability: 20, expected_close_date: '' })
  const [activityForm, setActivityForm] = useState<{ activity_type: CRMActivityType; subject: string; description: string; due_at: string }>({
    activity_type: 'call', subject: '', description: '', due_at: '',
  })
  const [convertForm, setConvertForm] = useState({
    client_type: 'legal' as 'legal' | 'individual', identification_code: '', is_vat_payer: true, name: '', address: '', notes: '',
  })
  const [stagesOpen, setStagesOpen] = useState(false)
  const [stageForm, setStageForm] = useState({ key: '', name: '', probability: 10, color: '#3b82f6' })
  const [editingStage, setEditingStage] = useState<CRMPipelineStage | null>(null)
  const [quotationMsg, setQuotationMsg] = useState('')

  useEffect(() => {
    if (requestedView && ['overview', 'leads', 'pipeline', 'activities', 'enterprise'].includes(requestedView)) setView(requestedView)
  }, [requestedView])

  const changeView = (next: CRMView) => {
    setView(next)
    setSearchParams(next === 'overview' ? {} : { view: next })
  }

  const leadsQuery = useQuery({
    queryKey: ['crm-leads', search, statusFilter],
    queryFn: () => crmApi.listLeads({ page_size: 100, search: search || undefined, status: statusFilter || undefined }),
  })
  const opportunitiesQuery = useQuery({
    queryKey: ['crm-opportunities'],
    queryFn: () => crmApi.listOpportunities({ page_size: 100 }),
  })
  const activitiesQuery = useQuery({
    queryKey: ['crm-activities'],
    queryFn: () => crmApi.listActivities({ page_size: 100 }),
  })
  const stagesQuery = useQuery({
    queryKey: ['crm-pipeline-stages'],
    queryFn: () => crmApi.listPipelineStages().then(r => r.data.data as CRMPipelineStage[]),
  })
  const teamsQuery = useQuery({
    queryKey: ['sales-teams'],
    queryFn: () => salesOrgApi.listTeams({ page_size: 100 }).then(r => r.data.data.items as { id: string; name: string }[]),
  })
  // ── CRM ინდიკატორები ──
  const conversionQuery = useQuery({
    queryKey: ['crm-conversion'],
    queryFn: () => crmApi.conversionRate({ days: 90 }).then(r => r.data.data),
  })
  const staleQuery = useQuery({
    queryKey: ['crm-stale'],
    queryFn: () => crmApi.staleLeads({ threshold_days: 30 }).then(r => r.data.data),
  })
  const pipelineValueQuery = useQuery({
    queryKey: ['crm-pipeline-value'],
    queryFn: () => crmApi.pipelineValue().then(r => r.data.data),
  })

  const leads = (leadsQuery.data?.data?.data?.items || []) as CRMLead[]
  const opportunities = (opportunitiesQuery.data?.data?.data?.items || []) as CRMOpportunity[]
  const activities = (activitiesQuery.data?.data?.data?.items || []) as CRMActivity[]
  const conversion = conversionQuery.data
  const staleLeads = (staleQuery.data || []) as { id: string; company_name: string; contact_name: string | null; status: string; estimated_value: number | null; days_since_last_activity: number }[]
  const pipelineValueStages = (pipelineValueQuery.data?.stages || []) as { stage: string; stage_label: string; count: number; total_amount: number }[]
  const pipelineValueTotal = pipelineValueQuery.data?.total_pipeline_value || 0
  const stages = (stagesQuery.data || []) as CRMPipelineStage[]
  const activeStages = stages.filter((s) => s.is_active)
  const teams = (teamsQuery.data || []) as { id: string; name: string }[]
  const stageLabel = (key: string) => stages.find((s) => s.key === key)?.name || key

  const refreshCRM = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['crm-leads'] }),
      queryClient.invalidateQueries({ queryKey: ['crm-opportunities'] }),
      queryClient.invalidateQueries({ queryKey: ['crm-activities'] }),
      queryClient.invalidateQueries({ queryKey: ['crm-conversion'] }),
      queryClient.invalidateQueries({ queryKey: ['crm-stale'] }),
      queryClient.invalidateQueries({ queryKey: ['crm-pipeline-value'] }),
      queryClient.invalidateQueries({ queryKey: ['crm-pipeline-stages'] }),
    ])
  }

  const createLeadMutation = useMutation({
    mutationFn: () => crmApi.createLead(leadForm),
    onSuccess: async () => {
      await refreshCRM()
      setNewLeadOpen(false)
      setLeadForm(emptyLead)
      setMessage(t('ლიდი დაემატა CRM-ში. ახლა შეგიძლიათ დაგეგმოთ კომუნიკაცია ან შექმნათ გაყიდვების შესაძლებლობა.'))
    },
  })

  const updateLeadMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) => crmApi.updateLead(id, data),
    onSuccess: async (response) => {
      await refreshCRM()
      const updated = response.data.data as CRMLead
      setSelectedLead(updated)
      setMessage(t('ლიდის სტატუსი განახლდა.'))
    },
  })

  const createOpportunityMutation = useMutation({
    mutationFn: () => crmApi.createOpportunity({
      lead_id: selectedLead?.id,
      name: opportunityForm.name,
      amount: Number(opportunityForm.amount),
      probability: Number(opportunityForm.probability),
      expected_close_date: opportunityForm.expected_close_date || null,
      stage: 'qualification',
    }),
    onSuccess: async () => {
      await refreshCRM()
      setOpportunityOpen(false)
      setOpportunityForm({ name: '', amount: 0, probability: 20, expected_close_date: '' })
      setMessage(t('გაყიდვების შესაძლებლობა დაემატა pipeline-ში.'))
      changeView('pipeline')
    },
  })

  const moveOpportunityMutation = useMutation({
    mutationFn: ({ id, stage }: { id: string; stage: CRMOpportunityStage }) => crmApi.updateOpportunity(id, { stage }),
    onSuccess: refreshCRM,
  })

  const createStageMutation = useMutation({
    mutationFn: () => crmApi.createPipelineStage(stageForm),
    onSuccess: async () => {
      await refreshCRM()
      setStageForm({ key: '', name: '', probability: 10, color: '#3b82f6' })
      setMessage(t('Pipeline ეტაპი დაემატა.'))
    },
  })

  const updateStageMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) => crmApi.updatePipelineStage(id, data),
    onSuccess: async () => {
      await refreshCRM()
      setEditingStage(null)
      setStageForm({ key: '', name: '', probability: 10, color: '#3b82f6' })
      setMessage(t('Pipeline ეტაპი განახლდა.'))
    },
  })

  const deleteStageMutation = useMutation({
    mutationFn: (id: string) => crmApi.deletePipelineStage(id),
    onSuccess: async () => {
      await refreshCRM()
      setMessage(t('Pipeline ეტაპი წაიშალა.'))
    },
  })

  const quotationMutation = useMutation({
    mutationFn: (opportunityId: string) => crmApi.createQuotationFromOpportunity(opportunityId),
    onSuccess: async (response) => {
      await refreshCRM()
      const data = response.data.data as { quotation_number: string }
      setQuotationMsg(t('შემოთავაზება შეიქმნა:') + ` ${data.quotation_number}`)
    },
  })

  const sendEmailMutation = useMutation({
    mutationFn: (quotationId: string) => crmApi.sendQuotationEmail(quotationId),
    onSuccess: async (response) => {
      await refreshCRM()
      const data = response.data.data as { to_email: string; status: string }
      setQuotationMsg(data.status === 'sent'
        ? t('შემოთავაზება გაგზავნილია ელფოსტაზე:') + ` ${data.to_email}`
        : t('ელფოსტის გაგზავნა ვერ მოხერხდა.'))
    },
  })

  const createActivityMutation = useMutation({
    mutationFn: () => crmApi.createActivity({
      lead_id: selectedLead?.id,
      activity_type: activityForm.activity_type,
      subject: activityForm.subject,
      description: activityForm.description || null,
      due_at: activityForm.due_at || null,
    }),
    onSuccess: async () => {
      await refreshCRM()
      setActivityOpen(false)
      setActivityForm({ activity_type: 'call', subject: '', description: '', due_at: '' })
      setMessage(t('შემდგომი მოქმედება დაგეგმილია.'))
    },
  })

  const completeActivityMutation = useMutation({
    mutationFn: (id: string) => crmApi.updateActivity(id, { status: 'completed' }),
    onSuccess: refreshCRM,
  })

  const convertLeadMutation = useMutation({
    mutationFn: () => crmApi.convertLead(selectedLead!.id, {
      ...convertForm,
      name: convertForm.name || selectedLead?.company_name,
    }),
    onSuccess: async (response) => {
      await refreshCRM()
      setConvertOpen(false)
      setSelectedLead(response.data.data.lead)
      setMessage(t('ლიდი გადაყვანილია კლიენტების რეესტრში. CRM აქტივობების ისტორია შენარჩუნებულია.'))
    },
  })

  const kpis = useMemo(() => ({
    newLeads: leads.filter((lead) => lead.status === 'new').length,
    qualified: leads.filter((lead) => lead.status === 'qualified').length,
    openPipeline: opportunities.filter((item) => !['won', 'lost'].includes(item.stage)).reduce((sum, item) => sum + Number(item.amount), 0),
    planned: activities.filter((item) => item.status === 'planned').length,
  }), [leads, opportunities, activities])

  const busy = leadsQuery.isLoading || opportunitiesQuery.isLoading || activitiesQuery.isLoading
  const overviewCards: { label: string; value: string | number; Icon: LucideIcon; hint: string }[] = [
    { label: t('ახალი ლიდები'), value: kpis.newLeads, Icon: Users, hint: t('ჯერ არ დამუშავებულა') },
    { label: t('კვალიფიცირებული ლიდები'), value: kpis.qualified, Icon: CheckCircle2, hint: t('მზადაა კლიენტად გადასაყვანად') },
    { label: t('აქტიური pipeline'), value: money(kpis.openPipeline), Icon: CircleDollarSign, hint: t('ღია შესაძლებლობების ღირებულება — კვალიფიცირებული ლიდი ავტომატურად ხვდება pipeline-ში') },
    { label: t('დაგეგმილი მოქმედებები'), value: kpis.planned, Icon: CalendarClock, hint: t('ზარები, შეხვედრები და დავალებები') },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-primary-50 px-3 py-1 text-xs font-semibold text-primary-800 dark:bg-primary-900/30 dark:text-primary-200">
            <Target size={14} /> {t('პოტენციური გაყიდვების მართვა')}
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('CRM — ლიდები და გაყიდვების შესაძლებლობები')}</h1>
          <p className="mt-1 max-w-3xl text-sm text-gray-600 dark:text-gray-400">
            {t('აქ იმართება დაინტერესებული პირი ლიდიდან კვალიფიცირებულ შესაძლებლობამდე. რეალური შეკვეთა იქმნება მხოლოდ კლიენტების რეესტრში გადაყვანის შემდეგ.')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={async () => {
              try {
                const { data } = await authApi.ssoToken()
                const ssoToken = data?.data?.token
                if (ssoToken) {
                  window.location.href = `http://localhost:5174/sso?token=${encodeURIComponent(ssoToken)}`
                }
              } catch {
                setMessage(t('CRM OS-ზე გადასვლა ვერ მოხერხდა — თავიდან შედით სისტემაში'))
              }
            }}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-primary-700 px-4 py-2.5 text-sm font-semibold text-primary-700 hover:bg-primary-50"
          >
            <ExternalLink size={18} /> CRM OS
          </button>
          <button onClick={() => setNewLeadOpen(true)} className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-800">
            <UserPlus size={18} /> {t('ახალი ლიდი')}
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-primary-100 bg-gradient-to-r from-primary-50 to-white p-4 dark:border-primary-900 dark:from-primary-950/40 dark:to-dark-200">
        <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
          <span className="rounded-lg bg-white px-3 py-2 shadow-sm dark:bg-dark-100">{t('1. ლიდი')}</span><ArrowRight size={16} />
          <span className="rounded-lg bg-white px-3 py-2 shadow-sm dark:bg-dark-100">{t('2. კვალიფიკაცია')}</span><ArrowRight size={16} />
          <span className="rounded-lg bg-white px-3 py-2 shadow-sm dark:bg-dark-100">{t('3. კლიენტების რეესტრი')}</span><ArrowRight size={16} />
          <span className="rounded-lg bg-white px-3 py-2 shadow-sm dark:bg-dark-100">{t('4. გაყიდვის შეკვეთა')}</span><ArrowRight size={16} />
          <span className="rounded-lg bg-white px-3 py-2 shadow-sm dark:bg-dark-100">{t('5. გაყიდვის ინვოისი')}</span>
        </div>
      </div>

      {message && <div className="flex items-center justify-between rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800"><span>{message}</span><button onClick={() => setMessage('')}>×</button></div>}

      <div className="flex gap-1 overflow-x-auto rounded-xl border border-gray-200 bg-white p-1 dark:border-dark-50 dark:bg-dark-200">
        {([
          ['overview', t('CRM მიმოხილვა')],
          ['leads', t('ლიდები')],
          ['pipeline', t('გაყიდვების pipeline')],
          ['activities', t('აქტივობები და follow-up')],
          ['enterprise', t('Enterprise (CRM 2.0)')],
        ] as [CRMView, string][]).map(([key, label]) => (
          <button key={key} onClick={() => changeView(key)} className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-semibold ${view === key ? 'bg-primary-700 text-white' : 'text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-dark-100'}`}>
            {t(label)}
          </button>
        ))}
      </div>

      {busy && <div className="rounded-xl border bg-white p-10 text-center text-gray-500 dark:bg-dark-200 dark:text-gray-400">{t('CRM მონაცემები იტვირთება…')}</div>}

      {!busy && view === 'overview' && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {overviewCards.map(({ label, value, Icon, hint }) => (
              <div key={label} className="rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-50 dark:bg-dark-200">
                <div className="flex items-center justify-between"><span className="text-sm font-medium text-gray-500 dark:text-gray-400">{t(label)}</span><Icon size={20} className="text-primary-700" /></div>
                <div className="mt-3 text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</div>
                <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{hint}</div>
              </div>
            ))}
          </div>

          {/* ── CRM ინდიკატორები ── */}
          <div className="grid gap-6 xl:grid-cols-3">
            {/* კონვერსიის მაჩვენებელი */}
            <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-50 dark:bg-dark-200">
              <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold text-gray-900 dark:text-gray-100">{t('ლიდის კონვერსია')}</h2><CheckCircle2 size={18} className="text-green-600" /></div>
              {conversionQuery.isLoading ? (
                <div className="py-6 text-center text-sm text-gray-400 dark:text-gray-500">{t('იტვირთება...')}</div>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-end justify-between">
                    <span className="text-3xl font-bold text-gray-900 dark:text-gray-100">{conversion?.conversion_rate ?? 0}%</span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">{t('ბოლო 90 დღე')}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-dark-100">
                    <div className="h-full rounded-full bg-green-500" style={{ width: `${Math.min(conversion?.conversion_rate ?? 0, 100)}%` }} />
                  </div>
                  <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
                    <span>{t('ლიდი:')} {conversion?.total_leads ?? 0}</span>
                    <span>{t('კლიენტად გადაყვანილი:')} {conversion?.converted_leads ?? 0}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Pipeline ღირებულება ეტაპების მიხედვით */}
            <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-50 dark:bg-dark-200">
              <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold text-gray-900 dark:text-gray-100">{t('Pipeline ღირებულება')}</h2><span className="text-sm font-bold text-primary-700">{money(pipelineValueTotal)}</span></div>
              {pipelineValueQuery.isLoading ? (
                <div className="py-6 text-center text-sm text-gray-400 dark:text-gray-500">{t('იტვირთება...')}</div>
              ) : (
                <div className="space-y-2">
                  {pipelineValueStages.length === 0 && <div className="py-6 text-center text-sm text-gray-400 dark:text-gray-500">{t('ღია შესაძლებლობები არ არის')}</div>}
                  {pipelineValueStages.map((s) => (
                    <div key={s.stage} className="flex items-center justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-300 dark:text-gray-400">{s.stage_label}</span>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-gray-400 dark:text-gray-500">{s.count} ც.</span>
                        <span className="font-semibold text-gray-900 dark:text-gray-100">{money(s.total_amount)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* გაუქმებული ლიდები */}
            <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-50 dark:bg-dark-200">
              <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold text-gray-900 dark:text-gray-100">{t('უმოქმედო ლიდები')}</h2><span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">{staleLeads.length}</span></div>
              {staleQuery.isLoading ? (
                <div className="py-6 text-center text-sm text-gray-400 dark:text-gray-500">{t('იტვირთება...')}</div>
              ) : staleLeads.length === 0 ? (
                <div className="py-6 text-center text-sm text-gray-400 dark:text-gray-500">{t('30 დღეზე მეტი უმოქმედო ლიდი არ არის ✓')}</div>
              ) : (
                <div className="space-y-2">
                  {staleLeads.slice(0, 5).map((lead) => (
                    <button
                      key={lead.id}
                      onClick={() => {
                        const full = leads.find((l) => l.id === lead.id)
                        if (full) setSelectedLead(full)
                      }}
                      className="flex w-full items-center justify-between rounded-lg border border-gray-100 p-2.5 text-left hover:bg-gray-50 dark:border-dark-50 dark:hover:bg-dark-100"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-gray-900 dark:text-gray-100">{lead.company_name}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">{lead.contact_name || '—'} · {lead.days_since_last_activity} დღე</div>
                      </div>
                      <ArrowRight size={15} className="ml-2 shrink-0 text-gray-400 dark:text-gray-500" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-50 dark:bg-dark-200">
              <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold text-gray-900 dark:text-gray-100">{t('ბოლო ლიდები')}</h2><button onClick={() => changeView('leads')} className="text-sm font-semibold text-primary-700">{t('ყველას ნახვა')}</button></div>
              <div className="space-y-3">{leads.slice(0, 5).map((lead) => <LeadRow key={lead.id} lead={lead} onOpen={() => setSelectedLead(lead)} />)}{!leads.length && <Empty text="ლიდები ჯერ არ არის დამატებული." />}</div>
            </div>
            <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-50 dark:bg-dark-200">
              <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold text-gray-900 dark:text-gray-100">{t('შემდეგი მოქმედებები')}</h2><button onClick={() => changeView('activities')} className="text-sm font-semibold text-primary-700">{t('ყველას ნახვა')}</button></div>
              <div className="space-y-3">{activities.filter((item) => item.status === 'planned').slice(0, 5).map((item) => <ActivityRow key={item.id} activity={item} onComplete={() => completeActivityMutation.mutate(item.id)} />)}{!activities.filter((item) => item.status === 'planned').length && <Empty text="დაგეგმილი მოქმედებები არ არის." />}</div>
            </div>
          </div>
        </>
      )}

      {!busy && view === 'leads' && (
        <div className="space-y-4">
          <div className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4 sm:flex-row dark:border-dark-50 dark:bg-dark-200">
            <label className="relative flex-1"><Search size={17} className="absolute left-3 top-3 text-gray-400 dark:text-gray-500" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('კომპანია, საკონტაქტო პირი ან ელფოსტა')} className="w-full rounded-lg border border-gray-300 py-2.5 pl-10 pr-3 text-sm dark:border-dark-50 dark:bg-dark-100" /></label>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-2.5 text-sm dark:border-dark-50 dark:bg-dark-100">
              <option value="">{t('ყველა სტატუსი')}</option>{Object.entries(leadStatusLabels).map(([key, label]) => <option key={key} value={key}>{t(label)}</option>)}
            </select>
          </div>
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-dark-50 dark:bg-dark-200">
            <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500 dark:bg-dark-100 dark:text-gray-400"><tr><th className="px-4 py-3">{t('ლიდი / კომპანია')}</th><th className="px-4 py-3">{t('საკონტაქტო ინფორმაცია')}</th><th className="px-4 py-3">{t('წყარო')}</th><th className="px-4 py-3">{t('სტატუსი')}</th><th className="px-4 py-3 text-right">{t('სავარაუდო ღირებულება')}</th><th className="px-4 py-3"></th></tr></thead><tbody className="divide-y divide-gray-100 dark:divide-dark-50">
              {leads.map((lead) => <tr key={lead.id} className="hover:bg-gray-50 dark:hover:bg-dark-100"><td className="px-4 py-4"><div className="font-semibold text-gray-900 dark:text-gray-100">{lead.company_name}</div><div className="text-xs text-gray-500 dark:text-gray-400">{lead.contact_name || t('საკონტაქტო პირი არ არის მითითებული')}</div></td><td className="px-4 py-4"><div>{lead.phone || '—'}</div><div className="text-xs text-gray-500 dark:text-gray-400">{lead.email || '—'}</div></td><td className="px-4 py-4">{sourceLabels[lead.source]}</td><td className="px-4 py-4"><LeadStatus status={lead.status} /></td><td className="px-4 py-4 text-right font-semibold">{money(lead.estimated_value)}</td><td className="px-4 py-4 text-right"><button onClick={() => setSelectedLead(lead)} className="rounded-lg border border-gray-300 px-3 py-1.5 font-medium hover:bg-gray-50 dark:border-dark-50 dark:hover:bg-dark-100">{t('გახსნა')}</button></td></tr>)}
            </tbody></table></div>
            {!leads.length && <Empty text="მოცემული ფილტრებით ლიდი არ მოიძებნა." />}
          </div>
        </div>
      )}

      {!busy && view === 'pipeline' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500 dark:text-gray-400">{t('გადაიტანეთ შესაძლებლობები ეტაპებს შორის — ეტაპის კონფიგურაცია ხელმისაწვდომია ღილაკზე დაჭერით.')}</p>
            <button onClick={() => setStagesOpen(true)} className="inline-flex items-center gap-2 rounded-lg border border-primary-700 px-4 py-2 text-sm font-semibold text-primary-700 hover:bg-primary-50">
              <Settings2 size={16} /> {t('ეტაპების კონფიგურაცია')}
            </button>
          </div>
          <div className="overflow-x-auto pb-3"><div className="grid min-w-[1320px] gap-4" style={{ gridTemplateColumns: `repeat(${Math.max(activeStages.length, 1)}, minmax(200px, 1fr))` }}>
            {activeStages.map((stage) => {
              const cards = opportunities.filter((item) => item.stage === stage.key)
              return <div key={stage.id} className="rounded-xl bg-gray-100 p-3 dark:bg-dark-100"><div className="mb-3 flex items-center justify-between"><div><h3 className="text-sm font-bold text-gray-800 dark:text-gray-100 dark:text-gray-200">{stageLabel(stage.key)}</h3><p className="text-xs text-gray-500 dark:text-gray-400">{cards.length} შესაძლებლობა · {money(cards.reduce((sum, item) => sum + Number(item.amount), 0))}</p></div><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: stage.color }} /></div><div className="space-y-3">{cards.map((item) => <div key={item.id} className="rounded-lg border border-gray-200 bg-white p-3 shadow-sm dark:border-dark-50 dark:bg-dark-200"><div className="font-semibold text-gray-900 dark:text-gray-100">{item.name}</div><div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{item.lead_company_name || t('კლიენტთან დაკავშირებული შესაძლებლობა')}</div><div className="mt-3 flex items-center justify-between"><span className="font-bold text-primary-800 dark:text-primary-300">{money(item.amount)}</span><span className="text-xs text-gray-500 dark:text-gray-400">{item.probability}%</span></div><select aria-label={`${item.name} — pipeline ეტაპი`} value={item.stage} onChange={(e) => moveOpportunityMutation.mutate({ id: item.id, stage: e.target.value as CRMOpportunityStage })} className="mt-3 w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs dark:border-dark-50 dark:bg-dark-100">{activeStages.map((s) => <option key={s.key} value={s.key}>{stageLabel(s.key)}</option>)}</select>{item.stage === 'won' && <div className="mt-2 flex gap-2"><button onClick={() => quotationMutation.mutate(item.id)} disabled={quotationMutation.isPending} className="flex-1 rounded-md bg-primary-700 px-2 py-1.5 text-xs font-semibold text-white disabled:opacity-50">{t('შემოთავაზება')}</button><button onClick={() => { const q = quotationMutation.data?.data?.data as { quotation_id?: string } | undefined; if (q?.quotation_id) sendEmailMutation.mutate(q.quotation_id) }} disabled={sendEmailMutation.isPending} className="flex-1 rounded-md border border-primary-300 px-2 py-1.5 text-xs font-semibold text-primary-700 disabled:opacity-50">{t('ელფოსტით გაგზავნა')}</button></div>}</div>)}{!cards.length && <div className="rounded-lg border border-dashed border-gray-300 p-4 text-center text-xs text-gray-500 dark:border-dark-50 dark:text-gray-400">{t('ამ ეტაპზე ჩანაწერი არ არის')}</div>}</div></div>
            })}
          </div></div>
        </div>
      )}

      {!busy && view === 'activities' && (
        <div className="rounded-xl border border-gray-200 bg-white dark:border-dark-50 dark:bg-dark-200"><div className="border-b border-gray-200 p-5 dark:border-dark-50"><h2 className="font-semibold text-gray-900 dark:text-gray-100">{t('აქტივობები და follow-up')}</h2><p className="text-sm text-gray-500 dark:text-gray-400">{t('ზარები, შეხვედრები, ელფოსტა და შემდეგი მოქმედებები.')}</p></div><div className="divide-y divide-gray-100 dark:divide-dark-50">{activities.map((item) => <ActivityRow key={item.id} activity={item} onComplete={() => completeActivityMutation.mutate(item.id)} />)}{!activities.length && <Empty text="CRM აქტივობები ჯერ არ არის დამატებული." />}</div></div>
      )}

      {!busy && view === 'enterprise' && <CrmEnterpriseView />}

      <Modal open={newLeadOpen} onClose={() => setNewLeadOpen(false)} title={t('ახალი ლიდი — პოტენციური გაყიდვა')} size="lg"><form onSubmit={(e) => { e.preventDefault(); createLeadMutation.mutate() }} className="space-y-4"><p className="rounded-lg bg-blue-50 p-3 text-sm text-blue-800">{t('ეს ჩანაწერი ჯერ კლიენტი არ არის. კვალიფიკაციის შემდეგ შეძლებთ მის კლიენტების რეესტრში გადაყვანას.')}</p><div className="grid gap-4 sm:grid-cols-2"><Field label={t('კომპანია ან პირის დასახელება')} required><input required value={leadForm.company_name} onChange={(e) => setLeadForm({ ...leadForm, company_name: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><Field label={t('საკონტაქტო პირი')}><input value={leadForm.contact_name} onChange={(e) => setLeadForm({ ...leadForm, contact_name: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><Field label={t('ტელეფონი')}><input value={leadForm.phone} onChange={(e) => setLeadForm({ ...leadForm, phone: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><Field label={t('ელფოსტა')}><input type="email" value={leadForm.email} onChange={(e) => setLeadForm({ ...leadForm, email: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><Field label={t('ლიდის წყარო')}><select value={leadForm.source} onChange={(e) => setLeadForm({ ...leadForm, source: e.target.value as CRMLeadSource })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100">{Object.entries(sourceLabels).map(([key, label]) => <option key={key} value={key}>{t(label)}</option>)}</select></Field><Field label={t('სავარაუდო გაყიდვის ღირებულება')}><input type="number" min="0" value={leadForm.estimated_value || ''} onChange={(e) => setLeadForm({ ...leadForm, estimated_value: Number(e.target.value) })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><Field label={t('გაყიდვების გუნდი')}><select value={leadForm.team_id || ''} onChange={(e) => setLeadForm({ ...leadForm, team_id: e.target.value || undefined })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100"><option value="">{t('არ არის მინიჭებული')}</option>{teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select></Field></div><Field label={t('ინტერესი / შენიშვნა')}><textarea value={leadForm.notes} onChange={(e) => setLeadForm({ ...leadForm, notes: e.target.value })} className="min-h-24 w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><FormError error={createLeadMutation.error} /><Actions busy={createLeadMutation.isPending} onCancel={() => setNewLeadOpen(false)} primary="ლიდის დამატება" /></form></Modal>

      <Modal open={Boolean(selectedLead)} onClose={() => setSelectedLead(null)} title={t('ლიდის ბარათი — პოტენციური კლიენტი')} size="lg">{selectedLead && <div className="space-y-5"><div className="flex flex-col gap-3 rounded-xl bg-gray-50 p-4 sm:flex-row sm:items-center sm:justify-between dark:bg-dark-100"><div><h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">{selectedLead.company_name}</h3><p className="text-sm text-gray-500 dark:text-gray-400">{selectedLead.contact_name || t('საკონტაქტო პირი არ არის მითითებული')}</p></div><div className="flex items-center gap-3"><LeadStatus status={selectedLead.status} /><span className="inline-flex items-center gap-1 rounded-full bg-primary-50 px-2.5 py-1 text-xs font-bold text-primary-800 dark:bg-primary-900/30 dark:text-primary-200" title={t('ლიდის ქულა')}><Target size={12} /> {selectedLead.score ?? 0}/100</span></div></div><div className="grid gap-4 sm:grid-cols-2"><Info icon={Phone} label={t('ტელეფონი')} value={selectedLead.phone || t('არ არის მითითებული')} /><Info icon={Mail} label={t('ელფოსტა')} value={selectedLead.email || t('არ არის მითითებული')} /><Info icon={Target} label={t('წყარო')} value={sourceLabels[selectedLead.source]} /><Info icon={CircleDollarSign} label={t('სავარაუდო ღირებულება')} value={money(selectedLead.estimated_value)} /><Info icon={Users} label={t('გაყიდვების გუნდი')} value={teams.find((team) => team.id === selectedLead.team_id)?.name || t('არ არის მინიჭებული')} /></div>{selectedLead.notes && <div className="rounded-lg border border-gray-200 p-4 text-sm dark:border-dark-50"><div className="mb-1 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">{t('ინტერესი / შენიშვნა')}</div>{selectedLead.notes}</div>}<div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4"><button disabled={selectedLead.status === 'converted'} onClick={() => updateLeadMutation.mutate({ id: selectedLead.id, data: { status: 'contacted' } })} className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-dark-50 dark:hover:bg-dark-100">{t('დაკავშირებულად მონიშვნა')}</button><button disabled={selectedLead.status === 'converted'} onClick={() => updateLeadMutation.mutate({ id: selectedLead.id, data: { status: 'qualified' } })} className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-dark-50 dark:hover:bg-dark-100">{t('კვალიფიცირება')}</button><button disabled={selectedLead.status === 'converted'} onClick={() => setOpportunityOpen(true)} className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-dark-50 dark:hover:bg-dark-100">{t('შესაძლებლობის შექმნა')}</button><button disabled={selectedLead.status !== 'qualified'} onClick={() => { setConvertForm({ ...convertForm, name: selectedLead.company_name }); setConvertOpen(true) }} className="rounded-lg bg-green-700 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40">{t('კლიენტად გადაყვანა')}</button></div><button disabled={selectedLead.status === 'converted'} onClick={() => setActivityOpen(true)} className="inline-flex items-center gap-2 text-sm font-semibold text-primary-700 disabled:opacity-40"><CalendarClock size={17} /> {t('შემდეგი მოქმედების დაგეგმვა')}</button></div>}</Modal>

      <Modal open={opportunityOpen} onClose={() => setOpportunityOpen(false)} title={t('ახალი გაყიდვების შესაძლებლობა')} size="md"><form onSubmit={(e) => { e.preventDefault(); createOpportunityMutation.mutate() }} className="space-y-4"><p className="text-sm text-gray-600 dark:text-gray-400">{t('ლიდი:')} <strong>{selectedLead?.company_name}</strong>{t('. შესაძლებლობა გამოჩნდება ვიზუალურ pipeline-ში.')}</p><Field label={t('გარიგების დასახელება')} required><input required value={opportunityForm.name} onChange={(e) => setOpportunityForm({ ...opportunityForm, name: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" placeholder={t('მაგ. ERP სისტემის დანერგვა')} /></Field><div className="grid gap-4 sm:grid-cols-2"><Field label={t('სავარაუდო თანხა')}><input type="number" min="0" value={opportunityForm.amount || ''} onChange={(e) => setOpportunityForm({ ...opportunityForm, amount: Number(e.target.value) })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><Field label={t('წარმატების ალბათობა %')}><input type="number" min="0" max="100" value={opportunityForm.probability} onChange={(e) => setOpportunityForm({ ...opportunityForm, probability: Number(e.target.value) })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field></div><Field label={t('მოსალოდნელი დახურვის თარიღი')}><input type="date" value={opportunityForm.expected_close_date} onChange={(e) => setOpportunityForm({ ...opportunityForm, expected_close_date: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><FormError error={createOpportunityMutation.error} /><Actions busy={createOpportunityMutation.isPending} onCancel={() => setOpportunityOpen(false)} primary="pipeline-ში დამატება" /></form></Modal>

      <Modal open={activityOpen} onClose={() => setActivityOpen(false)} title={t('შემდეგი მოქმედების დაგეგმვა')} size="md"><form onSubmit={(e) => { e.preventDefault(); createActivityMutation.mutate() }} className="space-y-4"><p className="text-sm text-gray-600 dark:text-gray-400">{t('დაკავშირებული ლიდი:')} <strong>{selectedLead?.company_name}</strong></p><Field label={t('მოქმედების ტიპი')}><select value={activityForm.activity_type} onChange={(e) => setActivityForm({ ...activityForm, activity_type: e.target.value as CRMActivityType })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100">{Object.entries(activityLabels).map(([key, label]) => <option key={key} value={key}>{t(label)}</option>)}</select></Field><Field label={t('სათაური')} required><input required value={activityForm.subject} onChange={(e) => setActivityForm({ ...activityForm, subject: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><Field label={t('შესრულების ვადა')}><input type="datetime-local" value={activityForm.due_at} onChange={(e) => setActivityForm({ ...activityForm, due_at: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><Field label={t('აღწერა')}><textarea value={activityForm.description} onChange={(e) => setActivityForm({ ...activityForm, description: e.target.value })} className="min-h-20 w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><FormError error={createActivityMutation.error} /><Actions busy={createActivityMutation.isPending} onCancel={() => setActivityOpen(false)} primary="მოქმედების დაგეგმვა" /></form></Modal>

      <Modal open={convertOpen} onClose={() => setConvertOpen(false)} title={t('ლიდის კლიენტად გადაყვანა')} size="lg"><form onSubmit={(e) => { e.preventDefault(); convertLeadMutation.mutate() }} className="space-y-4"><p className="rounded-lg bg-green-50 p-3 text-sm text-green-800">{t('შეიქმნება ოფიციალური ჩანაწერი კლიენტების რეესტრში. ამის შემდეგ ამ კლიენტისთვის შეძლებთ გაყიდვის შეკვეთისა და Invoice-ის მომზადებას. CRM ისტორია შენარჩუნდება.')}</p><div className="grid gap-4 sm:grid-cols-2"><Field label={t('კლიენტის დასახელება')} required><input required value={convertForm.name} onChange={(e) => setConvertForm({ ...convertForm, name: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><Field label={t('კლიენტის ტიპი')}><select value={convertForm.client_type} onChange={(e) => setConvertForm({ ...convertForm, client_type: e.target.value as 'legal' | 'individual' })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100"><option value="legal">{t('იურიდიული პირი')}</option><option value="individual">{t('ფიზიკური პირი')}</option></select></Field><Field label={t('საიდენტიფიკაციო კოდი')} required><input required value={convertForm.identification_code} onChange={(e) => setConvertForm({ ...convertForm, identification_code: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><Field label={t('დღგ-ს სტატუსი')}><label className="flex h-[42px] items-center gap-2 rounded-lg border border-gray-300 px-3 dark:border-dark-50"><input type="checkbox" checked={convertForm.is_vat_payer} onChange={(e) => setConvertForm({ ...convertForm, is_vat_payer: e.target.checked })} className="h-4 w-4" /> {t('დღგ-ს გადამხდელი')}</label></Field><Field label={t('მისამართი')}><input value={convertForm.address} onChange={(e) => setConvertForm({ ...convertForm, address: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field><Field label={t('შენიშვნა')}><textarea value={convertForm.notes} onChange={(e) => setConvertForm({ ...convertForm, notes: e.target.value })} className="min-h-20 w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field></div><FormError error={convertLeadMutation.error} /><Actions busy={convertLeadMutation.isPending} onCancel={() => setConvertOpen(false)} primary={t('კლიენტად გადაყვანა')} /></form></Modal>

      <Modal open={stagesOpen} onClose={() => setStagesOpen(false)} title={t('Pipeline ეტაპების კონფიგურაცია')} size="lg">
        <div className="space-y-5">
          {quotationMsg && <div className="flex items-center justify-between rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800"><span>{quotationMsg}</span><button onClick={() => setQuotationMsg('')}>×</button></div>}
          <form onSubmit={(e) => { e.preventDefault(); editingStage ? updateStageMutation.mutate({ id: editingStage.id, data: { name: stageForm.name, probability: Number(stageForm.probability), color: stageForm.color } }) : createStageMutation.mutate() }} className="space-y-4 rounded-xl border border-gray-200 p-4 dark:border-dark-50">
            <div className="flex items-center justify-between"><h3 className="font-semibold text-gray-900 dark:text-gray-100">{editingStage ? t('ეტაპის რედაქტირება') : t('ახალი ეტაპი')}</h3>{editingStage && <button type="button" onClick={() => { setEditingStage(null); setStageForm({ key: '', name: '', probability: 10, color: '#3b82f6' }) }} className="text-sm font-semibold text-primary-700">{t('გაუქმება')}</button>}</div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t('სახელი')} required><input required value={stageForm.name} onChange={(e) => setStageForm({ ...stageForm, name: e.target.value })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" placeholder={t('მაგ. ხელშეკრულების გაფორმება')} /></Field>
              {!editingStage && <Field label={t('Key (უნიკალური)')} required><input required value={stageForm.key} onChange={(e) => setStageForm({ ...stageForm, key: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_') })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" placeholder="contract_signing" /></Field>}
              <Field label={t('წარმატების ალბათობა %')}><input type="number" min="0" max="100" value={stageForm.probability} onChange={(e) => setStageForm({ ...stageForm, probability: Number(e.target.value) })} className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100" /></Field>
              <Field label={t('ფერი')}><input type="color" value={stageForm.color} onChange={(e) => setStageForm({ ...stageForm, color: e.target.value })} className="h-[42px] w-full rounded-lg border border-gray-300 dark:border-dark-50" /></Field>
            </div>
            <div className="flex justify-end"><button disabled={createStageMutation.isPending || updateStageMutation.isPending} className="rounded-lg bg-primary-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{editingStage ? t('შენახვა') : t('დამატება')}</button></div>
          </form>
          <div className="space-y-2">
            {stages.map((stage) => (
              <div key={stage.id} className="flex items-center justify-between rounded-lg border border-gray-200 p-3 dark:border-dark-50">
                <div className="flex items-center gap-3">
                  <span className="h-3 w-3 rounded-full" style={{ backgroundColor: stage.color }} />
                  <div>
                    <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{stage.name} {stage.is_won && <span className="ml-1 rounded bg-green-50 px-1.5 py-0.5 text-xs text-green-700">{t('მოგებული')}</span>}{stage.is_lost && <span className="ml-1 rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">{t('დაკარგული')}</span>}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{stage.key} · {stage.probability}% · {t('რიგი:')} {stage.sort_order}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => { setEditingStage(stage); setStageForm({ key: stage.key, name: stage.name, probability: stage.probability, color: stage.color }) }} className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium hover:bg-gray-50 dark:border-dark-50 dark:hover:bg-dark-100">{t('რედაქტირება')}</button>
                  {!stage.is_won && !stage.is_lost && <button onClick={() => { if (window.confirm(t('წავშალოთ ეს ეტაპი?'))) deleteStageMutation.mutate(stage.id) }} className="rounded-lg border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50">{t('წაშლა')}</button>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </Modal>
    </div>
  )
}

function LeadStatus({ status }: { status: CRMLeadStatus }) {
  const { t } = useTranslation()
  const styles: Record<CRMLeadStatus, string> = { new: 'bg-blue-50 text-blue-700', contacted: 'bg-amber-50 text-amber-700', qualified: 'bg-green-50 text-green-700', unqualified: 'bg-gray-100 text-gray-600', converted: 'bg-purple-50 text-purple-700' }
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${styles[status]}`}>{t(leadStatusLabels[status])}</span>
}

function LeadRow({ lead, onOpen }: { lead: CRMLead; onOpen: () => void }) {
  const { t } = useTranslation()
  return <button onClick={onOpen} className="flex w-full items-center justify-between rounded-lg border border-gray-100 p-3 text-left hover:border-primary-200 hover:bg-primary-50/40 dark:border-dark-50 dark:hover:bg-dark-100"><div><div className="font-semibold text-gray-900 dark:text-gray-100">{lead.company_name}</div><div className="text-xs text-gray-500 dark:text-gray-400">{lead.contact_name || lead.phone || t('საკონტაქტო ინფორმაცია არ არის')}</div></div><div className="text-right"><LeadStatus status={lead.status} /><div className="mt-1 text-xs font-medium text-gray-500 dark:text-gray-400">{money(lead.estimated_value)}</div></div></button>
}

function ActivityRow({ activity, onComplete }: { activity: CRMActivity; onComplete: () => void }) {
  const { t } = useTranslation()
  return <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex items-center gap-2"><span className="rounded-md bg-primary-50 px-2 py-1 text-xs font-semibold text-primary-700">{activityLabels[activity.activity_type]}</span><span className="font-semibold text-gray-900 dark:text-gray-100">{activity.subject}</span></div><div className="mt-1 text-sm text-gray-500 dark:text-gray-400">{activity.related_name || t('დაკავშირებული ჩანაწერი')} · {dateTime(activity.due_at)}</div>{activity.description && <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{activity.description}</div>}</div>{activity.status === 'planned' ? <button onClick={onComplete} className="rounded-lg border border-green-300 px-3 py-2 text-sm font-semibold text-green-700 hover:bg-green-50">{t('შესრულებულად მონიშვნა')}</button> : <span className="inline-flex items-center gap-1 text-sm font-semibold text-green-700"><CheckCircle2 size={16} /> {t('შესრულებულია')}</span>}</div>
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  const { t } = useTranslation()
  return <label className="block"><span className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">{t(label)}{required && <span className="text-red-500"> *</span>}</span>{children}</label>
}

function Info({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  const { t } = useTranslation()
  return <div className="flex items-start gap-3 rounded-lg border border-gray-200 p-3 dark:border-dark-50"><Icon size={18} className="mt-0.5 text-primary-700" /><div><div className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{t(label)}</div><div className="mt-1 text-sm text-gray-900 dark:text-gray-100">{value}</div></div></div>
}

function Empty({ text }: { text: string }) { return <div className="p-8 text-center text-sm text-gray-500 dark:text-gray-400">{text}</div> }
function FormError({ error }: { error: unknown }) { return error ? <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{errorMessage(error)}</div> : null }
function Actions({ busy, onCancel, primary }: { busy: boolean; onCancel: () => void; primary: string }) {
  const { t } = useTranslation()
  return <div className="flex justify-end gap-2 border-t border-gray-200 pt-4 dark:border-dark-50"><button type="button" onClick={onCancel} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold dark:border-dark-50">{t('გაუქმება')}</button><button disabled={busy} className="rounded-lg bg-primary-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? t('ინახება…') : primary}</button></div>
}