// frontend/src/components/layout/Sidebar.tsx
import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Users, ShoppingCart, Package,
  CheckSquare, Bot, Settings, X, ReceiptText, Building2, WalletCards, Landmark, BookOpen, FileText, TrendingUp, Scale, Car, ChevronDown, ChevronRight, DollarSign, Banknote, HandCoins, Wrench, BarChart3, Target, Coins, Network, CalendarClock, CalendarRange, Loader2, Star, Factory, FolderKanban, ChefHat, LifeBuoy, Boxes, Store, LayoutGrid, Settings2, BadgeCheck, Zap, CreditCard, Plug, Shield, RefreshCw, Tags, Globe, TrendingDown, BookOpenCheck
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { modulesApi } from '../../services/api'
import { useAuthStore } from '../../store/authStore'
import { readRecent } from '../../hooks/useRecent'
import type { CompanyModuleStatus } from '../../types'

// ── Icon map ─────────────────────────────────────────────────────────
const iconMap: Record<string, any> = {
  LayoutDashboard, Users, ShoppingCart, Package,
  CheckSquare, Bot, Settings, ReceiptText, Building2, WalletCards,
  Landmark, BookOpen, FileText, TrendingUp, Scale, Car,
  DollarSign, Banknote, HandCoins, Wrench, BarChart3, Target,
  Coins, Network, CalendarClock, CalendarRange,
  Factory, FolderKanban, ChefHat, LifeBuoy, Boxes, Store,
  LayoutGrid, Settings2, BadgeCheck, Zap, CreditCard, Plug, Shield,
  RefreshCw, Tags, Globe, TrendingDown, BookOpenCheck,
}

// ── Sidebar structure (user-defined) ──────────────────────────────────
// Direct items: shown as top-level links.
// Groups: collapsible sections keyed by route prefixes.
// Everything not listed falls into the "სხვა" (Other) group.

interface NavItem { to: string; icon: any; label: string }

const DIRECT_PREFIXES = [
  '/dashboard', '/crm', '/production', '/maintenance', '/hr', '/fleet',
  '/helpdesk', '/projects', '/tasks', '/documents', '/reports', '/ai', '/settings',
]

const GROUP_DEFS: { id: string; label: string; icon: any; prefixes: string[] }[] = [
  { id: 'sales', label: 'გაყიდვები', icon: ShoppingCart, prefixes: ['/clients', '/orders', '/invoices', '/quotations', '/price-lists', '/sales-teams', '/email-tracking', '/subscriptions', '/customer-portal', '/ecommerce', '/pos'] },
  { id: 'purchases', label: 'შესყიდვები', icon: Building2, prefixes: ['/purchases', '/procurement', '/suppliers', '/supplier-finance', '/vendor-portal'] },
  { id: 'warehouse', label: 'საწყობი', icon: Package, prefixes: ['/inventory', '/wms', '/inventory-valuation'] },
  { id: 'finance', label: 'ფინანსები', icon: DollarSign, prefixes: ['/cash', '/banking', '/banking-rules', '/currency', '/customer-finance', '/expenses', '/assets'] },
  { id: 'accounting', label: 'ბუღალტერია', icon: BookOpen, prefixes: ['/chart-of-accounts', '/journal-entries', '/trial-balance', '/profit-loss', '/balance-sheet', '/srs', '/budgeting', '/analytic-accounting', '/deferred', '/accounting-periods', '/gl-recurring', '/gl-exchange-differences', '/gl-consolidated', '/accounting-controls'] },
  { id: 'other', label: 'სხვა', icon: Settings, prefixes: ['/automations', '/payments', '/email-calendar', '/integrations', '/security', '/kitchen', '/studio', '/platform-studio', '/marketplace', '/field-service', '/quality'] },
]

// User-defined order: group ids and direct route prefixes interleaved.
// მიმოხილვა, რჩეულები და ბოლო ნანახი ყოველთვის ზევით რჩება.
const NAV_ORDER: (string)[] = [
  'sales', 'purchases', 'warehouse',
  'maintenance', '/production',
  'finance', 'accounting',
  '/crm', '/hr', '/projects', '/tasks', '/fleet', '/documents', '/helpdesk',
  '/reports', '/ai',
  'other',
  '/settings',
]

