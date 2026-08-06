import { useTranslation } from 'react-i18next'
import { Globe } from 'lucide-react'

export default function LanguageSwitcher() {
  const { i18n } = useTranslation()
  const lang = i18n.language || 'ka'

  return (
    <button
      onClick={() => i18n.changeLanguage(lang === 'ka' ? 'en' : 'ka')}
      className="p-2 hover:bg-gray-100 rounded-lg dark:hover:bg-dark-100 flex items-center gap-1"
      aria-label="ენის შეცვლა / Change language"
      title="ქართული / English"
    >
      <Globe size={18} className="text-gray-500 dark:text-gray-400" />
      <span className="text-xs font-semibold text-gray-600 dark:text-gray-300">
        {lang === 'ka' ? 'EN' : 'ქარ'}
      </span>
    </button>
  )
}
