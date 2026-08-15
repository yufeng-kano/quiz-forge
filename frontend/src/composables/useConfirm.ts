/**
 * Promise-based confirmation.
 *
 * Usage in an action handler:
 *
 * ```ts
 * const { confirm } = useConfirm()
 * if (!(await confirm({ title: t('...'), message: t('...'), tone: 'danger' }))) {
 *   return
 * }
 * ```
 *
 * The dialog itself is `ConfirmDialog.vue`, mounted once in `App.vue`. The
 * pending request lives in module state rather than in a Pinia store: it is
 * never shared across pages and never outlives the click that opened it — it
 * is one dialog's worth of UI plumbing, not application state.
 *
 * A second request while one is open resolves the first as cancelled, so no
 * caller is left awaiting a promise that can never settle.
 */

import { readonly, ref, type DeepReadonly, type Ref } from 'vue'

export interface ConfirmOptions {
  /** Localised heading. */
  title: string
  /** Localised body text, e.g. what the action will destroy. */
  message: string
  /** Localised label of the confirming button; defaults to the generic one. */
  confirmLabel?: string
  /** Localised label of the cancelling button; defaults to the generic one. */
  cancelLabel?: string
  /** `danger` colours the confirming button as destructive. */
  tone?: 'default' | 'danger'
}

export interface PendingConfirm {
  options: ConfirmOptions
  resolve: (confirmed: boolean) => void
}

const pending = ref<PendingConfirm | null>(null)

function settle(confirmed: boolean): void {
  const request = pending.value
  if (request === null) {
    return
  }
  pending.value = null
  request.resolve(confirmed)
}

export interface UseConfirmResult {
  confirm: (options: ConfirmOptions) => Promise<boolean>
}

/** Ask the user; resolves `true` only when they press the confirming button. */
export function useConfirm(): UseConfirmResult {
  return {
    confirm(options: ConfirmOptions): Promise<boolean> {
      settle(false)
      return new Promise<boolean>((resolve) => {
        pending.value = { options, resolve }
      })
    },
  }
}

export interface UseConfirmHostResult {
  /** The request being asked right now, or null when the dialog is closed. */
  request: DeepReadonly<Ref<PendingConfirm | null>>
  accept: () => void
  cancel: () => void
}

/** Wiring for `ConfirmDialog.vue`; no other component should use this. */
export function useConfirmHost(): UseConfirmHostResult {
  return {
    request: readonly(pending),
    accept: () => settle(true),
    cancel: () => settle(false),
  }
}
