import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ordersApi, productsApi, dashboardApi, clientsApi, tasksApi, exportsApi } from '../services/api'
import { BarChart2, Download, FileText, Users, ShoppingCart, Package, Bot } from 'lucide-react'
import { downloadBlob } from '../services/download'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'

const COLORS = ['#16A6D4', '#4CAF32', '#7C6966', '#8EDFF7', '#94DF79', '#BCAEAB']

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState('sales')

  const { data: dashboardData } = useQuery({
    queryKey: ['dashboard', '90d'],
    queryFn: () => dashboardApi.getSummary('90d').then(r => r.data.data),
  })

  const { data: ordersData } = useQuery({
    queryKey: ['orders-all'],
    queryFn: () => ordersApi.list({ page_size: 200 }).then(r => r.data.data),
  })

  const { data: productsData } = useQuery({
    queryKey: ['products-all'],
    queryFn: () => productsApi.list({ page_size: 200 }).then(r => r.data.data),
  })

  const { data: clientsData } = useQuery({
    queryKey: ['clients-all'],
    queryFn: () => clientsApi.list({ page_size: 200 }).then(r => r.data.data),
  })

  const { data: tasksData } = useQuery({
    queryKey: ['tasks-all'],
    queryFn: () => tasksApi.list({ page_size: 200 }).then(r => r.data.data),
  })

  const revenueData = dashboardData?.revenue_chart?.data || []
  const orders = ordersData?.items || []
  const products = productsData?.items || []
  const clients = clientsData?.items || []
  const tasks = tasksData?.items || []

  const tabs = [
    { id: 'sales', label: 'გაყიდვები', icon: BarChart2, exportFn: () => downloadBlob(exportsApi.orders(), 'orders.xlsx') },
    { id: 'orders', label: 'შეკვეთები', icon: ShoppingCart, exportFn: () => downloadBlob(exportsApi.orders(), 'orders.xlsx') },
    { id: 'inventory', label: 'საწყობი', icon: Package, exportFn: () => downloadBlob(exportsApi.products(), 'products.xlsx') },
    { id: 'clients', label: 'კლიენტები', icon: Users, exportFn: () => downloadBlob(exportsApi.clients(), 'clients.xlsx') },
    { id: 'tasks', label: 'დავალებები', icon: Bot, exportFn: () => downloadBlob(exportsApi.tasks(), 'tasks.xlsx') },
  ]

  const currentTab = tabs.find(t => t.id === activeTab)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">რეპორტები</h1>
        {currentTab?.exportFn && (
          <button onClick={currentTab.exportFn} className="btn-primary flex items-center gap-2 text-sm">
            <Download size={16} /> Excel ექსპორტი
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
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">შემოსავლები (90 დღე)</h3>
            <button onClick={() => downloadBlob(exportsApi.orders(), 'orders.xlsx')} className="btn-secondary flex items-center gap-2 text-sm">
              <Download size={14} /> ექსპორტი
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
            <p className="text-gray-400 text-center py-56 dark:text-gray-500">მონაცემები არ არის</p>
          )}
          <div className="mt-4 grid grid-cols-3 gap-4">
            <div className="p-3 bg-blue-50 rounded-lg text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400">ჯამური შემოსავალი</p>
              <p className="text-xl font-bold text-blue-700">{revenueData.reduce((s: number, d: any) => s + (d.amount || 0), 0).toLocaleString()} ₾</p>
            </div>
            <div className="p-3 bg-green-50 rounded-lg text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400">საშუალო დღიური</p>
              <p className="text-xl font-bold text-green-700">{revenueData.length ? Math.round(revenueData.reduce((s: number, d: any) => s + (d.amount || 0), 0) / revenueData.length).toLocaleString() : 0} ₾</p>
            </div>
            <div className="p-3 bg-purple-50 rounded-lg text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400">დღეები</p>
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
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">შეკვეთების სტატისტიკა</h3>
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
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-4">სულ შეკვეთები: {orders.length}</p>
          </div>
          <div className="card">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">შეკვეთების განაწილება</h3>
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
              <h3 className="font-semibold text-gray-900 dark:text-gray-100">ნაშთების სტატუსი</h3>
              <button onClick={() => downloadBlob(exportsApi.products(), 'products.xlsx')} className="btn-secondary flex items-center gap-2 text-xs">
                <Download size={12} /> Excel
              </button>
            </div>
            <div className="space-y-3">
              {[
                { label: 'კარგი', status: 'good', color: 'bg-green-500' },
                { label: 'დაბალი', status: 'low', color: 'bg-yellow-500' },
                { label: 'კრიტიკული', status: 'critical', color: 'bg-red-500' },
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
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-4">სულ პროდუქტები: {products.length}</p>
          </div>
          <div className="card">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">პროდუქტების სია</h3>
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
                    <span className="font-medium">{p.sale_price} ₾</span>
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
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">კლიენტების სტატისტიკა</h3>
            <button onClick={() => downloadBlob(exportsApi.clients(), 'clients.xlsx')} className="btn-secondary flex items-center gap-2 text-xs">
              <Download size={12} /> Excel
            </button>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="p-4 bg-green-50 rounded-xl text-center">
              <p className="text-3xl font-bold text-green-700">{clients.filter((c: any) => c.status === 'active').length}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">აქტიური</p>
            </div>
            <div className="p-4 bg-gray-50 dark:bg-dark-100 rounded-xl text-center">
              <p className="text-3xl font-bold text-gray-700 dark:text-gray-300">{clients.filter((c: any) => c.status === 'potential').length}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">პოტენციური</p>
            </div>
            <div className="p-4 bg-red-50 rounded-xl text-center">
              <p className="text-3xl font-bold text-red-700">{clients.filter((c: any) => c.status === 'inactive').length}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">არააქტიური</p>
            </div>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">სულ კლიენტები: {clients.length}</p>
        </div>
      )}

      {/* Tasks Report */}
      {activeTab === 'tasks' && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">დავალებების სტატისტიკა</h3>
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
    </div>
  )
}