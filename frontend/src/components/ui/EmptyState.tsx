import { FileQuestion, Plus, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

interface EmptyStateProps {
  title?: string
  message?: string
  icon?: React.ReactNode
  actionLabel?: string
  actionTo?: string
  onAction?: () => void
  secondaryLabel?: string
  secondaryTo?: string
}

export default function EmptyState({
  title = 'მონაცემები არ არის',
  message = 'ამ გვერდზე ჯერ არაფერია. დაიწყეთ ახალი ჩანაწერის დამატებით.',
  icon,
  actionLabel,
  actionTo,
  onAction,
  secondaryLabel,
  secondaryTo,
}: EmptyStateProps) {
  const navigate = useNavigate()

  return (
    <div className="card" aria-label="ცარიელი გვერდი">
      <div className="p-12 text-center">
        <div className="flex justify-center mb-4 text-gray-300 dark:text-gray-600">
          {icon || <FileQuestion size={48} />}
        </div>
        <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-200 mb-2">{title}</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto mb-6">{message}</p>
        <div className="flex items-center justify-center gap-3 flex-wrap">
          {actionLabel && (actionTo || onAction) && (
            <button
              onClick={() => {
                if (onAction) onAction()
                else if (actionTo) navigate(actionTo)
              }}
              className="btn btn-primary inline-flex items-center gap-2"
            >
              <Plus size={16} />
              {actionLabel}
            </button>
          )}
          {secondaryLabel && secondaryTo && (
            <button
              onClick={() => navigate(secondaryTo)}
              className="btn btn-secondary inline-flex items-center gap-2"
            >
              {secondaryLabel}
              <ArrowRight size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
