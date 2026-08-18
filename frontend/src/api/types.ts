/**
 * Response types for `/api/v1`.
 *
 * This is the single place the frontend describes the backend contract: when a
 * server schema changes, only this file is edited — callers (`src/api/*.ts`,
 * stores, views) never redeclare shapes of their own.
 */

import type { ExportHeaderField, PaperSize } from './config'

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
 * Query parameters of `GET /api/v1/jobs`. `status` and `kind` are the two
 * filters the endpoint supports; `limit`'s cap is `JOB_LIST_LIMIT`'s comment.
 */
export interface JobListQuery {
  status?: JobStatus
  kind?: string
  limit?: number
}

/**
 * `jobs.kind` values the backend enqueues today (`Job(kind=...)` in
 * `backend.api.v1`). The column is a plain string, so an unknown kind is shown
 * verbatim rather than hidden — this list only decides which kinds get a
 * translated name and appear in the 任務中心 filter.
 */
export const JOB_KINDS = [
  'parse_document',
  'parse_page',
  'rechunk_document',
  'generate_questions',
  'embed_questions',
  'bank_agent_turn',
  'export_docx',
] as const

export type JobKind = (typeof JOB_KINDS)[number]

export function isJobKind(value: string): value is JobKind {
  return JOB_KINDS.some((kind) => kind === value)
}

/**
 * `GET /api/v1/stats` — the Dashboard's overview counts
 * (`backend.schemas.stats.StatsOut`).
 *
 * The two `*_by_status` maps are keyed by whatever status strings exist in the
 * database right now: a status with no rows is simply absent from the map, so
 * callers must default a missing key to 0 rather than expecting every status.
 */
export interface Stats {
  documents_by_status: Record<string, number>
  questions_by_status: Record<string, number>
  chunk_count: number
  category_count: number
  failed_job_count: number
  llm_call_count: number
  llm_prompt_tokens: number
  llm_completion_tokens: number
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
  /** Library folder the document sits in; `null` means 未分類. */
  folder_id: number | null
  created_at: string
  page_count: number
}

/**
 * One row of `GET /api/v1/folders` (`backend.schemas.folder.FolderOut`) — a
 * flat, user-managed library folder, unrelated to the LLM `Category` tree.
 *
 * `document_count` is the server's own count. The 文件庫 sidebar does not
 * display it: that page already holds every document, so it derives the counts
 * from the list it is filtering, which keeps a badge and the rows next to it
 * from disagreeing after a move (see `DocumentLibrarySidebar.vue`).
 */
export interface Folder {
  id: number
  name: string
  created_at: string
  document_count: number
}

/**
 * Body of `POST /api/v1/folders` and `PATCH /api/v1/folders/{id}`
 * (`backend.schemas.folder.FolderIn`). The name is trimmed server-side and must
 * not be blank; another folder with the same name is a 409.
 */
export interface FolderInput {
  name: string
}

/**
 * Body of `PATCH /api/v1/documents/{id}` (`backend.schemas.document.
 * DocumentPatchIn`) — a partial update, so only the fields actually sent are
 * touched.
 *
 * `title` is trimmed and must be non-blank and within the server's length
 * limit. `folder_id` is nullable on purpose: `null` unfiles the document, an
 * unknown id is a 404. Leaving a field out of the object is what "do not
 * change it" looks like on the wire, since `JSON.stringify` drops `undefined`.
 */
