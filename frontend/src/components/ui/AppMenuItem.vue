<script setup lang="ts">
import { inject } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'

import { APP_MENU_CLOSE_KEY } from './appMenu'

/**
 * One row of an `AppMenu`.
 *
 * A `to` target renders a `RouterLink`; otherwise it is a button. Either way
 * the item activates, closes the menu, and (for a link) navigates. `danger`
 * is the destructive tone (刪除).
 */
const props = withDefaults(
  defineProps<{
    to?: RouteLocationRaw
    disabled?: boolean
    danger?: boolean
  }>(),
  { disabled: false, danger: false },
)

const emit = defineEmits<{ select: [] }>()

const closeMenu = inject(APP_MENU_CLOSE_KEY, () => {
  /* Standalone render has nothing to dismiss. */
})

function activate(event: Event): void {
  if (props.disabled) {
    event.preventDefault()
    return
  }
  emit('select')
  closeMenu()
}
</script>

<template>
  <RouterLink
    v-if="props.to !== undefined"
    class="app-menu-item"
    :class="{ 'app-menu-item--danger': props.danger, 'is-disabled': props.disabled }"
    :to="props.to"
    role="menuitem"
    :tabindex="props.disabled ? -1 : 0"
    :aria-disabled="props.disabled"
    @click="activate"
  >
    <slot />
  </RouterLink>

  <button
    v-else
    class="app-menu-item"
    :class="{ 'app-menu-item--danger': props.danger }"
    type="button"
    role="menuitem"
    :disabled="props.disabled"
    @click="activate"
  >
    <slot />
  </button>
</template>

<style scoped>
.app-menu-item {
  display: block;
  width: 100%;
  padding: 0.35rem 0.7rem;
  border: none;
  border-radius: var(--radius-sm);
  background: none;
  color: var(--color-text);
  font: inherit;
  font-size: var(--font-size-md);
  text-align: left;
  text-decoration: none;
  cursor: pointer;
}

.app-menu-item:hover,
.app-menu-item:focus-visible {
  background: var(--color-background-mute);
  color: var(--color-heading);
  text-decoration: none;
  outline: none;
}

.app-menu-item--danger {
  color: var(--color-status-failed-text);
}

.app-menu-item--danger:hover,
.app-menu-item--danger:focus-visible {
  background: var(--color-status-failed-bg);
  color: var(--color-status-failed-text);
}

.app-menu-item:disabled,
.app-menu-item.is-disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
</style>
