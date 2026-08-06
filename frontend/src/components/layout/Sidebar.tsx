// frontend/src/components/layout/Sidebar.tsx
import { NavLink } from 'react-router-dom'
import { 
  LayoutDashboard, Users, ShoppingCart, Package, 
  CheckSquare, Bot, Settings, X, ReceiptText, Building2, WalletCards, Landmark, BookOpen, FileText, TrendingUp, Scale, Car, ChevronDown, ChevronRight, DollarSign, Banknote, HandCoins, Wrench, BarChart3, Target, Coins, Network, CalendarClock, CalendarRange, Loader2
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { modulesApi } from '../../services/api'
import type { CompanyModuleStatus } from '../../types'

// ── Icon map ─────────────────────────────────────────────────────────
const iconMap: Record<string, any> = {
  LayoutDashboard, Users, ShoppingCart, Package,
  CheckSquare, Bot, Settings, ReceiptText, Building2, WalletCards,
  Landmark, BookOpen, FileText, TrendingUp, Scale, Car,
  DollarSign, Banknote, HandCoins, Wrench, BarChart3, Target,
  Coins, Network, CalendarClock, CalendarRange,
}

// ── Category groups (static structure, filtered by enabled modules) ──

interface NavGroup {
  id: string
  label: string
  icon: any
  category: string  // matches AppModule.category
  items: { to: string; icon: any; label: string }[]
}

const categoryGroups: NavGroup[] = [
  { id: 'crm', label: 'CRM — გაყიდვების მართვა', icon: Target, category: 'sales', items: [] },
  { id: 'sales', label: 'გაყიდვები', icon: ShoppingCart, category: 'sales', items: [] },
  { id: 'operations', label: 'ოპერაციები', icon: Package, category: 'operations', items: [] },
  { id: 'purchases', label: 'შესყიდვები', icon: Building2, category: 'purchases', items: [] },
  { id: 'finance', label: 'ფინანსები', icon: DollarSign, category: 'finance', items: [] },
  { id: 'accounting', label: 'ბუღალტერია', icon: BookOpen, category: 'accounting', items: [] },
  { id: 'fleet', label: 'ავტოპარკი', icon: Car, category: 'fleet', items: [] },
  { id: 'other', label: 'სხვა', icon: Settings, category: 'other', items: [] },
]

// ── Sub-components ──────────────────────────────────────────────────

function NavLinkItem({ item, onClose, depth = 0 }: { item: { to: string; icon: any; label: string }; onClose: () => void; depth?: number }) {
  const { t } = useTranslation()
  return (
    <NavLink
      to={item.to}
      onClick={onClose}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all
        ${isActive 
          ? 'bg-primary-50 text-primary-800 shadow-sm ring-1 ring-primary-100 dark:bg-primary-900/40 dark:text-primary-200 dark:ring-primary-800/50' 
          : 'text-brandgray-600 hover:bg-brandgray-50 hover:text-brandgray-900 dark:text-gray-400 dark:hover:bg-dark-100 dark:hover:text-gray-200'
        }`
      }
    >
      <item.icon size={depth === 0 ? 20 : 17} className="transition-transform group-hover:scale-105 shrink-0" />
      <span className="truncate">{t(item.label)}</span>
    </NavLink>
  )
}

function CollapsibleGroup({
  icon: Icon,
  label,
  open,
  onToggle,
  children,
}: {
  icon: any
  label: string
  open: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  const { t } = useTranslation()
  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-brandgray-600 hover:bg-brandgray-50 hover:text-brandgray-900 transition-colors dark:text-gray-400 dark:hover:bg-dark-100 dark:hover:text-gray-200"
      >
        <Icon size={18} className="shrink-0" />
        <span className="flex-1 text-left truncate">{t(label)}</span>
        {open ? <ChevronDown size={14} className="shrink-0" /> : <ChevronRight size={14} className="shrink-0" />}
      </button>
      {open && (
        <div className="ml-3 pl-3 border-l border-brandgray-200 dark:border-dark-50 space-y-0.5 mt-0.5">
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
  const [modules, setModules] = useState<CompanyModuleStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [openGroups, setOpenGroups] = useState<Set<string>>(() => new Set())

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

  // Ensure modules are loaded before rendering navigation
  // Prevents race condition where sidebar renders empty before API responds
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
            <div className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-primary-700 dark:text-primary-400">ბიზნესის მართვა</div>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center text-brandgray-400">
          <Loader2 size={20} className="animate-spin mr-2" />
          <span className="text-sm">{t('იტვირთება...')}</span>
        </div>
      </aside>
    )
  }

  // Build nav items from enabled modules
  const enabledModules = modules.filter((m) => m.enabled && m.module.is_active)

  const getNavItems = (category: string) =>
    enabledModules
      .filter((m) => m.module.category === category)
      .map((m) => ({
        to: m.module.route || `/${m.module.code}`,
        icon: iconMap[m.module.icon || 'FileText'] || FileText,
        label: m.module.name,
      }))

  // Separate CRM items (they go in a special group)
  const crmItems = getNavItems('sales').filter((i) => i.to.startsWith('/crm'))
  const salesItems = getNavItems('sales').filter((i) => !i.to.startsWith('/crm'))

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
            <div className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-primary-700 dark:text-primary-400">ბიზნესის მართვა</div>
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
              {/* Dashboard */}
              {enabledModules.some((m) => m.module.code === 'dashboard') && (
                <NavLinkItem
                  item={{ to: '/dashboard', icon: LayoutDashboard, label: 'მიმოხილვა' }}
                  onClose={onClose}
                  depth={0}
                />
              )}

              {/* CRM group */}
              {crmItems.length > 0 && (
                <div className="pt-1">
                  <CollapsibleGroup
                    icon={Target}
                    label={t('CRM — გაყიდვების მართვა')}
                    open={openGroups.has('crm')}
                    onToggle={() => toggleGroup('crm')}
                  >
                    {crmItems.map((item) => (
                      <NavLinkItem key={item.to} item={item} onClose={onClose} depth={1} />
                    ))}
                  </CollapsibleGroup>
                </div>
              )}

              {/* Sales group */}
              {salesItems.length > 0 && (
                <div className="pt-1">
                  <CollapsibleGroup
                    icon={ShoppingCart}
                    label={t('გაყიდვები')}
                    open={openGroups.has('sales')}
                    onToggle={() => toggleGroup('sales')}
                  >
                    {salesItems.map((item) => (
                      <NavLinkItem key={item.to} item={item} onClose={onClose} depth={1} />
                    ))}
                  </CollapsibleGroup>
                </div>
              )}

              {/* Operations */}
              {getNavItems('operations').map((item) => (
                <NavLinkItem key={item.to} item={item} onClose={onClose} depth={0} />
              ))}

              {/* Purchases group */}
              {getNavItems('purchases').length > 0 && (
                <div className="pt-1">
                  <CollapsibleGroup
                    icon={Building2}
                    label={t('შესყიდვები')}
                    open={openGroups.has('purchases')}
                    onToggle={() => toggleGroup('purchases')}
                  >
                    {getNavItems('purchases').map((item) => (
                      <NavLinkItem key={item.to} item={item} onClose={onClose} depth={1} />
                    ))}
                  </CollapsibleGroup>
                </div>
              )}

              {/* Finance group */}
              {getNavItems('finance').length > 0 && (
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => toggleGroup('finance')}
                    aria-expanded={openGroups.has('finance')}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-brandgray-600 hover:bg-brandgray-50 hover:text-brandgray-900 transition-colors dark:text-gray-400 dark:hover:bg-dark-100 dark:hover:text-gray-200"
                  >
                    <DollarSign size={20} />
                    <span className="flex-1 text-left">{t('ფინანსები')}</span>
                    {openGroups.has('finance') ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  </button>

                  {openGroups.has('finance') && (
                    <div className="ml-3 pl-3 border-l border-brandgray-200 dark:border-dark-50 space-y-1 mt-1">
                      {getNavItems('finance').map((item) => (
                        <NavLinkItem key={item.to} item={item} onClose={onClose} depth={1} />
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Accounting group */}
              {getNavItems('accounting').length > 0 && (
                <div className="pt-1">
                  <CollapsibleGroup
                    icon={BookOpen}
                    label={t('ბუღალტერია')}
                    open={openGroups.has('accounting')}
                    onToggle={() => toggleGroup('accounting')}
                  >
                    {getNavItems('accounting').map((item) => (
                      <NavLinkItem key={item.to} item={item} onClose={onClose} depth={1} />
                    ))}
                  </CollapsibleGroup>
                </div>
              )}

              {/* Fleet */}
              {getNavItems('fleet').map((item) => (
                <NavLinkItem key={item.to} item={item} onClose={onClose} depth={0} />
              ))}

              {/* Other items */}
              {getNavItems('other').map((item) => (
                <NavLinkItem key={item.to} item={item} onClose={onClose} depth={0} />
              ))}
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
            {t('ვერსია 1.0.0 — MVP')}
          </div>
        </div>
      </aside>
    </>
  )
}
