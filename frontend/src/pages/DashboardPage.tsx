import { Link , useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dashboardApi, usersApi, warehousesApi, salesOrgApi } from '../services/api'
import { TrendingUp, Users, ShoppingCart, AlertTriangle, Package, ArrowUp, ArrowDown, Wallet, Clock , ArrowUpRight, LayoutGrid, Info, X, Factory, Car, Wrench, CheckSquare, Gauge, Truck } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, AreaChart, Area } from 'recharts'
import { StatusBadge, orderStatusMap } from '../components/ui/Badges'
import type { DashboardData } from '../types'
import Modal from '../components/ui/Modal'
// Unified currency format: "590 ₾"
const money = (v: number | string | null | undefined) =>
  new Intl.NumberFormat('ka-GE', { style: 'currency', currency: 'GEL' }).format(Number(v || 0))

const COLORS = ['#16A6D4', '#4CAF32', '#7C6966', '#8EDFF7', '#94DF79', '#BCAEAB']

// All known KPI keys (used when a role view has no explicit list)
const KPI_ORDER = ['revenue', 'orders', 'clients', 'tasks', 'pipeline', 'leads', 'cashflow', 'receivables', 'payables', 'unpaid_invoices', 'low_stock', 'stock_value', 'inventory', 'delayed_shipments', 'production_backlog', 'fleet_unavailable', 'maintenance_critical', 'approvals_pending', 'otif_rate', 'tms_dispatched', 'tms_active', 'tms_delayed']

// KPI keys → icons/colors for the role view rendering
const KPI_META: Record<string, { icon: any; color: 'blue' | 'green' | 'red' | 'gray'; to?: string }> = {
  revenue: { icon: TrendingUp, color: 'blue', to: '/sales' },
  orders: { icon: ShoppingCart, color: 'green', to: '/sales' },
  clients: { icon: Users, color: 'gray', to: '/crm' },
  tasks: { icon: Clock, color: 'red', to: '/tasks' },
  pipeline: { icon: TrendingUp, color: 'blue', to: '/crm' },
  leads: { icon: Users, color: 'green', to: '/crm' },
  cashflow: { icon: Wallet, color: 'green' },
  receivables: { icon: Wallet, color: 'red' },
  payables: { icon: Wallet, color: 'gray' },
  unpaid_invoices: { icon: AlertTriangle, color: 'red' },
  low_stock: { icon: Package, color: 'red', to: '/warehouse' },
  stock_value: { icon: Package, color: 'blue', to: '/warehouse' },
  inventory: { icon: Package, color: 'gray', to: '/warehouse' },
  delayed_shipments: { icon: AlertTriangle, color: 'red', to: '/orders' },
  production_backlog: { icon: Factory, color: 'red', to: '/production' },
  fleet_unavailable: { icon: Car, color: 'red', to: '/fleet' },
  maintenance_critical: { icon: Wrench, color: 'red', to: '/maintenance' },
  approvals_pending: { icon: CheckSquare, color: 'blue' },
  otif_rate: { icon: Gauge, color: 'green', to: '/orders' },
  tms_dispatched: { icon: Truck, color: 'blue', to: '/fleet/tms' },
  tms_active: { icon: Truck, color: 'green', to: '/fleet/tms' },
  tms_delayed: { icon: Truck, color: 'red', to: '/fleet/tms' },
}

