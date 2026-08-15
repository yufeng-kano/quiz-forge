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
 * Extensions `POST /api/v1/documents/upload` accepts. The backend rejects
 * anything else with 400 (`backend.ingestion.kind._EXTENSION_KIND`), so the
 * file picker offers exactly this set instead of letting the user pick a file
 * that can only fail.
 */
export const UPLOAD_ACCEPT_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.docx'] as const

/** The same list in the form an `<input type="file" accept>` expects. */
export const UPLOAD_ACCEPT_ATTRIBUTE = UPLOAD_ACCEPT_EXTENSIONS.join(',')

/**
 * Bounds of the 出題 form's 數量 field.
 *
 * The backend only requires `count > 0` (`GenerateIn`), so the minimum mirrors
 * that. The maximum is a frontend guard rather than a server rule: one
 * question is one `TEXT_MODEL` call billed to the user
 * (`backend.questions.generation`), so a mistyped 500 must not be sendable in
 * a single click. It lives here with every other API-layer constant instead of
 * being written into the view.
 */
export const GENERATE_COUNT_MIN = 1
export const GENERATE_COUNT_MAX = 50

/** What the 數量 field starts at, chosen to be a usable batch without being costly. */
export const GENERATE_COUNT_DEFAULT = 5

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
