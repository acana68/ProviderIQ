import { describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  DEFAULT_TIMEOUT_MS,
  apiGet,
  apiPost,
  isAbortError,
} from '../src/services/apiClient'
import { errorBody, hangingFetch, jsonResponse, mockFetch } from './utils'

/** The rejection value of a promise that must reject. */
async function rejectionOf(promise: Promise<unknown>): Promise<unknown> {
  return promise.then(
    () => {
      throw new Error('expected the promise to reject')
    },
    (error: unknown) => error,
  )
}

describe('apiClient', () => {
  it('returns the parsed JSON body on success', async () => {
    const fetchSpy = mockFetch().mockResolvedValue(jsonResponse([{ slug: 'cardiology' }]))

    const data = await apiGet<{ slug: string }[]>('/specialties')

    expect(data).toEqual([{ slug: 'cardiology' }])
    const [url, init] = fetchSpy.mock.calls[0]!
    expect(url).toBe('/api/v1/specialties')
    expect(init?.method).toBe('GET')
    expect(init?.signal).toBeInstanceOf(AbortSignal)
  })

  it('posts JSON', async () => {
    const fetchSpy = mockFetch().mockResolvedValue(jsonResponse({ items: [] }))

    await apiPost('/search', { specialty: 'cardiology' })

    const [url, init] = fetchSpy.mock.calls[0]!
    expect(url).toBe('/api/v1/search')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe('{"specialty":"cardiology"}')
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json')
  })

  it('turns the backend error shape into an ApiError', async () => {
    const details = [{ field: 'page_size', message: 'Input should be less than or equal to 50' }]
    mockFetch().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Request validation failed',
            request_id: 'req-422',
            details,
          },
        },
        { status: 422 },
      ),
    )

    const error = await rejectionOf(apiPost('/search', { page_size: 51 }))

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 422,
      code: 'VALIDATION_ERROR',
      message: 'Request validation failed',
      requestId: 'req-422',
      details,
    })
  })

  it('falls back to the X-Request-ID header for the request ID', async () => {
    mockFetch().mockResolvedValue(
      jsonResponse(errorBody('NOT_FOUND', 'Not Found', null), {
        status: 404,
        headers: { 'X-Request-ID': 'req-from-header' },
      }),
    )

    const error = await rejectionOf(apiGet('/nope'))

    expect(error).toMatchObject({ status: 404, code: 'NOT_FOUND', requestId: 'req-from-header' })
  })

  it('reports a network failure as NETWORK_ERROR', async () => {
    mockFetch().mockRejectedValue(new TypeError('Failed to fetch'))

    const error = await rejectionOf(apiGet('/specialties'))

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 0, code: 'NETWORK_ERROR', requestId: null })
  })

  it('handles a non-JSON error body', async () => {
    mockFetch().mockResolvedValue(
      new Response('<html><body>502 Bad Gateway</body></html>', {
        status: 502,
        headers: { 'Content-Type': 'text/html', 'X-Request-ID': 'req-502' },
      }),
    )

    const error = await rejectionOf(apiGet('/specialties'))

    expect(error).toMatchObject({ status: 502, code: 'UNKNOWN_ERROR', requestId: 'req-502' })
    expect((error as ApiError).message).toContain('502')
  })

  it('handles JSON that is not the error shape', async () => {
    mockFetch().mockResolvedValue(jsonResponse({ detail: 'Not Found' }, { status: 404 }))

    const error = await rejectionOf(apiGet('/nope'))

    expect(error).toMatchObject({ status: 404, code: 'UNKNOWN_ERROR' })
  })

  it('handles a success response whose body is not JSON', async () => {
    mockFetch().mockResolvedValue(new Response('not json', { status: 200 }))

    const error = await rejectionOf(apiGet('/specialties'))

    expect(error).toMatchObject({ status: 200, code: 'UNKNOWN_ERROR' })
  })

  it('times out after 10 seconds with TIMEOUT', async () => {
    vi.useFakeTimers()
    mockFetch().mockImplementation(hangingFetch)
    let settled = false
    const result = rejectionOf(apiGet('/slow')).finally(() => {
      settled = true
    })

    await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS - 1)
    expect(settled).toBe(false)
    await vi.advanceTimersByTimeAsync(1)

    const error = await result
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 0, code: 'TIMEOUT' })
  })

  it("passes a caller's cancellation through as an AbortError, not an ApiError", async () => {
    mockFetch().mockImplementation(hangingFetch)
    const controller = new AbortController()
    const result = rejectionOf(apiGet('/specialties', { signal: controller.signal }))

    controller.abort()

    const error = await result
    expect(error).not.toBeInstanceOf(ApiError)
    expect(isAbortError(error)).toBe(true)
  })
})
