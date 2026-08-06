// frontend/src/pages/RegisterPage.tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { authApi } from '../services/api'

export default function RegisterPage() {
  const { t } = useTranslation()
  const { isAuthenticated, setAuth } = useAuthStore()
  const [form, setForm] = useState({ company_name: '', full_name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (isAuthenticated) return <Navigate to="/dashboard" />

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await authApi.register(form)
      setAuth(res.data.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'შეცდომა რეგისტრაციისას')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-dark-100 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-primary-600">Business OS</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-2">{t('ქართული ბიზნეს ოპერაციული სისტემა')}</p>
        </div>

        <div className="card">
          <h2 className="text-xl font-semibold mb-6">{t('რეგისტრაცია')}</h2>

          {error && (
            <div className="bg-red-50 text-red-700 px-4 py-3 rounded-lg mb-4 text-sm">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('კომპანიის სახელი')}</label>
              <input type="text" value={form.company_name} onChange={(e) => setForm({...form, company_name: e.target.value})} className="input" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('სახელი')}</label>
              <input type="text" value={form.full_name} onChange={(e) => setForm({...form, full_name: e.target.value})} className="input" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('ელფოსტა')}</label>
              <input type="email" value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} className="input" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t('პაროლი')}</label>
              <input type="password" value={form.password} onChange={(e) => setForm({...form, password: e.target.value})} className="input" minLength={8} required />
            </div>
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? 'რეგისტრაცია...' : 'რეგისტრაცია'}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 dark:text-gray-400 mt-6">
            უკვე გაქვთ ანგარიში?{' '}
            <Link to="/login" className="text-primary-600 hover:underline font-medium">{t('შესვლა')}</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
