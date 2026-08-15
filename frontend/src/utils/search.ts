/**
 * Client-side text matching for the search boxes that narrow a list already in
 * memory (the 出題 pickers, the 文件 list).
 *
 * Server-side search stays server-side — 題庫 sends `q` to
 * `GET /api/v1/questions` — this is only for lists the client already holds in
 * full, where a round trip would add latency and nothing else.
 */

import { APP_LOCALE } from '@/i18n'

/**
 * Search text as the matchers compare it: trimmed and lower-cased with the app
 * locale, so matching is case-insensitive wherever case exists. An empty result
 * means "no filter".
 */
export function normalizeQuery(raw: string): string {
  return raw.trim().toLocaleLowerCase(APP_LOCALE)
}

/** Whether `text` contains the already normalized query. */
export function matchesQuery(text: string, normalizedQuery: string): boolean {
  return normalizedQuery === '' || text.toLocaleLowerCase(APP_LOCALE).includes(normalizedQuery)
}
