/** Public entry point of the API layer; callers always `import { ... } from '@/api'`. */

export {
  API_BASE_PATH,
  DOCUMENT_POLL_INTERVAL_MS,
  GENERATE_COUNT_DEFAULT,
  GENERATE_COUNT_MAX,
  GENERATE_COUNT_MIN,
  JOB_POLL_INTERVAL_MS,
  UPLOAD_ACCEPT_ATTRIBUTE,
  UPLOAD_ACCEPT_EXTENSIONS,
} from './config'
export { ApiError } from './client'
export type { ApiErrorCode, QueryParams, QueryValue } from './client'
export { apiDelete, apiGet, apiPatch, apiPost, apiUpload } from './client'
export * from './categories'
export * from './documents'
export * from './generate'
export * from './jobs'
export * from './questions'
export * from './usage'
export * from './types'
