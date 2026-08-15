<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'

import { useAppI18n } from '@/i18n'
import { useToastsStore, type ToastTone } from '@/stores/toasts'
import AppIcon from './AppIcon.vue'
import type { IconName } from './icons'

/**
 * Toast stack, mounted once in `App.vue` (top right).
 *
 * The store owns the queue; the timers live here because auto-dismiss has to
 * pause while the pointer or the keyboard focus is on the stack — otherwise a
 * message can disappear while it is being read or its close button reached.
 */
const store = useToastsStore()
const { t } = useAppI18n()

const TONE_ICONS: Record<ToastTone, IconName> = {
  success: 'success',
  error: 'error',
  info: 'info',
}

interface TimerEntry {
  handle: ReturnType<typeof setTimeout> | null
  /** Milliseconds still to run; recomputed every time the stack is paused. */
  remaining: number
  startedAt: number
}

const timers = new Map<number, TimerEntry>()
let paused = false

function start(id: number, entry: TimerEntry): void {
  entry.startedAt = Date.now()
  entry.handle = setTimeout(() => {
    timers.delete(id)
    store.dismiss(id)
  }, entry.remaining)
}

function stop(entry: TimerEntry): void {
  if (entry.handle !== null) {
    clearTimeout(entry.handle)
    entry.handle = null
  }
}

function pause(): void {
  if (paused) {
    return
  }
  paused = true
  const now = Date.now()
  for (const entry of timers.values()) {
    if (entry.handle !== null) {
      entry.remaining = Math.max(0, entry.remaining - (now - entry.startedAt))
      stop(entry)
    }
  }
}

function resume(): void {
  if (!paused) {
    return
  }
  paused = false
  for (const [id, entry] of timers) {
    if (entry.handle === null) {
      start(id, entry)
    }
  }
}

/** Keep the timer map in step with the queue: new toasts get a timer, removed ones lose theirs. */
watch(
  () => store.toasts,
  (toasts) => {
    const liveIds = new Set(toasts.map((toast) => toast.id))
    for (const [id, entry] of timers) {
      if (!liveIds.has(id)) {
        stop(entry)
        timers.delete(id)
      }
    }
    for (const toast of toasts) {
      if (timers.has(toast.id)) {
        continue
      }
      const entry: TimerEntry = { handle: null, remaining: toast.duration, startedAt: 0 }
      timers.set(toast.id, entry)
      if (!paused) {
        start(toast.id, entry)
      }
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  for (const entry of timers.values()) {
    stop(entry)
  }
  timers.clear()
})
</script>

<template>
  <Teleport to="body">
    <div
      class="toast-host"
      role="status"
      aria-live="polite"
      @mouseenter="pause"
      @mouseleave="resume"
      @focusin="pause"
      @focusout="resume"
    >
      <TransitionGroup name="toast">
        <div
          v-for="toast in store.toasts"
          :key="toast.id"
          class="toast"
          :class="`toast--${toast.tone}`"
        >
          <AppIcon class="toast__icon" :name="TONE_ICONS[toast.tone]" :size="18" />
          <p class="toast__message">{{ toast.message }}</p>
          <button
            class="toast__close"
            type="button"
            :aria-label="t('common.close')"
            @click="store.dismiss(toast.id)"
          >
            <AppIcon name="close" :size="16" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-host {
  position: fixed;
  top: var(--space-4);
  right: var(--space-4);
  z-index: var(--z-toast);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: min(24rem, calc(100vw - 2 * var(--space-4)));
  /* The stack must not swallow clicks on the page behind it */
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-background);
  box-shadow: var(--shadow-md);
  pointer-events: auto;
}

.toast--success {
  border-color: var(--color-status-done-border);
}

.toast--success .toast__icon {
  color: var(--color-status-done-text);
}

.toast--error {
  border-color: var(--color-status-failed-border);
}

.toast--error .toast__icon {
  color: var(--color-status-failed-text);
}

.toast--info .toast__icon {
  color: var(--color-status-running-text);
}

.toast__icon {
  margin-top: 0.15rem;
}

.toast__message {
  flex: 1;
  min-width: 0;
  color: var(--color-heading);
  font-size: var(--font-size-md);
  overflow-wrap: anywhere;
}

.toast__close {
  flex: none;
  display: inline-flex;
  padding: var(--space-1);
  border: none;
  border-radius: var(--radius-sm);
  background: none;
  color: var(--color-text-faint);
  cursor: pointer;
}

.toast__close:hover {
  background: var(--color-background-mute);
  color: var(--color-heading);
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(0.75rem);
}

@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active {
    transition: none;
  }
}
</style>
