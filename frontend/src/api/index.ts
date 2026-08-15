/** Public entry point of the API layer; callers always `import { ... } from '@/api'`. */

export {
  API_BASE_PATH,
  DEFAULT_PAPER_SIZE,
  DOCUMENT_POLL_INTERVAL_MS,
  GENERATE_COUNT_DEFAULT,
  GENERATE_COUNT_MAX,
  GENERATE_COUNT_MIN,
  JOB_POLL_INTERVAL_MS,
  PAPER_SIZE_NAMES,
  PAPER_SIZES,
  UPLOAD_ACCEPT_ATTRIBUTE,
  UPLOAD_ACCEPT_EXTENSIONS,
  findPaperSize,
} from './config'
export type { PaperSize, PaperSizeSpec } from './config'
export { ApiError } from './client'
export type { ApiErrorCode, QueryParams, QueryValue } from './client'
export { apiDelete, apiGet, apiPatch, apiPost, apiUpload } from './client'
export * from './categories'
export * from './documents'
export * from './exports'
export * from './generate'
export * from './jobs'
export * from './questions'
export * from './usage'
export * from './types'
