import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { ordersApi, productsApi, dashboardApi, clientsApi, tasksApi, exportsApi, reportsApi } from '../services/api'
import { BarChart2, Download, FileText, Users, ShoppingCart, Package, Bot, Bookmark, Clock, Layers } from 'lucide-react'
import { downloadBlob } from '../services/download'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { fmtDate, fmtDateTime, fmtTime } from '../lib/format'
// Unified currency format: "590 ₾"
const money = (v: number | string | null | undefined) =>
  new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(Number(v || 0))

const COLORS = ['#16A6D4', '#4CAF32', '#7C6966', '#8EDFF7', '#94DF79', '#BCAEAB']

export default function ReportsPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('sales')

  const { data: dashboardData } = useQuery({
    queryKey: ['dashboard', '90d'],
    queryFn: () => dashboardApi.getSummary('90d').then(r => r.data.data),
  })

  const { data: ordersData } = useQuery({
    queryKey: ['orders-all'],
    queryFn: () => ordersApi.list({ page_size: 100 }).then(r => r.data.data),
  })

  const { data: productsData } = useQuery({
    queryKey: ['products-all'],
    queryFn: () => productsApi.list({ page_size: 100 }).then(r => r.data.data),
  })

  const { data: clientsData } = useQuery({
    queryKey: ['clients-all'],
    queryFn: () => clientsApi.list({ page_size: 100 }).then(r => r.data.data),
  })

  const { data: tasksData } = useQuery({
    queryKey: ['tasks-all'],
    queryFn: () => tasksApi.list({ page_size: 100 }).then(r => r.data.data),
  })

  const { data: savedReports } = useQuery({ queryKey: ['reports-saved'], queryFn: () => reportsApi.saved().then(r => r.data.data) })
  const { data: schedules } = useQuery({ queryKey: ['reports-schedules'], queryFn: () => reportsApi.schedules().then(r => r.data.data) })
  const { data: dimensions } = useQuery({ queryKey: ['reports-dimensions'], queryFn: () => reportsApi.dimensions().then(r => r.data.data) })
  const [pivotMetric, setPivotMetric] = useState('revenue')
  const [pivotGroup, setPivotGroup] = useState('month')
  const { data: pivotData } = useQuery({
    queryKey: ['reports-pivot', pivotMetric, pivotGroup],
    queryFn: () => reportsApi.pivot({ metric: pivotMetric, group_by: pivotGroup }).then(r => r.data.data),
  })

  const revenueData = dashboardData?.revenue_chart?.data || []
  const orders = ordersData?.items || []
  const products = productsData?.items || []
  const clients = clientsData?.items || []
  const tasks = tasksData?.items || []

  const tabs = [
    { id: 'sales', label: t('გაყიდვები'), icon: BarChart2, exportFn: () => downloadBlob(exportsApi.orders(), 'orders.xlsx') },
    { id: 'orders', label: t('შეკვეთები'), icon: ShoppingCart, exportFn: () => downloadBlob(exportsApi.orders(), 'orders.xlsx') },
    { id: 'inventory', label: t('საწყობი'), icon: Package, exportFn: () => downloadBlob(exportsApi.products(), 'products.xlsx') },
    { id: 'clients', label: t('კლიენტები'), icon: Users, exportFn: () => downloadBlob(exportsApi.clients(), 'clients.xlsx') },
    { id: 'tasks', label: t('დავალებები'), icon: Bot, exportFn: () => downloadBlob(exportsApi.tasks(), 'tasks.xlsx') },
    { id: 'pivot', label: t('Pivot'), icon: BarChart2 },
    { id: 'saved', label: t('შენახული რეპორტები'), icon: Bookmark },
    { id: 'schedules', label: t('განრიგი'), icon: Clock },
    { id: 'dimensions', label: t('განზომილებები'), icon: Layers },
  ]

  const currentTab = tabs.find(t => t.id === activeTab)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('რეპორტები')}</h1>
        {currentTab?.exportFn && (
          <button onClick={currentTab.exportFn} className="btn-primary flex items-center gap-2 text-sm">
            <Download size={16} /> {t('Excel ექსპორტი')}
          </button>
        )}
      </div>

      <div className="flex gap-2 flex-wrap">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab.id ? 'bg-primary-600 text-white' : 'bg-white dark:bg-dark-200 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-100 dark:bg-dark-100 border border-gray-200 dark:border-dark-50'
            }`}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Sales Report */}
      {activeTab === 'sales' && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('შემოსავლები (90 დღე)')}</h3>
            <button onClick={() => downloadBlob(exportsApi.orders(), 'orders.xlsx')} className="btn-secondary flex items-center gap-2 text-sm">
              <Download size={14} /> {t('ექსპორტი')}
            </button>
          </div>
          {revenueData.length > 0 ? (
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={revenueData}>
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb' }} />
                <Bar dataKey="amount" fill="#3B82F6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-400 text-center py-56 dark:text-gray-500">{t('მონაცემები არ არის')}</p>
          )}
          <div className="mt-4 grid grid-cols-3 gap-4">
            <div className="p-3 bg-blue-50 rounded-lg text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400">{t('ჯამური შემოსავალი')}</p>
              <p className="text-xl font-bold text-blue-700">{money(dashboardData?.kpi?.total_revenue)}</p>
            </div>
            <div className="p-3 bg-green-50 rounded-lg text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400">{t('საშუალო დღიური')}</p>
              <p className="text-xl font-bold text-green-700">{revenueData.length ? Math.round(revenueData.reduce((s: number, d: any) => s + (d.amount || 0), 0) / revenueData.length).toLocaleString('ka-GE') : 0} ₾</p>
            </div>
            <div className="p-3 bg-purple-50 rounded-lg text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400">{t('დღეები')}</p>
              <p className="text-xl font-bold text-purple-700">{revenueData.length}</p>
            </div>
          </div>
        </div>
      )}

      {/* Orders Report */}
      {activeTab === 'orders' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('შეკვეთების სტატისტიკა')}</h3>
              <button onClick={() => downloadBlob(exportsApi.orders(), 'orders.xlsx')} className="btn-secondary flex items-center gap-2 text-xs">
                <Download size={12} /> Excel
              </button>
            </div>
            <div className="space-y-3">
              {['new', 'confirmed', 'preparing', 'shipping', 'completed', 'cancelled'].map(status => {
                const count = orders.filter((o: any) => o.status === status).length
                return (
                  <div key={status} className="flex items-center gap-3">
                    <span className="w-24 text-sm text-gray-600 dark:text-gray-400">{status}</span>
                    <div className="flex-1 bg-gray-100 dark:bg-dark-100 rounded-full h-2.5">
                      <div className="h-2.5 rounded-full bg-primary-500" style={{ width: `${orders.length ? (count / orders.length) * 100 : 0}%` }} />
                    </div>
                    <span className="text-sm font-medium w-10 text-right">{count}</span>
                  </div>
                )
              })}
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-4">{t('სულ შეკვეთები')}: {orders.length}</p>
          </div>
          <div className="card">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">{t('შეკვეთების განაწილება')}</h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={['new', 'confirmed', 'preparing', 'shipping', 'completed', 'cancelled'].map((s, i) => ({ name: s, value: orders.filter((o: any) => o.status === s).length })).filter(d => d.value > 0)} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}: ${value}`}>
                  {orders.filter((o: any) => o.status).map((_o: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Inventory Report */}
      {activeTab === 'inventory' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('ნაშთების სტატუსი')}</h3>
              <button onClick={() => downloadBlob(exportsApi.products(), 'products.xlsx')} className="btn-secondary flex items-center gap-2 text-xs">
                <Download size={12} /> Excel
              </button>
            </div>
            <div className="space-y-3">
              {[
                { label: t('კარგი'), status: 'good', color: 'bg-green-500' },
                { label: t('დაბალი'), status: 'low', color: 'bg-yellow-500' },
                { label: t('კრიტიკული'), status: 'critical', color: 'bg-red-500' },
              ].map(s => {
                const count = products.filter((p: any) => p.stock_status === s.status).length
                return (
                  <div key={s.status} className="flex items-center gap-3">
                    <span className="w-20 text-sm text-gray-600 dark:text-gray-400">{s.label}</span>
                    <div className="flex-1 bg-gray-100 dark:bg-dark-100 rounded-full h-2.5">
                      <div className={`h-2.5 rounded-full ${s.color}`} style={{ width: `${products.length ? (count / products.length) * 100 : 0}%` }} />
                    </div>
                    <span className="text-sm font-medium">{count}</span>
                  </div>
                )
              })}
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-4">{t('სულ პროდუქტები')}: {products.length}</p>
          </div>
          <div className="card">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">{t('პროდუქტების სია')}</h3>
            <div className="max-h-[300px] overflow-y-auto space-y-2">
              {products.slice(0, 10).map((p: any) => (
                <div key={p.id} className="flex items-center justify-between p-2 bg-gray-50 dark:bg-dark-100 rounded-lg text-sm">
                  <div>
                    <span className="font-medium">{p.name}</span>
                    <span className="text-xs text-gray-400 ml-2 dark:text-gray-500">{p.sku}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`badge ${p.stock_status === 'good' ? 'badge-green' : p.stock_status === 'low' ? 'badge-yellow' : 'badge-red'} text-xs`}>
                      {p.current_stock} {p.unit}
                    </span>
                    <span className="font-medium">{money(p.sale_price)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Clients Report */}
      {activeTab === 'clients' && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('კლიენტების სტატისტიკა')}</h3>
            <button onClick={() => downloadBlob(exportsApi.clients(), 'clients.xlsx')} className="btn-secondary flex items-center gap-2 text-xs">
              <Download size={12} /> Excel
            </button>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="p-4 bg-green-50 rounded-xl text-center">
              <p className="text-3xl font-bold text-green-700">{clients.filter((c: any) => c.status === 'active').length}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">{t('აქტიური')}</p>
            </div>
            <div className="p-4 bg-gray-50 dark:bg-dark-100 rounded-xl text-center">
              <p className="text-3xl font-bold text-gray-700 dark:text-gray-300">{clients.filter((c: any) => c.status === 'potential').length}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">{t('პოტენციური')}</p>
            </div>
            <div className="p-4 bg-red-50 rounded-xl text-center">
              <p className="text-3xl font-bold text-red-700">{clients.filter((c: any) => c.status === 'inactive').length}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">{t('არააქტიური')}</p>
            </div>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">{t('სულ კლიენტები')}: {clients.length}</p>
        </div>
      )}

      {/* Tasks Report */}
      {activeTab === 'tasks' && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('დავალებების სტატისტიკა')}</h3>
            <button onClick={() => downloadBlob(exportsApi.tasks(), 'tasks.xlsx')} className="btn-secondary flex items-center gap-2 text-xs">
              <Download size={12} /> Excel
            </button>
          </div>
          <div className="grid grid-cols-4 gap-4 mb-6">
            {['todo', 'in_progress', 'done', 'cancelled'].map(status => {
              const labels: Record<string, string> = { todo: 'საჭიროებს', in_progress: 'პროცესში', done: 'დასრულებული', cancelled: 'გაუქმებული' }
              const colors: Record<string, string> = { todo: 'bg-gray-50 dark:bg-dark-100 text-gray-700 dark:text-gray-300', in_progress: 'bg-blue-50 text-blue-700', done: 'bg-green-50 text-green-700', cancelled: 'bg-red-50 text-red-700' }
              const count = tasks.filter((t: any) => t.status === status).length
              return (
                <div key={status} className={`p-4 rounded-xl text-center ${colors[status]}`}>
                  <p className="text-3xl font-bold">{count}</p>
                  <p className="text-sm opacity-75">{labels[status]}</p>
                </div>
              )
            })}
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">სულ დავალებები: {tasks.length}</p>
        </div>
      )}

      {/* Pivot Report */}
      {activeTab === 'pivot' && (
        <div className="card">
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{t('Pivot ანალიზი')}</h3>
            <select value={pivotMetric} onChange={e => setPivotMetric(e.target.value)} className="input w-36 text-sm">
              <option value="revenue">{t('შემოსავალი')}</option>
              <option value="expenses">{t('ხარჯები')}</option>
            </select>
            <select value={pivotGroup} onChange={e => setPivotGroup(e.target.value)} className="input w-40 text-sm">
              <option value="month">{t('თვე')}</option>
              <option value="branch">{t('ფილიალი')}</option>
              <option value="product">{t('პროდუქტი')}</option>
              <option value="manager">{t('მენეჯერი')}</option>
            </select>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 dark:bg-dark-100 dark:text-gray-400">
                <tr>
                  <th className="px-4 py-3">{t('ჯგუფი')}</th>
                  <th className="px-4 py-3 text-right">{t('მნიშვნელობა')}</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-dark-50">
                {!pivotData || pivotData.rows.length === 0 ? (
                  <tr><td colSpan={2} className="p-8 text-center text-gray-500 dark:text-gray-400">{t('მონაცემები არ არის')}</td></tr>
                ) : pivotData.rows.map((r: any) => (
                  <tr key={r.group} className="hover:bg-gray-50 dark:hover:bg-dark-100">
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{r.group}</td>
                    <td className="px-4 py-3 text-right font-mono">{money(r.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Saved Reports */}
      {activeTab === 'saved' && (
        <div className="card">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">{t('შენახული რეპორტები')}</h3>
          {(savedReports || []).length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">{t('შენახული რეპორტები არ არის')}</p>
          ) : (
            <div className="space-y-2">
              {(savedReports || []).map((r: any) => (
                <div key={r.id} className="flex items-center justify-between rounded-lg border border-gray-200 dark:border-dark-50 px-4 py-3">
                  <div>
                    <div className="font-medium text-gray-900 dark:text-gray-100">{r.name}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{r.report_type}</div>
                  </div>
                  <span className="text-xs text-gray-400">{fmtDate(new Date(r.created_at))}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Schedules */}
      {activeTab === 'schedules' && (
        <div className="card">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">{t('განრიგი')}</h3>
          {(schedules || []).length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">{t('განრიგები არ არის')}</p>
          ) : (
            <div className="space-y-2">
              {(schedules || []).map((s: any) => (
                <div key={s.id} className="flex items-center justify-between rounded-lg border border-gray-200 dark:border-dark-50 px-4 py-3">
                  <div>
                    <div className="font-medium text-gray-900 dark:text-gray-100">{s.frequency}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{s.recipients || '—'}</div>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${s.is_active ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {s.is_active ? t('აქტიური') : t('არააქტიური')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Dimensions */}
      {activeTab === 'dimensions' && (
        <div className="card">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">{t('განზომილებები')}</h3>
          {(dimensions || []).length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">{t('განზომილებები არ არის')}</p>
          ) : (
            <div className="grid gap-3 md:grid-cols-3">
              {(dimensions || []).map((d: any) => (
                <div key={d.id} className="rounded-lg border border-gray-200 dark:border-dark-50 p-4">
                  <div className="font-medium text-gray-900 dark:text-gray-100">{d.label}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{d.name}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}