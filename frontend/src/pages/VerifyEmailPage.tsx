import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams, Link } from 'react-router-dom'
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { authApi } from '../services/api'

export default function VerifyEmailPage() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setMessage(t('Verification token არ მოიძებნა'))
      return
    }
    authApi.verifyEmail(token)
      .then((res) => {
        setStatus('success')
        setMessage(res.data.data?.message || t('ელფოსტა წარმატებით დადასტურდა'))
      })
      .catch((err) => {
        setStatus('error')
        setMessage(err?.response?.data?.detail || t('ვერიფიკაცია ვერ შესრულდა'))
      })
  }, [token])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-dark-100 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-primary-600 dark:text-primary-400">Business OS</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-2">{t('ქართული ბიზნეს ოპერაციული სისტემა')}</p>
        </div>

        <div className="card text-center py-10">
          {status === 'loading' && (
            <div>
              <Loader2 size={48} className="mx-auto text-primary-600 animate-spin mb-4 dark:text-primary-400" />
              <p className="text-gray-600 dark:text-gray-400">{t('ელფოსტის დადასტურება...')}</p>
            </div>
          )}

          {status === 'success' && (
            <div>
              <CheckCircle2 size={48} className="mx-auto text-green-500 mb-4" />
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">{t('ელფოსტა დადასტურებულია')}</h2>
              <p className="text-gray-600 dark:text-gray-400 mb-6">{message}</p>
              <Link to="/login" className="btn-primary inline-flex">{t('შესვლა')}</Link>
            </div>
          )}

          {status === 'error' && (
            <div>
              <XCircle size={48} className="mx-auto text-red-500 mb-4" />
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">{t('ვერიფიკაცია ვერ შესრულდა')}</h2>
              <p className="text-gray-600 dark:text-gray-400 mb-6">{message}</p>
              <Link to="/login" className="btn-primary inline-flex">{t('შესვლის გვერდზე დაბრუნება')}</Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
