// frontend/src/components/layout/Header.tsx
import { Menu, Bell, User, LogOut, Moon, Sun, CheckCheck } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import LanguageSwitcher from '../LanguageSwitcher'
import GlobalSearch from './GlobalSearch'
import { notificationsApi } from '../../services/api'

interface HeaderProps {
  onMenuClick: () => void
}

export default function Header({ onMenuClick }: HeaderProps) {
  const { user, logout } = useAuthStore()
  const { t } = useTranslation()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')
  const [notifOpen, setNotifOpen] = useState(false)
  const qc = useQueryClient()

  const { data: notifData } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationsApi.list(20).then(r => r.data.data),
    refetchInterval: 30000, // auto-refresh every 30s
  })
  const { data: unreadData } = useQuery({
    queryKey: ['notif-unread'],
    queryFn: () => notificationsApi.unreadCount().then(r => r.data.data),
    refetchInterval: 30000,
  })
  const unread = unreadData?.count || 0

  const markRead = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['notifications'] }); qc.invalidateQueries({ queryKey: ['notif-unread'] }) },
  })
  const markAllRead = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['notifications'] }); qc.invalidateQueries({ queryKey: ['notif-unread'] }) },
  })

  useEffect(() => {
    if (dark) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [dark])

  return (
    <header className="relative h-16 bg-white/95 border-b border-brandgray-100 flex items-center justify-between px-4 md:px-6 backdrop-blur dark:bg-dark-200 dark:border-dark-50">
      <div className="absolute inset-x-0 top-0 h-0.5 brand-topline" />
      {/* Left */}
      <div className="flex items-center">
        <button
          onClick={onMenuClick}
          className="md:hidden p-2 hover:bg-gray-100 rounded-lg"
        >
          <Menu size={20} />
        </button>
      </div>

      {/* Global search */}
      <div className="hidden md:flex flex-1 justify-center">
        <GlobalSearch />
      </div>

      {/* Right */}
      <div className="flex items-center gap-3">
        {/* Language switcher */}
        <LanguageSwitcher />

        {/* Dark mode toggle */}
        <button
          onClick={() => setDark(!dark)}
          className="p-2 hover:bg-gray-100 rounded-lg dark:hover:bg-dark-100"
          title={dark ? t('ღია რეჟიმი') : t('მუქი რეჟიმი')}
        >
          {dark ? <Sun size={20} className="text-yellow-400" /> : <Moon size={20} className="text-gray-500" />}
        </button>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setNotifOpen(!notifOpen)}
            className="relative p-2 hover:bg-gray-100 rounded-lg"
            title={t('შეტყობინებები')}
            aria-label={t('შეტყობინებები')}
          >
            <Bell size={20} className="text-gray-500" />
            {unread > 0 && (
              <span className="absolute top-0.5 right-0.5 min-w-[16px] h-4 px-1 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                {unread > 99 ? '99+' : unread}
              </span>
            )}
          </button>

          {notifOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setNotifOpen(false)} />
              <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-50 dark:bg-dark-200 dark:border-dark-50 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-dark-50">
                  <span className="text-sm font-semibold text-gray-800 dark:text-gray-100">{t('შეტყობინებები')}</span>
                  {unread > 0 && (
                    <button onClick={() => markAllRead.mutate()} className="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-1">
                      <CheckCheck size={14} /> {t('ყველას წაკითხვა')}
                    </button>
                  )}
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {(notifData || []).length === 0 ? (
                    <div className="p-6 text-center text-sm text-gray-500 dark:text-gray-400">{t('შეტყობინებები არ არის')}</div>
                  ) : (notifData || []).map((n: any) => (
                    <button
                      key={n.id}
                      onClick={() => { if (!n.is_read) markRead.mutate(n.id); setNotifOpen(false); if (n.link) window.location.href = n.link }}
                      className={`w-full text-left px-4 py-3 border-b border-gray-50 dark:border-dark-50 hover:bg-gray-50 dark:hover:bg-dark-100 ${n.is_read ? 'opacity-60' : ''}`}
                    >
                      <div className="flex items-start gap-2">
                        <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${n.is_read ? 'bg-gray-300 dark:bg-dark-50' : 'bg-red-500'}`} />
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">{n.title}</p>
                          {n.message && <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{n.message}</p>}
                          <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                            {n.created_at ? new Date(n.created_at).toLocaleString('ka-GE') : ''}
                          </p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2 p-2 hover:bg-gray-100 rounded-lg"
          >
            <div className="w-8 h-8 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-sm font-medium">
              {user?.full_name?.charAt(0) || '?'}
            </div>
            <span className="text-sm font-medium text-gray-700 hidden sm:block">
              {user?.full_name || t('მომხმარებელი')}
            </span>
          </button>

          {dropdownOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setDropdownOpen(false)} />
              <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50 dark:bg-dark-200 dark:border-dark-50">
                <div className="px-4 py-2 border-b border-gray-100 dark:border-dark-50">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{user?.full_name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{user?.email}</p>
                  <span className="badge badge-blue mt-1">{user?.role}</span>
                </div>
                <button
                  onClick={() => { logout(); setDropdownOpen(false) }}
                  className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/30"
                >
                  <LogOut size={16} />
                  {t('გასვლა')}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