export interface DocumentPatch {
  title?: string
  folder_id?: number | null
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

/**
 * Request body of `PATCH /api/v1/categories/{id}` — rename only
 * (`backend.schemas.document.CategoryPatchIn`; 不做合併). The name is trimmed
 * server-side and must not be blank; a sibling with the same name is a 409.
 */
export interface CategoryPatch {
  name: string
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
  folder_id: number | null
  created_at: string
  pages: DocumentPage[]
  chunks: DocumentChunk[]
}

/**
 * `POST /api/v1/documents/{id}/rechunk` — the id of the queued
 * `rechunk_document` job, which deletes and rebuilds every chunk of the
 * document (pages are left untouched).
 */
export interface RechunkResult {
  job_id: number
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

/**
 * Query parameters of `GET /api/v1/questions`; every one of them is optional.
 *
 * `q` is a case-insensitive `ILIKE` against the payload text, so it matches
 * stems, options and answers alike. `limit` must stay within the server's
 * `questions_list_limit_max` (`QUESTIONS_LIST_LIMIT_MAX`), which rejects a
 * larger value with 422.
 *
 * `similar_to` is free text embedded once server-side and used to rank the
 * result by cosine similarity, dropping anything under
 * `QUESTION_SIMILARITY_MIN` (docs/question-bank.md 題目向量化與語意搜尋). It
 * never replaces the filters above: they all still apply, and a question with
 * no embedding yet simply cannot appear — which is what `unembedded_total` on
 * the response is for. `q` and `similar_to` combine as documented: `q` is the
 * hard literal condition, `similar_to` decides the order.
 */
export interface QuestionListQuery {
  status?: QuestionStatus
  type?: QuestionType
  difficulty?: string
  category_id?: number
  q?: string
  similar_to?: string
  limit?: number
  offset?: number
}

/**
 * Request body of `POST /api/v1/questions` — manual authoring
 * (`backend.schemas.question.QuestionCreateIn`).
 *
 * `status` defaults to `approved` server-side (老師自己寫的不需審) and only
 * `draft` or `approved` may be sent. `source_chunk_ids` is not settable: the
 * backend always stores an empty list for a hand-written question.
 */
export interface QuestionCreateRequest {
  type: QuestionType
  difficulty?: string | null
  payload: QuestionPayload
  status?: Extract<QuestionStatus, 'draft' | 'approved'>
}

/**
 * `GET /api/v1/questions` — the pagination envelope
 * (`backend.schemas.question.QuestionListOut`).
 *
 * `limit` and `offset` are echoed back as the server applied them: an omitted
 * `limit` is filled in from `Settings.questions_list_limit_default`, so `total`
 * can be larger than `items.length` even when the caller asked for no page.
 *
 * `unembedded_total` counts the questions matching every non-semantic filter
 * of the request whose `embedding IS NULL`. It is computed whether or not
 * `similar_to` was given, so the page can always say how many questions a
 * semantic search would silently skip over.
 */
export interface QuestionListPage {
  items: QuestionListItem[]
  total: number
  limit: number
  offset: number
  unembedded_total: number
}

/**
 * Request body of `POST /api/v1/questions/embed`
 * (`backend.schemas.question.EmbedQuestionsIn`).
 *
 * `null` backfills every question whose `embedding IS NULL`; an explicit list
 * re-embeds exactly those ids. Either way the work happens in an
 * `embed_questions` job, never in the request.
 */
export interface EmbedQuestionsRequest {
  question_ids: number[] | null
}

/** `POST /api/v1/questions/embed` — the id of the queued `embed_questions` job. */
export interface EmbedQuestionsResult {
  job_id: number
}

/**
 * `PATCH /api/v1/questions/{id}`. Only the keys present in the request are
 * applied, so an omitted field is left untouched.
 */
export interface QuestionPatch {
  payload?: QuestionPayload
  difficulty?: string | null
}

/**
 * One `items[]` entry of `POST /api/v1/generate`
 * (`backend.schemas.question.GenerateItemIn`): a question type, how many of it
 * to draft, and optionally that item's own difficulty
 * (docs/decisions/2026-08-18-generate-row-difficulty-percent-scoring.md D31).
 * `count` must be positive and no two entries of one request may carry the
 * same `question_type` — both are 422 on the server.
 */
export interface GenerateItem {
  question_type: QuestionType
  count: number
  difficulty?: string
}

/**
 * Request body of `POST /api/v1/generate` (docs/question-bank.md 出題流程
 * step 1 — 多個「題型 × 數量 × 難度」項目，一個 job 出完).
 *
 * At least one scope list is required and `items` must not be empty. The whole
 * combination is drafted by a single job whose progress counts every question
 * of every item together, and one item failing outright does not fail the rest.
 */
export interface GenerateRequest {
  document_ids?: number[]
  category_ids?: number[]
  items: GenerateItem[]
}

/** `POST /api/v1/generate` — the id of the queued `generate_questions` job. */
export interface GenerateResult {
  job_id: number
}

/**
 * Points per question type, e.g. `{ single_choice: 2 }`
 * (`ExportIn.points`, docs/export.md 卷面結構).
 *
 * A type left out simply has no score printed for it; every value present must
 * be a positive integer, and an unknown key is a 422.
 */
export type ExportPoints = Partial<Record<QuestionType, number>>

/**
 * Per-question point overrides (`ExportIn.question_points`, docs/export.md
 * 配分參數), e.g. `{ "12": 9 }`.
 *
 * The key is a question id written as a string, which is what a JSON object key
 * always is; every id must be one of the request's `question_ids` and every
 * value a positive integer, or the request is a 422. An override wins over the
 * per-type `points` entry for that question.
 */
export type ExportQuestionPoints = Record<string, number>

/**
 * The 卷首 student-information row of the paper (`ExportIn.header_fields`,
 * docs/export.md 卷面結構): 班級／座號／姓名 and the 總分 box.
 *
 * All four default to true server-side; sending them explicitly keeps the
 * request a full statement of what the user chose. Unticking every one omits
 * the whole row.
 */
export type ExportHeaderFields = Record<ExportHeaderField, boolean>

/**
 * Request body of `POST /api/v1/exports`.
 *
 * `question_ids` must be non-empty and every id must be `approved`; a
 * non-approved id is not rejected by the request but fails the job, whose
 * `error` then lists the offending ids (docs/export.md 選題流程). Their order is
 * the paper's numbering order.
 *
 * `title` is required and must not be blank — it is printed on the paper's
 * first line. `points` is optional scoring per question type,
 * `question_points` the per-question override on top of it, and
 * `header_fields` which columns the student-information row carries.
 */
export interface ExportRequest {
  question_ids: number[]
  paper_size: PaperSize
  title: string
  points?: ExportPoints
  question_points?: ExportQuestionPoints
  header_fields?: ExportHeaderFields
}

/** `POST /api/v1/exports` — the id of the queued `export_docx` job. */
export interface ExportResult {
  job_id: number
}

/**
 * One row of `GET /api/v1/exports`.
 *
 * `paper_size` stays a plain string as the backend declares it: the two
 * `*_available` flags say whether the file is on disk right now, so a row of a
 * still-running or failed job renders with its download links disabled instead
 * of pointing at a 404.
 */
export interface ExportListItem {
  id: number
  /** The paper's printed title, as it was given when the job was created. */
  title: string
  paper_size: string
  question_count: number
  created_at: string
  questions_available: boolean
  answers_available: boolean
}

/**
 * `conversation_messages.role`. The column is CHECK-constrained to these two
 * values, and they decide how a chat message is drawn, so they are named
 * here instead of being written as bare strings in components.
 */
export const CONVERSATION_ROLE_USER = 'user'
export const CONVERSATION_ROLE_ASSISTANT = 'assistant'

/**
 * One message of a 題庫選題助手 conversation
 * (`backend.schemas.conversation.ConversationMessageOut`).
 *
 * `proposed_question_ids` is what the agent suggests, nothing more: the
 * backend never writes it anywhere else. The bank page opens the question
 * on the left; the person ticks the checkbox themselves (docs/decisions/
 * 2026-08-17-bank-on-questions-page.md D14).
 *
 * `steps` is the turn's jsonb search log (D6). It is typed as `unknown[]`
 * because the backend declares it `list[object]`: the entries are read field
 * by field in `src/questions/agentSteps.ts` rather than trusted here.
 */
export interface ConversationMessage {
  id: number
  role: string
  content: string
  proposed_question_ids: number[]
  steps: unknown[] | null
  created_at: string
}

/**
 * One row of `GET /api/v1/conversations`, newest activity first.
 *
 * `title` is empty until the first user message, which the backend truncates
 * into it (docs/question-bank.md — 標題由第一則使用者訊息截斷產生); a list item
 * with an empty title is therefore a conversation nobody has written in yet.
 */
export interface Conversation {
  id: number
  title: string
  created_at: string
  updated_at: string
}

/** `GET /api/v1/conversations/{id}` — the conversation with every message, oldest first. */
export interface ConversationDetail extends Conversation {
  messages: ConversationMessage[]
}

/**
 * Body of `POST /api/v1/conversations/{id}/messages`
 * (`backend.schemas.conversation.ConversationMessageIn`).
 *
 * `content` must not be empty. `selected_question_ids` is the export selection
 * as it stands on screen; the agent is given it as context so it can say
 * 「再補三題」 sensibly, but it can never write to it.
 */
export interface ConversationMessageRequest {
  content: string
  selected_question_ids: number[]
}

/**
 * `POST /api/v1/conversations/{id}/messages` — the stored user message and the
 * one `bank_agent_turn` job that runs this turn (docs/question-bank.md — 一個
 * 回合＝一個 job). The assistant's reply only exists once that job is done.
 */
export interface PostConversationMessageResult {
  job_id: number
  message_id: number
}
