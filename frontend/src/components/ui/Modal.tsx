import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
}

export default function Modal({ open, onClose, title, children, size = 'md' }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [open])

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (open) window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [open, onClose])

  if (!open) return null

  const sizeClasses: Record<string, string> = {
    sm: 'max-w-sm',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
    full: 'max-w-7xl',
  }

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-end justify-center p-2 sm:p-4 sm:items-center bg-black/50"
      onClick={(e) => e.target === overlayRef.current && onClose()}
    >
      <div className={`bg-white rounded-t-xl sm:rounded-xl shadow-xl w-full ${sizeClasses[size]} max-h-[92vh] sm:max-h-[90vh] flex flex-col overflow-hidden dark:bg-dark-200 dark:border dark:border-dark-50`}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-gray-200 dark:border-dark-50 shrink-0">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 truncate">{title}</h2>
          <button aria-label={`${title} — დახურვა`} onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg transition-colors dark:hover:bg-dark-100 shrink-0 ml-2">
            <X size={20} className="text-gray-500 dark:text-gray-400" />
          </button>
        </div>
        {/* Body — horizontal fallback for wide tables on mobile */}
        <div className="flex-1 overflow-y-auto overflow-x-auto px-4 sm:px-6 py-4">
          {children}
        </div>
      </div>
    </div>
  )
}