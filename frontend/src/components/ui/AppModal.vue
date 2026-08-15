<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'

import { useAppI18n } from '@/i18n'
import AppIcon from './AppIcon.vue'

/**
 * Overlay dialog of the design system.
 *
 * Accessibility basics that a hand-rolled dialog must not skip:
 * - `role="dialog" aria-modal="true"` with the title as its accessible name;
 * - focus moves into the panel on open and returns to the trigger on close;
 * - Tab and Shift+Tab cycle inside the panel instead of walking the page
 *   behind it;
 * - Esc and a backdrop click close it (unless `dismissible` is off);
 * - the page behind cannot scroll while it is open.
 */
const props = withDefaults(
  defineProps<{
    open: boolean
    /** Localised heading; also the dialog's accessible name. */
    title: string
    /** Esc and backdrop clicks close the dialog. */
    dismissible?: boolean
    /** `lg` widens the panel for a form (新增題目, 管理分類); `md` is a message. */
    size?: 'md' | 'lg'
  }>(),
  { dismissible: true, size: 'md' },
)

const emit = defineEmits<{ close: [] }>()

const { t } = useAppI18n()

const titleId = useId()
const panel = ref<HTMLElement | null>(null)
let previouslyFocused: HTMLElement | null = null
let restoreBodyOverflow: string | null = null

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function focusableElements(): HTMLElement[] {
  const container = panel.value
  if (container === null) {
    return []
  }
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
}

function lockBodyScroll(): void {
  restoreBodyOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
}

function unlockBodyScroll(): void {
  if (restoreBodyOverflow !== null) {
    document.body.style.overflow = restoreBodyOverflow
    restoreBodyOverflow = null
  }
}

function requestClose(): void {
  if (props.dismissible) {
    emit('close')
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.stopPropagation()
    requestClose()
    return
  }
  if (event.key !== 'Tab') {
    return
  }
  const elements = focusableElements()
  if (elements.length === 0) {
    // Nothing to move to; keep focus on the panel itself.
    event.preventDefault()
    return
  }
  const first = elements[0]
  const last = elements[elements.length - 1]
  if (first === undefined || last === undefined) {
    return
  }
  const active = document.activeElement
  if (event.shiftKey && (active === first || active === panel.value)) {
    event.preventDefault()
    last.focus()
    return
  }
  if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      previouslyFocused =
        document.activeElement instanceof HTMLElement ? document.activeElement : null
      lockBodyScroll()
      await nextTick()
      const elements = focusableElements()
      ;(elements[0] ?? panel.value)?.focus()
      return
    }
    unlockBodyScroll()
    previouslyFocused?.focus()
    previouslyFocused = null
  },
)

onBeforeUnmount(unlockBodyScroll)
</script>

<template>
  <Teleport to="body">
    <div v-if="props.open" class="modal">
      <div class="modal__backdrop" @click="requestClose" />
      <div
        ref="panel"
        class="modal__panel"
        :class="`modal__panel--${props.size}`"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        tabindex="-1"
        @keydown="onKeydown"
      >
        <header class="modal__header">
          <h2 :id="titleId" class="modal__title">{{ props.title }}</h2>
          <button
            v-if="props.dismissible"
            class="modal__close"
            type="button"
            :aria-label="t('common.close')"
            @click="requestClose"
          >
            <AppIcon name="close" :size="18" />
          </button>
        </header>

        <div class="modal__body">
          <slot />
        </div>

        <footer v-if="$slots.actions" class="modal__actions">
          <slot name="actions" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5);
}

.modal__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(24, 24, 27, 0.32);
}

.modal__panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-height: 100%;
  overflow: auto;
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-background);
  box-shadow: var(--shadow-lg);
}

.modal__panel--md {
  width: min(32rem, 100%);
}

.modal__panel--lg {
  width: min(48rem, 100%);
}

.modal__panel:focus {
  outline: none;
}

.modal__header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
}

.modal__title {
  flex: 1;
  font-size: var(--font-size-lg);
}

.modal__close {
  flex: none;
  display: inline-flex;
  padding: var(--space-1);
  border: none;
  border-radius: var(--radius-md);
  background: none;
  color: var(--color-text-muted);
  cursor: pointer;
}

.modal__close:hover {
  background: var(--color-background-mute);
  color: var(--color-heading);
}

.modal__body {
  color: var(--color-text);
  overflow-wrap: anywhere;
}

.modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
