/**
 * Response types for `/api/v1`.
 *
 * This is the single place the frontend describes the backend contract: when a
 * server schema changes, only this file is edited — callers (`src/api/*.ts`,
 * stores, views) never redeclare shapes of their own.
 */

/** `jobs.status`, see the background-task section of docs/architecture.md. */
export const JOB_STATUSES = ['pending', 'running', 'done', 'failed'] as const

export type JobStatus = (typeof JOB_STATUSES)[number]

/** Statuses that end a job, so polling can stop. */
export const TERMINAL_JOB_STATUSES = ['done', 'failed'] as const satisfies readonly JobStatus[]

export function isTerminalJobStatus(status: JobStatus): boolean {
  return TERMINAL_JOB_STATUSES.some((terminal) => terminal === status)
}

/**
 * `GET /api/v1/jobs/{id}` and `POST /api/v1/jobs/{id}/retry`.
 *
 * `progress` is free-form text (for example `12/40`), not a percentage. The
 * backend currently sends an empty string before a job starts; `null` is
 * allowed here so a future nullable column would not ripple into callers.
 */
export interface Job {
  id: number
  kind: string
  status: JobStatus
  progress: string | null
  error: string | null
  retry_count: number
  created_at: string
  updated_at: string
}

/**
 * `documents.source_type`. The backend types this field as a plain string but
 * a CHECK constraint restricts it to these two values, so the union is safe.
 */
export type DocumentSourceType = 'upload' | 'url'

/**
 * `documents.status` / `pages.status` values that mean "the pipeline is still
 * working on this row", so a view knows when to keep polling.
 *
 * Both columns are plain `String(30)` on the backend with no CHECK constraint;
 * `backend.ingestion.pipeline` writes `pending` / `processing` / `ready` /
 * `failed`. Only the two working states are listed here, and the check takes a
 * plain string: an unexpected value counts as settled and stops the polling
 * loop rather than being forced into a union the server does not guarantee.
 */
export const ACTIVE_ENTITY_STATUSES = ['pending', 'processing'] as const

export function isActiveEntityStatus(status: string): boolean {
  return ACTIVE_ENTITY_STATUSES.some((active) => active === status)
}

/**
 * The value `backend.ingestion.pipeline` writes once a document is fully
 * parsed, chunked and classified. Only such a document has chunks to generate
 * questions from, so the generate page's scope picker filters on it.
 */
export const READY_ENTITY_STATUS = 'ready'

export function isReadyEntityStatus(status: string): boolean {
  return status === READY_ENTITY_STATUS
}

/**
 * One row of `GET /api/v1/documents`.
 *
 * `status` is a plain string rather than a union: docs/data-model.md does not
 * define the value range of `documents.status`, and inventing one here would
 * be fake data. It can be narrowed once the pipeline settles.
 */
export interface DocumentListItem {
  id: number
  source_type: DocumentSourceType
  title: string
  status: string
  source_url: string | null
  created_at: string
  page_count: number
}

/** One `pages` row as exposed on the document detail response. */
export interface DocumentPage {
  id: number
  page_no: number
  status: string
  /** Parsed Markdown; figure placeholders already point at `/api/v1/assets/{id}`. */
  markdown: string | null
}

/** A node of the `categories` hierarchy. */
export interface Category {
  id: number
  name: string
  parent_id: number | null
}

/** One `chunks` row. The embedding vector itself is never sent to the client. */
export interface DocumentChunk {
  id: number
  content: string
  tags: string[]
  category: Category | null
  has_embedding: boolean
}

/** `GET /api/v1/documents/{id}` — the document with its pages and chunks. */
export interface DocumentDetail {
  id: number
  source_type: DocumentSourceType
  title: string
  status: string
  source_url: string | null
  summary: string | null
  created_at: string
  pages: DocumentPage[]
  chunks: DocumentChunk[]
}

/**
 * `POST /api/v1/documents/upload` and `POST /api/v1/documents/url`: both create
 * a document and queue the `parse_document` job whose id the caller then polls.
 */
export interface DocumentUploadResult {
  document: DocumentListItem
  job_id: number
}

/** Request body of `POST /api/v1/documents/url`. */
export interface DocumentUrlRequest {
  url: string
  title?: string
}

/** Numeric fields shared by every usage aggregate. */
export interface UsageTotals {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  call_count: number
}

export interface ModelUsage extends UsageTotals {
  model: string
}

export interface PurposeUsage extends UsageTotals {
  purpose: string
}

/** `GET /api/v1/usage`. */
export interface UsageSummary {
  total: UsageTotals
  by_model: ModelUsage[]
  by_purpose: PurposeUsage[]
}