export default function DashboardPage() {
  const { t } = useTranslation()
  const [period, setPeriod] = useState('30d')
  const [ownerId, setOwnerId] = useState('')
  const [warehouseId, setWarehouseId] = useState('')
  const [teamId, setTeamId] = useState('')
  const [showCustomize, setShowCustomize] = useState(false)
  const [activeView, setActiveView] = useState<string | null>(null)
  const [drillKpi, setDrillKpi] = useState<string | null>(null)
  const [kpiTooltip, setKpiTooltip] = useState<string | null>(null)
  const [refreshFrozen, setRefreshFrozen] = useState(false)
  const [hiddenKpis, setHiddenKpis] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('bos_hidden_kpis') || '[]') } catch { return [] }
  })

  // Role views (from backend) — auto-select default on first load
  const { data: roleViewsData } = useQuery({
    queryKey: ['dashboard-role-views'],
    queryFn: () => dashboardApi.getRoleViews().then(r => r.data.data),
  })
  const { data: kpiDefs } = useQuery({
    queryKey: ['dashboard-kpi-defs'],
    queryFn: () => dashboardApi.getKpiDefinitions().then(r => r.data.data),
  })
  const { data: drillData, isLoading: drillLoading } = useQuery({
    queryKey: ['dashboard-drill', drillKpi, period, ownerId, warehouseId],
    queryFn: () => drillKpi ? dashboardApi.getKpiDrillDown(drillKpi, 15, { period, warehouse_id: warehouseId || undefined, owner_id: ownerId || undefined }).then(r => r.data.data) : null,
    enabled: !!drillKpi,
  })

  // saved layout per view — server-side (authoritative) + localStorage (fast-path cache)
  const [savedLayouts, setSavedLayouts] = useState<Record<string, string[]>>(() => {
    try { return JSON.parse(localStorage.getItem('bos_dash_layouts') || '{}') } catch { return {} }
  })
  const persistLayout = (viewKey: string, kpis: string[]) => {
    const next = { ...savedLayouts, [viewKey]: kpis }
    setSavedLayouts(next)
    localStorage.setItem('bos_dash_layouts', JSON.stringify(next))
    // REQ-DASH layout contract: persist on server too (role-change-safe)
    dashboardApi.putLayout(next).catch(() => {})
  }

  // Seed from server layout on first load (overrides any stale localStorage)
  const { data: serverLayoutData } = useQuery({
    queryKey: ['dashboard-server-layout'],
    queryFn: () => dashboardApi.getLayout().then(r => r.data.data),
    staleTime: 60_000,
  })
  useEffect(() => {
    const sl = (serverLayoutData as any)?.layouts
    if (sl && typeof sl === 'object' && Object.keys(sl).length) {
      try {
        const cur = JSON.parse(localStorage.getItem('bos_dash_layouts') || '{}')
        const merged = { ...cur, ...sl }
        localStorage.setItem('bos_dash_layouts', JSON.stringify(merged))
      } catch { /* ignore */ }
    }
  }, [serverLayoutData])

  const effectiveView = activeView ?? roleViewsData?.default_view ?? 'director'
  const roleView = roleViewsData?.views?.find((v: any) => v.key === effectiveView) || roleViewsData?.views?.[0]
  // For this view: saved layout overrides, else backend defaults — but always
  // merge in any new canonical KPI codes that arrived after the layout was saved,
  // so newly added KPIs (e.g. TMS) surface without resetting user layout.
  const _baseKpis = (roleView?.kpis || KPI_ORDER) as string[]
  const _saved = savedLayouts[effectiveView] as string[] | undefined
  const viewKpis = (_saved?.length ? _saved : _baseKpis).slice()
  for (const k of _baseKpis) {
    if (!viewKpis.includes(k)) viewKpis.push(k)
  }

  const toggleKpi = (key: string) => {
    setHiddenKpis(prev => {
      const next = prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
      localStorage.setItem('bos_hidden_kpis', JSON.stringify(next))
      return next
    })
  }

  // Per-view layout toggle — persists which KPIs a role view shows
  const toggleViewKpi = (key: string) => {
    const base = roleView?.kpis || KPI_ORDER
    const current = savedLayouts[effectiveView]?.length ? savedLayouts[effectiveView] : base
    const next = current.includes(key)
      ? current.filter((x: string) => x !== key)
      : [...base, key]
    persistLayout(effectiveView, next)
  }

  const { data: users } = useQuery({
    queryKey: ['dashboard-users'],
    queryFn: () => usersApi.list({ page_size: 100 }).then(r => r.data.data),
  })
  const { data: warehouses } = useQuery({
    queryKey: ['dashboard-warehouses'],
    queryFn: () => warehousesApi.list().then(r => r.data.data),
  })
  const { data: teams } = useQuery({
    queryKey: ['dashboard-teams'],
    queryFn: () => salesOrgApi.listTeams({ page_size: 100 }).then(r => r.data.data),
  })

  const { data, isLoading, isError, dataUpdatedAt, error } = useQuery({
    queryKey: ['dashboard', period, ownerId, warehouseId, teamId],
    queryFn: () => dashboardApi.getSummary(period, ownerId || undefined, warehouseId || undefined, teamId || undefined).then(r => r.data.data),
    refetchInterval: refreshFrozen ? false : 60_000,  // silent auto-refresh, frozen while paused
    retry: 1,
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
      {/* Header row 1: title + role views */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 dark:text-gray-200">{t('მიმოხილვა')}</h1>
        {roleViewsData?.views && (
          <div className="flex gap-1 bg-white dark:bg-dark-200 rounded-lg border border-gray-200 dark:border-dark-50 p-1">
            {roleViewsData.views.map((v: any) => (
              <button
                key={v.key}
                onClick={() => {
                  setActiveView(v.key)
                  // switch to this layout's saved KPIs when user picks a view
                  if (savedLayouts[v.key]?.length) {
                    setHiddenKpis(savedLayouts[v.key].filter((k: string) => !roleViewsData.views.every((vv: any) => !vv.kpis.includes(k))))
                  }
                }}
                title={`${v.label} — ${v.modules.join(', ')}`}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${effectiveView === v.key ? 'bg-primary-600 text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-100'}`}
              >
                {v.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Header row 2: snapshot control + filters + customize */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Snapshot control: pause/resume auto-refresh + last update time */}
        <div className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500">
          <span>{t('ავტო-განახლება')}</span>
          <button
            onClick={() => setRefreshFrozen(f => !f)}
            title={refreshFrozen ? t('ავტო-განახლების გაგრძელება') : t('ავტო-განახლების გაჩერება')}
            className={`w-8 h-4.5 rounded-full transition-colors relative ${refreshFrozen ? 'bg-gray-300 dark:bg-dark-50' : 'bg-primary-600'}`}
            style={{ height: 18 }}
          >
            <span className={`absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white shadow transition-all ${refreshFrozen ? 'left-0.5' : 'left-4'}`} style={{ top: 2 }} />
          </button>
          {dataUpdatedAt > 0 && (
            <span title={t('ბოლო განახლება')}>
              {new Date(dataUpdatedAt).toLocaleTimeString('ka-GE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          {/* Freshness / fault states (REQ-DASH-03):
              1. fetch error → show a clear red badge (data is NOT shown as zero)
              2. > 5 min since last successful refresh → stale amber badge
              3. otherwise → nothing (silent live dashboard) */}
          {isError ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
              {t('მონაცემების დატვირთვა ვერ მოხერხდა')}
              {dataUpdatedAt > 0 && (
                <span title={t('ბოლო წარმატებული განახლება')}>
                  · {new Date(dataUpdatedAt).toLocaleTimeString('ka-GE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              )}
              <span title={String((error as any)?.message || '')}>?</span>
            </span>
          ) : (() => {
            const luRaw = data?.kpi?.last_updated_at
            if (!luRaw) return null
            // backend sends naive UTC — append Z so the client parses it as UTC
            const lu = new Date(luRaw.endsWith('Z') || luRaw.includes('+') ? luRaw : luRaw + 'Z')
            if (Number.isNaN(lu.getTime())) return null
            const ageSec = (Date.now() - lu.getTime()) / 1000
            if (ageSec <= 300) return null   // fresh within 5 min (60s auto-refresh → normally never shown)
            return (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                {t('მონაცემები მოძველდა')}
              </span>
            )
          })()}
        </div>
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
        {/* REQ-DASH-04: warehouse filter narrows order KPIs */}
        <select
          value={warehouseId}
          onChange={(e) => setWarehouseId(e.target.value)}
          className="input h-9 w-auto text-sm"
          aria-label={t('საწყობის ფილტრი')}
        >
          <option value="">{t('ყველა საწყობი')}</option>
          {(warehouses || []).map((w: any) => (
            <option key={w.id} value={w.id}>{w.name || w.code || w.id.slice(0, 8)}</option>
          ))}
        </select>
        {/* REQ-DASH-04: team filter — narrows order/task KPIs to team members */}
        <select
          value={teamId}
          onChange={(e) => setTeamId(e.target.value)}
          className="input h-9 w-auto text-sm"
          aria-label={t('გუნდის ფილტრი')}
        >
          <option value="">{t('ყველა გუნდი')}</option>
          {((teams as any)?.items || teams || []).map((tm: any) => (
            <option key={tm.id} value={tm.id}>{tm.name || tm.id.slice(0, 8)}</option>
          ))}
        </select>
        {/* REQ-DASH-03: period start/end frame */}
        <span className="text-xs text-gray-500 dark:text-gray-400 tabular-nums" title={t('გაანალიზებული პერიოდი')}>
          {(() => {
            const days = { '7d': 7, '30d': 30, '90d': 90 }[period] || 30
            const end = new Date()
            const start = new Date(end.getTime() - days * 24 * 3600 * 1000)
            const fmt = (d: Date) => d.toISOString().slice(0, 10)
            return `${fmt(start)} – ${fmt(end)}`
          })()}
        </span>
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

      {/* Customize panel — per-view layout */}
      {showCustomize && (
        <div className="card p-4">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
            {t('KPI ბარათების მორგება')} — {roleView?.label || effectiveView}
          </h3>
          <p className="text-xs text-gray-400 dark:text-gray-500 mb-3">
            {t('ჩართეთ / გამორთეთ ბარათები — შეინახება ამ ხედისთვის (მხოლოდ თქვენს ბრაუზერში)')}
          </p>
          <div className="flex flex-wrap gap-2">
            {(roleView?.kpis || KPI_ORDER).map((k: string) => {
              const meta = KPI_META[k]
              const def = kpiDefs?.find((d: any) => d.key === k)
              const isOn = viewKpis.includes(k)
              return (
                <button
                  key={k}
                  onClick={() => toggleViewKpi(k)}
                  title={def?.formula}
                  className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${isOn ? 'bg-primary-50 text-primary-700 border-primary-200' : 'bg-gray-100 dark:bg-dark-100 text-gray-400 line-through'}`}
                >
                  {meta?.icon ? (() => { const Ico = meta.icon; return <Ico size={13} className="inline mr-1" /> })() : null}
                  {def?.label || k}
                </button>
              )
            })}
          </div>
          <button
            onClick={() => persistLayout(effectiveView, roleView?.kpis || KPI_ORDER)}
            className="mt-3 text-xs px-3 py-1.5 rounded-lg border border-gray-200 dark:border-dark-50 text-gray-500 dark:text-gray-400 hover:text-primary-600 transition-colors"
          >
            {t('ნაგულისხმები აღდგენა')}
          </button>
        </div>
      )}

      {/* KPI Cards — role view driven, click = drill-down, ? = definition */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {viewKpis.map((k: string) => {
          if (hiddenKpis.includes(k)) return null
          const meta = KPI_META[k]
          if (!meta) return null
          const def = kpiDefs?.find((d: any) => d.key === k)
          const val = (() => {
            switch (k) {
              case 'revenue': return kpi?.total_revenue != null ? money(kpi.total_revenue) : money(0)
              case 'orders': return String(kpi?.active_orders || 0)
              case 'clients': return String(kpi?.active_clients || 0)
              case 'tasks': return String(kpi?.overdue_tasks || 0)
              case 'pipeline': return kpi?.pipeline_value != null ? money(kpi.pipeline_value) : money(0)
              case 'leads': return String(kpi?.open_leads || 0)
              case 'receivables': return kpi?.receivables_outstanding != null ? money(kpi.receivables_outstanding) : money(0)
              case 'payables': return kpi?.payables_outstanding != null ? money(kpi.payables_outstanding) : money(0)
              case 'unpaid_invoices': return kpi?.unpaid_invoices != null ? money(kpi.unpaid_invoices) : money(0)
              case 'cashflow': return kpi?.cashflow_30d != null ? money(kpi.cashflow_30d) : money(0)
              case 'low_stock': return String(kpi?.low_stock_products || 0)
              case 'stock_value': return kpi?.stock_value != null ? money(kpi.stock_value) : money(0)
              case 'inventory': return kpi?.inventory_units != null ? String(new Intl.NumberFormat('ka-GE').format(Math.round(kpi.inventory_units))) : '0'
              case 'delayed_shipments': return String(kpi?.delayed_shipments || 0)
              case 'production_backlog': return String(kpi?.production_backlog || 0)
              case 'fleet_unavailable': return String(kpi?.fleet_unavailable || 0)
              case 'maintenance_critical': return String(kpi?.maintenance_critical || 0)
              case 'approvals_pending': return String(kpi?.approvals_pending || 0)
              case 'otif_rate': return kpi?.otif_rate != null ? `${kpi.otif_rate}%` : 'N/A'
              case 'tms_dispatched': return String(kpi?.tms_dispatched || 0)
              case 'tms_active': return String(kpi?.tms_active || 0)
              case 'tms_delayed': return String(kpi?.tms_delayed || 0)
              default: return '—'
            }
          })()
          return (
            <KPICard
              key={k}
              icon={meta.icon}
              label={t(def?.label || k)}
              value={val}
              change={(() => {
                switch (k) {
                  case 'revenue': return kpi?.revenue_change ?? null
                  case 'orders': return kpi?.orders_change ?? null
                  case 'clients': return kpi?.clients_change ?? null
                  case 'tasks': return kpi?.tasks_change ?? null
                  case 'cashflow': return kpi?.cashflow_change ?? null
                  default: return undefined
                }
              })()}
              color={meta.color}
              to={meta.to}
              onDrill={() => setDrillKpi(k)}
              infoTitle={def ? `${def.label}: ${def.formula}` : undefined}
              infoSource={def?.source}
            />
          )
        })}
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

      {/* KPI Drill-down modal */}
      <Modal open={!!drillKpi} onClose={() => setDrillKpi(null)} title={drillData?.title || t('დეტალები')}>
        <div className="space-y-3 max-h-[60vh] overflow-y-auto">
          {drillLoading && <p className="text-sm text-gray-500">{t('ჩატვირთვა...')}</p>}
          {drillData && (
            <>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">{t('ჯამი')}</span>
                <span className="font-bold text-gray-900 dark:text-gray-100">{drillData.total}</span>
              </div>
              {drillData.rows.length === 0 ? (
                <p className="text-sm text-gray-400 py-6 text-center">{t('ჩანაწერები არ არის')}</p>
              ) : (
                <table className="w-full text-sm">
                  <tbody className="divide-y dark:divide-dark-50">
                    {drillData.rows.slice(0, 15).map((r: any, i: number) => (
                      <tr key={i}>
                        <td className="py-2 pr-4 text-gray-700 dark:text-gray-300">{r.label}</td>
                        <td className="py-2 pr-4 text-gray-500">{r.date}</td>
                        {r.status && <td className="py-2"><span className="badge">{r.status}</span></td>}
                        <td className="py-2 text-right font-medium text-gray-900 dark:text-gray-100">{r.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      </Modal>
    </div>
  )
}

function KPICard({ icon: Icon, label, value, change, color, hint, to, onDrill, infoTitle, infoSource }: { icon: any; label: string; value: string; change?: number | null; color: string; hint?: string; to?: string; onDrill?: () => void; infoTitle?: string; infoSource?: string }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const colorMap: Record<string, string> = {
    blue: 'bg-primary-50 text-primary-700',
    green: 'bg-accent-50 text-accent-700',
    red: 'bg-red-50 text-red-600',
    gray: 'bg-brandgray-100 dark:bg-dark-100 text-brandgray-700 dark:text-gray-300',
  }

  const content = (
    <div className="card relative flex items-center gap-4 dark:bg-dark-200 dark:border-dark-50 min-h-[140px]">
      {infoSource && (
        <div className="absolute top-2 right-2 flex items-center gap-1">
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); }}
            title={infoTitle}
            className="text-gray-300 dark:text-gray-600 hover:text-primary-500 transition-colors cursor-help"
          >
            <Info size={14} />
          </button>
        </div>
      )}
      <div className={`p-3 rounded-xl shrink-0 ${colorMap[color] || colorMap.blue}`}>
        <Icon size={24} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 dark:text-gray-200 truncate">{value}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500 truncate">{t(label)}</p>
        {change !== null && change !== undefined && (
          <span className={`text-xs flex items-center gap-1 mt-0.5 ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {change >= 0 ? <ArrowUp size={12} /> : <ArrowDown size={12} />}
            {Math.abs(change).toFixed(1)}%
          </span>
        )}
        {change === null && (
          <span className="text-xs text-gray-400 dark:text-gray-500 mt-0.5" title={t('წინა პერიოდი ცარიელია, შედარება ვერ გამოითვლება')}>
            {t('შედარება ვერ ითვლება')}
          </span>
        )}
        {hint && (
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1 truncate" title={t('შემოსავალი ითვლება მხოლოდ გაცემული (issued) ინვოისებიდან')}>{hint}</p>
        )}
        {infoSource && (
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1 truncate" title={infoSource}>
            {infoSource}
          </p>
        )}
      </div>
      {onDrill && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onDrill() }}
          title={t('დეტალები (drill-down)')}
          className="absolute bottom-2 right-2 p-1.5 rounded-lg bg-gray-100 dark:bg-dark-100 text-gray-500 dark:text-gray-400 hover:bg-primary-50 hover:text-primary-600 transition-colors"
        >
          <ArrowUpRight size={14} />
        </button>
      )}
      {!onDrill && to && (
        <ArrowUpRight size={16} className="text-gray-300 dark:text-gray-600 transition-colors group-hover:text-primary-500 shrink-0" />
      )}
    </div>
  )

  return to && !onDrill ? (
    <button
      type="button"
      onClick={() => navigate(to)}
      title={t('დეტალურად ნახვა')}
      className="group text-left transition-transform hover:-translate-y-0.5"
    >
      {content}
    </button>
  ) : (
    <div className="group transition-transform hover:-translate-y-0.5 cursor-pointer" onClick={onDrill}>
      {content}
    </div>
  )
}