/**
 * Timestamp formatting for the single app locale.
 *
 * The backend sends timezone-aware ISO 8601 strings (`created_at`), which are
 * rendered in the browser's own timezone. The formatter is built once: an
 * `Intl.DateTimeFormat` instance is expensive relative to a list render.
 */

import { APP_LOCALE } from './index'

const DATE_TIME_FORMAT = new Intl.DateTimeFormat(APP_LOCALE, {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** Formats an ISO timestamp; an unparsable value is returned unchanged. */
export function formatDateTime(iso: string): string {
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime()) ? iso : DATE_TIME_FORMAT.format(parsed)
}
