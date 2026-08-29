import { Link , useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dashboardApi, usersApi } from '../services/api'
import { TrendingUp, Users, ShoppingCart, AlertTriangle, Package, ArrowUp, ArrowDown, Wallet, Clock , ArrowUpRight } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, AreaChart, Area } from 'recharts'
import { StatusBadge, orderStatusMap } from '../components/ui/Badges'
import type { DashboardData } from '../types'
// Unified currency format: "590 ₾"
const money = (v: number | string | null | undefined) =>
  new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(Number(v || 0))

const COLORS = ['#16A6D4', '#4CAF32', '#7C6966', '#8EDFF7', '#94DF79', '#BCAEAB']

export default function DashboardPage() {
  const { t } = useTranslation()
  const [period, setPeriod] = useState('30d')
  const [ownerId, setOwnerId] = useState('')
  const [showCustomize, setShowCustomize] = useState(false)
  const [hiddenKpis, setHiddenKpis] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('bos_hidden_kpis') || '[]') } catch { return [] }
  })

  const toggleKpi = (key: string) => {
    setHiddenKpis(prev => {
      const next = prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
      localStorage.setItem('bos_hidden_kpis', JSON.stringify(next))
      return next
    })
  }

  const { data: users } = useQuery({
    queryKey: ['dashboard-users'],
    queryFn: () => usersApi.list({ page_size: 100 }).then(r => r.data.data),
  })

  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', period, ownerId],
    queryFn: () => dashboardApi.getSummary(period, ownerId || undefined).then(r => r.data.data),
  })
  const { data: aging } = useQuery({
    queryKey: ['dashboard-aging'],
    queryFn: () => dashboardApi.getAging().then(r => r.data.data),
  })
  const { data: cashFlow } = useQuery({
    queryKey: ['dashboard-cashflow'],
    queryFn: () => dashboardApi.getCashFlow().then(r => r.data.data),
  })

  if (isLoading) return <div className="flex items-center justify-center h-64 text-gray-500 dark:text-gray-400 dark:text-gray-500">{t('ჩატვირთვა...')}</div>

  const kpi = data?.kpi
  const revenueData: any[] = data?.revenue_chart?.data || []
  const orderDist: any[] = data?.order_status_distribution || []
  const alerts: any[] = data?.critical_alerts || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 dark:text-gray-200">{t('მიმოხილვა')}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={ownerId}
            onChange={(e) => setOwnerId(e.target.value)}
            className="input h-9 w-auto text-sm"
            aria-label={t('პასუხისმგებელი ფილტრი')}
          >
            <option value="">{t('ყველა თანამშრომელი')}</option>
            {(users?.items || users || []).map((u: any) => (
              <option key={u.id} value={u.id}>{u.full_name}</option>
            ))}
          </select>
          <div className="flex gap-2 bg-white dark:bg-dark-200 rounded-lg border border-gray-200 dark:border-dark-50 p-1 dark:bg-dark-200 dark:border-dark-50">
            {[
              { key: '7d', label: t('7 დღე') },
              { key: '30d', label: t('30 დღე') },
              { key: '90d', label: t('90 დღე') },
            ].map(p => (
              <button
                key={p.key}
                onClick={() => setPeriod(p.key)}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${period === p.key ? 'bg-primary-600 text-white' : 'text-gray-600 dark:text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 dark:text-gray-400 dark:text-gray-500 dark:hover:bg-dark-100'}`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => setShowCustomize(!showCustomize)}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${showCustomize ? 'bg-primary-600 text-white border-primary-600' : 'bg-white dark:bg-dark-200 border-gray-200 dark:border-dark-50 text-gray-600 dark:text-gray-400'}`}
          >
            {t('მორგება')}
          </button>
        </div>
      </div>

      {/* Customize panel */}
      {showCustomize && (
        <div className="card p-4">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">{t('KPI ბარათების მორგება')}</h3>
          <div className="flex flex-wrap gap-2">
            {[
              { key: 'revenue', label: t('შემოსავალი') },
              { key: 'clients', label: t('აქტიური კლიენტები') },
              { key: 'orders', label: t('მიმდინარე შეკვეთები') },
              { key: 'tasks', label: t('დაგვიანებული დავალებები') },
            ].map(k => (
              <button
                key={k.key}
                onClick={() => toggleKpi(k.key)}
                className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${hiddenKpis.includes(k.key) ? 'bg-gray-100 dark:bg-dark-100 text-gray-400 line-through' : 'bg-primary-50 text-primary-700 border-primary-200'}`}
              >
                {k.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {!hiddenKpis.includes('revenue') && (
        <KPICard
          icon={TrendingUp}
          label={t('შემოსავალი')}
          value={kpi?.total_revenue != null ? money(kpi.total_revenue) : money(0)}
          change={kpi?.revenue_change}
          color="blue"
          hint={`${t('ინვოისირებული შეკვეთები')}: ${data?.invoiced_orders_count ?? 0} / ${data?.total_orders_count ?? 0}`}
          to="/invoices"
        />
        )}
        {!hiddenKpis.includes('clients') && <KPICard icon={Users} label={t('აქტიური კლიენტები')} value={String(kpi?.active_clients || 0)} color="green" to="/clients" />}
        {!hiddenKpis.includes('orders') && <KPICard icon={ShoppingCart} label={t('მიმდინარე შეკვეთები')} value={String(kpi?.active_orders || 0)} color="gray" to="/orders" />}
        {!hiddenKpis.includes('tasks') && <KPICard icon={AlertTriangle} label={t('დაგვიანებული დავალებები')} value={String(kpi?.overdue_tasks || 0)} color="red" to="/tasks" />}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Revenue Chart */}
        <div className="lg:col-span-2 card">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 dark:text-gray-200 mb-4">{t('შემოსავლების დინამიკა')}</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={revenueData.filter((d: any) => d.amount > 0)}>
              <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="#9CA3AF" />
              <YAxis tick={{ fontSize: 10 }} stroke="#9CA3AF" width={45} />
              <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb' }} />
              <Line type="monotone" dataKey="amount" stroke="#16A6D4" strokeWidth={3} dot={{ fill: '#16A6D4', r: 3 }} activeDot={{ fill: '#4CAF32', r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Order Distribution */}
        <div className="card">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 dark:text-gray-200 mb-4">{t('შეკვეთების სტატუსები')}</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={orderDist} dataKey="count" nameKey="status" cx="50%" cy="50%" innerRadius={50} outerRadius={80}>
                {orderDist.map((_: any, i: number) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-4">
            {orderDist.map((d: any, index: number) => (
              <div key={d.status} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                  <span>{t(orderStatusMap[d.status]?.label || d.status)}</span>
                </div>
                <span className="font-medium">{d.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="card">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 dark:text-gray-200 mb-4">{t('გაფრთხილებები')}</h3>
          <div className="space-y-2">
            {alerts.map((alert: any, i: number) => {
  // Translate alert titles: backend sends Georgian prefixes, but the
  // entity name (product/task title) is business data — keep it as-is.
  const alertTitle = (alert: any) => {
    const raw: string = alert.title || ''
    if (alert.type === 'low_stock') {
      return `${t('დაბალი ნაშთი')}: ${raw.replace(/^დაბალი ნაშთი:?\s*/i, '')}`
    }
    if (alert.type === 'overdue_task') {
      return `${t('დაგვიანებული დავალება')}: ${raw.replace(/^დაგვიანებული დავალება:?\s*/i, '')}`
    }
    return raw
  }

  // Translate alert descriptions: backend sends Georgian prefixes, the
  // entity name (product/task title) is business data — keep it as-is.
  const alertDescription = (alert: any) => {
    const raw: string = alert.description || ''
    if (alert.type === 'low_stock') {
      return raw.replace(/^მიმდინარე ნაშთი:\s*/i, `${t('მიმდინარე ნაშთი')}: `)
    }
    if (alert.type === 'overdue_task') {
      return raw.replace(/^ვადაგადაცილება:\s*/i, `${t('ვადაგადაცილება')}: `)
    }
    return raw
  }

  const target =
    alert.type === 'low_stock' ? `/inventory?highlight=${alert.entity_id}`
                : alert.type === 'overdue_task' ? `/tasks?highlight=${alert.entity_id}`
                : alert.type === 'overdue_invoice' ? `/invoices?highlight=${alert.entity_id}`
                : null
              const inner = (
                <>
                  <AlertTriangle size={18} className="shrink-0" />
                  <div className="min-w-0">
                    <p className="font-medium text-sm">{alertTitle(alert)}</p>
                    <p className="text-xs opacity-75">{alertDescription(alert)}</p>
                  </div>
                </>
              )
              return target ? (
                <Link
                  key={i}
                  to={target}
                  className={`flex items-center gap-3 p-3 rounded-lg transition-colors hover:brightness-95 ${
                    alert.severity === 'high' ? 'bg-red-50 text-red-800' : 'bg-yellow-50 text-yellow-800'
                  }`}
                >
                  {inner}
                </Link>
              ) : (
                <div key={i} className={`flex items-center gap-3 p-3 rounded-lg ${
                  alert.severity === 'high' ? 'bg-red-50 text-red-800' : 'bg-yellow-50 text-yellow-800'
                }`}>
                  {inner}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Low stock products */}
      {kpi?.low_stock_products > 0 && (
        <div className="card bg-brandgray-50 dark:bg-dark-100 border-brandgray-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <Package size={20} className="text-primary-600" />
            <div>
              <p className="font-medium text-brandgray-800 dark:text-gray-200">{t('დაბალი ნაშთი')}: {kpi.low_stock_products} {t('პროდუქტი')}</p>
              <p className="text-sm text-primary-700">{t('გადადით საწყობში შესავსებად')}</p>
            </div>
          </div>
        </div>
      )}

      {/* Dashboard 2.0: AR/AP Aging + Cash Flow */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AR/AP Aging */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Clock size={18} className="text-primary-600" />
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 dark:text-gray-200">{t('ვადიანობა — მოთხოვნები / ვალდებულებები')}</h3>
          </div>
          {aging && (
            <>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{t('მოთხოვნები (AR)')}</p>
                  <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{money(aging.ar_total)}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-500 dark:text-gray-400">{t('ვალდებულებები (AP)')}</p>
                  <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{money(aging.ap_total)}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  {aging.ar_buckets.map((b: any) => (
                    <div key={b.bucket} className="flex items-center justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-400">{t(b.label)}</span>
                      <span className="font-medium">{money(b.amount)}</span>
                    </div>
                  ))}
                </div>
                <div className="space-y-1.5">
                  {aging.ap_buckets.map((b: any) => (
                    <div key={b.bucket} className="flex items-center justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-400">{t(b.label)}</span>
                      <span className="font-medium">{money(b.amount)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Cash Flow */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Wallet size={18} className="text-primary-600" />
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 dark:text-gray-200">{t('ფულადი ნაკადი — 6 თვე')}</h3>
          </div>
          {cashFlow && (
            <>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{t('წმინდა ნაკადი (6 თვე)')}</p>
                  <p className={`text-xl font-bold ${Number(cashFlow.net_6m) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {money(cashFlow.net_6m)}
                  </p>
                </div>
                <div className="flex gap-4 text-xs">
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-green-500" /> {t('შემოსავლები')}</span>
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-400" /> {t('ხარჯები')}</span>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={cashFlow.series}>
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} stroke="#9CA3AF" />
                  <YAxis tick={{ fontSize: 10 }} stroke="#9CA3AF" />
                  <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb' }} />
                  <Area type="monotone" dataKey="inflow" stroke="#4CAF32" fill="#4CAF32" fillOpacity={0.15} name={t('შემოსავალი')} />
                  <Area type="monotone" dataKey="outflow" stroke="#EF6F6C" fill="#EF6F6C" fillOpacity={0.15} name={t('ხარჯები')} />
                </AreaChart>
              </ResponsiveContainer>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function KPICard({ icon: Icon, label, value, change, color, hint, to }: { icon: any; label: string; value: string; change?: number; color: string; hint?: string; to?: string }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const colorMap: Record<string, string> = {
    blue: 'bg-primary-50 text-primary-700',
    green: 'bg-accent-50 text-accent-700',
    red: 'bg-red-50 text-red-600',
    gray: 'bg-brandgray-100 dark:bg-dark-100 text-brandgray-700 dark:text-gray-300',
  }

  const content = (
    <div className="card flex items-center gap-4 dark:bg-dark-200 dark:border-dark-50">
      <div className={`p-3 rounded-xl ${colorMap[color] || colorMap.blue}`}>
        <Icon size={24} />
      </div>
      <div className="flex-1">
        <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 dark:text-gray-200">{value}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500">{t(label)}</p>
        {change !== undefined && (
          <span className={`text-xs flex items-center gap-1 mt-0.5 ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {change >= 0 ? <ArrowUp size={12} /> : <ArrowDown size={12} />}
            {Math.abs(change).toFixed(1)}%
          </span>
        )}
        {hint && (
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1" title={t('შემოსავალი ითვლება მხოლოდ გაცემული (issued) ინვოისებიდან')}>{hint}</p>
        )}
      </div>
      {to && (
        <ArrowUpRight size={16} className="text-gray-300 dark:text-gray-600 transition-colors group-hover:text-primary-500" />
      )}
    </div>
  )

  return to ? (
    <button
      type="button"
      onClick={() => navigate(to)}
      title={t('დეტალურად ნახვა')}
      className="group text-left transition-transform hover:-translate-y-0.5"
    >
      {content}
    </button>
  ) : (
    content
  )
}