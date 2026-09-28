import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { detailToText, apiErrorMessage } from './apiError.ts'
import { helpdeskTicketCreateBody } from './helpdeskForm.ts'

const emptyForm = {
  subject: 'Printer jam',
  description: '',
  priority: 'medium',
  client_id: '',
  queue_id: '',
  attachment_url: '',
  assignee_id: '',
  category: '',
  ticket_type: '',
  source_channel: 'email',
  tags: '',
}

describe('helpdeskTicketCreateBody', () => {
  it('omits empty optional uuid fields and blank strings', () => {
    const body = helpdeskTicketCreateBody(emptyForm)
    assert.deepEqual(body, {
      subject: 'Printer jam',
      priority: 'medium',
      source_channel: 'email',
    })
    assert.equal('client_id' in body, false)
    assert.equal('assignee_id' in body, false)
    assert.equal('queue_id' in body, false)
  })

  it('keeps selected uuid values and parsed tags', () => {
    const body = helpdeskTicketCreateBody({
      ...emptyForm,
      client_id: '11111111-1111-1111-1111-111111111111',
      assignee_id: '22222222-2222-2222-2222-222222222222',
      queue_id: '  ',
      tags: 'auth, urgent, ',
      description: 'paper stuck',
    })
    assert.equal(body.client_id, '11111111-1111-1111-1111-111111111111')
    assert.equal(body.assignee_id, '22222222-2222-2222-2222-222222222222')
    assert.equal('queue_id' in body, false)
    assert.deepEqual(body.tags, ['auth', 'urgent'])
    assert.equal(body.description, 'paper stuck')
  })
})

describe('api error text', () => {
  it('stringifies fastapi 422 uuid_parsing details', () => {
    const detail = [
      {
        type: 'uuid_parsing',
        loc: ['body', 'client_id'],
        msg: 'Input should be a valid UUID, invalid length',
        input: '',
      },
      {
        type: 'uuid_parsing',
        loc: ['body', 'assignee_id'],
        msg: 'Input should be a valid UUID, invalid length',
        input: '',
      },
    ]
    const text = detailToText(detail)
    assert.equal(typeof text, 'string')
    assert.match(text, /client_id: Input should be a valid UUID/)
    assert.match(text, /assignee_id: Input should be a valid UUID/)

    const message = apiErrorMessage({ response: { data: { detail } } }, 'შეცდომა')
    assert.equal(message, text)
    assert.equal(typeof message, 'string')
  })

  it('keeps string details and falls back when detail is missing', () => {
    assert.equal(apiErrorMessage({ response: { data: { detail: 'ტიკეტი არ მოიძებნა' } } }, 'შეცდომა'), 'ტიკეტი არ მოიძებნა')
    assert.equal(apiErrorMessage({}, 'შეცდომა'), 'შეცდომა')
  })

  it('renders a {message} object as text', () => {
    assert.equal(detailToText({ message: 'validation failed' }), 'validation failed')
  })
})
