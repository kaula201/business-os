import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Send, CheckCircle2, Wallet } from 'lucide-react'

import Modal from '../ui/Modal'
import { procurementApi, productsApi } from '../../services/api'

const inputCls = 'w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200'

export default function RequisitionsTab() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ department: '', priority: 'normal', product_id: '', quantity: '', estimated_price: '' })

  const { data: reqs } = useQuery({
    queryKey: ['proc-requisitions'],
    queryFn: () => procurementApi.listRequisitions().then((r: any) => r.data.data),
  })
  const { data: products } = useQuery({
    queryKey: ['products-all-req'],
    queryFn: () => productsApi.list({ page_size: 100 }).then((r: any) => r.data.data.items),
  })

  const create = useMutation({
    mutationFn: () => procurementApi.createRequisition({
      department: form.department, priority: form.priority,
      lines: [{ product_id: form.product_id, quantity: Number(form.quantity), estimated_price: form.estimated_price ? Number(form.estimated_price) : null }],
    }),
    onSuccess: () => { setOpen(false); setForm({ department: '', priority: 'normal', product_id: '', quantity: '', estimated_price: '' }); qc.invalidateQueries({ queryKey: ['proc-requisitions'] }) },
  })
  const submit = useMutation({
    mutationFn: (id: string) => procurementApi.submitRequisition(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proc-requisitions'] }),
  })
  const approve = useMutation({
    mutationFn: (id: string) => procurementApi.approveRequisition(id, 1),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proc-requisitions'] }),
  })
  const budgetCheck = useMutation({
    mutationFn: (id: string) => procurementApi.requisitionBudgetCheck(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['proc-requisitions'] }),
  })

  const statusBadge = (s: string) => {
    const map: Record<string, { label: string; cls: string }> = {
      draft: { label: t('მონახაზი'), cls: 'bg-gray-100 text-gray-600 dark:bg-dark-100 dark:text-gray-400' },
      submitted: { label: t('გადაცემული'), cls: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
      approved: { label: t('დამტკიცებული'), cls: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' },
      rejected: { label: t('უარყოფილი'), cls: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300' },
      converted: { label: t('გადაყვანილი'), cls: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' },
    }
    const b = map[s] || map.draft
    return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${b.cls}`}>{b.label}</span>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500 dark:text-gray-400">{t('დეპარტამენტის მოთხოვნა → procurement → დამტკიცება → PO')}</p>
        <button onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary-600 text-white hover:bg-primary-700">
          <Plus size={15} /> {t('ახალი მოთხოვნა')}
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
            <tr>
              <th className="px-4 py-3">{t('ნომერი')}</th>
              <th className="px-4 py-3">{t('დეპარტამენტი')}</th>
              <th className="px-4 py-3">{t('პრიორიტეტი')}</th>
              <th className="px-4 py-3">{t('სტატუსი')}</th>
              <th className="px-4 py-3">{t('ბიუჯეტი')}</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y dark:divide-dark-50">
            {(reqs || []).length === 0 ? (
              <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('მოთხოვნები არ არის')}</td></tr>
            ) : (reqs || []).map((r: any) => (
              <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                <td className="px-4 py-3 font-mono text-xs font-semibold text-primary-700 dark:text-primary-400">{r.requisition_number}</td>
                <td className="px-4 py-3 font-medium">{r.department}</td>
                <td className="px-4 py-3"><span className="badge badge-warning">{r.priority}</span></td>
                <td className="px-4 py-3">{statusBadge(r.status)}</td>
                <td className="px-4 py-3">
                  {r.budget_check === 'ok' ? <span className="badge badge-success">{t('OK')}</span>
                    : r.budget_check === 'over_budget' ? <span className="badge badge-danger">{t('ლიმიტზე მეტი')}</span>
                    : r.budget_check === 'no_budget' ? <span className="badge">{t('ბიუჯეტი არ არის')}</span> : '—'}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1.5">
                    {r.status === 'draft' && (
                      <button onClick={() => submit.mutate(r.id)} className="text-xs font-medium text-primary-700 hover:text-primary-800 dark:text-primary-400">
                        <Send size={13} className="inline mr-0.5" />{t('გადაცემა')}
                      </button>
                    )}
                    {r.status === 'submitted' && (
                      <>
                        <button onClick={() => approve.mutate(r.id)} className="text-xs font-medium text-emerald-600 hover:text-emerald-700 dark:text-emerald-400">
                          <CheckCircle2 size={13} className="inline mr-0.5" />{t('დამტკიცება')}
                        </button>
                        <button onClick={() => budgetCheck.mutate(r.id)} className="text-xs font-medium text-violet-600 hover:text-violet-700 dark:text-violet-400">
                          <Wallet size={13} className="inline mr-0.5" />{t('ბიუჯეტი')}
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი მოთხოვნა')}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('დეპარტამენტი')}</label>
              <input className={inputCls} value={form.department} onChange={e => setForm({ ...form, department: e.target.value })} placeholder="მარკეტინგი" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პრიორიტეტი')}</label>
              <select className={inputCls} value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })}>
                <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტი')}</label>
            <select className={inputCls} value={form.product_id} onChange={e => setForm({ ...form, product_id: e.target.value })}>
              <option value="">—</option>
              {(products || []).map((p: any) => <option key={p.id} value={p.id}>{p.sku || p.code} — {p.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('რაოდენობა')}</label>
              <input type="number" min="1" className={inputCls} value={form.quantity} onChange={e => setForm({ ...form, quantity: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('სავარაუდო ფასი')}</label>
              <input type="number" min="0" step="0.01" className={inputCls} value={form.estimated_price} onChange={e => setForm({ ...form, estimated_price: e.target.value })} />
            </div>
          </div>
          <button onClick={() => create.mutate()} disabled={!form.department || !form.product_id || !form.quantity}
            className="w-full px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-50">
            {t('შენახვა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
