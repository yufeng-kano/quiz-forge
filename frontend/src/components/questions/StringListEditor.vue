<script setup lang="ts">
import AppButton from '@/components/AppButton.vue'
import { useAppI18n } from '@/i18n'

/**
 * Editable list of plain strings — option lists, aspects, blank answers, key
 * points. Every list in the question editors is edited through this one
 * component, so they all behave the same: one row per entry, a remove button
 * per row, one add button at the end.
 *
 * The list is a `v-model`, and every change assigns a new array rather than
 * mutating the one passed in, so the parent's payload draft is only ever
 * updated through its own binding.
 *
 * `rowLabels` is optional and lets a caller name the rows (`第 1 格` for the
 * blanks of a fill-in question); without it the rows are unlabelled.
 */
const items = defineModel<string[]>({ required: true })

defineProps<{
  label: string
  addLabel?: string
  rowLabels?: readonly string[]
  multiline?: boolean
  placeholder?: string
}>()

const { t } = useAppI18n()

function updateItem(index: number, event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLTextAreaElement)) {
    return
  }
  const next = [...items.value]
  next.splice(index, 1, target.value)
  items.value = next
}

function removeItem(index: number): void {
  items.value = items.value.filter((_item, current) => current !== index)
}

function addItem(): void {
  items.value = [...items.value, '']
}
</script>

<template>
  <div class="form-field">
    <span class="form-label">{{ label }}</span>

    <div v-for="(item, index) in items" :key="index" class="editor-row">
      <span v-if="rowLabels !== undefined" class="list-editor__row-label">
        {{ rowLabels[index] }}
      </span>
      <textarea
        v-if="multiline"
        class="form-textarea"
        rows="2"
        :value="item"
        :placeholder="placeholder"
        @input="updateItem(index, $event)"
      />
      <input
        v-else
        class="form-input"
        type="text"
        :value="item"
        :placeholder="placeholder"
        @input="updateItem(index, $event)"
      />
      <button type="button" class="editor-remove" @click="removeItem(index)">
        {{ t('editor.remove') }}
      </button>
    </div>

    <div class="list-editor__add">
      <AppButton variant="secondary" @click="addItem">
        {{ addLabel ?? t('editor.add') }}
      </AppButton>
    </div>
  </div>
</template>

<style scoped>
.list-editor__row-label {
  flex: none;
  padding-top: 0.45rem;
  color: var(--color-text-muted);
  font-size: 0.8125rem;
  white-space: nowrap;
}

.list-editor__add {
  display: flex;
}
</style>
