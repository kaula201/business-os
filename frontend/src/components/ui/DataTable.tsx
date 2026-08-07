import { useEffect, useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronLeft, ChevronRight, AlertCircle, RefreshCw, ArrowUpDown, ArrowUp, ArrowDown, Search, ChevronRight as ChevronRightIcon, FileQuestion, Plus, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

interface Column<T> {
  key: string
  label: string
  render?: (item: T) => React.ReactNode
  className?: string
  hideOnMobile?: boolean
  sortable?: boolean
  /** Label shown in mobile card view for this field */
  mobileLabel?: string
  /** Priority columns shown in card header (max 2) */
  priority?: boolean
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  isLoading?: boolean
  error?: string | null
  onRetry?: () => void
  onRowClick?: (item: T) => void
  page?: number
  totalPages?: number
  total?: number
  onPageChange?: (page: number) => void
  searchable?: boolean
  searchPlaceholder?: string
  onSearch?: (term: string) => void
  searchValue?: string
  pageSizeOptions?: number[]
  onPageSizeChange?: (size: number) => void
  pageSize?: number
  /** Opt-in pagination for endpoints that return a complete small/reference list */
  clientPageSize?: number
  /** Show mobile card layout below md breakpoint */
  mobileCards?: boolean
  /** Empty-state props — shown instead of the plain "no data" message */
  emptyTitle?: string
  emptyMessage?: string
  emptyIcon?: React.ReactNode
  emptyActionLabel?: string
  emptyActionTo?: string
  emptyOnAction?: () => void
}

export default function DataTable<T extends Record<string, any>>({
  columns, data, isLoading, error, emptyMessage = 'მონაცემები არ მოიძებნა',
  onRetry, onRowClick, page, totalPages, total, onPageChange,
  searchable, searchPlaceholder = 'ძებნა...', onSearch, searchValue,
  pageSizeOptions, onPageSizeChange, pageSize, clientPageSize,
  mobileCards = true, emptyTitle, emptyIcon,
  emptyActionLabel, emptyActionTo, emptyOnAction,
}: DataTableProps<T>) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [clientPage, setClientPage] = useState(1)

  useEffect(() => {
    if (clientPageSize) setClientPage(1)
  }, [data, clientPageSize])

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const sortedData = useMemo(() => {
    if (!sortKey) return data
    return [...data].sort((a, b) => {
      const aVal = a[sortKey]
      const bVal = b[sortKey]
      if (aVal == null) return 1
      if (bVal == null) return -1
      const cmp = typeof aVal === 'number' ? aVal - bVal : String(aVal).localeCompare(String(bVal))
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [data, sortKey, sortDir])

  const usesClientPagination = Boolean(clientPageSize && page === undefined)
  const effectivePage = usesClientPagination ? clientPage : (page || 1)
  const effectiveTotal = usesClientPagination ? data.length : total
  const effectiveTotalPages = usesClientPagination
    ? Math.max(1, Math.ceil(data.length / (clientPageSize || 20)))
    : totalPages
  const displayedData = usesClientPagination
    ? sortedData.slice((effectivePage - 1) * (clientPageSize || 20), effectivePage * (clientPageSize || 20))
    : sortedData
  const changePage = usesClientPagination ? setClientPage : onPageChange

  if (isLoading) {
    return (
      <div className="card" role="status" aria-label={t('იტვირთება')}>
        <div className="p-8 text-center text-gray-500 dark:text-gray-400">
          <div className="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full mx-auto mb-2" />
          <span className="text-sm">{t('იტვირთება...')}</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card" role="alert" aria-label={t('შეცდომა')}>
        <div className="p-8 text-center">
          <AlertCircle size={32} className="mx-auto mb-2 text-red-500" />
          <p className="text-sm text-red-600 dark:text-red-400 mb-3">{error}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="btn btn-secondary btn-sm inline-flex items-center gap-2"
              aria-label={t('ხელახლა ცდა')}
            >
              <RefreshCw size={14} />
              ხელახლა ცდა
            </button>
          )}
        </div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="card" aria-label={t('ცარიელი შედეგი')}>
        <div className="p-10 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-gray-100 dark:bg-dark-100">
            {emptyIcon || <FileQuestion size={28} className="text-gray-400 dark:text-gray-500" />}
          </div>
          <h3 className="text-base font-semibold text-gray-700 dark:text-gray-200">
            {emptyTitle || t('მონაცემები არ მოიძებნა')}
          </h3>
          <p className="mx-auto mt-1 max-w-md text-sm text-gray-500 dark:text-gray-400">
            {t(emptyMessage)}
          </p>
          {(emptyActionLabel && (emptyActionTo || emptyOnAction)) && (
            <button
              onClick={() => {
                if (emptyOnAction) emptyOnAction()
                else if (emptyActionTo) navigate(emptyActionTo)
              }}
              className="btn btn-primary btn-sm mt-5 inline-flex items-center gap-2"
            >
              <Plus size={15} />
              {emptyActionLabel}
              <ArrowRight size={15} />
            </button>
          )}
        </div>
      </div>
    )
  }

  // ── Mobile card view ──────────────────────────────────────────────
  const priorityColumns = columns.filter((c) => c.priority)
  const detailColumns = columns.filter((c) => !c.priority && !c.hideOnMobile)

  const renderMobileCards = () => (
    <div className="space-y-3 md:hidden">
      {displayedData.map((item, idx) => (
        <div
          key={item.id || idx}
          onClick={() => onRowClick?.(item)}
          className={`rounded-xl border border-gray-200 bg-white p-4 dark:border-dark-50 dark:bg-dark-200 ${onRowClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}
        >
          {/* Card header — priority columns */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex-1 min-w-0">
              {priorityColumns.map((col) => (
                <div key={col.key} className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
                  {col.render ? col.render(item) : item[col.key]}
                </div>
              ))}
            </div>
            {onRowClick && <ChevronRightIcon size={18} className="shrink-0 text-gray-400 ml-2" />}
          </div>

          {/* Card body — detail columns */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
            {detailColumns.map((col) => (
              <div key={col.key} className={col.hideOnMobile ? 'hidden' : ''}>
                <span className="text-gray-500 dark:text-gray-400 block">{t(col.mobileLabel || col.label)}</span>
                <span className="text-gray-800 dark:text-gray-200 font-medium">
                  {col.render ? col.render(item) : item[col.key] ?? '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )

  return (
    <div className="card overflow-hidden p-0">
      {/* Toolbar: search + page size */}
      {(searchable || pageSizeOptions) && (
        <div className="flex items-center justify-between gap-4 px-6 py-3 border-b border-gray-200 dark:border-dark-50 bg-gray-50/50 dark:bg-dark-100/50">
          {searchable && (
            <div className="relative flex-1 max-w-xs">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchValue || ''}
                onChange={(e) => onSearch?.(e.target.value)}
                placeholder={searchPlaceholder}
                className="input pl-9 w-full text-sm"
                aria-label={searchPlaceholder}
              />
            </div>
          )}
          {pageSizeOptions && onPageSizeChange && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span className="hidden sm:inline">{t('ჩანაწერი:')}</span>
              <select
                value={pageSize || 20}
                onChange={(e) => onPageSizeChange(Number(e.target.value))}
                className="input py-1 px-2 text-sm"
                aria-label={t('გვერდის ზომა')}
              >
                {pageSizeOptions.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}

      {/* Mobile cards */}
      {mobileCards && renderMobileCards()}

      {/* Desktop table */}
      <div className={`${mobileCards ? 'hidden md:block' : ''}`} role="region" aria-label={t('მონაცემთა ცხრილი')}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px]">
            <thead className="bg-gray-50 border-b border-gray-200 dark:bg-dark-100 dark:border-dark-50">
              <tr>
                {columns.map((col) => (
                  <th
                    key={col.key}
                    scope="col"
                    className={`text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400 ${col.hideOnMobile ? 'hidden md:table-cell' : ''} ${col.className || ''}`}
                  >
                    {col.sortable ? (
                      <button
                        onClick={() => handleSort(col.key)}
                        className="inline-flex items-center gap-1 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
                        aria-label={t('დალაგება') + ' ' + t(col.label)}
                      >
                        {t(col.label)}
                        {sortKey === col.key ? (
                          sortDir === 'asc' ? <ArrowUp size={14} /> : <ArrowDown size={14} />
                        ) : (
                          <ArrowUpDown size={14} className="opacity-30" />
                        )}
                      </button>
                    ) : t(col.label)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-dark-50">
              {displayedData.map((item, idx) => (
                <tr
                  key={item.id || idx}
                  onClick={() => onRowClick?.(item)}
                  className={`${onRowClick ? 'cursor-pointer' : ''} hover:bg-gray-50 transition-colors dark:hover:bg-dark-100`}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-6 py-4 text-sm dark:text-gray-300 ${col.hideOnMobile ? 'hidden md:table-cell' : ''} ${col.className || ''}`}
                    >
                      {col.render ? col.render(item) : item[col.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {effectiveTotalPages && effectiveTotalPages > 1 && (
        <div className="flex items-center justify-between px-6 py-3 bg-gray-50 border-t border-gray-200 dark:bg-dark-100 dark:border-dark-50">
          <span className="text-sm text-gray-500 dark:text-gray-400">სულ: {effectiveTotal}</span>
          <nav aria-label="გვერდების ნავიგაცია" className="flex items-center gap-2">
            <button
              disabled={effectivePage <= 1}
              onClick={() => changePage?.(effectivePage - 1)}
              className="p-1 hover:bg-gray-200 rounded disabled:opacity-30 dark:hover:bg-dark-50"
              aria-label="წინა გვერდი"
            >
              <ChevronLeft size={18} />
            </button>
            <span className="text-sm text-gray-700 dark:text-gray-300" aria-current="page">{effectivePage} / {effectiveTotalPages}</span>
            <button
              disabled={effectivePage === effectiveTotalPages}
              onClick={() => changePage?.(effectivePage + 1)}
              className="p-1 hover:bg-gray-200 rounded disabled:opacity-30 dark:hover:bg-dark-50"
              aria-label="შემდეგი გვერდი"
            >
              <ChevronRight size={18} />
            </button>
          </nav>
        </div>
      )}
    </div>
  )
}