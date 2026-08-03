import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { authApi } from '../services/api'

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setMessage('Verification token არ მოიძებნა')
      return
    }
    authApi.verifyEmail(token)
      .then((res) => {
        setStatus('success')
        setMessage(res.data.data?.message || 'ელფოსტა წარმატებით დადასტურდა')
      })
      .catch((err) => {
        setStatus('error')
        setMessage(err?.response?.data?.detail || 'ვერიფიკაცია ვერ შესრულდა')
      })
  }, [token])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-primary-600">Business OS</h1>
          <p className="text-gray-500 mt-2">ქართული ბიზნეს ოპერაციული სისტემა</p>
        </div>

        <div className="card text-center py-10">
          {status === 'loading' && (
            <div>
              <Loader2 size={48} className="mx-auto text-primary-600 animate-spin mb-4" />
              <p className="text-gray-600">ელფოსტის დადასტურება...</p>
            </div>
          )}

          {status === 'success' && (
            <div>
              <CheckCircle2 size={48} className="mx-auto text-green-500 mb-4" />
              <h2 className="text-xl font-semibold text-gray-900 mb-2">ელფოსტა დადასტურებულია</h2>
              <p className="text-gray-600 mb-6">{message}</p>
              <Link to="/login" className="btn-primary inline-flex">შესვლა</Link>
            </div>
          )}

          {status === 'error' && (
            <div>
              <XCircle size={48} className="mx-auto text-red-500 mb-4" />
              <h2 className="text-xl font-semibold text-gray-900 mb-2">ვერიფიკაცია ვერ შესრულდა</h2>
              <p className="text-gray-600 mb-6">{message}</p>
              <Link to="/login" className="btn-primary inline-flex">შესვლის გვერდზე დაბრუნება</Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
