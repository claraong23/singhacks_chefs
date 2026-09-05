import { afterEach, describe, expect, it, vi } from 'vitest'
import { createFollowTask, hasWriteToken, setWriteToken } from './api'

describe('hosted write token transport', () => {
  afterEach(() => { sessionStorage.clear(); vi.unstubAllGlobals() })

  it('adds a session-only bearer token to mutations', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ task: {} }), { status: 201 }))
    vi.stubGlobal('fetch', fetchMock); setWriteToken('demo-token')
    await createFollowTask({ role: 'rm' })
    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer demo-token')
  })

  it('clears the session token after an unauthorised mutation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"error":"Unauthorized"}', { status: 401, statusText: 'Unauthorized' })))
    setWriteToken('invalid-token')
    await expect(createFollowTask({ role: 'rm' })).rejects.toThrow('401')
    expect(hasWriteToken()).toBe(false)
  })
})
