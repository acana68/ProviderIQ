// Mirrors backend/app/schemas/common.py. Keep the two in sync by hand.

export interface ErrorDetail {
  field: string
  message: string
}

export interface ErrorBody {
  code: string
  message: string
  request_id: string | null
  // Present only when the error is about specific request fields.
  details?: ErrorDetail[] | null
}

/** The shape of every error response from the API. */
export interface ErrorResponse {
  error: ErrorBody
}

export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
  total_pages: number
}