// Maintenance sub-groups (collapsible under the Maintenance group)
// Simple one-level list: Maintenance → sub-item. Each maps to /maintenance?tab=<key>
const MAINTENANCE_SUBGROUPS: { key: string; label: string }[] = [
  { key: 'requests', label: 'მოთხოვნები' },
  { key: 'orders', label: 'სამუშაო დავალებები' },
  { key: 'plans', label: 'მოვლის გეგმები' },
  { key: 'calendar', label: 'კალენდარი' },
  { key: 'assets', label: 'აქტივები' },
  { key: 'locations', label: 'მდებარეობები' },
  { key: 'meters', label: 'მრიცხველები' },
  { key: 'technicians', label: 'ტექნიკოსები და გუნდები' },
  { key: 'contractors', label: 'კონტრაქტორები და SLA' },
  { key: 'parts', label: 'ნაწილები და მასალები' },
  { key: 'costs', label: 'ხარჯები' },
  { key: 'analytics', label: 'ანალიტიკა' },
  { key: 'config', label: 'კონფიგურაცია' },
]

// ── Sub-components ──────────────────────────────────────────────────

function NavLinkItem({ item, onClose, depth = 0, isFav, onToggleFav, exact = false }: { item: NavItem; onClose: () => void; depth?: number; isFav?: boolean; onToggleFav?: (to: string) => void; exact?: boolean }) {
  const { t } = useTranslation()
  const { search } = useLocation()
  const targetSearch = item.to.includes('?') ? '?' + item.to.split('?')[1] : ''
  return (
    <NavLink
      to={item.to}
      onClick={onClose}
      className={({ isActive }) => {
        // For query-param links (?tab=) require an exact match so only the
        // active sub-item is highlighted — not every /maintenance link.
        const active = exact ? isActive && search === targetSearch : isActive
        return `group relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all
        ${active 
          ? 'bg-primary-50 text-primary-800 shadow-sm ring-1 ring-primary-100 dark:bg-primary-900/40 dark:text-primary-200 dark:ring-primary-800/50' 
          : 'text-brandgray-600 hover:bg-brandgray-50 hover:text-brandgray-900 dark:text-gray-400 dark:hover:bg-dark-100 dark:hover:text-gray-200'
        }`
      }}
    >
      <item.icon size={depth === 0 ? 20 : 17} className="transition-transform group-hover:scale-105 shrink-0" />
      <span className="truncate flex-1">{t(item.label)}</span>
      {onToggleFav && (
        <button
          type="button"
          title={isFav ? t('რჩეულებიდან ამოღება') : t('რჩეულებში დამატება')}
          aria-label={isFav ? t('რჩეულებიდან ამოღება') : t('რჩეულებში დამატება')}
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggleFav(item.to) }}
          className={`shrink-0 rounded-md p-0.5 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-amber-100 dark:hover:bg-amber-900/40 ${isFav ? 'opacity-100' : ''}`}
        >
          <Star size={14} className={isFav ? 'fill-amber-400 text-amber-400' : 'text-brandgray-400 dark:text-gray-500'} />
        </button>
      )}
    </NavLink>
  )
}

function CollapsibleGroup({
  icon: Icon,
  label,
  open,
  onToggle,
  children,
  depth = 0,
}: {
  icon: any
  label: string
  open: boolean
  onToggle: () => void
  children: React.ReactNode
  depth?: number
}) {
  const { t } = useTranslation()
  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className={`w-full flex items-center gap-3 rounded-lg text-sm font-semibold transition-colors
          ${depth === 0
            ? 'px-3 py-2 text-brandgray-700 hover:bg-brandgray-50 hover:text-brandgray-900 dark:text-gray-300 dark:hover:bg-dark-100 dark:hover:text-gray-100'
            : 'px-2 py-1.5 text-[13px] text-brandgray-500 hover:bg-brandgray-50 hover:text-brandgray-800 dark:text-gray-400 dark:hover:bg-dark-100 dark:hover:text-gray-200'
          }`}
      >
        <Icon size={depth === 0 ? 18 : 14} className={`shrink-0 ${depth === 0 ? 'text-primary-700 dark:text-primary-400' : 'text-brandgray-400 dark:text-gray-500'}`} />
        <span className="flex-1 text-left truncate">{t(label)}</span>
        <span className={`shrink-0 transition-transform duration-150 ${open ? 'rotate-90' : ''}`}>
          <ChevronRight size={14} className="text-brandgray-400 dark:text-gray-500" />
        </span>
      </button>
      {open && (
        <div className={`${depth === 0 ? 'ml-3 pl-3 border-l border-brandgray-200 dark:border-dark-50' : 'ml-2 pl-2'} space-y-0.5 mt-0.5`}>
          {children}
        </div>
      )}
    </div>
  )
}

// ── Main Component ──────────────────────────────────────────────────

interface SidebarProps {
  open: boolean
  onClose: () => void
  onChatToggle?: () => void
}

