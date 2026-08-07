// frontend/src/components/layout/Header.tsx
import { Menu, Bell, User, LogOut, Moon, Sun } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import LanguageSwitcher from '../LanguageSwitcher'

interface HeaderProps {
  onMenuClick: () => void
}

export default function Header({ onMenuClick }: HeaderProps) {
  const { user, logout } = useAuthStore()
  const { t } = useTranslation()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')

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
        <button className="relative p-2 hover:bg-gray-100 rounded-lg">
          <Bell size={20} className="text-gray-500" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
        </button>

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
