<script setup lang="ts">
import { RouterLink, type RouteLocationRaw } from 'vue-router'

import AppSkeleton from './AppSkeleton.vue'

/**
 * One overview number of the Dashboard.
 *
 * With `to` the whole card is the link to the page that can act on the number
 * (待審題目 → 審題, 失敗任務 → 任務中心), which is what makes the Dashboard a
 * starting point rather than a read-only board.
 */
withDefaults(
  defineProps<{
    /** Localised caption above the number. */
    label: string
    /** Already-formatted number; the card does no formatting of its own. */
    value: string
    /** Localised line under the number: a breakdown, a unit, a call to action. */
    hint?: string
    /** Makes the whole card a link. */
    to?: RouteLocationRaw
    /** `attention` marks a number that is asking for work (待審、失敗). */
    tone?: 'default' | 'attention'
    loading?: boolean
  }>(),
  { tone: 'default', loading: false },
)
</script>

<template>
  <component
    :is="to === undefined ? 'div' : RouterLink"
    class="stat-card"
    :class="[`stat-card--${tone}`, { 'stat-card--link': to !== undefined }]"
    :to="to"
  >
    <span class="stat-card__label">{{ label }}</span>

    <AppSkeleton v-if="loading" class="stat-card__skeleton" width="4rem" />
    <span v-else class="stat-card__value">{{ value }}</span>

    <span v-if="hint !== undefined && !loading" class="stat-card__hint">{{ hint }}</span>

    <div v-if="$slots.default && !loading" class="stat-card__breakdown">
      <slot />
    </div>
  </component>
</template>

<style scoped>
.stat-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-background);
  color: var(--color-text);
}

.stat-card--link:hover {
  border-color: var(--color-border-hover);
  background: var(--color-background-soft);
  text-decoration: none;
}

.stat-card__label {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.stat-card__value {
  color: var(--color-heading);
  font-size: var(--font-size-2xl);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.stat-card--attention .stat-card__value {
  color: var(--color-accent-strong);
}

.stat-card__skeleton {
  height: 1.5rem;
}

.stat-card__hint {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.stat-card--attention .stat-card__hint {
  color: var(--color-accent);
}

.stat-card__breakdown {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-3);
  margin-top: var(--space-2);
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}
</style>
