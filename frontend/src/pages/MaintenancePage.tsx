import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Wrench, CalendarClock, Hammer, Plus, CheckCircle2 } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { maintenanceApi } from '../services/api'
import { fmtDate } from '../lib/format'

const statusBadge = (s: string) => {
  const map: Record<string, string> = {
    draft: 'badge', scheduled: 'badge-warning', in_progress: 'badge-info',
    completed: 'badge-success', cancelled: 'badge-danger', pending: 'badge-warning',
    done: 'badge-success', open: 'badge-danger',
  }
  return map[s] || 'badge'
}

export default function MaintenancePage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'plans' | 'orders' | 'repairs'>('plans')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<Record<string, any>>({})

  const { data: plans } = useQuery({ queryKey: ['maint-plans'], queryFn: () => maintenanceApi.plans().then(r => r.data.data) })
  const { data: orders } = useQuery({ queryKey: ['maint-orders'], queryFn: () => maintenanceApi.orders().then(r => r.data.data) })
  const { data: repairs } = useQuery({ queryKey: ['maint-repairs'], queryFn: () => maintenanceApi.repairs().then(r => r.data.data) })

  const createPlan = useMutation({
    mutationFn: () => maintenanceApi.createPlan(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-plans'] }) },
  })
  const createOrder = useMutation({
    mutationFn: () => maintenanceApi.createOrder(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-orders'] }) },
  })
  const createRepair = useMutation({
    mutationFn: () => maintenanceApi.createRepair(form),
    onSuccess: () => { setOpen(false); setForm({}); qc.invalidateQueries({ queryKey: ['maint-repairs'] }) },
  })
  const updateOrder = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) => maintenanceApi.updateOrder(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['maint-orders'] }),
  })
  const updateRepair = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) => maintenanceApi.updateRepair(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['maint-repairs'] }),
  })

  const openCreate = (kind: string) => {
    setForm({ kind })
    setOpen(true)
  }

  const renderForm = () => {
    const kind = form.kind
    if (kind === 'plan') return (
      <>
        <FormField label={t('სახელი')}><input className="input" value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
        <FormField label={t('ინტერვალი (დღე)')}><input type="number" className="input" value={form.interval_days || 30} onChange={e => setForm({ ...form, interval_days: e.target.value })} /></FormField>
        <FormField label={t('შემდეგი ვადა')}><input type="date" className="input" value={form.next_due_at || ''} onChange={e => setForm({ ...form, next_due_at: e.target.value })} /></FormField>
      </>
    )
    if (kind === 'order') return (
      <>
        <FormField label={t('აქტივი')}><input className="input" value={form.asset_name || ''} onChange={e => setForm({ ...form, asset_name: e.target.value })} /></FormField>
        <FormField label={t('ტიპი')}>
          <select className="input" value={form.maintenance_type || 'preventive'} onChange={e => setForm({ ...form, maintenance_type: e.target.value })}>
            <option value="preventive">Preventive</option><option value="corrective">Corrective</option><option value="predictive">Predictive</option>
          </select>
        </FormField>
        <FormField label={t('პრიორიტეტი')}>
          <select className="input" value={form.priority || 'medium'} onChange={e => setForm({ ...form, priority: e.target.value })}>
            <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
          </select>
        </FormField>
        <FormField label={t('თარიღი')}><input type="date" className="input" value={form.scheduled_date || ''} onChange={e => setForm({ ...form, scheduled_date: e.target.value })} /></FormField>
        <FormField label={t('აღწერა')}><textarea className="input min-h-[80px]" value={form.description || ''} onChange={e => setForm({ ...form, description: e.target.value })} /></FormField>
      </>
    )
    return (
      <>
        <FormField label={t('აღჭურვილობა')}><input className="input" value={form.equipment_name || ''} onChange={e => setForm({ ...form, equipment_name: e.target.value })} /></FormField>
        <FormField label={t('პრიორიტეტი')}>
          <select className="input" value={form.priority || 'medium'} onChange={e => setForm({ ...form, priority: e.target.value })}>
            <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
          </select>
        </FormField>
        <FormField label={t('აღწერა')}><textarea className="input min-h-[80px]" value={form.description || ''} onChange={e => setForm({ ...form, description: e.target.value })} /></FormField>
      </>
    )
  }

  const submit = () => {
    if (form.kind === 'plan') createPlan.mutate()
    else if (form.kind === 'order') createOrder.mutate()
    else createRepair.mutate()
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('მოვლა და შეკეთება')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('გეგმები, მოვლის დავალებები, სარემონტო სამუშაოები')}</p>
        </div>
        <button onClick={() => openCreate(tab === 'plans' ? 'plan' : tab === 'orders' ? 'order' : 'repair')} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t('ახალი')}
        </button>
      </div>

      <div className="flex gap-2 border-b dark:border-dark-50">
        {([['plans', 'გეგმები', CalendarClock], ['orders', 'მოვლის დავალებები', Wrench], ['repairs', 'შეკეთება', Hammer]] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)} className={`flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium ${tab === key ? 'border-primary-600 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'}`}>
            <Icon size={16} /> {t(label)}
          </button>
        ))}
      </div>

      {tab === 'plans' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('სახელი')}</th>
                <th className="px-4 py-3">{t('ინტერვალი')}</th>
                <th className="px-4 py-3">{t('შემდეგი ვადა')}</th>
                <th className="px-4 py-3">{t('აქტიური')}</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(plans || []).length === 0 ? (
                <tr><td colSpan={4} className="p-8 text-center text-gray-500">{t('გეგმები არ არის')}</td></tr>
              ) : (plans || []).map((p: any) => (
                <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{p.name}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{p.interval_days} {t('დღე')}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{p.next_due_at ? fmtDate(new Date(p.next_due_at)) : '—'}</td>
                  <td className="px-4 py-3">{p.is_active ? <span className="badge badge-success">{t('აქტიური')}</span> : <span className="badge">{t('გაჩერებული')}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'orders' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('ნომერი')}</th>
                <th className="px-4 py-3">{t('აქტივი')}</th>
                <th className="px-4 py-3">{t('ტიპი')}</th>
                <th className="px-4 py-3">{t('სტატუსი')}</th>
                <th className="px-4 py-3">{t('თარიღი')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(orders || []).length === 0 ? (
                <tr><td colSpan={6} className="p-8 text-center text-gray-500">{t('დავალებები არ არის')}</td></tr>
              ) : (orders || []).map((o: any) => (
                <tr key={o.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{o.order_number}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{o.asset_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{o.maintenance_type}</td>
                  <td className="px-4 py-3"><span className={`badge ${statusBadge(o.status)}`}>{o.status}</span></td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{o.scheduled_date ? fmtDate(new Date(o.scheduled_date)) : '—'}</td>
                  <td className="px-4 py-3">
                    {o.status !== 'completed' && (
                      <button onClick={() => updateOrder.mutate({ id: o.id, data: { status: 'completed' } })} className="btn btn-sm btn-success flex items-center gap-1">
                        <CheckCircle2 size={14} /> {t('დასრულება')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'repairs' && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('ნომერი')}</th>
                <th className="px-4 py-3">{t('აღჭურვილობა')}</th>
                <th className="px-4 py-3">{t('სტატუსი')}</th>
                <th className="px-4 py-3">{t('პრიორიტეტი')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(repairs || []).length === 0 ? (
                <tr><td colSpan={5} className="p-8 text-center text-gray-500">{t('სარემონტო სამუშაოები არ არის')}</td></tr>
              ) : (repairs || []).map((r: any) => (
                <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{r.repair_number}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.equipment_name || '—'}</td>
                  <td className="px-4 py-3"><span className={`badge ${statusBadge(r.status)}`}>{r.status}</span></td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.priority}</td>
                  <td className="px-4 py-3">
                    {r.status !== 'done' && (
                      <button onClick={() => updateRepair.mutate({ id: r.id, data: { status: 'done' } })} className="btn btn-sm btn-success flex items-center gap-1">
                        <CheckCircle2 size={14} /> {t('დასრულება')}
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
          {renderForm()}
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn" onClick={() => setOpen(false)}>{t('გაუქმება')}</button>
            <button className="btn btn-primary" onClick={submit}>{t('შექმნა')}</button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
