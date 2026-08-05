import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dashboardApi } from '../services/api'
import { TrendingUp, Users, ShoppingCart, AlertTriangle, Package, ArrowUp, ArrowDown } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from 'recharts'
import { StatusBadge, orderStatusMap } from '../components/ui/Badges'
import type { DashboardData } from '../types'

const COLORS = ['#16A6D4', '#4CAF32', '#7C6966', '#8EDFF7', '#94DF79', '#BCAEAB']

export default function DashboardPage() {
  const [period, setPeriod] = useState('30d')

  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', period],
    queryFn: () => dashboardApi.getSummary(period).then(r => r.data.data),
  })

  if (isLoading) return <div className="flex items-center justify-center h-64 text-gray-500 dark:text-gray-400 dark:text-gray-500">ჩატვირთვა...</div>

  const kpi = data?.kpi
  const revenueData: any[] = data?.revenue_chart?.data || []
  const orderDist: any[] = data?.order_status_distribution || []
  const alerts: any[] = data?.critical_alerts || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 dark:text-gray-200">მიმოხილვა</h1>
        <div className="flex gap-2 bg-white dark:bg-dark-200 rounded-lg border border-gray-200 dark:border-dark-50 p-1 dark:bg-dark-200 dark:border-dark-50">
          {[
            { key: '7d', label: '7 დღე' },
            { key: '30d', label: '30 დღე' },
            { key: '90d', label: '90 დღე' },
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
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          icon={TrendingUp}
          label="შემოსავალი"
          value={kpi?.total_revenue != null ? `${kpi.total_revenue.toLocaleString()} ₾` : '0 ₾'}
          change={kpi?.revenue_change}
          color="blue"
          hint={`ინვოისირებული შეკვეთები: ${data?.invoiced_orders_count ?? 0} / ${data?.total_orders_count ?? 0}`}
        />
        <KPICard icon={Users} label="აქტიური კლიენტები" value={String(kpi?.active_clients || 0)} color="green" />
        <KPICard icon={ShoppingCart} label="მიმდინარე შეკვეთები" value={String(kpi?.active_orders || 0)} color="gray" />
        <KPICard icon={AlertTriangle} label="დაგვიანებული დავალებები" value={String(kpi?.overdue_tasks || 0)} color="red" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Revenue Chart */}
        <div className="lg:col-span-2 card">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 dark:text-gray-200 mb-4">შემოსავლების დინამიკა</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={revenueData.filter((d: any) => d.amount > 0)}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#9CA3AF" />
              <YAxis tick={{ fontSize: 11 }} stroke="#9CA3AF" />
              <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb' }} />
              <Line type="monotone" dataKey="amount" stroke="#16A6D4" strokeWidth={3} dot={{ fill: '#16A6D4', r: 3 }} activeDot={{ fill: '#4CAF32', r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Order Distribution */}
        <div className="card">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 dark:text-gray-200 mb-4">შეკვეთების სტატუსები</h3>
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
                  <span>{orderStatusMap[d.status]?.label || d.status}</span>
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
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 dark:text-gray-200 mb-4">გაფრთხილებები</h3>
          <div className="space-y-2">
            {alerts.map((alert: any, i: number) => (
              <div key={i} className={`flex items-center gap-3 p-3 rounded-lg ${
                alert.severity === 'high' ? 'bg-red-50 text-red-800' : 'bg-yellow-50 text-yellow-800'
              }`}>
                <AlertTriangle size={18} />
                <div>
                  <p className="font-medium text-sm">{alert.title}</p>
                  <p className="text-xs opacity-75">{alert.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Low stock products */}
      {kpi?.low_stock_products > 0 && (
        <div className="card bg-brandgray-50 dark:bg-dark-100 border-brandgray-200 dark:border-dark-50">
          <div className="flex items-center gap-3">
            <Package size={20} className="text-primary-600" />
            <div>
              <p className="font-medium text-brandgray-800 dark:text-gray-200">{kpi.low_stock_products} პროდუქტს აქვს დაბალი ნაშთი</p>
              <p className="text-sm text-primary-700">გადადით საწყობში შესავსებად</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function KPICard({ icon: Icon, label, value, change, color, hint }: { icon: any; label: string; value: string; change?: number; color: string; hint?: string }) {
  const colorMap: Record<string, string> = {
    blue: 'bg-primary-50 text-primary-700',
    green: 'bg-accent-50 text-accent-700',
    red: 'bg-red-50 text-red-600',
    gray: 'bg-brandgray-100 dark:bg-dark-100 text-brandgray-700 dark:text-gray-300',
  }

  return (
    <div className="card flex items-center gap-4 dark:bg-dark-200 dark:border-dark-50">
      <div className={`p-3 rounded-xl ${colorMap[color] || colorMap.blue}`}>
        <Icon size={24} />
      </div>
      <div className="flex-1">
        <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 dark:text-gray-200">{value}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500">{label}</p>
        {change !== undefined && (
          <span className={`text-xs flex items-center gap-1 mt-0.5 ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {change >= 0 ? <ArrowUp size={12} /> : <ArrowDown size={12} />}
            {Math.abs(change).toFixed(1)}%
          </span>
        )}
        {hint && (
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1" title="შემოსავალი ითვლება მხოლოდ გაცემული (issued) ინვოისებიდან">{hint}</p>
        )}
      </div>
    </div>
  )
}