import { useId } from 'react'

interface FormFieldProps {
  label: string
  error?: string
  required?: boolean
  children: React.ReactNode
  name?: string
}

export default function FormField({ label, error, required, children, name }: FormFieldProps) {
  const autoId = useId()
  const fieldId = name || autoId

  return (
    <div className="space-y-1">
      <label htmlFor={fieldId} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
        {label}
        {required && <span className="text-red-500 ml-1" aria-hidden="true">*</span>}
      </label>
      <div id={fieldId}>
        {children}
      </div>
      {error && <p className="text-xs text-red-600 mt-1 dark:text-red-400" role="alert">{error}</p>}
    </div>
  )
}

// Select helper
interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  options: { value: string; label: string }[]
  placeholder?: string
}

export function Select({ options, placeholder, className = '', ...props }: SelectProps) {
  return (
    <select
      {...props}
      className={`input ${className}`}
    >
      {placeholder && <option value="">{placeholder}</option>}
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  )
}
