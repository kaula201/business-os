// Optional UUID fields on HelpdeskTicketCreate. An empty select posts ""
// which Pydantic rejects with 422 uuid_parsing. Omit them instead.

export interface HelpdeskTicketFormInput {
  subject: string
  description: string
  priority: string
  client_id: string
  queue_id: string
  attachment_url: string
  assignee_id: string
  category: string
  ticket_type: string
  source_channel: string
  tags: string
}

const OPTIONAL_TEXT_FIELDS = [
  'description',
  'attachment_url',
  'category',
  'ticket_type',
  'source_channel',
] as const

const OPTIONAL_UUID_FIELDS = ['client_id', 'assignee_id', 'queue_id'] as const

export function helpdeskTicketCreateBody(form: HelpdeskTicketFormInput): Record<string, unknown> {
  const body: Record<string, unknown> = {
    subject: form.subject,
    priority: form.priority || 'medium',
  }

  for (const key of OPTIONAL_TEXT_FIELDS) {
    const value = form[key]
    if (value !== '') body[key] = value
  }

  for (const key of OPTIONAL_UUID_FIELDS) {
    const value = form[key].trim()
    if (value) body[key] = value
  }

  const tags = form.tags
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)
  if (tags.length) body.tags = tags

  return body
}
