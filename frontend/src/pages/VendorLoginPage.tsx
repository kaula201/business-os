import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Link } from 'react-router-dom'
import { ArrowRight, Loader2, Building2 } from 'lucide-react'

import { useVendorAuthStore } from '../store/vendorAuthStore'
import LanguageSwitcher from '../components/LanguageSwitcher'
import { vendorAuthApi } from '../services/api'

export default function VendorLoginPage() {
  const { t } = useTranslation()
  const { isAuthenticated, setAuth } = useVendorAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (isAuthenticated) return <Navigate to="/vendor/dashboard" />

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await vendorAuthApi.login({ email, password })
      setAuth(res.data.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('შეცდომა შესვლისას'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="brand-auth-background relative min-h-screen overflow-hidden px-4 py-8">
      <div className="absolute right-4 top-4">
        <LanguageSwitcher />
      </div>
      <div className="absolute inset-x-0 top-0 h-1.5 brand-topline" />
      <div className="pointer-events-none absolute -left-16 top-28 h-52 w-52 rounded-full border-[28px] border-primary-100/50" />
      <div className="pointer-events-none absolute -right-20 bottom-16 h-64 w-64 rounded-full border-[34px] border-accent-100/50" />

      <div className="relative mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-md items-center">
        <div className="w-full overflow-hidden rounded-3xl border border-brandgray-100 dark:border-dark-50 bg-white dark:bg-dark-200 shadow-[0_30px_80px_-40px_rgba(16,95,125,0.45)]">
          <div className="relative bg-brandgray-700 p-8 text-white">
            <div className="absolute inset-x-0 top-0 h-1.5 brand-topline" />
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-500/20">
                <Building2 size={22} className="text-primary-300" />
              </div>
              <div>
                <div className="text-lg font-bold tracking-tight">{t('მომწოდებლის პორტალი')}</div>
                <div className="text-xs text-white/60">{t('შესყიდვების თანამშრომლობა')}</div>
              </div>
            </div>
          </div>

          <div className="p-7 sm:p-10">
            <h1 className="text-xl font-bold text-brandgray-800 dark:text-gray-100">{t('ანგარიშზე შესვლა')}</h1>
            <p className="mt-1 text-sm text-brandgray-500 dark:text-gray-400">{t('შედით თქვენი მომწოდებლის ანგარიშით')}</p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('ელ.ფოსტა')}</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200"
                  placeholder="vendor@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('პაროლი')}</label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-brandgray-200 bg-white px-3 py-2 text-sm focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100 dark:border-dark-50 dark:bg-dark-100 dark:text-gray-200"
                />
              </div>

              {error && (
                <div className="rounded-lg bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-600 dark:text-red-400">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
              >
                {loading ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
                {t('შესვლა')}
              </button>
            </form>

            <div className="mt-6 text-center text-sm">
              <Link to="/login" className="text-primary-600 hover:text-primary-700 dark:text-primary-400">
                {t('თანამშრომლის შესვლა')}
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
