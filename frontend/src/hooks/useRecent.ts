// frontend/src/hooks/useRecent.ts
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

const STORAGE_KEY = 'bos_recent'
const MAX_RECENT = 6

// Only track these top-level module routes (business records live at module level)
const TRACKABLE = new Set([
  '/dashboard', '/clients', '/crm', '/orders', '/invoices', '/inventory',
  '/tasks', '/purchases', '/suppliers', '/supplier-finance', '/cash',
  '/banking', '/currency', '/customer-finance', '/expenses', '/assets',
  '/chart-of-accounts', '/journal-entries', '/trial-balance', '/profit-loss',
  '/balance-sheet', '/srs', '/budgeting', '/analytic-accounting', '/deferred',
  '/accounting-periods', '/fleet', '/reports', '/ai', '/settings', '/hr',
  '/documents', '/production', '/projects',
])

export function readRecent(): string[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

export function useRecentTracker() {
  const { pathname } = useLocation()

  useEffect(() => {
    if (!TRACKABLE.has(pathname)) return
    const current = readRecent().filter((p) => p !== pathname)
    current.unshift(pathname)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(current.slice(0, MAX_RECENT)))
  }, [pathname])
}

export function useRecentList(): string[] {
  return readRecent()
}
