/** Public entry point of the API layer; callers always `import { ... } from '@/api'`. */

export {
  API_BASE_PATH,
  DASHBOARD_RECENT_JOB_LIMIT,
  DEFAULT_PAPER_SIZE,
  DOCUMENT_POLL_INTERVAL_MS,
  EXPORT_HEADER_FIELD_NAMES,
  GENERATE_COUNT_DEFAULT,
  GENERATE_COUNT_MAX,
  GENERATE_COUNT_MIN,
  JOB_LIST_LIMIT,
  JOB_LIST_POLL_INTERVAL_MS,
  JOB_POLL_INTERVAL_MS,
  PAPER_SIZE_NAMES,
  PAPER_SIZES,
  QUESTIONS_LIST_LIMIT_MAX,
  QUESTIONS_PAGE_SIZE,
  SCOPE_CHIP_VISIBLE_LIMIT,
  SEARCH_DEBOUNCE_MS,
  UPLOAD_ACCEPT_ATTRIBUTE,
  UPLOAD_ACCEPT_EXTENSIONS,
  findPaperSize,
} from './config'
export type { ExportHeaderField, PaperSize, PaperSizeSpec } from './config'
export { ApiError } from './client'
export type { ApiErrorCode, QueryParams, QueryValue } from './client'
export { apiDelete, apiGet, apiPatch, apiPost, apiUpload } from './client'
export * from './categories'
export * from './conversations'
export * from './documents'
export * from './exports'
export * from './folders'
export * from './generate'
export * from './jobs'
export * from './questions'
export * from './stats'
export * from './usage'
export * from './types'
