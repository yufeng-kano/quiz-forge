<script setup lang="ts">
import { computed } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import { useAppI18n } from '@/i18n'
import type { ScopeChip } from './scope'

/**
 * The picked items of a scope field.
 *
 * At most `limit` chips are ever laid out; everything beyond that collapses
 * into one 「+N」 chip that reopens the picker, so the form is the same height
 * whether two documents or two hundred are selected (docs/frontend.md
 * 清單有界原則). Each chip is a single ellipsised line with the full text in
 * its `title`, which is what keeps a URL-derived document title from wrapping
 * over six lines.
 */
const props = defineProps<{
  chips: readonly ScopeChip[]
  /** How many chips to show before the rest become a 「+N」 chip. */
  limit: number
}>()

const emit = defineEmits<{ remove: [id: number]; expand: [] }>()

const { t } = useAppI18n()

const visibleChips = computed(() => props.chips.slice(0, props.limit))

const hiddenCount = computed(() => Math.max(0, props.chips.length - props.limit))
</script>

<template>
  <ul v-if="props.chips.length > 0" class="scope-chips">
    <li v-for="chip in visibleChips" :key="chip.id" class="scope-chips__chip">
      <span class="scope-chips__label text-ellipsis" :title="chip.label">{{ chip.label }}</span>
      <button
        class="scope-chips__remove"
        type="button"
        :aria-label="t('generate.scope.remove', { label: chip.label })"
        @click="emit('remove', chip.id)"
      >
        <AppIcon name="close" :size="12" />
      </button>
    </li>

    <li v-if="hiddenCount > 0">
      <button
        class="scope-chips__more"
        type="button"
        :title="t('generate.scope.moreTitle', { count: hiddenCount })"
        @click="emit('expand')"
      >
        {{ t('generate.scope.more', { count: hiddenCount }) }}
      </button>
    </li>
  </ul>
</template>

<style scoped>
.scope-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: 0;
  list-style: none;
}

.scope-chips__chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  max-width: 100%;
  padding: 0.1rem var(--space-1) 0.1rem var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  background: var(--color-background-soft);
  font-size: var(--font-size-md);
}

.scope-chips__label {
  /* Long enough to read a real title, short enough that a few chips still fit
     on one line; the full text stays in the tooltip either way */
  max-width: 14rem;
  color: var(--color-heading);
}

.scope-chips__remove {
  flex: none;
  display: inline-flex;
  padding: var(--space-1);
  border: none;
  border-radius: var(--radius-pill);
  background: none;
  color: var(--color-text-muted);
  cursor: pointer;
}

.scope-chips__remove:hover {
  background: var(--color-background-mute);
  color: var(--color-heading);
}

.scope-chips__more {
  padding: 0.1rem var(--space-3);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-pill);
  background: none;
  color: var(--color-text-muted);
  font: inherit;
  font-size: var(--font-size-md);
  font-variant-numeric: tabular-nums;
  cursor: pointer;
}

.scope-chips__more:hover {
  border-color: var(--color-border-hover);
  color: var(--color-heading);
}
</style>
