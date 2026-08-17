<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { SCOPE_CHIP_VISIBLE_LIMIT } from '@/api'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import { useAppI18n } from '@/i18n'
import { useCategoriesStore } from '@/stores/categories'
import CategoryPickerModal from './CategoryPickerModal.vue'
import ScopeChips from './ScopeChips.vue'
import type { ScopeChip } from './scope'

/**
 * 「選擇分類」 — the trigger, the current selection state, and the chips of what
 * is picked; the tree itself lives in the modal (docs/frontend.md 清單有界原則).
 *
 * A picked id is almost always a topic, so its chip carries the subject in
 * front of it: two subjects can both have a 「總論」 topic and the chip has to
 * say which one is selected.
 */
const selectedIds = defineModel<number[]>({ required: true })

const { t } = useAppI18n()
const store = useCategoriesStore()

const pickerOpen = ref(false)

onMounted(async () => {
  await store.ensureLoaded()
})

function labelOf(categoryId: number): string {
  const category = store.categories.find((item) => item.id === categoryId)
  if (category === undefined) {
    return t('generate.scope.categories.unknown', { id: categoryId })
  }
  const parent =
    category.parent_id === null
      ? undefined
      : store.categories.find((item) => item.id === category.parent_id)
  return parent === undefined
    ? category.name
    : `${parent.name}${t('generate.scope.categories.pathSeparator')}${category.name}`
}

const chips = computed<ScopeChip[]>(() =>
  selectedIds.value.map((id) => ({ id, label: labelOf(id) })),
)

function remove(id: number): void {
  selectedIds.value = selectedIds.value.filter((existing) => existing !== id)
}
</script>

<template>
  <div class="scope-field">
    <!-- The trigger is a plus icon right after the label: its position names
         its purpose (docs/decisions/2026-08-18-generate-row-difficulty-percent-scoring.md D32) -->
    <div class="scope-field__head">
      <span class="form-label">{{ t('generate.scope.categories.label') }}</span>
      <AppButton
        variant="ghost"
        icon
        size="sm"
        :aria-label="t('generate.scope.categories.select')"
        :title="t('generate.scope.categories.select')"
        @click="pickerOpen = true"
      >
        <AppIcon name="plus" :size="16" />
      </AppButton>
    </div>

    <!-- Only the empty state needs words: once there is a selection the chips
         below are the count (docs/frontend.md 設計節制原則: 不重述) -->
    <span v-if="selectedIds.length === 0" class="scope-field__state">
      {{ t('generate.scope.categories.none') }}
    </span>

    <ScopeChips
      :chips="chips"
      :limit="SCOPE_CHIP_VISIBLE_LIMIT"
      @remove="remove"
      @expand="pickerOpen = true"
    />

    <p v-if="store.loadError !== null" class="form-error">{{ store.loadError }}</p>

    <CategoryPickerModal
      v-model:selected-ids="selectedIds"
      :open="pickerOpen"
      @close="pickerOpen = false"
    />
  </div>
</template>

<style scoped>
.scope-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.scope-field__head {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.scope-field__state {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}
</style>
