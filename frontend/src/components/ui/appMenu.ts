import type { InjectionKey } from 'vue'

/**
 * Close callback injected by `AppMenu` into its items.
 *
 * An item that activates (or a parent that must dismiss) always goes through
 * this function so Esc, outside click and item select share one path.
 */
export const APP_MENU_CLOSE_KEY: InjectionKey<() => void> = Symbol('appMenuClose')

/**
 * Only one overflow menu may be open. The active instance registers its
 * `close` here; a second open call closes the first before taking the slot.
 */
let activeClose: (() => void) | null = null

export function claimMenu(close: () => void): void {
  if (activeClose !== null && activeClose !== close) {
    activeClose()
  }
  activeClose = close
}

export function releaseMenu(close: () => void): void {
  if (activeClose === close) {
    activeClose = null
  }
}
