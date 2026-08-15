/**
 * Integer formatting for the single app locale.
 *
 * Token counts run into the millions, so they are grouped (`1,234,567`) rather
 * than printed as a raw digit run. The formatter is built once: an
 * `Intl.NumberFormat` instance is expensive relative to a table render.
 */

import { APP_LOCALE } from './index'

const INTEGER_FORMAT = new Intl.NumberFormat(APP_LOCALE, { maximumFractionDigits: 0 })

/** Formats a count for display; a non-finite value is rendered as-is. */
export function formatCount(value: number): string {
  return Number.isFinite(value) ? INTEGER_FORMAT.format(value) : String(value)
}
