// frontend/src/components/layout/GlobalSearch.tsx
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Search, Users, Package, ShoppingCart, ReceiptText, Building2, Loader2 } from 'lucide-react'
import { api } from '../../services/api'

interface SearchResults {
  clients: { id: string; name: string; identification_code: string; status: string }[]
  products: { id: string; name: string; sku: string }[]
  orders: { id: string; order_number: string; client_name: string }[]
  invoices: { id: string; invoice_number: string; client_name: string }[]
  suppliers: { id: string; name: string; identification_code: string }[]
}

const EMPTY: SearchResults = { clients: [], products: [], orders: [], invoices: [], suppliers: [] }

export default function GlobalSearch() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResults>(EMPTY)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  // Debounced search
  useEffect(() => {
    const q = query.trim()
    if (q.length < 2) {
      setResults(EMPTY)
      setOpen(false)
      setLoading(false)
      return
    }
    setLoading(true)
    const timer = setTimeout(async () => {
      try {
        const res = await api.get('/search', { params: { q } })
        setResults(res.data.data || EMPTY)
        setOpen(true)
      } catch {
        setResults(EMPTY)
        setOpen(true)
      } finally {
        setLoading(false)
      }
    }, 350)
    return () => clearTimeout(timer)
  }, [query])

  // Close on outside click
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const total = results.clients.length + results.products.length + results.orders.length + results.invoices.length + results.suppliers.length

  const go = (to: string) => {
    setOpen(false)
    setQuery('')
    navigate(to)
  }

  return (
    <div ref={wrapRef} className="relative flex-1 max-w-md mx-2">
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => { if (total > 0) setOpen(true) }}
          placeholder={t('გლობალური ძებნა...')}
          className="input h-9 pl-9 pr-8 text-sm"
        />
        {loading && <Loader2 size={14} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-gray-400" />}
      </div>

      {open && (
        <div className="absolute left-0 right-0 mt-1.5 max-h-[70vh] overflow-y-auto rounded-xl border border-gray-200 bg-white shadow-lg z-50 dark:border-dark-50 dark:bg-dark-200">
          {total === 0 && !loading ? (
            <p className="px-4 py-5 text-center text-sm text-gray-500 dark:text-gray-400">{t('შედეგი არ მოიძებნა')}</p>
          ) : (
            <>
              {results.clients.length > 0 && (
                <SearchGroup title={t('კლიენტები')} icon={<Users size={14} />}>
                  {results.clients.map((c) => (
                    <SearchRow key={c.id} primary={c.name} secondary={c.identification_code} onClick={() => go(`/clients/${c.id}`)} />
                  ))}
                </SearchGroup>
              )}
              {results.products.length > 0 && (
                <SearchGroup title={t('პროდუქტები')} icon={<Package size={14} />}>
                  {results.products.map((p) => (
                    <SearchRow key={p.id} primary={p.name} secondary={p.sku} onClick={() => go('/inventory')} />
                  ))}
                </SearchGroup>
              )}
              {results.orders.length > 0 && (
                <SearchGroup title={t('შეკვეთები')} icon={<ShoppingCart size={14} />}>
                  {results.orders.map((o) => (
                    <SearchRow key={o.id} primary={o.order_number} secondary={o.client_name} onClick={() => go(`/orders/${o.id}`)} />
                  ))}
                </SearchGroup>
              )}
              {results.invoices.length > 0 && (
                <SearchGroup title={t('ინვოისები')} icon={<ReceiptText size={14} />}>
                  {results.invoices.map((i) => (
                    <SearchRow key={i.id} primary={i.invoice_number} secondary={i.client_name} onClick={() => go('/invoices')} />
                  ))}
                </SearchGroup>
              )}
              {results.suppliers.length > 0 && (
                <SearchGroup title={t('მომწოდებლები')} icon={<Building2 size={14} />}>
                  {results.suppliers.map((s) => (
                    <SearchRow key={s.id} primary={s.name} secondary={s.identification_code} onClick={() => go('/suppliers')} />
                  ))}
                </SearchGroup>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function SearchGroup({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="py-1">
      <p className="flex items-center gap-1.5 px-4 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-brandgray-400 dark:text-gray-500">
        {icon} {title}
      </p>
      {children}
    </div>
  )
}

function SearchRow({ primary, secondary, onClick }: { primary: string; secondary?: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full flex items-center justify-between gap-3 px-4 py-2 text-left text-sm transition-colors hover:bg-primary-50 dark:hover:bg-primary-900/30"
    >
      <span className="truncate font-medium text-brandgray-900 dark:text-gray-100">{primary}</span>
      {secondary && <span className="shrink-0 text-xs text-brandgray-400 dark:text-gray-500">{secondary}</span>}
    </button>
  )
}
