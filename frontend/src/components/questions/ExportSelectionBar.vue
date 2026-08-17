<script setup lang="ts">
import { RouterLink } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import { useAppI18n } from '@/i18n'
import { useExportSelectionStore } from '@/stores/exportSelection'

/**
 * Flush toolbar of the export selection: count, a jump to 已選, go-to-export,
 * and clear. There is no select-all
 * (docs/decisions/2026-08-17-bank-on-questions-page.md D11).
 *
 * The count is always clickable into the 已選 view so the user can see what
 * those ids actually are, not just how many there are.
 */
const emit = defineEmits<{ viewSelected: [] }>()

const { t } = useAppI18n()
const selection = useExportSelectionStore()
</script>

<template>
  <div class="selection-bar">
    <button class="selection-bar__count" type="button" @click="emit('viewSelected')">
      {{ t('bank.selection.selected', { count: selection.count }) }}
    </button>

    <AppButton variant="ghost" size="sm" @click="emit('viewSelected')">
      {{ t('bank.selection.viewSelected') }}
    </AppButton>

    <RouterLink v-if="selection.count > 0" class="selection-bar__link" :to="{ name: 'exports' }">
      {{ t('bank.selection.goExport') }}
    </RouterLink>

    <AppButton v-if="selection.count > 0" variant="ghost" size="sm" @click="selection.clear()">
      {{ t('bank.selection.clear') }}
    </AppButton>
  </div>
</template>

<style scoped>
.selection-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
  padding: var(--space-2) 0;
}

.selection-bar__count {
  padding: 0;
  border: none;
  background: none;
  color: var(--color-heading);
  font: inherit;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
}

.selection-bar__count:hover {
  color: var(--color-accent-strong);
}

.selection-bar__link {
  color: var(--color-accent-strong);
  font-size: var(--font-size-md);
  font-weight: 600;
}
</style>
