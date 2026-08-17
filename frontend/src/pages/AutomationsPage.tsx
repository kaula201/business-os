import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Zap, Plus, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { automationsApi } from '../services/api'

const triggers = [
  { value: 'invoice_issued', label: 'ინვოისი დადასტურდა' },
  { value: 'order_created', label: 'შეკვეთა შეიქმნა' },
  { value: 'stock_low', label: 'მარაგი დაბალია' },
  { value: 'task_overdue', label: 'დავალება დაგვიანდა' },
]
const actions = [
  { value: 'notify', label: 'შეტყობინება' },
  { value: 'create_task', label: 'დავალების შექმნა' },
  { value: 'send_email', label: 'ელ.ფოსტა' },
]

export default function AutomationsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: '', trigger: 'invoice_issued', action: 'notify', target: 'manager' })

  const { data: rules } = useQuery({ queryKey: ['automations'], queryFn: () => automationsApi.list().then(r => r.data.data) })

  const createRule = useMutation({
    mutationFn: () => automationsApi.create(form),
    onSuccess: () => { setOpen(false); setForm({ name: '', trigger: 'invoice_issued', action: 'notify', target: 'manager' }); qc.invalidateQueries({ queryKey: ['automations'] }) },
  })
  const toggleRule = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => automationsApi.update(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['automations'] }),
  })
  const removeRule = useMutation({
    mutationFn: (id: string) => automationsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['automations'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('ავტომატიზაცია')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('წესები: ტრიგერი → მოქმედება')}</p>
        </div>
        <button onClick={() => setOpen(true)} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t('ახალი წესი')}
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('სახელი')}</th>
                <th className="px-4 py-3">{t('ტრიგერი')}</th>
                <th className="px-4 py-3">{t('მოქმედება')}</th>
                <th className="px-4 py-3">{t('სამიზნე')}</th>
                <th className="px-4 py-3">{t('აქტიური')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {(rules || []).length === 0 ? (
                <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('წესები არ არის')}</td></tr>
              ) : (rules || []).map((r: any) => (
                <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{r.name}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{t(triggers.find(x => x.value === r.trigger)?.label || r.trigger)}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{t(actions.find(x => x.value === r.action)?.label || r.action)}</td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.target || '—'}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleRule.mutate({ id: r.id, is_active: !r.is_active })} className="text-gray-500 hover:text-primary-600">
                      {r.is_active ? <ToggleRight size={20} className="text-green-600" /> : <ToggleLeft size={20} />}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
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
              {triggers.map(x => <option key={x.value} value={x.value}>{t(x.label)}</option>)}
            </select>
          </FormField>
          <FormField label={t('მოქმედება')}>
            <select value={form.action} onChange={e => setForm({ ...form, action: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              {actions.map(x => <option key={x.value} value={x.value}>{t(x.label)}</option>)}
            </select>
          </FormField>
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
