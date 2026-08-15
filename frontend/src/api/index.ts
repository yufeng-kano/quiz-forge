/** Public entry point of the API layer; callers always `import { ... } from '@/api'`. */

export {
  API_BASE_PATH,
  DOCUMENT_POLL_INTERVAL_MS,
  JOB_POLL_INTERVAL_MS,
  UPLOAD_ACCEPT_ATTRIBUTE,
  UPLOAD_ACCEPT_EXTENSIONS,
} from './config'
export { ApiError } from './client'
export type { ApiErrorCode, QueryParams, QueryValue } from './client'
export { apiDelete, apiGet, apiPost, apiUpload } from './client'
export * from './documents'
export * from './jobs'
export * from './usage'
export * from './types'
