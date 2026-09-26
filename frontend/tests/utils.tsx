import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import { App } from '../src/App'

/** A JSON fetch Response, like the API's. */
export function jsonResponse(
  body: unknown,
  { status = 200, headers = {} }: { status?: number; headers?: Record<string, string> } = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

/** The backend's error shape. */
export function errorBody(code: string, message: string, requestId: string | null = 'req-123') {
  return { error: { code, message, request_id: requestId } }
}

export function mockFetch() {
  return vi.spyOn(globalThis, 'fetch')
}

/**
 * A fetch that never answers, but rejects with an AbortError when its signal aborts, like
 * the real one.
 */
export function hangingFetch(_input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return new Promise((_resolve, reject) => {
    init?.signal?.addEventListener('abort', () =>
      reject(new DOMException('The operation was aborted.', 'AbortError')),
    )
  })
}

/** The whole app at a URL, with an in-memory router instead of the browser's. */
export function renderAppAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}
