import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import {
  FileText, Calculator, Scale, Download, Calendar, Building2, TrendingUp, TrendingDown, DollarSign
} from 'lucide-react'

import { api } from '../services/api'
import type { VatDeclaration, IncomeTaxReport, BalanceForm } from '../types'

const today = () => new Date().toISOString().slice(0, 10)
const currentYear = new Date().getFullYear()
const currentMonth = new Date().getMonth() + 1

function money(value: number) {
  return new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(value)
}

const tabs = [
  { id: 'vat', label: 'დღგ-ის დეკლარაცია', icon: Calculator },
  { id: 'income', label: 'საშემოსავლო გადასახადი', icon: TrendingUp },
  { id: 'balance', label: 'ბალანსის ფორმა', icon: Scale },
]

export default function SrsPage() {
  const { t } = useTranslation()
  const [tab, setTab] = useState('vat')
  const [year, setYear] = useState(currentYear)
  const [month, setMonth] = useState(currentMonth)
  const [asOfDate, setAsOfDate] = useState(today())

  // ── Queries ──────────────────────────────────────────────────────

  const { data: vatData, isLoading: vatLoading } = useQuery({
    queryKey: ['srs-vat', year, month],
    queryFn: () => api.get('/srs/vat-declaration', { params: { year, month } }).then((r) => r.data.data),
    enabled: tab === 'vat',
  })

  const { data: incomeData, isLoading: incomeLoading } = useQuery({
    queryKey: ['srs-income', year, month],
    queryFn: () => api.get('/srs/income-tax', { params: { year, month } }).then((r) => r.data.data),
    enabled: tab === 'income',
  })

  const { data: balanceData, isLoading: balanceLoading } = useQuery({
    queryKey: ['srs-balance', asOfDate],
    queryFn: () => api.get('/srs/balance-form', { params: { as_of_date: asOfDate } }).then((r) => r.data.data),
    enabled: tab === 'balance',
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brandgray-900 dark:text-gray-100">{t('SRS ანგარიშგება')}</h1>
          <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('საგადასახადო ანგარიშები — დღგ, საშემოსავლო, ბალანსი')}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-brandgray-100 dark:border-dark-50">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id
                ? 'border-primary-600 text-primary-700 dark:border-primary-400 dark:text-primary-300'
                : 'border-transparent text-brandgray-500 hover:text-brandgray-700 hover:border-brandgray-300 dark:text-gray-400 dark:hover:text-gray-200'
            }`}
          >
            <t.icon size={18} />
            {t.label}
          </button>
        ))}
      </div>

      {/* ── VAT Declaration ──────────────────────────────────────── */}
      {tab === 'vat' && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Calendar size={18} className="text-gray-400 dark:text-gray-500" />
              <select value={year} onChange={(e) => setYear(Number(e.target.value))} className="input w-28">
                {Array.from({ length: 10 }, (_, i) => currentYear - 5 + i).map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
              <select value={month} onChange={(e) => setMonth(Number(e.target.value))} className="input w-32">
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <option key={m} value={m}>{m.toString().padStart(2, '0')}</option>
                ))}
              </select>
            </div>
          </div>

          {vatLoading ? (
            <div className="card p-8 text-center text-gray-500 dark:text-gray-400 dark:bg-dark-200 dark:border-dark-50">{t('იტვირთება...')}</div>
          ) : vatData ? (
            <div className="space-y-4">
              <div className="card dark:bg-dark-200 dark:border-dark-50">
                <h3 className="font-semibold text-brandgray-900 dark:text-gray-100 mb-4">დღგ-ის დეკლარაცია — {vatData.period}</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-brandgray-50 dark:bg-dark-100">
                      <tr>
                        <th className="px-4 py-3 text-left text-brandgray-600 dark:text-gray-400">{t('კოდი')}</th>
                        <th className="px-4 py-3 text-left text-brandgray-600 dark:text-gray-400">{t('დასახელება')}</th>
                        <th className="px-4 py-3 text-right text-brandgray-600 dark:text-gray-400">{t('თანხა')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-brandgray-100 dark:divide-dark-50">
                      {vatData.rows.map((row: any) => (
                        <tr key={row.line_code} className="hover:bg-brandgray-50/50 dark:hover:bg-dark-100">
                          <td className="px-4 py-3 font-mono text-brandgray-600 dark:text-gray-400">{row.line_code}</td>
                          <td className="px-4 py-3">{row.line_name}</td>
                          <td className="px-4 py-3 text-right font-medium">{money(row.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
                  <div className="flex items-center gap-3">
                    <TrendingUp className="text-green-600" />
                    <div>
                      <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('გასაყიდი დღგ')}</div>
                      <div className="text-xl font-semibold text-brandgray-900 dark:text-gray-100">{money(vatData.total_vat_payable)}</div>
                    </div>
                  </div>
                </div>
                <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
                  <div className="flex items-center gap-3">
                    <TrendingDown className="text-amber-600" />
                    <div>
                      <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('შესაძენი დღგ')}</div>
                      <div className="text-xl font-semibold text-brandgray-900 dark:text-gray-100">{money(vatData.total_vat_credit)}</div>
                    </div>
                  </div>
                </div>
                <div className="card p-5 border-2 border-primary-200 dark:border-primary-800 dark:bg-dark-200">
                  <div className="flex items-center gap-3">
                    <DollarSign className="text-primary-600" />
                    <div>
                      <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('გადასახდელი დღგ')}</div>
                      <div className="text-xl font-semibold text-primary-700 dark:text-primary-300">{money(vatData.net_vat)}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="card p-8 text-center text-gray-500 dark:text-gray-400 dark:bg-dark-200 dark:border-dark-50">{t('მონაცემები არ მოიძებნა ამ პერიოდისთვის')}</div>
          )}
        </>
      )}

      {/* ── Income Tax ────────────────────────────────────────────── */}
      {tab === 'income' && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Calendar size={18} className="text-gray-400 dark:text-gray-500" />
              <select value={year} onChange={(e) => setYear(Number(e.target.value))} className="input w-28">
                {Array.from({ length: 10 }, (_, i) => currentYear - 5 + i).map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
              <select value={month} onChange={(e) => setMonth(Number(e.target.value))} className="input w-32">
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <option key={m} value={m}>{m.toString().padStart(2, '0')}</option>
                ))}
              </select>
            </div>
          </div>

          {incomeLoading ? (
            <div className="card p-8 text-center text-gray-500 dark:text-gray-400 dark:bg-dark-200 dark:border-dark-50">{t('იტვირთება...')}</div>
          ) : incomeData ? (
            <div className="space-y-4">
              <div className="card dark:bg-dark-200 dark:border-dark-50">
                <h3 className="font-semibold text-brandgray-900 dark:text-gray-100 mb-4">საშემოსავლო გადასახადი — {incomeData.period}</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-brandgray-50 dark:bg-dark-100">
                      <tr>
                        <th className="px-4 py-3 text-left text-brandgray-600 dark:text-gray-400">{t('კოდი')}</th>
                        <th className="px-4 py-3 text-left text-brandgray-600 dark:text-gray-400">{t('დასახელება')}</th>
                        <th className="px-4 py-3 text-right text-brandgray-600 dark:text-gray-400">{t('თანხა')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-brandgray-100 dark:divide-dark-50">
                      {incomeData.rows.map((row: any) => (
                        <tr key={row.line_code} className="hover:bg-brandgray-50/50 dark:hover:bg-dark-100">
                          <td className="px-4 py-3 font-mono text-brandgray-600 dark:text-gray-400">{row.line_code}</td>
                          <td className="px-4 py-3">{row.line_name}</td>
                          <td className="px-4 py-3 text-right font-medium">{money(row.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-4">
                <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
                  <div className="flex items-center gap-3">
                    <TrendingUp className="text-green-600" />
                    <div>
                      <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('შემოსავალი')}</div>
                      <div className="text-xl font-semibold text-brandgray-900 dark:text-gray-100">{money(incomeData.total_revenue)}</div>
                    </div>
                  </div>
                </div>
                <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
                  <div className="flex items-center gap-3">
                    <TrendingDown className="text-red-600" />
                    <div>
                      <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('ხარჯი')}</div>
                      <div className="text-xl font-semibold text-brandgray-900 dark:text-gray-100">{money(incomeData.total_expenses)}</div>
                    </div>
                  </div>
                </div>
                <div className="card p-5 dark:bg-dark-200 dark:border-dark-50">
                  <div className="flex items-center gap-3">
                    <Calculator className="text-amber-600" />
                    <div>
                      <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('დასაბეგრი მოგება')}</div>
                      <div className="text-xl font-semibold text-brandgray-900 dark:text-gray-100">{money(incomeData.taxable_profit)}</div>
                    </div>
                  </div>
                </div>
                <div className="card p-5 border-2 border-primary-200 dark:border-primary-800 dark:bg-dark-200">
                  <div className="flex items-center gap-3">
                    <DollarSign className="text-primary-600" />
                    <div>
                      <div className="text-sm text-brandgray-500 dark:text-gray-400">{t('სავარაუდო გადასახადი (15%)')}</div>
                      <div className="text-xl font-semibold text-primary-700 dark:text-primary-300">{money(incomeData.estimated_tax)}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="card p-8 text-center text-gray-500 dark:text-gray-400 dark:bg-dark-200 dark:border-dark-50">{t('მონაცემები არ მოიძებნა')}</div>
          )}
        </>
      )}

      {/* ── Balance Form ──────────────────────────────────────────── */}
      {tab === 'balance' && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Calendar size={18} className="text-gray-400 dark:text-gray-500" />
              <input type="date" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)} className="input w-44" />
            </div>
          </div>

          {balanceLoading ? (
            <div className="card p-8 text-center text-gray-500 dark:text-gray-400 dark:bg-dark-200 dark:border-dark-50">{t('იტვირთება...')}</div>
          ) : balanceData ? (
            <div className="space-y-4">
              <div className="card dark:bg-dark-200 dark:border-dark-50">
                <h3 className="font-semibold text-brandgray-900 dark:text-gray-100 mb-4">{t('აქტივები')}</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-brandgray-50 dark:bg-dark-100">
                      <tr>
                        <th className="px-4 py-3 text-left text-brandgray-600 dark:text-gray-400">{t('კოდი')}</th>
                        <th className="px-4 py-3 text-left text-brandgray-600 dark:text-gray-400">{t('დასახელება')}</th>
                        <th className="px-4 py-3 text-right text-brandgray-600 dark:text-gray-400">{t('თანხა')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-brandgray-100 dark:divide-dark-50">
                      {balanceData.assets.map((row: any) => (
                        <tr key={row.code} className="hover:bg-brandgray-50/50 dark:hover:bg-dark-100">
                          <td className="px-4 py-3 font-mono text-brandgray-600 dark:text-gray-400">{row.code}</td>
                          <td className="px-4 py-3">{row.name}</td>
                          <td className="px-4 py-3 text-right font-medium">{money(row.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-brandgray-50 dark:bg-dark-100 font-semibold">
                      <tr>
                        <td colSpan={2} className="px-4 py-3 text-brandgray-800 dark:text-gray-200">{t('სულ აქტივები')}</td>
                        <td className="px-4 py-3 text-right text-primary-700 dark:text-primary-300">{money(balanceData.total_assets)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              <div className="card dark:bg-dark-200 dark:border-dark-50">
                <h3 className="font-semibold text-brandgray-900 dark:text-gray-100 mb-4">{t('ვალდებულებები')}</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-brandgray-50 dark:bg-dark-100">
                      <tr>
                        <th className="px-4 py-3 text-left text-brandgray-600 dark:text-gray-400">{t('კოდი')}</th>
                        <th className="px-4 py-3 text-left text-brandgray-600 dark:text-gray-400">{t('დასახელება')}</th>
                        <th className="px-4 py-3 text-right text-brandgray-600 dark:text-gray-400">{t('თანხა')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-brandgray-100 dark:divide-dark-50">
                      {balanceData.liabilities.map((row: any) => (
                        <tr key={row.code} className="hover:bg-brandgray-50/50 dark:hover:bg-dark-100">
                          <td className="px-4 py-3 font-mono text-brandgray-600 dark:text-gray-400">{row.code}</td>
                          <td className="px-4 py-3">{row.name}</td>
                          <td className="px-4 py-3 text-right font-medium">{money(row.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-brandgray-50 dark:bg-dark-100 font-semibold">
                      <tr>
                        <td colSpan={2} className="px-4 py-3 text-brandgray-800 dark:text-gray-200">{t('სულ ვალდებულებები')}</td>
                        <td className="px-4 py-3 text-right text-amber-700 dark:text-amber-300">{money(balanceData.total_liabilities)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              <div className="card dark:bg-dark-200 dark:border-dark-50">
                <h3 className="font-semibold text-brandgray-900 dark:text-gray-100 mb-4">{t('კაპიტალი')}</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-brandgray-50 dark:bg-dark-100">
                      <tr>
                        <th className="px-4 py-3 text-left text-brandgray-600 dark:text-gray-400">{t('კოდი')}</th>
                        <th className="px-4 py-3 text-left text-brandgray-600 dark:text-gray-400">{t('დასახელება')}</th>
                        <th className="px-4 py-3 text-right text-brandgray-600 dark:text-gray-400">{t('თანხა')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-brandgray-100 dark:divide-dark-50">
                      {balanceData.equity.map((row: any) => (
                        <tr key={row.code} className="hover:bg-brandgray-50/50 dark:hover:bg-dark-100">
                          <td className="px-4 py-3 font-mono text-brandgray-600 dark:text-gray-400">{row.code}</td>
                          <td className="px-4 py-3">{row.name}</td>
                          <td className="px-4 py-3 text-right font-medium">{money(row.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-brandgray-50 dark:bg-dark-100 font-semibold">
                      <tr>
                        <td colSpan={2} className="px-4 py-3 text-brandgray-800 dark:text-gray-200">{t('სულ კაპიტალი')}</td>
                        <td className="px-4 py-3 text-right text-green-700 dark:text-green-300">{money(balanceData.total_equity)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              <div className="card p-5 border-2 border-primary-200 dark:border-primary-800 dark:bg-dark-200">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Scale className="text-primary-600" />
                    <div>
                      <p className="text-sm text-brandgray-500 dark:text-gray-400">{t('ბალანსის შემოწმება')}</p>
                      <p className="text-lg font-semibold text-brandgray-900 dark:text-gray-100">
                        აქტივები: {money(balanceData.total_assets)} = ვალდებულებები: {money(balanceData.total_liabilities)} + კაპიტალი: {money(balanceData.total_equity)}
                      </p>
                    </div>
                  </div>
                  <span className={`badge ${Math.abs(balanceData.total_assets - balanceData.total_liabilities - balanceData.total_equity) < 0.01 ? 'badge-green' : 'badge-red'}`}>
                    {Math.abs(balanceData.total_assets - balanceData.total_liabilities - balanceData.total_equity) < 0.01 ? '✅ დაბალანსებულია' : '❌ შეუსაბამობა'}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="card p-8 text-center text-gray-500 dark:text-gray-400 dark:bg-dark-200 dark:border-dark-50">{t('მონაცემები არ მოიძებნა')}</div>
          )}
        </>
      )}
    </div>
  )
}
