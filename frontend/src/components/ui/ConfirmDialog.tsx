import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'

interface ConfirmDialogProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void | null | undefined
  title: string
  message: string
  confirmLabel?: string
  confirmVariant?: 'danger' | 'warning'
  variant?: string  // backward compat
  loading?: boolean  // backward compat
  reason?: boolean
}

export default function ConfirmDialog({
  open, onClose, onConfirm, title, message,
  confirmLabel = 'დადასტურება', confirmVariant = 'danger',
  reason = false,
}: ConfirmDialogProps) {
  const [inputReason, setInputReason] = useState('')
  const [loading, setLoading] = useState(false)

  if (!open) return null

  const handleConfirm = async () => {
    if (reason && !inputReason.trim()) return
    setLoading(true)
    try {
      await onConfirm()
    } finally {
      setLoading(false)
      onClose()
    }
  }

  const variantStyles = confirmVariant === 'danger'
    ? 'bg-red-600 hover:bg-red-700 text-white'
    : 'bg-amber-600 hover:bg-amber-700 text-white'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md dark:bg-dark-200 dark:border dark:border-dark-50" role="alertdialog" aria-labelledby="confirm-title" aria-describedby="confirm-message">
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className={`p-2 rounded-full ${confirmVariant === 'danger' ? 'bg-red-100 dark:bg-red-900/30' : 'bg-amber-100 dark:bg-amber-900/30'}`}>
              <AlertTriangle size={24} className={confirmVariant === 'danger' ? 'text-red-600' : 'text-amber-600'} />
            </div>
            <h3 id="confirm-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
          </div>
          <p id="confirm-message" className="text-sm text-gray-600 dark:text-gray-400 mb-4">{message}</p>

          {reason && (
            <div className="mb-4">
              <label htmlFor="confirm-reason" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">მიზეზი <span className="text-red-500">*</span></label>
              <textarea
                id="confirm-reason"
                value={inputReason}
                onChange={(e) => setInputReason(e.target.value)}
                className="input w-full"
                rows={2}
                placeholder="აღწერეთ მოქმედების მიზეზი"
                aria-required="true"
              />
            </div>
          )}

          <div className="flex justify-end gap-3">
            <button onClick={onClose} className="btn btn-secondary" disabled={loading}>გაუქმება</button>
            <button
              onClick={handleConfirm}
              className={`btn ${variantStyles}`}
              disabled={loading || (reason && !inputReason.trim())}
            >
              {loading ? 'მიმდინარეობს...' : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
