<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import { useAppI18n } from '@/i18n'
import { useExportSelectionStore } from '@/stores/exportSelection'

/**
 * Summary of what is queued for the Word export, plus the bulk controls.
 *
 * `visibleIds` is the current filter's result, so 全選 adds exactly what is on
 * screen and never silently picks up questions the user cannot see. The count
 * is the whole selection, which may include questions selected under a
 * different filter — that is the point of keeping it in a store.
 */
const props = defineProps<{ visibleIds: readonly number[] }>()

const { t } = useAppI18n()
const selection = useExportSelectionStore()

const allVisibleSelected = computed(() => selection.areAllSelected(props.visibleIds))

function toggleVisible(): void {
  if (allVisibleSelected.value) {
    selection.deselectMany(props.visibleIds)
  } else {
    selection.selectMany(props.visibleIds)
  }
}
</script>

<template>
  <div class="selection-bar">
    <AppButton variant="secondary" :disabled="visibleIds.length === 0" @click="toggleVisible">
      {{ allVisibleSelected ? t('bank.selection.deselectAll') : t('bank.selection.selectAll') }}
    </AppButton>

    <span class="selection-bar__count">
      {{ t('bank.selection.selected', { count: selection.count }) }}
    </span>

    <RouterLink v-if="selection.count > 0" class="selection-bar__link" :to="{ name: 'exports' }">
      {{ t('bank.selection.goExport') }}
    </RouterLink>

    <AppButton v-if="selection.count > 0" variant="secondary" @click="selection.clear()">
      {{ t('bank.selection.clear') }}
    </AppButton>
  </div>
</template>

<style scoped>
.selection-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-accent-soft);
}

.selection-bar__count {
  color: var(--color-heading);
  font-variant-numeric: tabular-nums;
}

.selection-bar__link {
  color: var(--color-accent-strong);
  font-weight: 600;
}
</style>
