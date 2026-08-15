<script setup lang="ts" generic="Id extends string">
import { useId } from 'vue'

import type { AppTabItem } from './tabs'

/**
 * Underline tab control of the design system.
 *
 * It owns both halves of the WAI-ARIA tabs pattern — the tab list and the
 * panel wrapper — because they have to agree on ids and on which panel is
 * mounted; splitting them would push that bookkeeping into every page. A panel
 * is rendered through the slot named after its tab id, and only the selected
 * one is mounted, so a hidden panel starts no polling and fetches nothing.
 *
 * The selected tab is a `v-model`: where that value is kept (a route query, a
 * store, a local ref) is the page's decision, not this component's.
 */
const props = defineProps<{
  tabs: readonly AppTabItem<Id>[]
  modelValue: Id
  /** Localised name of the tab group, for assistive technology. */
  label: string
}>()

const emit = defineEmits<{ 'update:modelValue': [tab: Id] }>()

const uid = useId()

/** Tab buttons in render order, so arrow keys can move focus between them. */
const tabElements: HTMLButtonElement[] = []

/** `element` is whatever Vue passes a template ref (element, component, null). */
function setTabElement(index: number, element: unknown): void {
  if (element instanceof HTMLButtonElement) {
    tabElements[index] = element
  }
}

function tabId(id: Id): string {
  return `${uid}-tab-${id}`
}

function panelId(id: Id): string {
  return `${uid}-panel-${id}`
}

function select(index: number): void {
  const tab = props.tabs[index]
  if (tab === undefined) {
    return
  }
  emit('update:modelValue', tab.id)
  tabElements[index]?.focus()
}

/**
 * Arrow / Home / End move between tabs, as the pattern requires: only the
 * selected tab is in the tab order (`tabindex`), so these keys are the way a
 * keyboard reaches the others.
 */
function onKeydown(event: KeyboardEvent, index: number): void {
  const last = props.tabs.length - 1
  let next: number
  switch (event.key) {
    case 'ArrowRight':
      next = index === last ? 0 : index + 1
      break
    case 'ArrowLeft':
      next = index === 0 ? last : index - 1
      break
    case 'Home':
      next = 0
      break
    case 'End':
      next = last
      break
    default:
      return
  }
  event.preventDefault()
  select(next)
}
</script>

<template>
  <div class="app-tabs">
    <div class="app-tabs__list" role="tablist" :aria-label="props.label">
      <button
        v-for="(tab, index) in props.tabs"
        :id="tabId(tab.id)"
        :key="tab.id"
        :ref="(element) => setTabElement(index, element)"
        class="app-tabs__tab"
        :class="{ 'is-active': tab.id === props.modelValue }"
        type="button"
        role="tab"
        :aria-selected="tab.id === props.modelValue"
        :aria-controls="panelId(tab.id)"
        :tabindex="tab.id === props.modelValue ? 0 : -1"
        @click="emit('update:modelValue', tab.id)"
        @keydown="onKeydown($event, index)"
      >
        {{ tab.label }}
        <span v-if="tab.badge !== undefined" class="app-tabs__badge">{{ tab.badge }}</span>
      </button>
    </div>

    <div
      v-for="tab in props.tabs"
      v-show="tab.id === props.modelValue"
      :id="panelId(tab.id)"
      :key="tab.id"
      class="app-tabs__panel"
      role="tabpanel"
      :aria-labelledby="tabId(tab.id)"
    >
      <slot v-if="tab.id === props.modelValue" :name="tab.id" />
    </div>
  </div>
</template>

<style scoped>
.app-tabs {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* The list rides on a full-width hairline, so the active tab's underline reads
   as a segment of the same line rather than a floating bar */
.app-tabs__list {
  display: flex;
  gap: var(--space-1);
  border-bottom: 1px solid var(--color-border);
}

.app-tabs__tab {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  background: none;
  color: var(--color-text-muted);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  transition:
    color 0.15s ease,
    border-color 0.15s ease;
}

.app-tabs__tab:hover {
  color: var(--color-heading);
}

.app-tabs__tab.is-active {
  border-bottom-color: var(--color-accent);
  color: var(--color-accent-strong);
}

.app-tabs__tab:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: -2px;
}

.app-tabs__badge {
  padding: 0 var(--space-2);
  border-radius: var(--radius-pill);
  background: var(--color-accent-soft);
  color: var(--color-accent-strong);
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
}

.app-tabs__panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
</style>
