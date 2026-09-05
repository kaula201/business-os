import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Mail, Phone, Tag, Route, MapPin, Clock, ShieldCheck, Plus } from 'lucide-react'

import Modal from '../ui/Modal'
import { crmApi } from '../../services/api'

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function CrmEnterpriseView() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'contacts' | 'email' | 'calls' | 'attribution' | 'routing' | 'territories' | 'sla' | 'gdpr'>('contacts')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<any>({})

  const { data: contacts } = useQuery({ queryKey: ['crm-contacts'], queryFn: () => crmApi.listContacts().then((r: any) => r.data.data) })
  const { data: calls } = useQuery({ queryKey: ['crm-calls'], queryFn: () => crmApi.listCalls().then((r: any) => r.data.data) })
  const { data: attribution } = useQuery({ queryKey: ['crm-attribution'], queryFn: () => crmApi.attributionAnalytics().then((r: any) => r.data.data) })
  const { data: territories } = useQuery({ queryKey: ['crm-territories'], queryFn: () => crmApi.listTerritories().then((r: any) => r.data.data) })
  const { data: slas } = useQuery({ queryKey: ['crm-slas'], queryFn: () => crmApi.listSlas().then((r: any) => r.data.data) })
  const { data: gdpr } = useQuery({ queryKey: ['crm-gdpr'], queryFn: () => crmApi.listGdprConsents().then((r: any) => r.data.data) })
  const { data: leads } = useQuery({ queryKey: ['crm-leads-all'], queryFn: () => crmApi.listLeads({ page_size: 100 }).then((r: any) => r.data.data.items) })

  const createContact = useMutation({
    mutationFn: () => crmApi.createContact(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['crm-contacts'] }) },
  })
  const logCall = useMutation({
    mutationFn: () => crmApi.logCall(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['crm-calls'] }) },
  })
  const createTerritory = useMutation({
    mutationFn: () => crmApi.createTerritory(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['crm-territories'] }) },
  })
  const createSla = useMutation({
    mutationFn: () => crmApi.createSla(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['crm-slas'] }) },
  })
  const setConsent = useMutation({
    mutationFn: (d: any) => crmApi.setGdprConsent(d),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['crm-gdpr'] }),
  })
  const runRouting = useMutation({
    mutationFn: (leadId: string) => crmApi.runRouting(leadId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['crm-leads-all'] }),
  })

  const tabs = [
    { id: 'contacts' as const, label: t('კონტაქტები'), icon: Building2 },
    { id: 'email' as const, label: t('ელ.ფოსტა'), icon: Mail },
    { id: 'calls' as const, label: t('ზარები'), icon: Phone },
    { id: 'attribution' as const, label: t('ატრიბუცია'), icon: Tag },
    { id: 'routing' as const, label: t('როუტინგი'), icon: Route },
    { id: 'territories' as const, label: t('ტერიტორიები'), icon: MapPin },
    { id: 'sla' as const, label: t('SLA'), icon: Clock },
    { id: 'gdpr' as const, label: t('GDPR'), icon: ShieldCheck },
  ]

  const openCreate = (kind: string) => {
    setForm({ kind })
    setOpen(true)
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-1 rounded-lg bg-brandgray-100 p-1 w-fit dark:bg-dark-100">
        {tabs.map(tb => (
          <button key={tb.id} onClick={() => setTab(tb.id)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium ${tab === tb.id ? 'bg-white shadow-sm text-gray-900 dark:bg-dark-200 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'}`}>
            <tb.icon size={14} className="inline mr-1 -mt-0.5" />{tb.label}
          </button>
        ))}
      </div>

      {tab === 'contacts' && (
        <div className="space-y-3">
          <button onClick={() => openCreate('contact')} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700">
            <Plus size={15} /> {t('ახალი კონტაქტი')}
          </button>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr><th className="px-4 py-3">{t('სახელი')}</th><th className="px-4 py-3">{t('ელფოსტა')}</th><th className="px-4 py-3">{t('ტელეფონი')}</th><th className="px-4 py-3">{t('თანამდებობა')}</th><th className="px-4 py-3">{t('პირველადი')}</th></tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(contacts || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('კონტაქტები არ არის')}</td></tr>
                ) : (contacts || []).map((c: any) => (
                  <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium">{c.first_name} {c.last_name}</td>
                    <td className="px-4 py-3 text-gray-500">{c.email || '—'}</td>
                    <td className="px-4 py-3 text-gray-500">{c.phone || c.mobile || '—'}</td>
                    <td className="px-4 py-3 text-gray-500">{c.job_title || '—'}</td>
                    <td className="px-4 py-3">{c.is_primary ? <span className="badge badge-success">{t('დიახ')}</span> : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'calls' && (
        <div className="space-y-3">
          <button onClick={() => openCreate('call')} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700">
            <Plus size={15} /> {t('ზარის ჩაწერა')}
          </button>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr><th className="px-4 py-3">{t('მიმართულება')}</th><th className="px-4 py-3">{t('ნომერი')}</th><th className="px-4 py-3">{t('ხანგრძლივობა')}</th><th className="px-4 py-3">{t('სტატუსი')}</th><th className="px-4 py-3">{t('შენიშვნა')}</th></tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(calls || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('ზარები არ არის')}</td></tr>
                ) : (calls || []).map((c: any) => (
                  <tr key={c.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3">{c.direction === 'inbound' ? '←' : '→'} {c.direction}</td>
                    <td className="px-4 py-3 font-mono">{c.phone_number}</td>
                    <td className="px-4 py-3">{c.duration_seconds}s</td>
                    <td className="px-4 py-3"><span className="badge badge-success">{c.status}</span></td>
                    <td className="px-4 py-3 text-gray-500">{c.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'attribution' && attribution && (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-gray-200 dark:border-dark-50 p-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('კამპანიების მიხედვით')}</h3>
            <div className="mt-3 space-y-2">
              {Object.entries(attribution.by_campaign || {}).map(([k, v]) => (
                <div key={k} className="flex justify-between text-sm"><span>{k}</span><span className="font-semibold">{v as number}</span></div>
              ))}
              {Object.keys(attribution.by_campaign || {}).length === 0 && <p className="text-sm text-gray-400">{t('მონაცემები არ არის')}</p>}
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 dark:border-dark-50 p-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('არხების მიხედვით')}</h3>
            <div className="mt-3 space-y-2">
              {Object.entries(attribution.by_channel || {}).map(([k, v]) => (
                <div key={k} className="flex justify-between text-sm"><span>{k}</span><span className="font-semibold">{v as number}</span></div>
              ))}
              {Object.keys(attribution.by_channel || {}).length === 0 && <p className="text-sm text-gray-400">{t('მონაცემები არ არის')}</p>}
            </div>
          </div>
        </div>
      )}

      {tab === 'routing' && (
        <div className="space-y-3">
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('ლიდის როუტინგი — მინიჭება მფლობელზე სტრატეგიით (round_robin / least_loaded / territory)')}</p>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr><th className="px-4 py-3">{t('ლიდი')}</th><th className="px-4 py-3">{t('სტატუსი')}</th><th className="px-4 py-3">{t('მფლობელი')}</th><th className="px-4 py-3"></th></tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(leads || []).slice(0, 10).map((l: any) => (
                  <tr key={l.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium">{l.company_name}</td>
                    <td className="px-4 py-3"><span className="badge badge-warning">{l.status}</span></td>
                    <td className="px-4 py-3 text-gray-500">{l.owner_id ? l.owner_id.slice(0, 8) : '—'}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => runRouting.mutate(l.id)} className="text-xs font-medium text-primary-700 hover:text-primary-800 dark:text-primary-400">{t('როუტინგი')}</button>
                    </td>
                  </tr>
                ))}
                {(leads || []).length === 0 && <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('ლიდები არ არის')}</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'territories' && (
        <div className="space-y-3">
          <button onClick={() => openCreate('territory')} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700">
            <Plus size={15} /> {t('ახალი ტერიტორია')}
          </button>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr><th className="px-4 py-3">{t('სახელი')}</th><th className="px-4 py-3">{t('რეგიონი')}</th><th className="px-4 py-3">{t('სტატუსი')}</th></tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(territories || []).length === 0 ? (
                  <tr><td colSpan={3} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('ტერიტორიები არ არის')}</td></tr>
                ) : (territories || []).map((t2: any) => (
                  <tr key={t2.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium">{t2.name}</td>
                    <td className="px-4 py-3 text-gray-500">{t2.region || '—'}</td>
                    <td className="px-4 py-3">{t2.is_active ? <span className="badge badge-success">{t('აქტიური')}</span> : <span className="badge">{t('გამორთული')}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'sla' && (
        <div className="space-y-3">
          <button onClick={() => openCreate('sla')} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700">
            <Plus size={15} /> {t('ახალი SLA')}
          </button>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr><th className="px-4 py-3">{t('სახელი')}</th><th className="px-4 py-3">{t('პრიორიტეტი')}</th><th className="px-4 py-3">{t('რეაგირება (სთ)')}</th><th className="px-4 py-3">{t('გადაწყვეტა (სთ)')}</th></tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(slas || []).length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('SLA არ არის')}</td></tr>
                ) : (slas || []).map((s: any) => (
                  <tr key={s.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium">{s.name}</td>
                    <td className="px-4 py-3"><span className="badge badge-warning">{s.priority}</span></td>
                    <td className="px-4 py-3">{s.response_hours}</td>
                    <td className="px-4 py-3">{s.resolution_hours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'gdpr' && (
        <div className="space-y-3">
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr><th className="px-4 py-3">{t('ტიპი')}</th><th className="px-4 py-3">{t('სტატუსი')}</th><th className="px-4 py-3">{t('მინიჭებულია')}</th><th className="px-4 py-3">{t('გაუქმებულია')}</th><th className="px-4 py-3">{t('წყარო')}</th></tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {(gdpr || []).length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('თანხმობები არ არის')}</td></tr>
                ) : (gdpr || []).map((g: any) => (
                  <tr key={g.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium">{g.consent_type}</td>
                    <td className="px-4 py-3">{g.granted ? <span className="badge badge-success">{t('მინიჭებული')}</span> : <span className="badge badge-danger">{t('გაუქმებული')}</span>}</td>
                    <td className="px-4 py-3 text-gray-500">{g.granted_at ? new Date(g.granted_at).toLocaleDateString() : '—'}</td>
                    <td className="px-4 py-3 text-gray-500">{g.revoked_at ? new Date(g.revoked_at).toLocaleDateString() : '—'}</td>
                    <td className="px-4 py-3 text-gray-500">{g.source || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'email' && (
        <div className="rounded-xl border border-gray-200 dark:border-dark-50 p-6 text-center text-sm text-gray-500 dark:text-gray-400">
          {t('ელ.ფოსტის thread-ები იქმნება API-ით (POST /crm/email-threads) — ლიდზე/კლიენტზე მიბმული მიმოწერა')}
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი ჩანაწერი')}>
        <div className="space-y-4">
          {form.kind === 'contact' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <input className={inputCls} placeholder={t('სახელი')} value={form.first_name || ''} onChange={e => setForm({ ...form, first_name: e.target.value })} />
                <input className={inputCls} placeholder={t('გვარი')} value={form.last_name || ''} onChange={e => setForm({ ...form, last_name: e.target.value })} />
              </div>
              <input className={inputCls} placeholder={t('ელფოსტა')} value={form.email || ''} onChange={e => setForm({ ...form, email: e.target.value })} />
              <input className={inputCls} placeholder={t('ტელეფონი')} value={form.phone || ''} onChange={e => setForm({ ...form, phone: e.target.value })} />
              <input className={inputCls} placeholder={t('თანამდებობა')} value={form.job_title || ''} onChange={e => setForm({ ...form, job_title: e.target.value })} />
            </>
          )}
          {form.kind === 'call' && (
            <>
              <input className={inputCls} placeholder={t('ნომერი')} value={form.phone_number || ''} onChange={e => setForm({ ...form, phone_number: e.target.value })} />
              <div className="grid grid-cols-2 gap-3">
                <select className={inputCls} value={form.direction || 'inbound'} onChange={e => setForm({ ...form, direction: e.target.value })}>
                  <option value="inbound">Inbound</option><option value="outbound">Outbound</option>
                </select>
                <input type="number" className={inputCls} placeholder={t('ხანგრძლივობა (წმ)')} value={form.duration_seconds || ''} onChange={e => setForm({ ...form, duration_seconds: e.target.value })} />
              </div>
              <input className={inputCls} placeholder={t('შენიშვნა')} value={form.notes || ''} onChange={e => setForm({ ...form, notes: e.target.value })} />
            </>
          )}
          {form.kind === 'territory' && (
            <>
              <input className={inputCls} placeholder={t('სახელი')} value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} />
              <input className={inputCls} placeholder={t('რეგიონი')} value={form.region || ''} onChange={e => setForm({ ...form, region: e.target.value })} />
            </>
          )}
          {form.kind === 'sla' && (
            <>
              <input className={inputCls} placeholder={t('სახელი')} value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} />
              <div className="grid grid-cols-3 gap-3">
                <select className={inputCls} value={form.priority || 'normal'} onChange={e => setForm({ ...form, priority: e.target.value })}>
                  <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option>
                </select>
                <input type="number" className={inputCls} placeholder={t('რეაგირება')} value={form.response_hours || ''} onChange={e => setForm({ ...form, response_hours: e.target.value })} />
                <input type="number" className={inputCls} placeholder={t('გადაწყვეტა')} value={form.resolution_hours || ''} onChange={e => setForm({ ...form, resolution_hours: e.target.value })} />
              </div>
            </>
          )}
          <button
            onClick={() => {
              if (form.kind === 'contact') createContact.mutate()
              else if (form.kind === 'call') logCall.mutate()
              else if (form.kind === 'territory') createTerritory.mutate()
              else if (form.kind === 'sla') createSla.mutate()
            }}
            disabled={!form.name && !form.first_name && !form.phone_number}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50"
          >
            {t('შენახვა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
