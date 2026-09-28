// Turn API error payloads into a string safe to render as a React child.
// FastAPI 422 responses put a list of objects in `detail`; rendering that
// list directly crashes with "Objects are not valid as a React child".

type ValidationItem = {
  msg?: unknown
  loc?: unknown
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = readDetail(error)
  const text = detailToText(detail)
  return text || fallback
}

function readDetail(error: unknown): unknown {
  if (!error || typeof error !== 'object') return undefined
  const response = (error as { response?: { data?: { detail?: unknown } } }).response
  return response?.data?.detail
}

export function detailToText(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (typeof detail === 'number' || typeof detail === 'boolean') return String(detail)
  if (Array.isArray(detail)) {
    return detail.map(validationItemText).filter(Boolean).join(' · ')
  }
  if (detail && typeof detail === 'object') {
    const rec = detail as ValidationItem & { message?: unknown }
    if (typeof rec.msg === 'string' && rec.msg) return rec.msg
    if (typeof rec.message === 'string' && rec.message) return rec.message
    try {
      return JSON.stringify(detail)
    } catch {
      return ''
    }
  }
  return ''
}

function validationItemText(item: unknown): string {
  if (typeof item === 'string') return item
  if (!item || typeof item !== 'object') return ''
  const rec = item as ValidationItem
  const msg = typeof rec.msg === 'string' ? rec.msg : ''
  const loc = Array.isArray(rec.loc)
    ? rec.loc
        .filter((part) => part !== 'body' && part !== 'query' && part !== 'path')
        .map(String)
        .join('.')
    : ''
  if (loc && msg) return `${loc}: ${msg}`
  return msg || loc
}
