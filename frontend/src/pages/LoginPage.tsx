import { useState } from 'react'
import { Navigate, Link } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Loader2 } from 'lucide-react'


import { useAuthStore } from '../store/authStore'
import { authApi } from '../services/api'
import Modal from '../components/ui/Modal'

export default function LoginPage() {
  const { isAuthenticated, setAuth } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [forgotOpen, setForgotOpen] = useState(false)
  const [forgotEmail, setForgotEmail] = useState('')
  const [forgotSent, setForgotSent] = useState(false)
  const [forgotLoading, setForgotLoading] = useState(false)
  const [forgotError, setForgotError] = useState('')

  if (isAuthenticated) return <Navigate to="/dashboard" />

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await authApi.login({ email, password })
      setAuth(res.data.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'შეცდომა შესვლისას')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="brand-auth-background relative min-h-screen overflow-hidden px-4 py-8">
      <div className="absolute inset-x-0 top-0 h-1.5 brand-topline" />
      <div className="pointer-events-none absolute -left-16 top-28 h-52 w-52 rounded-full border-[28px] border-primary-100/50" />
      <div className="pointer-events-none absolute -right-20 bottom-16 h-64 w-64 rounded-full border-[34px] border-accent-100/50" />

      <div className="relative mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-5xl items-center">
        <div className="grid w-full overflow-hidden rounded-3xl border border-brandgray-100 bg-white shadow-[0_30px_80px_-40px_rgba(16,95,125,0.45)] lg:grid-cols-[1.05fr_0.95fr]">
          <div className="relative hidden overflow-hidden bg-brandgray-700 p-12 text-white lg:flex lg:flex-col lg:justify-between">
            <div className="absolute inset-x-0 top-0 h-2 brand-topline" />
            <div className="absolute -bottom-24 -right-20 h-72 w-72 rounded-full bg-primary-500/15" />
            <div className="absolute bottom-16 right-20 h-32 w-32 rounded-full bg-accent-500/10" />

            <div>
              <div className="text-2xl font-bold tracking-tight text-white">Business OS</div>
              <div className="mt-1 text-xs font-medium uppercase tracking-[0.16em] text-primary-300">ქართული ბიზნესისთვის</div>
            </div>

            <div className="relative max-w-md">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary-300">ერთიანი სამუშაო გარემო</p>
              <h1 className="mt-4 text-4xl font-bold leading-tight">მართეთ ყოველდღიური ოპერაციები ერთი სისტემიდან.</h1>
              <div className="mt-8 space-y-3 text-sm text-white/75">
                {['შესყიდვები და მომწოდებლები', 'მარაგები და საწყობები', 'ფინანსური კონტროლი და ანგარიშგება'].map(item => (
                  <div key={item} className="flex items-center gap-3">
                    <CheckCircle2 size={18} className="text-accent-400" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            <p className="relative text-xs text-white/45">Business OS · ერთიანი სამუშაო გარემო</p>
          </div>

          <div className="p-7 sm:p-10 lg:p-12">
            <div className="mb-10 lg:hidden">
              <div className="text-xl font-bold text-brandgray-800">Business OS</div>
              <div className="mt-1 text-xs font-medium text-primary-700">ქართული ბიზნესისთვის</div>
            </div>
            <div className="mb-8">
              <p className="text-sm font-semibold text-primary-700">კეთილი იყოს თქვენი დაბრუნება</p>
              <h2 className="mt-2 text-3xl font-bold text-brandgray-900">ანგარიშზე შესვლა</h2>
              <p className="mt-2 text-sm text-brandgray-400">გამოიყენეთ თქვენი სამუშაო ელფოსტა და პაროლი.</p>
            </div>

            {error && <div className="mb-5 rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-brandgray-700">ელფოსტა</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="input h-11" placeholder="name@company.com" required />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-brandgray-700">პაროლი</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="input h-11" placeholder="••••••••" required />
              </div>

              <button type="submit" className="btn-primary flex h-11 w-full items-center justify-center gap-2" disabled={loading}>
                {loading ? 'შესვლა...' : <>შესვლა <ArrowRight size={17} /></>}
              </button>
            </form>

            <div className="mt-4 text-center">
              <button onClick={() => { setForgotOpen(true); setForgotEmail(email); setForgotSent(false); setForgotError('') }} className="text-sm text-primary-700 hover:text-primary-800 hover:underline">
                დაგავიწყდათ პაროლი?
              </button>
            </div>

            <p className="mt-7 text-center text-sm text-brandgray-400">
              არ გაქვთ ანგარიში?{' '}
              <Link to="/register" className="font-semibold text-primary-700 hover:text-primary-800 hover:underline">დარეგისტრირდით</Link>
            </p>
          </div>
        </div>
      </div>

      {/* Forgot Password Modal */}
      <Modal open={forgotOpen} onClose={() => setForgotOpen(false)} title="პაროლის აღდგენა" size="sm">
        {forgotSent ? (
          <div className="text-center py-4">
            <CheckCircle2 size={48} className="mx-auto text-green-500 mb-4" />
            <p className="text-sm text-gray-700">თუ ელფოსტა რეგისტრირებულია, პაროლის აღდგენის ინსტრუქცია გამოგეგზავნებათ.</p>
            <button onClick={() => setForgotOpen(false)} className="btn-primary mt-6">დახურვა</button>
          </div>
        ) : (
          <form onSubmit={async (e) => {
            e.preventDefault()
            setForgotLoading(true)
            setForgotError('')
            try {
              await authApi.forgotPassword(forgotEmail)
              setForgotSent(true)
            } catch (err: any) {
              setForgotError(err?.response?.data?.detail || 'შეცდომა')
            } finally {
              setForgotLoading(false)
            }
          }} className="space-y-4">
            <p className="text-sm text-gray-600">შეიყვანეთ თქვენი ელფოსტა და ჩვენ გამოგიგზავნით პაროლის აღდგენის ბმულს.</p>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-brandgray-700">ელფოსტა</label>
              <input type="email" value={forgotEmail} onChange={(e) => setForgotEmail(e.target.value)} className="input h-11" required />
            </div>
            {forgotError && <p className="text-sm text-red-600">{forgotError}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => setForgotOpen(false)} className="btn-secondary">გაუქმება</button>
              <button type="submit" className="btn-primary" disabled={forgotLoading}>
                {forgotLoading ? <><Loader2 size={16} className="animate-spin" /> გაგზავნა...</> : 'გაგზავნა'}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}
