/**
 * Tolerant `localStorage` access for user preferences.
 *
 * Preferences are a convenience, never data the app depends on: a browser with
 * storage disabled, a full quota, or a leftover value from an older build must
 * all end in "use the defaults", not in a blank page. Every entry point here
 * therefore reports failure as a value (`undefined`) instead of throwing, and
 * the caller decides the default.
 *
 * This is the one place in the frontend that swallows an exception, and it does
 * so deliberately: `localStorage` itself throws on access when cookies are
 * blocked, which is a browser setting rather than an application error there is
 * anything to report or retry. Nothing else may copy the pattern.
 *
 * Keys are namespaced and versioned by the caller (`quiz-forge:…:v1`) so a
 * changed shape is simply a new key rather than a value that has to be
 * migrated.
 */

/** The store, or null when this browser refuses to hand it over. */
function storage(): Storage | null {
  try {
    return globalThis.localStorage
  } catch {
    return null
  }
}

/**
 * The parsed JSON stored under `key`, or `undefined` when there is nothing
 * usable there — missing, unreadable, or not valid JSON.
 *
 * The result is `unknown` on purpose: what was written last may have been
 * written by an older build, so the caller has to check the shape it expects
 * field by field.
 */
export function readStoredValue(key: string): unknown {
  const store = storage()
  if (store === null) {
    return undefined
  }
  let raw: string | null
  try {
    raw = store.getItem(key)
  } catch {
    return undefined
  }
  if (raw === null) {
    return undefined
  }
  try {
    return JSON.parse(raw)
  } catch {
    return undefined
  }
}

/** Stores `value` as JSON; a refused or full store is silently left alone. */
export function writeStoredValue(key: string, value: unknown): void {
  const store = storage()
  if (store === null) {
    return
  }
  try {
    store.setItem(key, JSON.stringify(value))
  } catch {
    // Quota exceeded or storage disabled mid-session: the preference is lost
    // for the next visit, which is the whole consequence.
  }
}