export default function Sidebar({ open, onClose, onChatToggle }: SidebarProps) {
  const { t } = useTranslation()
  const { user } = useAuthStore()
  const { pathname } = useLocation()
  const [modules, setModules] = useState<CompanyModuleStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [openGroups, setOpenGroups] = useState<Set<string>>(() => new Set())
  const [favorites, setFavorites] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('bos_favs') || '[]')
    } catch {
      return []
    }
  })

  const toggleFav = (to: string) => {
    setFavorites((current) => {
      const next = current.includes(to)
        ? current.filter((p) => p !== to)
        : [...current, to]
      localStorage.setItem('bos_favs', JSON.stringify(next))
      return next
    })
  }

  const toggleGroup = (groupId: string) => {
    setOpenGroups((current) => {
      const next = new Set(current)
      if (next.has(groupId)) next.delete(groupId)
      else next.add(groupId)
      return next
    })
  }

  useEffect(() => {
    let cancelled = false
    modulesApi.getCompanyModules()
      .then((res) => {
        if (!cancelled) {
          setModules(res.data.data || [])
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <aside className={`fixed md:static inset-y-0 left-0 z-50
        w-64 bg-white border-r border-brandgray-100 flex flex-col shadow-[4px_0_24px_-20px_rgba(16,95,125,0.45)]
        dark:bg-dark-200 dark:border-dark-50
        ${open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        transform transition-transform duration-200`}>
        <div className="relative h-20 flex items-center justify-between px-5 border-b border-brandgray-100 dark:border-dark-50">
          <div className="absolute inset-x-0 top-0 h-1 brand-topline" />
          <div>
            <div className="text-lg font-bold tracking-tight text-brandgray-800 dark:text-gray-100">Business OS</div>
            <div className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-primary-700 dark:text-primary-400">{t('ბიზნესის მართვა')}</div>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center text-brandgray-400">
          <Loader2 size={20} className="animate-spin mr-2" />
          <span className="text-sm">{t('იტვირთება...')}</span>
        </div>
      </aside>
    )
  }

  // Build nav items from enabled modules + role-based access
  const enabledModules = modules.filter((m) => m.enabled && m.module.is_active)

  const canAccess = (moduleCode: string): boolean => {
    if (!user) return false
    if (user.role === 'admin' || user.role === 'owner') return true
    const status = enabledModules.find((m) => m.module.code === moduleCode)
    if (!status) return false
    return status.permissions.some(
      (p) => p.role === user.role && p.can_access,
    )
  }

  const allItems: NavItem[] = enabledModules
    .filter((m) => canAccess(m.module.code))
    .map((m) => ({
      to: m.module.route || `/${m.module.code}`,
      icon: iconMap[m.module.icon || 'FileText'] || FileText,
      label: m.module.name,
    }))

  // Direct items: top-level links (dashboard, crm, production, maintenance, hr, fleet, helpdesk, projects, documents, reports, ai, settings)
  const directItems = allItems
    .filter((i) =>
      DIRECT_PREFIXES.some((p) => i.to === p || i.to.startsWith(p + '/')),
    )
    .map((i) => (i.to === '/dashboard' ? { ...i, label: 'მიმოხილვა' } : i))

  // მიმოხილვა (dashboard) — rendered separately, always above "ბოლო ნანახი"
  const overviewItem = directItems.find((i) => i.to === '/dashboard')

  // Grouped items by route prefix
  const groupedItems = GROUP_DEFS.map((group) => ({
    ...group,
    items: allItems.filter((i) =>
      group.prefixes.some((p) => i.to === p || i.to.startsWith(p + '/')),
    ),
  })).filter((g) => g.items.length > 0)

  // Favorites: resolve stored routes to nav items (only those still accessible)
  const favoriteItems: NavItem[] = favorites
    .map((favTo) => allItems.find((i) => i.to === favTo))
    .filter((i): i is NavItem => i !== undefined)

  // Recent: last visited module routes (excluding dashboard itself)
  const recentItems: NavItem[] = readRecent()
    .filter((r) => r !== '/dashboard')
    .map((r) => allItems.find((i) => i.to === r))
    .filter((i): i is NavItem => i !== undefined)

  return (
    <>
      {open && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={onClose}
        />
      )}
      
      <aside className={`
        fixed md:static inset-y-0 left-0 z-50
        w-64 bg-white border-r border-brandgray-100 flex flex-col shadow-[4px_0_24px_-20px_rgba(16,95,125,0.45)]
        transform transition-transform duration-200
        dark:bg-dark-200 dark:border-dark-50
        ${open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
      `}>
        {/* Logo */}
        <div className="relative h-20 flex items-center justify-between px-5 border-b border-brandgray-100 dark:border-dark-50">
          <div className="absolute inset-x-0 top-0 h-1 brand-topline" />
          <div>
            <div className="text-lg font-bold tracking-tight text-brandgray-800 dark:text-gray-100">Business OS</div>
            <div className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-primary-700 dark:text-primary-400">{t('ბიზნესის მართვა')}</div>
          </div>
          <button onClick={onClose} className="md:hidden p-1 hover:bg-gray-100 rounded dark:hover:bg-dark-100">
            <X size={20} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-brandgray-400">
              <Loader2 size={20} className="animate-spin mr-2" />
              <span className="text-sm">იტვირთება...</span>
            </div>
          ) : (
            <>
              {/* Favorites */}
              {favorites.length > 0 && (
                <div className="pt-2">
                  <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
                    {t('რჩეულები')}
                  </p>
                  <div className="space-y-0.5">
                    {favoriteItems.map((item) => (
                      <NavLinkItem key={item.to} item={item} onClose={onClose} depth={0} isFav onToggleFav={toggleFav} />
                    ))}
                  </div>
                </div>
              )}

              {/* მიმოხილვა — always above "ბოლო ნანახი" */}
              {overviewItem && (
                <div className="pt-1">
                  <NavLinkItem item={overviewItem} onClose={onClose} depth={0} isFav={favorites.includes('/dashboard')} onToggleFav={toggleFav} />
                </div>
              )}

              {/* Recent */}
              {recentItems.length > 0 && (
                <div className="pt-2">
                  <div className="mx-3 mb-2 border-t border-brandgray-100 dark:border-dark-50" />
                  <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-brandgray-400 dark:text-gray-500">
                    {t('ბოლო ნანახი')}
                  </p>
                  <div className="mx-2 rounded-lg bg-brandgray-50/70 dark:bg-dark-100/60 p-1.5 space-y-0.5">
                    {recentItems.map((item) => (
                      <NavLinkItem key={item.to} item={item} onClose={onClose} depth={0} isFav={favorites.includes(item.to)} onToggleFav={toggleFav} />
                    ))}
                  </div>
                </div>
              )}

              {/* Direct top-level items (excluding მიმოხილვა) + groups, in user-defined order */}
              {NAV_ORDER.map((key) => {
                if (key === 'maintenance') {
                  const maintItem = directItems.find((i) => i.to === '/maintenance')
                  if (!maintItem) return null
                  return (
                    <div key="maintenance" className="pt-1">
                      <CollapsibleGroup
                        icon={Wrench}
                        label={maintItem.label}
                        open={openGroups.has('maintenance')}
                        onToggle={() => toggleGroup('maintenance')}
                      >
                        {MAINTENANCE_SUBGROUPS.map((sub) => (
                          <NavLinkItem
                            key={sub.key}
                            item={{ to: `/maintenance?tab=${sub.key}`, icon: Wrench, label: sub.label }}
                            onClose={onClose}
                            depth={1}
                            exact
                            isFav={favorites.includes(`/maintenance?tab=${sub.key}`)}
                            onToggleFav={toggleFav}
                          />
                        ))}
                      </CollapsibleGroup>
                    </div>
                  )
                }
                if (key.startsWith('/')) {
                  const item = directItems.find((i) => i.to === key)
                  if (!item || item.to === '/dashboard') return null
                  return (
                    <NavLinkItem key={item.to} item={item} onClose={onClose} depth={0} isFav={favorites.includes(item.to)} onToggleFav={toggleFav} />
                  )
                }
                const group = groupedItems.find((g) => g.id === key)
                if (!group) return null
                return (
                  <div key={group.id} className="pt-1">
                    <CollapsibleGroup
                      icon={group.icon}
                      label={group.label}
                      open={openGroups.has(group.id)}
                      onToggle={() => toggleGroup(group.id)}
                    >
                      {group.items.map((item) => (
                        <NavLinkItem key={item.to} item={item} onClose={onClose} depth={1} isFav={favorites.includes(item.to)} onToggleFav={toggleFav} />
                      ))}
                    </CollapsibleGroup>
                  </div>
                )
              })}
            </>
          )}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-brandgray-100 space-y-2 bg-brandgray-50/40 dark:border-dark-50 dark:bg-dark-300/50">
          <button
            onClick={() => { onChatToggle?.(); onClose() }}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-brandgray-600 hover:bg-primary-50 hover:text-primary-800 transition-colors dark:text-gray-400 dark:hover:bg-primary-900/30 dark:hover:text-primary-200"
          >
            <Bot size={20} />
            {t('AI ასისტენტი')}
            <span className="ml-auto w-2 h-2 bg-accent-500 rounded-full animate-pulse" />
          </button>
          <div className="text-xs text-gray-400 text-center dark:text-gray-500">
            {t('ვერსია 2.0')}
          </div>
        </div>
      </aside>
    </>
  )
}