/**
 * The six question types of docs/question-bank.md, matching the backend's
 * `QuestionType` literal (`backend.questions.schemas`).
 */
export const QUESTION_TYPES = [
  'comparison',
  'analogy',
  'single_choice',
  'true_false',
  'fill_blank',
  'short_answer',
] as const

export type QuestionType = (typeof QUESTION_TYPES)[number]

export function isQuestionType(value: string): value is QuestionType {
  return QUESTION_TYPES.some((type) => type === value)
}

/**
 * `questions.status`, restricted by the `ck_questions_status` CHECK constraint
 * to exactly these three values (docs/question-bank.md 狀態機).
 */
export const QUESTION_STATUSES = ['draft', 'approved', 'rejected'] as const

export type QuestionStatus = (typeof QUESTION_STATUSES)[number]

/**
 * Payload shapes of `questions.payload`, one per type, mirroring the Pydantic
 * models in `backend.questions.schemas`. They are declared as type aliases
 * rather than interfaces on purpose: an alias of an object type is assignable
 * to the JSON body types the client sends, an interface is not.
 *
 * The stored payload never contains the `type` discriminator — that lives in
 * the `questions.type` column — so neither do these types.
 */
export type ComparisonDifference = {
  aspect: string
  a: string
  b: string
}

export type ComparisonModelAnswer = {
  similarities: string[]
  differences: ComparisonDifference[]
}

export type ComparisonPayload = {
  stem: string
  subject_a: string
  subject_b: string
  aspects: string[]
  model_answer: ComparisonModelAnswer
}

/**
 * `analogy` stores slots only. The stem 「a 之於 b，猶如 c 之於＿＿」 is composed
 * for display; `options === null` means the question is asked as a blank to
 * fill in rather than as a single choice.
 */
export type AnalogyPayload = {
  a: string
  b: string
  c: string
  answer: string
  options: string[] | null
  explanation: string | null
}

export type SingleChoicePayload = {
  stem: string
  options: string[]
  answer_index: number
  explanation: string | null
}

export type TrueFalsePayload = {
  stem: string
  answer: boolean
  explanation: string | null
}

/** `stem` marks every blank with `____`; `answers` matches them left to right. */
export type FillBlankPayload = {
  stem: string
  answers: string[]
}

export type ShortAnswerPayload = {
  stem: string
  model_answer: string
  key_points: string[]
}

/** Which payload shape belongs to which type. */
export interface QuestionPayloadMap {
  comparison: ComparisonPayload
  analogy: AnalogyPayload
  single_choice: SingleChoicePayload
  true_false: TrueFalsePayload
  fill_blank: FillBlankPayload
  short_answer: ShortAnswerPayload
}

export type QuestionPayload = QuestionPayloadMap[QuestionType]

/**
 * A question whose `payload` has been checked against its `type`, so the two
 * can be consumed together (`src/questions/payload.ts` produces it).
 */
export type TypedQuestionPayload = {
  [K in QuestionType]: { type: K; payload: QuestionPayloadMap[K] }
}[QuestionType]

/**
 * One row of `GET /api/v1/questions`.
 *
 * `type` and `status` stay plain strings, as the backend declares them
 * (`QuestionListItemOut`): the payload of an unknown future type is still
 * rendered as an unreadable-payload notice instead of crashing the list.
 * `difficulty` is free text (`backend.questions.prompts` interpolates it into
 * the generation prompt), not an enum.
 */
export interface QuestionListItem {
  id: number
  type: string
  difficulty: string | null
  status: string
  payload: Record<string, unknown>
  source_chunk_ids: number[]
  created_at: string
}

/** One source chunk carried by the question detail response. */
export interface SourceChunk {
  id: number
  content: string
}

/** `GET /api/v1/questions/{id}` — the question plus its source chunks' full text. */
export interface QuestionDetail extends QuestionListItem {
  source_chunks: SourceChunk[]
}

/** Query parameters of `GET /api/v1/questions`; every one of them is optional. */
export interface QuestionListQuery {
  status?: QuestionStatus
  type?: QuestionType
  difficulty?: string
  category_id?: number
}

/**
 * `PATCH /api/v1/questions/{id}`. Only the keys present in the request are
 * applied, so an omitted field is left untouched.
 */
export interface QuestionPatch {
  payload?: QuestionPayload
  difficulty?: string | null
}

/** Request body of `POST /api/v1/generate`; at least one scope list is required. */
export interface GenerateRequest {
  document_ids?: number[]
  category_ids?: number[]
  question_type: QuestionType
  count: number
  difficulty?: string | null
}

/** `POST /api/v1/generate` — the id of the queued `generate_questions` job. */
export interface GenerateResult {
  job_id: number
}
