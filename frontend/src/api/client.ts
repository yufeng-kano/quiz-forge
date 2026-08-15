/**
 * Thin fetch wrapper around `/api/v1`.
 *
 * It does exactly three things: build the URL, send the request, and turn any
 * failure into an `ApiError`. It deliberately does not touch i18n (messages are
 * resolved from `ApiError.code` in `src/i18n/errors.ts`) and does not retry or
 * cache — retrying is the job layer's responsibility, see docs/architecture.md.
 */

import { API_BASE_PATH } from './config'

/** Failure kinds: could not reach the server, non-2xx response, unparsable body. */
export type ApiErrorCode = 'network' | 'http' | 'invalid_response'

/**
 * Cut-off for non-JSON error bodies (an nginx HTML error page, for example) so
 * a whole document never ends up inside an error message.
 */
const MAX_FALLBACK_DETAIL_LENGTH = 200

export class ApiError extends Error {
  readonly code: ApiErrorCode
  /** HTTP status code; 0 when the request never reached the server. */
  readonly status: number
  /** FastAPI `detail` content, or null when it could not be extracted. */
  readonly detail: string | null

  constructor(
    code: ApiErrorCode,
    status: number,
    detail: string | null,
    message: string,
    options?: { cause?: unknown },
  ) {
    super(message, options)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.detail = detail
  }
}

export type QueryValue = string | number | boolean | null | undefined
export type QueryParams = Record<string, QueryValue>

function buildUrl(path: string, query?: QueryParams): string {
  const url = `${API_BASE_PATH}${path}`
  if (query === undefined) {
    return url
  }
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined) {
      continue
    }
    search.append(key, String(value))
  }
  const queryString = search.toString()
  return queryString === '' ? url : `${url}?${queryString}`
}

interface FastApiValidationIssue {
  loc?: unknown
  msg?: unknown
}

function formatValidationIssue(issue: unknown): string | null {
  if (typeof issue !== 'object' || issue === null) {
    return null
  }
  const { loc, msg } = issue as FastApiValidationIssue
  if (typeof msg !== 'string') {
    return null
  }
  if (!Array.isArray(loc)) {
    return msg
  }
  // The first `loc` segment is body/query/path, which means nothing to a user.
  const field = loc.slice(1).map(String).join('.')
  return field === '' ? msg : `${field}: ${msg}`
}

/** Pull out FastAPI's `detail`: a string (HTTPException) or a 422 issue list. */
function extractDetail(payload: unknown): string | null {
  if (typeof payload !== 'object' || payload === null) {
    return null
  }
  const { detail } = payload as { detail?: unknown }
  if (typeof detail === 'string') {
    return detail === '' ? null : detail
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map(formatValidationIssue)
      .filter((message): message is string => message !== null)
    return messages.length === 0 ? null : messages.join('; ')
  }
  return null
}

function fallbackDetail(text: string): string | null {
  const trimmed = text.trim()
  if (trimmed === '') {
    return null
  }
  return trimmed.length > MAX_FALLBACK_DETAIL_LENGTH
    ? `${trimmed.slice(0, MAX_FALLBACK_DETAIL_LENGTH)}…`
    : trimmed
}

async function readBody(response: Response, url: string): Promise<string> {
  try {
    return await response.text()
  } catch (cause) {
    throw new ApiError('network', response.status, null, `Failed to read response body: ${url}`, {
      cause,
    })
  }
}

async function request<T>(method: string, url: string, init: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, { method, ...init })
  } catch (cause) {
    throw new ApiError('network', 0, null, `${method} ${url} failed to reach the server`, { cause })
  }

  const text = await readBody(response, url)
  let payload: unknown
  let jsonParseFailed = false
  if (text !== '') {
    try {
      payload = JSON.parse(text)
    } catch {
      jsonParseFailed = true
    }
  }

  if (!response.ok) {
    // An error response that is not JSON still carries useful text; do not let
    // the parse failure hide the actual HTTP error.
    const detail = extractDetail(payload) ?? fallbackDetail(text)
    throw new ApiError(
      'http',
      response.status,
      detail,
      `${method} ${url} returned HTTP ${response.status}`,
    )
  }

  if (jsonParseFailed) {
    throw new ApiError(
      'invalid_response',
      response.status,
      null,
      `${method} ${url} returned a non-JSON body`,
    )
  }

  // 204 / empty bodies (DELETE, for instance) resolve to undefined; those
  // callers declare `void` as the type argument.
  return payload as T
}

const JSON_HEADERS: HeadersInit = { 'Content-Type': 'application/json' }
const ACCEPT_JSON: HeadersInit = { Accept: 'application/json' }

export function apiGet<T>(path: string, query?: QueryParams): Promise<T> {
  return request<T>('GET', buildUrl(path, query), { headers: ACCEPT_JSON })
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  if (body === undefined) {
    return request<T>('POST', buildUrl(path), { headers: ACCEPT_JSON })
  }
  return request<T>('POST', buildUrl(path), {
    headers: { ...ACCEPT_JSON, ...JSON_HEADERS },
    body: JSON.stringify(body),
  })
}

export function apiDelete<T = void>(path: string): Promise<T> {
  return request<T>('DELETE', buildUrl(path), { headers: ACCEPT_JSON })
}

/**
 * Multipart upload.
 *
 * `Content-Type` is intentionally left unset: the browser must add the
 * multipart boundary itself, and setting the header by hand makes FastAPI
 * unable to parse the file part.
 */
export function apiUpload<T>(path: string, form: FormData): Promise<T> {
  return request<T>('POST', buildUrl(path), { headers: ACCEPT_JSON, body: form })
}
