import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Wrench, Package, Plus, Search, Calendar, User, ChevronDown, ChevronRight } from 'lucide-react'

import Modal from '../components/ui/Modal'
import { api } from '../services/api'
import type { ApiResponse, PaginatedResponse } from '../types'

interface BOM { id: string; code: string; name: string; product_id: string; quantity: number; is_active: boolean }
interface WorkOrder { id: string; order_number: string; bom_id: string; product_id: string; planned_quantity: number; completed_quantity: number; status: string; start_date: string | null; end_date: string | null; notes: string | null }

const statusColors: Record<string, string> = {
  draft: 'bg-gray-50 text-gray-600 dark:bg-dark-100 dark:text-gray-400',
  confirmed: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  in_progress: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  completed: 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  cancelled: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400',
}
const statusLabels: Record<string, string> = { draft: 'დრაფტი', confirmed: 'დადასტურებული', in_progress: 'მიმდინარე', completed: 'დასრულებული', cancelled: 'გაუქმებული' }

export default function ProductionPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState('boms')
  const [showBomModal, setShowBomModal] = useState(false)
  const [showWoModal, setShowWoModal] = useState(false)
  const [bomForm, setBomForm] = useState({ code: '', name: '', product_id: '', quantity: 1, notes: '' })
  const [woForm, setWoForm] = useState({ bom_id: '', product_id: '', planned_quantity: 1, notes: '' })
  const [error, setError] = useState('')

  const { data: bomData } = useQuery({ queryKey: ['boms'], queryFn: () => api.get('/production/boms', { params: { page_size: 100 } }).then(r => r.data.data) })
  const { data: woData } = useQuery({ queryKey: ['work-orders'], queryFn: () => api.get('/production/work-orders', { params: { page_size: 100 } }).then(r => r.data.data) })

  const boms: BOM[] = bomData?.items || []
  const workOrders: WorkOrder[] = woData?.items || []

  const createBom = useMutation({
    mutationFn: (d: any) => api.post('/production/boms', d),
    onSuccess: () => { setShowBomModal(false); queryClient.invalidateQueries({ queryKey: ['boms'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || 'შეცდომა'),
  })
  const createWo = useMutation({
    mutationFn: (d: any) => api.post('/production/work-orders', d),
    onSuccess: () => { setShowWoModal(false); queryClient.invalidateQueries({ queryKey: ['work-orders'] }) },
    onError: (e: any) => setError(e.response?.data?.detail || 'შეცდომა'),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('წარმოება')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('BOM, წარმოების დავალებები')}</p>
        </div>
      </div>

      <div className="flex gap-1 border-b border-brandgray-100 dark:border-dark-50">
        {[{ id: 'boms', label: 'BOM (რეცეპტურები)', icon: Package }, { id: 'orders', label: 'წარმოების დავალებები', icon: Wrench }].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id ? 'border-primary-600 text-primary-700 dark:border-primary-400 dark:text-primary-300'
                : 'border-transparent text-brandgray-500 dark:text-gray-400'
            }`}>
            <t.icon size={18} /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'boms' && (
        <>
          <button onClick={() => { setBomForm({ code: '', name: '', product_id: '', quantity: 1, notes: '' }); setShowBomModal(true) }}
            className="btn btn-primary flex items-center gap-2"><Plus size={18} /> {t('ახალი BOM')}</button>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr><th className="px-4 py-3">{t('კოდი')}</th><th className="px-4 py-3">{t('სახელი')}</th><th className="px-4 py-3 text-right">{t('რაოდენობა')}</th><th className="px-4 py-3">{t('სტატუსი')}</th></tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {boms.map(b => (
                  <tr key={b.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-mono text-brandgray-600 dark:text-gray-400">{b.code}</td>
                    <td className="px-4 py-3 font-medium dark:text-gray-100">{b.name}</td>
                    <td className="px-4 py-3 text-right dark:text-gray-200">{b.quantity}</td>
                    <td className="px-4 py-3"><span className={`rounded-full px-2.5 py-1 text-xs font-medium ${b.is_active ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-50 text-gray-600 dark:bg-dark-100 dark:text-gray-400'}`}>{b.is_active ? 'აქტიური' : 'არააქტიური'}</span></td>
                  </tr>
                ))}
                {boms.length === 0 && <tr><td colSpan={4} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('BOM არ მოიძებნა')}</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'orders' && (
        <>
          <button onClick={() => { setWoForm({ bom_id: '', product_id: '', planned_quantity: 1, notes: '' }); setShowWoModal(true) }}
            className="btn btn-primary flex items-center gap-2"><Plus size={18} /> {t('ახალი წარმოების დავალება')}</button>
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:border-dark-50 dark:bg-dark-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr><th className="px-4 py-3">{t('დავალება')}</th><th className="px-4 py-3 text-right">{t('დაგეგმილი')}</th><th className="px-4 py-3 text-right">{t('შესრულებული')}</th><th className="px-4 py-3">{t('სტატუსი')}</th><th className="px-4 py-3">{t('თარიღი')}</th></tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {workOrders.map(wo => (
                  <tr key={wo.id} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium dark:text-gray-100">{wo.order_number}</td>
                    <td className="px-4 py-3 text-right dark:text-gray-200">{wo.planned_quantity}</td>
                    <td className="px-4 py-3 text-right dark:text-gray-200">{wo.completed_quantity}</td>
                    <td className="px-4 py-3"><span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusColors[wo.status] || ''}`}>{statusLabels[wo.status] || wo.status}</span></td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{wo.start_date || '—'}</td>
                  </tr>
                ))}
                {workOrders.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('წარმოების დავალებები არ მოიძებნა')}</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      <Modal open={showBomModal} onClose={() => setShowBomModal(false)} title={t('ახალი BOM')}>
        <form onSubmit={e => { e.preventDefault(); createBom.mutate(bomForm) }} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div><label className="block text-sm font-medium mb-1 dark:text-gray-300">{t('კოდი *')}</label><input required value={bomForm.code} onChange={e => setBomForm({ ...bomForm, code: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
            <div><label className="block text-sm font-medium mb-1 dark:text-gray-300">{t('სახელი *')}</label><input required value={bomForm.name} onChange={e => setBomForm({ ...bomForm, name: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
            <div><label className="block text-sm font-medium mb-1 dark:text-gray-300">{t('პროდუქტის ID *')}</label><input required value={bomForm.product_id} onChange={e => setBomForm({ ...bomForm, product_id: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
            <div><label className="block text-sm font-medium mb-1 dark:text-gray-300">{t('რაოდენობა')}</label><input type="number" value={bomForm.quantity} onChange={e => setBomForm({ ...bomForm, quantity: Number(e.target.value) })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" disabled={createBom.isPending} className="w-full rounded-lg bg-primary-600 py-2 text-white disabled:opacity-50">{createBom.isPending ? 'ინახება...' : 'BOM-ის შექმნა'}</button>
        </form>
      </Modal>

      <Modal open={showWoModal} onClose={() => setShowWoModal(false)} title={t('ახალი წარმოების დავალება')}>
        <form onSubmit={e => { e.preventDefault(); createWo.mutate(woForm) }} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div><label className="block text-sm font-medium mb-1 dark:text-gray-300">BOM ID *</label><input required value={woForm.bom_id} onChange={e => setWoForm({ ...woForm, bom_id: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
            <div><label className="block text-sm font-medium mb-1 dark:text-gray-300">{t('პროდუქტის ID *')}</label><input required value={woForm.product_id} onChange={e => setWoForm({ ...woForm, product_id: e.target.value })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
            <div><label className="block text-sm font-medium mb-1 dark:text-gray-300">{t('დაგეგმილი რაოდენობა')}</label><input type="number" value={woForm.planned_quantity} onChange={e => setWoForm({ ...woForm, planned_quantity: Number(e.target.value) })} className="w-full rounded-lg border p-2 text-sm dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200" /></div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" disabled={createWo.isPending} className="w-full rounded-lg bg-primary-600 py-2 text-white disabled:opacity-50">{createWo.isPending ? 'ინახება...' : 'დავალების შექმნა'}</button>
        </form>
      </Modal>
    </div>
  )
}
