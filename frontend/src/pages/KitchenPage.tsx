import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChefHat, CheckCircle2, Flame } from 'lucide-react'

import { posApi } from '../services/api'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

export default function KitchenPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()

  const { data } = useQuery({
    queryKey: ['pos-kitchen'],
    queryFn: () => posApi.kitchenQueue().then(r => r.data.data),
    refetchInterval: 10000, // auto-refresh every 10s
  })
  const queue: any[] = data || []

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => posApi.setKitchenStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pos-kitchen'] }),
  })

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('სამზარეულო (KDS)')}</h1>
          <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('აქტიური შეკვეთები')}: {queue.length}</p>
        </div>
        <ChefHat size={28} className="text-primary-600" />
      </div>

      {queue.length === 0 ? (
        <div className="rounded-lg border border-brandgray-100 dark:border-dark-50 p-10 text-center text-sm text-brandgray-400 dark:text-gray-500">
          {t('სამზარეულოში შეკვეთები არ არის')}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {queue.map((o: any) => (
            <div key={o.id} className={`rounded-xl border p-4 ${o.kitchen_status === 'preparing' ? 'border-amber-300 bg-amber-50/60 dark:border-amber-900/40 dark:bg-amber-900/10' : 'border-brandgray-100 dark:border-dark-50'}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-bold text-gray-900 dark:text-gray-100">{o.order_number}</span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${o.kitchen_status === 'preparing' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300' : 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'}`}>
                  {o.kitchen_status === 'preparing' ? t('მზადდება') : t('ახალი')}
                </span>
              </div>
              <div className="text-xs text-brandgray-500 mb-3">{fmtTime(new Date(o.created_at))}</div>
              <div className="space-y-1 mb-3">
                {o.items.map((it: any, i: number) => (
                  <div key={i} className="flex justify-between text-sm">
                    <span className="text-gray-800 dark:text-gray-200">{it.product_name}</span>
                    <span className="font-mono font-semibold text-gray-600 dark:text-gray-400">×{it.quantity}</span>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                {o.kitchen_status === 'new' && (
                  <button
                    onClick={() => setStatus.mutate({ id: o.id, status: 'preparing' })}
                    className="flex-1 px-3 py-2 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-700"
                  >
                    <Flame size={14} className="inline mr-1" /> {t('მზადება')}
                  </button>
                )}
                {o.kitchen_status === 'preparing' && (
                  <button
                    onClick={() => setStatus.mutate({ id: o.id, status: 'done' })}
                    className="flex-1 px-3 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700"
                  >
                    <CheckCircle2 size={14} className="inline mr-1" /> {t('მზადაა')}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
