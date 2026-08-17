/**
 * URL display and normalization helpers (docs/frontend.md 網址顯示一律為解碼
 * 後的可讀文字).
 *
 * The backend stores URL imports verbatim, so an address with CJK characters
 * arrives percent-encoded (a blob of `%XX`). The UI shows the decoded,
 * readable form and only re-encodes when the value is sent to the backend or
 * used as a link target.
 */

const URL_PATTERN = /^https?:\/\//i

/**
 * Decode percent-encoded sequences so a URL reads as plain text. Only strings
 * that look like URLs are decoded, so a file title containing a literal
 * `%20` is left untouched. `decodeURI` throws on malformed sequences; the
 * original string is then shown as-is rather than failing the display.
 */
export function displayUrl(value: string): string {
  if (!URL_PATTERN.test(value)) {
    return value
  }
  try {
    return decodeURI(value)
  } catch {
    return value
  }
}

/**
 * Normalize a pasted URL for the intake input: drop all whitespace (pasted
 * addresses wrap across lines) and decode so the input shows readable text.
 */
export function normalizeUrlInput(raw: string): string {
  return displayUrl(raw.replace(/\s+/g, ''))
}

/**
 * Encode a URL before it is sent to the backend or used as a link target.
 * `encodeURI` leaves already-encoded sequences untouched; the fallback covers
 * lone surrogates, which `encodeURI` rejects.
 */
export function encodeUrl(value: string): string {
  try {
    return encodeURI(value)
  } catch {
    return value
  }
}