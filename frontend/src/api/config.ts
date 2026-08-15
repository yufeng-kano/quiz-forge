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
