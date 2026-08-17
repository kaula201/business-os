import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Building2, Users, Package, CreditCard, Check, X } from 'lucide-react'

const steps = [
  { id: 'company', icon: Building2, title: 'კომპანია', desc: 'კომპანიის დეტალები და ვალუტა' },
  { id: 'team', icon: Users, title: 'გუნდი', desc: 'მომხმარებლები და როლები' },
  { id: 'products', icon: Package, title: 'პროდუქტები', desc: 'პროდუქტები და მარაგები' },
  { id: 'finance', icon: CreditCard, title: 'ფინანსები', desc: 'საბანკო ანგარიშები და გადახდები' },
]

export default function OnboardingWizard() {
  const { t } = useTranslation()
  const [step, setStep] = useState(0)
  const [open, setOpen] = useState(() => localStorage.getItem('bos_onboarding') !== 'done')

  const finish = () => {
    localStorage.setItem('bos_onboarding', 'done')
    setOpen(false)
  }

  if (!open) return null

  return (
    <div className="pointer-events-none fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
      <div className="pointer-events-auto w-full max-w-lg rounded-2xl bg-white dark:bg-dark-200 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-dark-50">
          <h2 className="text-lg font-bold text-brandgray-900 dark:text-gray-100">{t('კეთილი იყოს თქვენი მობრძანება!')}</h2>
          <button onClick={finish} className="p-1.5 hover:bg-gray-100 dark:hover:bg-dark-100 rounded-lg text-gray-400" aria-label={t('დახურვა')}>
            <X size={18} />
          </button>
        </div>

        {/* Steps indicator */}
        <div className="flex gap-2 px-6 pt-4">
          {steps.map((s, i) => (
            <div key={s.id} className={`h-1.5 flex-1 rounded-full ${i <= step ? 'bg-primary-600' : 'bg-gray-200 dark:bg-dark-50'}`} />
          ))}
        </div>

        {/* Step content */}
        <div className="px-6 py-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-900/20 flex items-center justify-center text-primary-600">
              {(() => { const Icon = steps[step].icon; return <Icon size={20} /> })()}
            </div>
            <div>
              <h3 className="font-semibold text-brandgray-900 dark:text-gray-100">{t(steps[step].title)}</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">{t(steps[step].desc)}</p>
            </div>
          </div>

          <div className="rounded-xl border border-dashed border-gray-200 dark:border-dark-50 p-4 text-sm text-gray-500 dark:text-gray-400">
            {step === 0 && t('შეავსეთ კომპანიის დეტალები პარამეტრებში — სახელი, საიდენტიფიკაციო კოდი, ვალუტა (GEL).')}
            {step === 1 && t('დაამატეთ გუნდის წევრები და მიანიჭეთ როლები — admin, manager, employee, accountant.')}
            {step === 2 && t('შეიყვანეთ პროდუქტები და საწყისი მარაგები — SKU, ფასები, კატეგორიები.')}
            {step === 3 && t('დააკავშირეთ საბანკო ანგარიშები (TBC/BOG) და გადახდის მეთოდები.')}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100 dark:border-dark-50">
          <button
            onClick={() => setStep(Math.max(0, step - 1))}
            disabled={step === 0}
            className="px-4 py-2 text-sm font-medium text-gray-500 hover:text-gray-700 disabled:opacity-40 dark:text-gray-400"
          >
            {t('უკან')}
          </button>
          {step < steps.length - 1 ? (
            <button onClick={() => setStep(step + 1)} className="px-5 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700">
              {t('შემდეგი')}
            </button>
          ) : (
            <button onClick={finish} className="px-5 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 flex items-center gap-2">
              <Check size={16} /> {t('დასრულება')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
