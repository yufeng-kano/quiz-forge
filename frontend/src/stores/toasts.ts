/**
 * Transient feedback messages.
 *
 * Every write the user triggers (delete, retry, rechunk, upload…) reports its
 * outcome here (.rule 使用者體驗規則: 所有寫入操作必有成功/失敗回饋). The store
 * only owns the queue — the auto-dismiss timers live in `ToastHost.vue`,
 * because pausing them is a pointer interaction on the rendered stack.
 *
 * It is a Pinia store rather than a module-level ref so that a toast raised in
 * one view survives the navigation it may have caused, and so components reach
 * it the same way as every other piece of shared state.
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'

export type ToastTone = 'success' | 'error' | 'info'

/** How long a toast stays on screen; a failure is given longer to be read. */
export const TOAST_DURATION_MS = 5000
export const TOAST_ERROR_DURATION_MS = 9000

/** Oldest toasts beyond this many are dropped, so the stack cannot cover the page. */
export const TOAST_MAX_VISIBLE = 4

export interface Toast {
  id: number
  tone: ToastTone
  /** Already-localised text; the store never resolves locale keys itself. */
  message: string
  /** Milliseconds before auto-dismiss. */
  duration: number
}

export const useToastsStore = defineStore('toasts', () => {
  const toasts = ref<Toast[]>([])
  let nextId = 1

  function push(tone: ToastTone, message: string, duration?: number): number {
    const id = nextId
    nextId += 1
    const effectiveDuration =
      duration ?? (tone === 'error' ? TOAST_ERROR_DURATION_MS : TOAST_DURATION_MS)
    toasts.value = [...toasts.value, { id, tone, message, duration: effectiveDuration }].slice(
      -TOAST_MAX_VISIBLE,
    )
    return id
  }

  function success(message: string): number {
    return push('success', message)
  }

  function error(message: string): number {
    return push('error', message)
  }

  function info(message: string): number {
    return push('info', message)
  }

  function dismiss(id: number): void {
    toasts.value = toasts.value.filter((toast) => toast.id !== id)
  }

  return { toasts, push, success, error, info, dismiss }
})
