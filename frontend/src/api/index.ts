/** Public entry point of the API layer; callers always `import { ... } from '@/api'`. */

export { API_BASE_PATH, JOB_POLL_INTERVAL_MS } from './config'
export { ApiError } from './client'
export type { ApiErrorCode, QueryParams, QueryValue } from './client'
export { apiDelete, apiGet, apiPost, apiUpload } from './client'
export * from './documents'
export * from './jobs'
export * from './usage'
export * from './types'
