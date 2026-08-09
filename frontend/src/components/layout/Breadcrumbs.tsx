// frontend/src/components/layout/Breadcrumbs.tsx
import { Link, useLocation } from 'react-router-dom'
import { ChevronRight, Home } from 'lucide-react'
import { useTranslation } from 'react-i18next'

// Route → breadcrumb label map (keys are i18n keys / Georgian fallbacks)
const ROUTE_LABELS: Record<string, string> = {
  '/dashboard': 'მიმოხილვა',
  '/clients': 'კლიენტების რეესტრი',
  '/crm': 'CRM',
  '/orders': 'გაყიდვის შეკვეთები',
  '/invoices': 'გაყიდვის ინვოისები',
  '/inventory': 'საწყობი',
  '/tasks': 'დავალებები',
  '/purchases': 'შესყიდვები',
  '/suppliers': 'მომწოდებლები',
  '/supplier-finance': 'მომწოდებლის ფინანსები',
  '/cash': 'სალარო',
  '/banking': 'საბანკო',
  '/currency': 'ვალუტის კურსები',
  '/customer-finance': 'კლიენტის ფინანსები',
  '/expenses': 'ხარჯები',
  '/assets': 'ძირითადი საშუალებები',
  '/chart-of-accounts': 'ანგარიშთა გეგმა',
  '/journal-entries': 'საჟურნალო ჩანაწერები',
  '/trial-balance': 'საცდელი ბალანსი',
  '/profit-loss': 'მოგება-ზარალი',
  '/balance-sheet': 'ბალანსი',
  '/srs': 'SRS ანგარიშგება',
  '/budgeting': 'ბიუჯეტირება',
  '/analytic-accounting': 'ანალიტიკური აღრიცხვა',
  '/deferred': 'გადავადებული ოპერაციები',
  '/accounting-periods': 'სააღრიცხვო პერიოდები',
  '/fleet': 'ავტოპარკი',
  '/reports': 'რეპორტები',
  '/ai': 'AI ასისტენტი',
  '/settings': 'პარამეტრები',
  '/hr': 'კადრები',
  '/documents': 'დოკუმენტები',
  '/production': 'წარმოება',
  '/projects': 'პროექტები',
}

export default function Breadcrumbs() {
  const { t } = useTranslation()
  const { pathname } = useLocation()

  // Strip dynamic segments: /clients/:id → /clients
  const segments = pathname.split('/').filter(Boolean)
  const crumbs: { to: string; label: string }[] = []

  for (let i = 0; i < segments.length; i += 1) {
    const path = `/${segments.slice(0, i + 1).join('/')}`
    // Try exact match first, then the static prefix (e.g. /clients/123 → /clients)
    const label = ROUTE_LABELS[path] || ROUTE_LABELS[`/${segments[i]}`]
    if (label) {
      crumbs.push({ to: path, label })
    }
  }

  if (crumbs.length === 0) return null

  return (
    <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-1.5 text-sm text-brandgray-500 dark:text-gray-400">
      <Link to="/dashboard" className="flex items-center gap-1 rounded-md p-1 transition-colors hover:bg-brandgray-50 hover:text-brandgray-900 dark:hover:bg-dark-100 dark:hover:text-gray-200">
        <Home size={15} />
      </Link>
      {crumbs.map((crumb, index) => (
        <span key={crumb.to} className="flex items-center gap-1.5">
          <ChevronRight size={14} className="text-brandgray-300 dark:text-gray-600" />
          {index === crumbs.length - 1 ? (
            <span className="font-medium text-brandgray-900 dark:text-gray-100">{t(crumb.label)}</span>
          ) : (
            <Link
              to={crumb.to}
              className="rounded-md px-1 py-0.5 transition-colors hover:bg-brandgray-50 hover:text-brandgray-900 dark:hover:bg-dark-100 dark:hover:text-gray-200"
            >
              {t(crumb.label)}
            </Link>
          )}
        </span>
      ))}
    </nav>
  )
}
