import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CreditCard, Plus, CheckCircle2, RotateCcw } from 'lucide-react'

import Modal from '../components/ui/Modal'
import FormField from '../components/ui/FormField'
import { paymentsApi } from '../services/api'

const statusColors: Record<string, string> = {
  pending: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  succeeded: 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  failed: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  refunded: 'bg-gray-100 text-gray-600 dark:bg-dark-100 dark:text-gray-400',
}

export default function PaymentsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [form, setForm] = useState({ provider: 'stripe', amount: '', currency: 'GEL' })
  const [open, setOpen] = useState(false)

  const { data: payments, isLoading } = useQuery({
    queryKey: ['payments-list'],
    queryFn: () => paymentsApi.list().then(r => r.data.data),
  })

  const createPayment = useMutation({
    mutationFn: () => paymentsApi.create({ ...form, amount: Number(form.amount) }),
    onSuccess: () => { setOpen(false); setForm({ provider: 'stripe', amount: '', currency: 'GEL' }); qc.invalidateQueries({ queryKey: ['payments-list'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || t('შეცდომა')),
  })
  const confirmPayment = useMutation({
    mutationFn: (id: string) => paymentsApi.confirm(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payments-list'] }),
  })
  const refundPayment = useMutation({
    mutationFn: (id: string) => paymentsApi.refund(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payments-list'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('გადახდები')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('Payment gateway — Stripe, PayPal, TBC, BOG')}</p>
        </div>
        <button onClick={() => setOpen(true)} className="btn btn-primary flex items-center gap-2">
          <Plus size={18} /> {t('ახალი გადახდა')}
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3">{t('პროვაიდერი')}</th>
                <th className="px-4 py-3 text-right">{t('თანხა')}</th>
                <th className="px-4 py-3">{t('სტატუსი')}</th>
                <th className="px-4 py-3">{t('რეფერენსი')}</th>
                <th className="px-4 py-3">{t('თარიღი')}</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-dark-50">
              {isLoading ? (
                <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('იტვირთება...')}</td></tr>
              ) : (payments || []).length === 0 ? (
                <tr><td colSpan={6} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('გადახდები არ არის')}</td></tr>
              ) : (payments || []).map((p: any) => (
                <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                  <td className="px-4 py-3 font-medium text-brandgray-900 dark:text-gray-100">{p.provider}</td>
                  <td className="px-4 py-3 text-right font-mono">{p.amount} {p.currency}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusColors[p.status] || ''}`}>{p.status}</span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600 dark:text-gray-400">{p.provider_ref || '—'}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{new Date(p.created_at).toLocaleDateString('ka-GE')}</td>
                  <td className="px-4 py-3 text-right">
                    {p.status === 'pending' && (
                      <button onClick={() => confirmPayment.mutate(p.id)} className="text-green-600 hover:text-green-700 mr-2" title={t('დადასტურება')}>
                        <CheckCircle2 size={16} />
                      </button>
                    )}
                    {p.status === 'succeeded' && (
                      <button onClick={() => refundPayment.mutate(p.id)} className="text-red-500 hover:text-red-700" title={t('დაბრუნება')}>
                        <RotateCcw size={16} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={t('ახალი გადახდა')}>
        <div className="space-y-4">
          <FormField label={t('პროვაიდერი')}>
            <select value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="stripe">Stripe</option>
              <option value="paypal">PayPal</option>
              <option value="tbcpay">TBC Pay</option>
              <option value="bogpay">BOG Pay</option>
              <option value="cash">Cash</option>
            </select>
          </FormField>
          <FormField label={t('თანხა')} required>
            <input type="number" min={0.01} step={0.01} value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" />
          </FormField>
          <FormField label={t('ვალუტა')}>
            <select value={form.currency} onChange={e => setForm({ ...form, currency: e.target.value })}
              className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200">
              <option value="GEL">GEL</option>
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
            </select>
          </FormField>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <button onClick={() => createPayment.mutate()} disabled={!form.amount || Number(form.amount) <= 0 || createPayment.isPending}
            className="w-full rounded-lg bg-primary-600 py-2 text-white font-medium disabled:opacity-50">
            {t('შექმნა')}
          </button>
        </div>
      </Modal>
    </div>
  )
}
