import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Building2, Users, Package, CreditCard, Check, X, Loader2, RefreshCw } from 'lucide-react'

import { bankingApi, companyApi, productsApi, usersApi } from '../services/api'
import { useAuthStore } from '../store/authStore'
import i18n from '../i18n'

const steps = [
  { id: 'company', icon: Building2, title: 'კომპანია', desc: 'კომპანიის დეტალები და ვალუტა' },
  { id: 'team', icon: Users, title: 'გუნდი', desc: 'მომხმარებლები და როლები' },
  { id: 'products', icon: Package, title: 'პროდუქტები', desc: 'პროდუქტები და მარაგები' },
  { id: 'finance', icon: CreditCard, title: 'ფინანსები', desc: 'საბანკო ანგარიშები და გადახდები' },
]

const inputClass = 'input w-full'

function normalizeError(error: any, fallback: string): string {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => typeof item === 'string' ? item : item?.msg || fallback).join(' · ')
  }
  if (typeof detail === 'string') return detail
  if (typeof error?.message === 'string') return error.message
  return fallback
}

export default function OnboardingWizard() {
  const { t } = useTranslation()
  const user = useAuthStore((state) => state.user)
  const storageKey = useMemo(
    () => user ? `bos_onboarding:${user.company_id}:${user.id}` : '',
    [user?.company_id, user?.id],
  )
  const [step, setStep] = useState(0)
  const [open, setOpen] = useState(false)
  const [completed, setCompleted] = useState<boolean[]>([false, false, false, false])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [companyLoading, setCompanyLoading] = useState(false)
  const [companyReady, setCompanyReady] = useState(false)
  const [companyReload, setCompanyReload] = useState(0)
  const [company, setCompany] = useState({ name: '', address: '', phone: '', email: '', currency: 'GEL' })
  const [team, setTeam] = useState({ full_name: '', email: '', role: 'employee' })
  const [product, setProduct] = useState({ sku: '', name: '', sale_price: 0, current_stock: 0, unit: 'ცალი' })
  const [bank, setBank] = useState({ bank_name: '', account_name: '', iban: '', currency: 'GEL' })

  useEffect(() => {
    setOpen(Boolean(user?.role === 'admin' && storageKey && localStorage.getItem(storageKey) !== 'done'))
  }, [storageKey, user?.role])

  useEffect(() => {
    if (!open || user?.role !== 'admin') return
    let cancelled = false
    setCompanyLoading(true)
    setCompanyReady(false)
    setError('')
    companyApi.getMyCompany().then((response) => {
      if (cancelled) return
      const data = response.data.data
      setCompany({
        name: data.name || '',
        address: data.address || '',
        phone: data.phone || '',
        email: data.email || '',
        currency: data.currency || 'GEL',
      })
      setCompanyReady(true)
    }).catch((err: any) => {
      if (!cancelled) setError(normalizeError(err, i18n.t('კომპანიის მონაცემების ჩატვირთვა ვერ მოხერხდა')))
    }).finally(() => {
      if (!cancelled) setCompanyLoading(false)
    })
    return () => { cancelled = true }
  }, [companyReload, open, user?.role])

  const finish = () => {
    if (storageKey) localStorage.setItem(storageKey, 'done')
    setOpen(false)
  }

  const next = () => {
    setError('')
    if (step < steps.length - 1) setStep(step + 1)
    else finish()
  }

  const skip = () => next()

  const save = async () => {
    setSaving(true)
    setError('')
    try {
      if (step === 0) {
        if (!companyReady) throw new Error(t('ჯერ კომპანიის მონაცემები ჩაიტვირთოს'))
        if (!company.name.trim()) throw new Error(t('კომპანიის სახელი სავალდებულოა'))
        await companyApi.updateMyCompany(company)
      } else if (step === 1) {
        if (!team.full_name.trim() || !team.email.trim()) throw new Error(t('სახელი და ელფოსტა სავალდებულოა'))
        await usersApi.invite(team)
      } else if (step === 2) {
        if (!product.sku.trim() || !product.name.trim()) throw new Error(t('SKU და პროდუქტის სახელი სავალდებულოა'))
        await productsApi.create(product)
      } else {
        if (!bank.bank_name.trim() || !bank.account_name.trim() || !bank.iban.trim()) throw new Error(t('ბანკი, ანგარიშის სახელი და IBAN სავალდებულოა'))
        await bankingApi.createAccount(bank)
      }
      setCompleted((current) => current.map((value, index) => index === step ? true : value))
      next()
    } catch (err: any) {
      setError(normalizeError(err, t('შენახვა ვერ მოხერხდა')))
    } finally {
      setSaving(false)
    }
  }

  if (user?.role !== 'admin' || !open) return null
  const CurrentIcon = steps[step].icon

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/55 p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-white dark:bg-dark-200 shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-dark-50">
          <div>
            <h2 className="text-xl font-bold text-brandgray-900 dark:text-gray-100">{t('Business OS-ის გამართვა')}</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">{t('შეავსეთ აუცილებელი მონაცემები და დაიწყეთ მუშაობა')}</p>
          </div>
          <button onClick={finish} className="p-1.5 hover:bg-gray-100 dark:hover:bg-dark-100 rounded-lg text-gray-400" aria-label={t('დახურვა')}>
            <X size={20} />
          </button>
        </div>

        <div className="grid grid-cols-4 gap-2 px-6 pt-5">
          {steps.map((item, index) => (
            <button key={item.id} onClick={() => { setStep(index); setError('') }} className="text-left">
              <div className={`h-1.5 rounded-full ${completed[index] ? 'bg-green-500' : index === step ? 'bg-primary-600' : 'bg-gray-200 dark:bg-dark-50'}`} />
              <div className={`mt-2 text-xs font-medium ${index === step ? 'text-primary-700 dark:text-primary-300' : 'text-gray-500 dark:text-gray-400'}`}>
                {completed[index] ? '✓ ' : ''}{t(item.title)}
              </div>
            </button>
          ))}
        </div>

        <div className="px-6 py-6 min-h-[350px]">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-11 h-11 rounded-xl bg-primary-50 dark:bg-primary-900/20 flex items-center justify-center text-primary-600">
              <CurrentIcon size={22} />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-brandgray-900 dark:text-gray-100">{t(steps[step].title)}</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">{t(steps[step].desc)}</p>
            </div>
          </div>

          {step === 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {companyLoading && <div className="md:col-span-2 flex items-center gap-2 rounded-lg bg-primary-50 dark:bg-primary-900/20 px-4 py-3 text-sm text-primary-700 dark:text-primary-300"><Loader2 size={16} className="animate-spin" />{t('კომპანიის მონაცემები იტვირთება')}</div>}
              <label className="md:col-span-2 text-sm font-medium text-gray-700 dark:text-gray-300">{t('კომპანიის სახელი')}<input disabled={!companyReady} className={`${inputClass} mt-1.5`} value={company.name} onChange={(e) => setCompany({ ...company, name: e.target.value })} /></label>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('ელფოსტა')}<input disabled={!companyReady} type="email" className={`${inputClass} mt-1.5`} value={company.email} onChange={(e) => setCompany({ ...company, email: e.target.value })} /></label>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('ტელეფონი')}<input disabled={!companyReady} className={`${inputClass} mt-1.5`} value={company.phone} onChange={(e) => setCompany({ ...company, phone: e.target.value })} /></label>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('მისამართი')}<input disabled={!companyReady} className={`${inputClass} mt-1.5`} value={company.address} onChange={(e) => setCompany({ ...company, address: e.target.value })} /></label>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('ვალუტა')}<select disabled={!companyReady} className={`${inputClass} mt-1.5`} value={company.currency} onChange={(e) => setCompany({ ...company, currency: e.target.value })}><option value="GEL">GEL</option><option value="USD">USD</option><option value="EUR">EUR</option></select></label>
              {!companyLoading && !companyReady && <button type="button" onClick={() => setCompanyReload((value) => value + 1)} className="md:col-span-2 justify-self-start inline-flex items-center gap-2 text-sm font-medium text-primary-700 dark:text-primary-300"><RefreshCw size={15} />{t('ხელახლა ცდა')}</button>}
            </div>
          )}

          {step === 1 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('სახელი და გვარი')}<input className={`${inputClass} mt-1.5`} value={team.full_name} onChange={(e) => setTeam({ ...team, full_name: e.target.value })} /></label>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('ელფოსტა')}<input type="email" className={`${inputClass} mt-1.5`} value={team.email} onChange={(e) => setTeam({ ...team, email: e.target.value })} /></label>
              <label className="md:col-span-2 text-sm font-medium text-gray-700 dark:text-gray-300">{t('როლი')}<select className={`${inputClass} mt-1.5`} value={team.role} onChange={(e) => setTeam({ ...team, role: e.target.value })}><option value="employee">employee</option><option value="manager">manager</option><option value="accountant">accountant</option><option value="admin">admin</option></select></label>
            </div>
          )}

          {step === 2 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">SKU<input className={`${inputClass} mt-1.5`} value={product.sku} onChange={(e) => setProduct({ ...product, sku: e.target.value })} /></label>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('პროდუქტის სახელი')}<input className={`${inputClass} mt-1.5`} value={product.name} onChange={(e) => setProduct({ ...product, name: e.target.value })} /></label>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('გასაყიდი ფასი')}<input type="number" min="0" step="0.01" className={`${inputClass} mt-1.5`} value={product.sale_price} onChange={(e) => setProduct({ ...product, sale_price: Number(e.target.value) })} /></label>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('საწყისი მარაგი')}<input type="number" min="0" step="0.001" className={`${inputClass} mt-1.5`} value={product.current_stock} onChange={(e) => setProduct({ ...product, current_stock: Number(e.target.value) })} /></label>
              <label className="md:col-span-2 text-sm font-medium text-gray-700 dark:text-gray-300">{t('ერთეული')}<select className={`${inputClass} mt-1.5`} value={product.unit} onChange={(e) => setProduct({ ...product, unit: e.target.value })}><option value="ცალი">{t('ცალი')}</option><option value="კგ">{t('კგ')}</option><option value="ლიტრი">{t('ლიტრი')}</option><option value="მეტრი">{t('მეტრი')}</option></select></label>
            </div>
          )}

          {step === 3 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('ბანკი')}<input className={`${inputClass} mt-1.5`} placeholder="TBC / BOG" value={bank.bank_name} onChange={(e) => setBank({ ...bank, bank_name: e.target.value })} /></label>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{t('ანგარიშის სახელი')}<input className={`${inputClass} mt-1.5`} value={bank.account_name} onChange={(e) => setBank({ ...bank, account_name: e.target.value })} /></label>
              <label className="md:col-span-2 text-sm font-medium text-gray-700 dark:text-gray-300">IBAN<input className={`${inputClass} mt-1.5 font-mono`} value={bank.iban} onChange={(e) => setBank({ ...bank, iban: e.target.value.toUpperCase() })} /></label>
              <label className="md:col-span-2 text-sm font-medium text-gray-700 dark:text-gray-300">{t('ვალუტა')}<select className={`${inputClass} mt-1.5`} value={bank.currency} onChange={(e) => setBank({ ...bank, currency: e.target.value })}><option value="GEL">GEL</option><option value="USD">USD</option><option value="EUR">EUR</option></select></label>
            </div>
          )}

          {error && <div className="mt-4 rounded-lg bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</div>}
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100 dark:border-dark-50 bg-gray-50/60 dark:bg-dark-100/40">
          <button onClick={skip} className="px-3 py-2 text-sm font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400">{t('გამოტოვება')}</button>
          <div className="flex items-center gap-2">
            {step > 0 && <button onClick={() => { setStep(step - 1); setError('') }} className="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-300">{t('უკან')}</button>}
            <button onClick={save} disabled={saving || (step === 0 && !companyReady)} className="px-5 py-2.5 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 disabled:opacity-60 flex items-center gap-2">
              {saving ? <Loader2 size={16} className="animate-spin" /> : step === steps.length - 1 ? <Check size={16} /> : null}
              {step === steps.length - 1 ? t('შენახვა და დასრულება') : t('შენახვა და შემდეგი')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
