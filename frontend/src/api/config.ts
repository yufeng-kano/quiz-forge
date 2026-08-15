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
