<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { SCOPE_CHIP_VISIBLE_LIMIT } from '@/api'
import AppButton from '@/components/AppButton.vue'
import { useAppI18n } from '@/i18n'
import { useDocumentsStore } from '@/stores/documents'
import DocumentPickerModal from './DocumentPickerModal.vue'
import ScopeChips from './ScopeChips.vue'
import type { ScopeChip } from './scope'

/**
 * 「選擇文件」 — the trigger, the current selection state, and the chips of what
 * is picked; the list itself lives in the modal (docs/frontend.md 清單有界原則).
 *
 * The list is loaded on mount rather than only when the modal opens, because
 * the chips need titles for whatever selection is already there after coming
 * back to the page.
 */
const selectedIds = defineModel<number[]>({ required: true })

const { t } = useAppI18n()
const store = useDocumentsStore()

const pickerOpen = ref(false)

onMounted(async () => {
  await store.ensureLoaded()
})

/** A selected id whose row is not in the list (deleted meanwhile) keeps its id as the label. */
const chips = computed<ScopeChip[]>(() =>
  selectedIds.value.map((id) => {
    const document = store.documents.find((item) => item.id === id)
    return { id, label: document?.title ?? t('generate.scope.documents.unknown', { id }) }
  }),
)

function remove(id: number): void {
  selectedIds.value = selectedIds.value.filter((existing) => existing !== id)
}
</script>

<template>
  <div class="scope-field">
    <span class="form-label">{{ t('generate.scope.documents.label') }}</span>

    <div class="scope-field__control">
      <AppButton variant="secondary" size="sm" @click="pickerOpen = true">
        {{ t('generate.scope.documents.select') }}
      </AppButton>
      <!-- Only the empty state needs words: once there is a selection the chips
           below are the count (docs/frontend.md 設計節制原則: 不重述) -->
      <span v-if="selectedIds.length === 0" class="scope-field__state">
        {{ t('generate.scope.documents.none') }}
      </span>
    </div>

    <ScopeChips
      :chips="chips"
      :limit="SCOPE_CHIP_VISIBLE_LIMIT"
      @remove="remove"
      @expand="pickerOpen = true"
    />

    <p v-if="store.loadError !== null" class="form-error">{{ store.loadError }}</p>

    <DocumentPickerModal
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

.scope-field__control {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.scope-field__state {
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}
</style>
