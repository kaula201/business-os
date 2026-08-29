import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Zap, Plus, Trash2, ToggleLeft, ToggleRight, GitBranch } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { automationsApi } from '../services/api'

const triggerLabels: Record<string, string> = {
  invoice_issued: 'ინვოისი დადასტურდა',
  order_created: 'შეკვეთა შეიქმნა',
  order_confirmed: 'შეკვეთა დადასტურდა',
  order_paid: 'შეკვეთა გადახდილია',
  stock_low: 'მარაგი დაბალია',
  task_overdue: 'დავალება დაგვიანდა',
  client_created: 'კლიენტი შეიქმნა',
  supplier_invoice_received: 'მიმწოდებლის ინვოისი მიღებულია',
}
const actionLabels: Record<string, string> = {
  notify: 'შეტყობინება',
  send_email: 'ელ.ფოსტა',
  create_task: 'დავალების შექმნა',
  update_status: 'სტატუსის ცვლილება',
  webhook: 'Webhook',
}

export default function AutomationsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    name: '', trigger: 'invoice_issued', action: 'notify', target: 'manager',
    condField: '', condOp: 'gte', condValue: '', payloadStatus: '', payloadSubject: '',
  })
  const [runResult, setRunResult] = useState<string | null>(null)

  const { data: rules } = useQuery({ queryKey: ['automations'], queryFn: () => automationsApi.list().then((r: any) => r.data.data) })
  const { data: meta } = useQuery({ queryKey: ['automations-meta'], queryFn: () => automationsApi.meta() })

  const createRule = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {}
      if (form.action === 'update_status' && form.payloadStatus) payload.status_to = form.payloadStatus
      if (form.action === 'send_email' && form.payloadSubject) payload.subject = form.payloadSubject
      const conditions = form.condField.trim()
        ? [{ field: form.condField.trim(), op: form.condOp, value: isNaN(Number(form.condValue)) ? form.condValue : Number(form.condValue) }]
        : undefined
      return automationsApi.create({
        name: form.name, trigger: form.trigger, action: form.action,
        target: form.target, conditions, payload: Object.keys(payload).length ? payload : undefined,
      })
    },
    onSuccess: () => {
      setOpen(false)
      setForm({ name: '', trigger: 'invoice_issued', action: 'notify', target: 'manager', condField: '', condOp: 'gte', condValue: '', payloadStatus: '', payloadSubject: '' })
      qc.invalidateQueries({ queryKey: ['automations'] })
    },
    onError: (e: any) => setRunResult(e?.response?.data?.detail || null),
  })
  const toggleRule = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => automationsApi.update(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['automations'] }),
  })
  const removeRule = useMutation({
    mutationFn: (id: string) => automationsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['automations'] }),
  })
  const fireRule = useMutation({
    mutationFn: (trigger: string) => automationsApi.trigger(trigger, { amount: 2500, details: 'ხელით ტესტი', entity: 'order', entity_id: 'test' }),
    onSuccess: (r: any) => setRunResult((r?.data?.message as string) || ''),
    onError: (e: any) => setRunResult(e?.response?.data?.detail || null),
  })

  const allTriggers = meta?.triggers || Object.keys(triggerLabels)
  const allActions = meta?.actions || Object.keys(actionLabels)

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('ავტომატიზაცია')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('წესები: ტრიგერი → პირობა → მოქმედება')}</p>
        </div>
        <button onClick={() => setOpen(true)} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t('ახალი წესი')}
        </button>
      </div>

      {runResult && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900/40 dark:bg-emerald-900/10 dark:text-emerald-300">
          {runResult}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('სახელი')}</th>
                <th className="px-4 py-3">{t('ტრიგერი')}</th>
                <th className="px-4 py-3">{t('პირობა')}</th>
                <th className="px-4 py-3">{t('მოქმედება')}</th>
                <th className="px-4 py-3">{t('გაშვებები')}</th>
                <th className="px-4 py-3">{t('აქტიური')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(rules || []).length === 0 ? (
                <tr><td colSpan={7} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('წესები არ არის')}</td></tr>
              ) : (rules || []).map((r: any) => (
                <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{r.name}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{t(triggerLabels[r.trigger] || r.trigger)}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {(r.conditions || []).map((c: any, i: number) => (
                      <div key={i} className="flex items-center gap-1 font-mono text-xs">
                        <GitBranch size={12} className="text-primary-600" /> {c.field} {c.op} {String(c.value)}
                      </div>
                    ))}
                    {!r.conditions?.length && '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {t(actionLabels[r.action] || r.action)}
                    {r.action === 'update_status' && r.payload?.status_to ? ` → ${r.payload.status_to}` : ''}
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{r.run_count || 0}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleRule.mutate({ id: r.id, is_active: !r.is_active })} className="text-gray-500 hover:text-primary-600">
                      {r.is_active ? <ToggleRight size={20} className="text-green-600" /> : <ToggleLeft size={20} />}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => fireRule.mutate(r.trigger)} className="mr-2 text-primary-600 hover:text-primary-800" title={t('ხელით გაშვება')}><Zap size={17} /></button>
                    <button onClick={() => removeRule.mutate(r.id)} className="text-red-500 hover:text-red-700"><Trash2 size={18} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი წესი')}>
        <div className="space-y-4">
          <FormField label={t('სახელი')} required>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('ტრიგერი')}>
            <select value={form.trigger} onChange={e => setForm({ ...form, trigger: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              {allTriggers.map((x: string) => <option key={x} value={x}>{t(triggerLabels[x] || x)}</option>)}
            </select>
          </FormField>
          <div className="rounded-lg border border-gray-200 p-3 dark:border-dark-50">
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">{t('პირობა (არასავალდებულო)')}</div>
            <div className="grid grid-cols-[1fr_auto_1fr] gap-2">
              <input value={form.condField} onChange={e => setForm({ ...form, condField: e.target.value })} placeholder={t('ველი, e.g. amount')}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
              <select value={form.condOp} onChange={e => setForm({ ...form, condOp: e.target.value })}
                className="rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
                {(meta?.operators || ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'contains', 'in', 'is_set']).map((o: string) => <option key={o} value={o}>{o}</option>)}
              </select>
              <input value={form.condValue} onChange={e => setForm({ ...form, condValue: e.target.value })} placeholder={t('მნიშვნელობა')}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </div>
          </div>
          <FormField label={t('მოქმედება')}>
            <select value={form.action} onChange={e => setForm({ ...form, action: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              {allActions.map((x: string) => <option key={x} value={x}>{t(actionLabels[x] || x)}</option>)}
            </select>
          </FormField>
          {form.action === 'update_status' && (
            <FormField label={t('ახალი სტატუსი')}>
              <input value={form.payloadStatus} onChange={e => setForm({ ...form, payloadStatus: e.target.value })}
                placeholder="confirmed / shipping / completed"
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
          )}
          {form.action === 'send_email' && (
            <FormField label={t('სათაური (subject)')}>
              <input value={form.payloadSubject} onChange={e => setForm({ ...form, payloadSubject: e.target.value })}
                className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
            </FormField>
          )}
          <FormField label={t('სამიზნე')}>
            <select value={form.target} onChange={e => setForm({ ...form, target: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="manager">manager</option>
              <option value="admin">admin</option>
              <option value="accountant">accountant</option>
            </select>
          </FormField>
          <button onClick={() => createRule.mutate()} disabled={!form.name || createRule.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შექმნა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
