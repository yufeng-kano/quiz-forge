<script setup lang="ts">
import { nextTick, onBeforeUnmount, provide, ref, useId, watch } from 'vue'

import { APP_MENU_CLOSE_KEY, claimMenu, releaseMenu } from './appMenu'
import AppIcon from './AppIcon.vue'

/**
 * Overflow menu of the design system.
 *
 * A compact trigger (⋯ by default) opens a floating panel of `AppMenuItem`
 * children. The panel is teleported so a table's overflow does not clip it;
 * `--shadow-md` is allowed here because it is an overlay, not page chrome.
 *
 * Only one menu is open at a time: a second trigger claims the slot and the
 * first closes. Esc, an outside pointerdown, and any item activation close it.
 * Esc also returns focus to the trigger.
 */
const props = defineProps<{
  /** Accessible name of the trigger (e.g. 更多操作). */
  label: string
}>()

const open = ref(false)
const trigger = ref<HTMLButtonElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const menuId = useId()

const panelStyle = ref<Record<string, string>>({
  top: '0px',
  left: '0px',
})

function positionPanel(): void {
  const triggerEl = trigger.value
  const panelEl = panel.value
  if (triggerEl === null || panelEl === null) {
    return
  }
  const rect = triggerEl.getBoundingClientRect()
  const panelHeight = panelEl.offsetHeight
  const panelWidth = panelEl.offsetWidth
  const gap = 4
  const margin = 8
  const spaceBelow = window.innerHeight - rect.bottom
  const flip = spaceBelow < panelHeight + gap && rect.top > spaceBelow
  const top = flip ? rect.top - panelHeight - gap : rect.bottom + gap
  let left = rect.right - panelWidth
  left = Math.min(left, window.innerWidth - panelWidth - margin)
  left = Math.max(left, margin)
  panelStyle.value = {
    top: `${Math.max(margin, top)}px`,
    left: `${left}px`,
  }
}

function dismissMenu(): void {
  if (!open.value) {
    return
  }
  open.value = false
  releaseMenu(dismissMenu)
}

function closeMenu(): void {
  const wasOpen = open.value
  dismissMenu()
  if (wasOpen) {
    trigger.value?.focus()
  }
}

async function openMenu(): Promise<void> {
  if (open.value) {
    return
  }
  claimMenu(dismissMenu)
  open.value = true
  await nextTick()
  positionPanel()
  const first = panel.value?.querySelector<HTMLElement>('[role="menuitem"]')
  first?.focus()
}

function toggle(): void {
  if (open.value) {
    closeMenu()
    return
  }
  void openMenu()
}

function onDocumentPointerDown(event: PointerEvent): void {
  const target = event.target
  if (!(target instanceof Node)) {
    return
  }
  if (trigger.value?.contains(target) === true || panel.value?.contains(target) === true) {
    return
  }
  dismissMenu()
}

function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.stopPropagation()
    closeMenu()
  }
}

function onViewportChange(): void {
  dismissMenu()
}

watch(open, (isOpen) => {
  if (isOpen) {
    document.addEventListener('pointerdown', onDocumentPointerDown, true)
    document.addEventListener('keydown', onDocumentKeydown, true)
    window.addEventListener('resize', onViewportChange)
    window.addEventListener('scroll', onViewportChange, true)
    return
  }
  document.removeEventListener('pointerdown', onDocumentPointerDown, true)
  document.removeEventListener('keydown', onDocumentKeydown, true)
  window.removeEventListener('resize', onViewportChange)
  window.removeEventListener('scroll', onViewportChange, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown, true)
  document.removeEventListener('keydown', onDocumentKeydown, true)
  window.removeEventListener('resize', onViewportChange)
  window.removeEventListener('scroll', onViewportChange, true)
  releaseMenu(dismissMenu)
})

provide(APP_MENU_CLOSE_KEY, dismissMenu)
</script>

<template>
  <div class="app-menu">
    <button
      :id="`${menuId}-trigger`"
      ref="trigger"
      class="app-menu__trigger"
      type="button"
      :aria-label="props.label"
      aria-haspopup="menu"
      :aria-expanded="open"
      :aria-controls="menuId"
      @click="toggle"
    >
      <slot name="trigger">
        <AppIcon name="more" :size="16" />
      </slot>
    </button>

    <Teleport to="body">
      <div
        v-if="open"
        :id="menuId"
        ref="panel"
        class="app-menu__panel"
        role="menu"
        :aria-labelledby="`${menuId}-trigger`"
        :style="panelStyle"
      >
        <slot />
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.app-menu {
  display: inline-flex;
}

.app-menu__trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-1);
  border: none;
  border-radius: var(--radius-md);
  background: none;
  color: var(--color-text-muted);
  cursor: pointer;
}

.app-menu__trigger:hover,
.app-menu__trigger[aria-expanded='true'] {
  background: var(--color-background-mute);
  color: var(--color-heading);
}

.app-menu__trigger:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.app-menu__panel {
  position: fixed;
  z-index: var(--z-menu);
  display: flex;
  flex-direction: column;
  min-width: 10rem;
  padding: var(--space-1);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-background);
  box-shadow: var(--shadow-md);
}
</style>
