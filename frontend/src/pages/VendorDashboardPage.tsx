import { useTranslation } from 'react-i18next'
import { Navigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { LogOut, FileText, ShoppingCart, ReceiptText, Tag } from 'lucide-react'

import { useVendorAuthStore } from '../store/vendorAuthStore'
import { vendorAuthApi } from '../services/api'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'

function money(v: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(v)
}

export default function VendorDashboardPage() {
  const { t } = useTranslation()
  const { user, accessToken, logout, isAuthenticated } = useVendorAuthStore()

  const { data, isLoading } = useQuery({
    queryKey: ['vendor-dashboard', accessToken],
    queryFn: () => vendorAuthApi.dashboard(accessToken || '').then(r => r.data.data),
    enabled: !!accessToken,
  })

  if (!isAuthenticated) return <Navigate to="/vendor/login" />

  const d = data as any

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-dark-200">
      <header className="border-b border-brandgray-100 dark:border-dark-50 bg-white dark:bg-dark-200">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="text-lg font-bold text-brandgray-800 dark:text-gray-100">Business OS</div>
            <span className="rounded-full bg-primary-50 dark:bg-primary-900/30 px-2.5 py-0.5 text-xs font-medium text-primary-700 dark:text-primary-300">
              {t('მომწოდებლის პორტალი')}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-sm font-semibold text-brandgray-800 dark:text-gray-100">{user?.display_name}</div>
              <div className="text-xs text-brandgray-500 dark:text-gray-400">{user?.supplier_name}</div>
            </div>
            <button
              onClick={logout}
              className="inline-flex items-center gap-1.5 rounded-lg border border-brandgray-200 dark:border-dark-50 px-3 py-1.5 text-sm text-brandgray-600 hover:bg-brandgray-50 dark:text-gray-400 dark:hover:bg-dark-100"
            >
              <LogOut size={15} /> {t('გასვლა')}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">
          {t('მოგესალმებით')}, {user?.display_name}!
        </h1>
        <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">
          {t('თქვენი თანამშრომლობის მიმოხილვა')}
        </p>

        {isLoading ? (
          <div className="mt-8 text-center text-sm text-brandgray-500 dark:text-gray-400">{t('იტვირთება...')}</div>
        ) : (
          <>
            <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-xl border border-brandgray-100 dark:border-dark-50 bg-white dark:bg-dark-100 p-4">
                <div className="flex items-center gap-2 text-xs text-brandgray-500 dark:text-gray-400">
                  <FileText size={14} className="text-primary-600 dark:text-primary-400" /> {t('RFQ')}
                </div>
                <div className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">{d?.counts?.rfqs ?? 0}</div>
              </div>
              <div className="rounded-xl border border-brandgray-100 dark:border-dark-50 bg-white dark:bg-dark-100 p-4">
                <div className="flex items-center gap-2 text-xs text-brandgray-500 dark:text-gray-400">
                  <ShoppingCart size={14} className="text-blue-600 dark:text-blue-400" /> {t('შეკვეთები')}
                </div>
                <div className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">{d?.counts?.purchase_orders ?? 0}</div>
              </div>
              <div className="rounded-xl border border-brandgray-100 dark:border-dark-50 bg-white dark:bg-dark-100 p-4">
                <div className="flex items-center gap-2 text-xs text-brandgray-500 dark:text-gray-400">
                  <ReceiptText size={14} className="text-emerald-600 dark:text-emerald-400" /> {t('ინვოისები')}
                </div>
                <div className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">{d?.counts?.invoices ?? 0}</div>
              </div>
              <div className="rounded-xl border border-brandgray-100 dark:border-dark-50 bg-white dark:bg-dark-100 p-4">
                <div className="flex items-center gap-2 text-xs text-brandgray-500 dark:text-gray-400">
                  <Tag size={14} className="text-amber-600 dark:text-amber-400" /> {t('ფასების სია')}
                </div>
                <div className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">{d?.counts?.price_lists ?? 0}</div>
              </div>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <section className="rounded-xl border border-brandgray-100 dark:border-dark-50 bg-white dark:bg-dark-100 p-5">
                <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{t('RFQ-ები')}</h2>
                {!d?.rfqs?.length ? (
                  <p className="mt-3 text-sm text-brandgray-500 dark:text-gray-400">{t('RFQ არ არის')}</p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {d.rfqs.map((r: any) => (
                      <div key={r.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                        <span className="font-mono font-semibold text-gray-900 dark:text-gray-100">{r.rfq_number}</span>
                        <span className="text-brandgray-500 dark:text-gray-400">{r.title}</span>
                        <span className="rounded-full bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-300">{r.status}</span>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="rounded-xl border border-brandgray-100 dark:border-dark-50 bg-white dark:bg-dark-100 p-5">
                <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{t('შეკვეთები')}</h2>
                {!d?.purchase_orders?.length ? (
                  <p className="mt-3 text-sm text-brandgray-500 dark:text-gray-400">{t('შეკვეთები არ არის')}</p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {d.purchase_orders.map((o: any) => (
                      <div key={o.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                        <span className="font-mono font-semibold text-gray-900 dark:text-gray-100">{o.purchase_order_number}</span>
                        <span className="text-brandgray-500 dark:text-gray-400">{o.status}</span>
                        <span className="font-mono font-semibold">{money(o.total)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="rounded-xl border border-brandgray-100 dark:border-dark-50 bg-white dark:bg-dark-100 p-5">
                <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{t('ინვოისები')}</h2>
                {!d?.invoices?.length ? (
                  <p className="mt-3 text-sm text-brandgray-500 dark:text-gray-400">{t('ინვოისები არ არის')}</p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {d.invoices.map((inv: any) => (
                      <div key={inv.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                        <span className="font-mono font-semibold text-gray-900 dark:text-gray-100">{inv.supplier_invoice_number}</span>
                        <span className="text-brandgray-500 dark:text-gray-400">{fmtDate(new Date(inv.invoice_date))}</span>
                        <span className="font-mono font-semibold">{money(inv.total)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="rounded-xl border border-brandgray-100 dark:border-dark-50 bg-white dark:bg-dark-100 p-5">
                <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{t('ფასების სია')}</h2>
                {!d?.price_lists?.length ? (
                  <p className="mt-3 text-sm text-brandgray-500 dark:text-gray-400">{t('ფასები არ არის')}</p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {d.price_lists.map((pl: any) => (
                      <div key={pl.id} className="flex items-center justify-between rounded-lg border border-brandgray-100 dark:border-dark-50 px-3 py-2 text-sm">
                        <span className="font-mono text-gray-900 dark:text-gray-100">{pl.product_id.slice(0, 8)}</span>
                        <span className="font-mono font-semibold">{pl.price} {pl.currency}</span>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
