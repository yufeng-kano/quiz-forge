/**
 * API layer constants.
 *
 * The frontend is served same-origin with the backend (nginx serves the static
 * build at `/` and proxies `/api/v1` to FastAPI), so relative paths are enough:
 * no CORS, and no host injected at build time.
 *
 * Every endpoint path must be composed from the constants here — `/api/v1`
 * is never written a second time anywhere else.
 */

/** Public API version prefix, see docs/architecture.md. */
export const API_BASE_PATH = '/api/v1'

/**
 * Job polling interval in milliseconds. The backend advances jobs roughly once
 * per second (`JOB_POLL_INTERVAL_SECONDS`), so a slightly wider client interval
 * avoids requests that cannot have new information yet.
 */
export const JOB_POLL_INTERVAL_MS = 1500

/**
 * Interval for refetching a document while its pipeline is still working.
 * A document response carries every page and chunk, so it is heavier than a
 * job poll and is fetched less often.
 */
export const DOCUMENT_POLL_INTERVAL_MS = 3000

/**
 * Interval for refetching the job list (任務中心 and the Dashboard's recent
 * activity) while at least one listed job is still pending or running. A list
 * response covers many jobs at once, so it is fetched at the same rate as a
 * document rather than as often as a single job.
 */
export const JOB_LIST_POLL_INTERVAL_MS = 3000

/**
 * How many jobs the Dashboard's recent-activity block asks for. It is a
 * glance, not the 任務中心 list, so it stays short.
 */
export const DASHBOARD_RECENT_JOB_LIMIT = 8

/**
 * How many jobs 任務中心 asks for. `GET /api/v1/jobs` caps `limit` at
 * `Settings.jobs_list_limit_max` (200) and rejects anything larger with 422,
 * so this stays inside that bound.
 */
export const JOB_LIST_LIMIT = 100

/**
 * Page size of 題庫 (`GET /api/v1/questions`).
 *
 * It mirrors the server's own `Settings.questions_list_limit_default` (50), so
 * a page asked for explicitly is the same size as one the server fills in.
 */
export const QUESTIONS_PAGE_SIZE = 50

/**
 * Largest `limit` `GET /api/v1/questions` accepts
 * (`Settings.questions_list_limit_max`); anything larger is a 422. Used where
 * a caller has to walk the whole list in as few requests as possible (the
 * 匯出 selection resolving its ids).
 */
export const QUESTIONS_LIST_LIMIT_MAX = 200

/**
 * How long the 題庫 search box waits after the last keystroke before querying.
 * Long enough that typing a word is one request, short enough to feel live.
 */
export const SEARCH_DEBOUNCE_MS = 300

/**
 * Extensions `POST /api/v1/documents/upload` accepts. The backend rejects
 * anything else with 400 (`backend.ingestion.kind._EXTENSION_KIND`), so the
 * file picker offers exactly this set instead of letting the user pick a file
 * that can only fail.
 */
export const UPLOAD_ACCEPT_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.docx'] as const

/** The same list in the form an `<input type="file" accept>` expects. */
export const UPLOAD_ACCEPT_ATTRIBUTE = UPLOAD_ACCEPT_EXTENSIONS.join(',')

/**
 * Bounds of one 題型 × 數量 row's 題數 field on the 出題 form.
 *
 * The backend only requires `count > 0` (`GenerateItemIn`), so the minimum
 * mirrors that. The maximum is a frontend guard rather than a server rule: one
 * question is one `TEXT_MODEL` call billed to the user
 * (`backend.questions.generation`), so a mistyped 500 must not be sendable in
 * a single click. It lives here with every other API-layer constant instead of
 * being written into the view.
 */
export const GENERATE_COUNT_MIN = 1
export const GENERATE_COUNT_MAX = 50

/** What a new 題數 field starts at, a usable batch without being costly. */
export const GENERATE_COUNT_DEFAULT = 5

/**
 * How many picked items the 出題 scope fields lay out as chips before the rest
 * collapse into a single 「+N」 chip that reopens the picker.
 *
 * It is what keeps the form's height independent of how much is selected
 * (docs/frontend.md 清單有界原則), so it belongs with the other tuning
 * constants rather than inside the component.
 */
export const SCOPE_CHIP_VISIBLE_LIMIT = 6

/** Paper size names `POST /api/v1/exports` accepts; anything else is a 422. */
export const PAPER_SIZE_NAMES = ['A4', 'B4', 'B3'] as const

export type PaperSize = (typeof PAPER_SIZE_NAMES)[number]

export interface PaperSizeSpec {
  readonly name: PaperSize
  readonly widthMm: number
  readonly heightMm: number
}

/**
 * The three supported sheets with the dimensions the backend actually renders
 * them at (`backend/src/backend/export/paper.py` `PAPER_SIZES_MM`). B4 and B3
 * are the JIS B-series sizes 台灣考卷慣用的尺寸, not the smaller ISO ones — see
 * docs/export.md — so the numbers are mirrored here rather than guessed, and
 * the 匯出 form reads them from this one module instead of inlining them.
 */
export const PAPER_SIZES = [
  { name: 'A4', widthMm: 210, heightMm: 297 },
  { name: 'B4', widthMm: 257, heightMm: 364 },
  { name: 'B3', widthMm: 364, heightMm: 515 },
] as const satisfies readonly PaperSizeSpec[]

/** What the 紙張尺寸 field starts at: the everyday sheet of the three. */
export const DEFAULT_PAPER_SIZE: PaperSize = 'A4'

/**
 * The spec of a paper size name, or `null` when the name is not one of the
 * three. `exports.paper_size` is a plain string column, so a history row could
 * carry a value this build does not know; the caller then shows it verbatim.
 */
export function findPaperSize(name: string): PaperSizeSpec | null {
  return PAPER_SIZES.find((size) => size.name === name) ?? null
}
