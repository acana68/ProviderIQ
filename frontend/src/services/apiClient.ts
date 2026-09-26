import type { ErrorDetail, ErrorResponse } from '../types/api'

/** Always relative: the dev server proxies it, and production serves it from the same domain. */
export const API_BASE = '/api/v1'
export const DEFAULT_TIMEOUT_MS = 10_000

/** Codes for failures that never got an API error body. The API's own codes are strings too. */
export const CLIENT_ERROR_CODES = {
  network: 'NETWORK_ERROR',
  timeout: 'TIMEOUT',
  unknown: 'UNKNOWN_ERROR',
  /** 429, whether or not the body had the API's error shape (the API says RATE_LIMITED too). */
  rateLimited: 'RATE_LIMITED',
  /** 502/503/504 without an API error body, e.g. from a proxy while the backend restarts. */
  unavailable: 'SERVICE_UNAVAILABLE',
} as const

export const UNAVAILABLE_MESSAGE = "Can't reach the server right now. Please try again in a moment."
const GATEWAY_STATUSES = new Set([502, 503, 504])

interface ApiErrorInit {
  /** HTTP status, or 0 when no response arrived (network failure, timeout). */
  status: number
  code: string
  message: string
  requestId?: string | null
  details?: ErrorDetail[]
  retryAfterSeconds?: number | null
}

/** Every failed API call rejects with one of these (except caller cancellation). */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string | null
  readonly details: ErrorDetail[]
  /** From Retry-After on a 429: how long to wait before trying again. */
  readonly retryAfterSeconds: number | null

  constructor({
    status,
    code,
    message,
    requestId = null,
    details = [],
    retryAfterSeconds = null,
  }: ApiErrorInit) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
    this.details = details
    this.retryAfterSeconds = retryAfterSeconds
  }
}

export interface RequestOptions {
  /** Cancels the request; the promise then rejects with the signal's AbortError. */
  signal?: AbortSignal
  timeoutMs?: number
}

export function apiGet<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return request<T>('GET', path, undefined, options)
}

export function apiPost<T>(path: string, body: unknown, options: RequestOptions = {}): Promise<T> {
  return request<T>('POST', path, body, options)
}

/** True for a request cancelled by its caller (e.g. a component unmounting). */
export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

/** Any thrown value as an ApiError, for code that just needs something to display. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  return new ApiError({
    status: 0,
    code: CLIENT_ERROR_CODES.unknown,
    message: 'Something went wrong.',
  })
}

async function request<T>(
  method: 'GET' | 'POST',
  path: string,
  body: unknown,
  { signal, timeoutMs = DEFAULT_TIMEOUT_MS }: RequestOptions,
): Promise<T> {
  // One controller for both the caller's signal and our timeout, so either cancels fetch.
  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  const forwardAbort = () => controller.abort(signal?.reason)
  if (signal?.aborted) forwardAbort()
  signal?.addEventListener('abort', forwardAbort)

  try {
    let response: Response
    try {
      response = await fetch(`${API_BASE}${path}`, {
        method,
        headers: {
          Accept: 'application/json',
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      })
    } catch (error) {
      throw noResponseError(error, timedOut, signal)
    }

    if (!response.ok) {
      throw await errorFromResponse(response)
    }
    try {
      return (await response.json()) as T
    } catch (error) {
      // The body is read under the same timeout, so an abort can land here too.
      if (timedOut || signal?.aborted) throw noResponseError(error, timedOut, signal)
      throw new ApiError({
        status: response.status,
        code: CLIENT_ERROR_CODES.unknown,
        message: 'The server sent a response that could not be read.',
        requestId: response.headers.get('X-Request-ID'),
      })
    }
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', forwardAbort)
  }
}

function noResponseError(error: unknown, timedOut: boolean, signal?: AbortSignal): unknown {
  if (timedOut) {
    return new ApiError({
      status: 0,
      code: CLIENT_ERROR_CODES.timeout,
      message: 'The server took too long to respond. Please try again.',
    })
  }
  if (signal?.aborted) {
    // Cancelled by the caller: pass the AbortError through so it can be ignored.
    return error
  }
  return new ApiError({
    status: 0,
    code: CLIENT_ERROR_CODES.network,
    message: "Couldn't reach the server. Check your connection and try again.",
  })
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  const headerRequestId = response.headers.get('X-Request-ID')
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    // Not JSON: e.g. an HTML error page from a proxy in front of the API.
  }
  const apiError = isErrorResponse(body) ? body.error : null
  const common = {
    status: response.status,
    requestId: apiError?.request_id ?? headerRequestId,
    details: apiError?.details ?? [],
  }

  if (response.status === 429) {
    const retryAfterSeconds = parseRetryAfter(response.headers.get('Retry-After'))
    return new ApiError({
      ...common,
      code: CLIENT_ERROR_CODES.rateLimited,
      message: rateLimitMessage(retryAfterSeconds),
      retryAfterSeconds,
    })
  }
  if (GATEWAY_STATUSES.has(response.status)) {
    // Whatever the body says, the useful message is the same: the backend is unreachable.
    return new ApiError({
      ...common,
      code: apiError?.code ?? CLIENT_ERROR_CODES.unavailable,
      message: UNAVAILABLE_MESSAGE,
    })
  }
  if (apiError) {
    return new ApiError({ ...common, code: apiError.code, message: apiError.message })
  }
  return new ApiError({
    ...common,
    code: CLIENT_ERROR_CODES.unknown,
    message: `Unexpected response from the server (HTTP ${response.status}).`,
  })
}

/** Retry-After is either delay-seconds ("30") or an HTTP date. Null if missing or invalid. */
export function parseRetryAfter(value: string | null, now: number = Date.now()): number | null {
  const trimmed = value?.trim()
  if (!trimmed) return null
  if (/^\d+$/.test(trimmed)) return Number(trimmed)
  // An HTTP date always names the day and month; without letters, Date.parse would still
  // accept junk like "-5" or "1.5" as a date.
  if (!/[a-z]/i.test(trimmed)) return null
  const date = Date.parse(trimmed)
  return Number.isNaN(date) ? null : Math.max(0, Math.ceil((date - now) / 1000))
}

function rateLimitMessage(seconds: number | null): string {
  if (seconds === null) return 'Too many requests. Please wait a moment and try again.'
  return `Too many requests. Please wait ${seconds} second${seconds === 1 ? '' : 's'}.`
}

function isErrorResponse(body: unknown): body is ErrorResponse {
  if (typeof body !== 'object' || body === null || !('error' in body)) return false
  const error = (body as { error: unknown }).error
  return (
    typeof error === 'object' &&
    error !== null &&
    typeof (error as { code?: unknown }).code === 'string' &&
    typeof (error as { message?: unknown }).message === 'string'
  )
}
