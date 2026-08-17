<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { Category } from '@/api'
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useConfirm } from '@/composables/useConfirm'
import { useAppI18n } from '@/i18n'
import { translateApiError } from '@/i18n/errors'
import { useCategoriesStore } from '@/stores/categories'
import { useToastsStore } from '@/stores/toasts'

/**
 * 管理分類 — rename and delete the categories chunk classification produced
 * (docs/decisions/2026-08-15-ux-overhaul-feature-expansion.md F4).
 *
 * Categories are created by the ingestion pipeline, never by hand, so this
 * dialog only corrects what is already there. Deleting is guarded by the
 * backend (409 while chunks reference the category or it still has children);
 * the reason comes back in the response `detail` and is shown as-is rather
 * than being turned into a generic failure — 「有 3 段引用」 is what tells the
 * user what to do next.
 *
 * Merging is deliberately absent (see the decision document).
 */
const props = defineProps<{ open: boolean }>()

const emit = defineEmits<{ close: []; changed: [] }>()

const { t } = useAppI18n()
const store = useCategoriesStore()
const toasts = useToastsStore()
const { confirm } = useConfirm()

/** Which category's name is being edited, and the text typed so far. */
const editingId = ref<number | null>(null)
const editingName = ref('')
const busyId = ref<number | null>(null)

interface CategoryRow {
  category: Category
  /** Subject name of a topic row; null for a subject row. */
  parentName: string | null
}

const rows = computed<CategoryRow[]>(() =>
  store.tree.flatMap((node) => [
    { category: node.category, parentName: null },
    ...node.children.map((child) => ({ category: child, parentName: node.category.name })),
  ]),
)

watch(
  () => props.open,
  async (open) => {
    editingId.value = null
    busyId.value = null
    if (open) {
      await store.ensureLoaded()
    }
  },
)

function startEditing(category: Category): void {
  editingId.value = category.id
  editingName.value = category.name
}

function cancelEditing(): void {
  editingId.value = null
  editingName.value = ''
}

async function saveName(category: Category): Promise<void> {
  const name = editingName.value.trim()
  if (name === '' || name === category.name) {
    cancelEditing()
    return
  }
  busyId.value = category.id
  try {
    const updated = await store.rename(category.id, name)
    toasts.success(t('bank.categories.renamed', { name: updated.name }))
    cancelEditing()
    emit('changed')
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    busyId.value = null
  }
}

async function removeCategory(category: Category): Promise<void> {
  const confirmed = await confirm({
    title: t('bank.categories.deleteTitle'),
    message: t('bank.categories.deleteMessage', { name: category.name }),
    confirmLabel: t('bank.categories.deleteConfirm'),
    tone: 'danger',
  })
  if (!confirmed) {
    return
  }
  busyId.value = category.id
  try {
    await store.remove(category.id)
    toasts.success(t('bank.categories.deleted', { name: category.name }))
    emit('changed')
  } catch (error) {
    toasts.error(translateApiError(error))
  } finally {
    busyId.value = null
  }
}
</script>

<template>
  <AppModal :open="props.open" size="lg" :title="t('bank.categories.title')" @close="emit('close')">
    <p v-if="store.loading" class="form-hint">{{ t('bank.categories.loading') }}</p>
    <p v-else-if="store.loadError !== null" class="form-error">{{ store.loadError }}</p>
    <p v-else-if="rows.length === 0" class="form-hint">{{ t('bank.categories.empty') }}</p>

    <ul v-else class="category-list">
      <li v-for="row in rows" :key="row.category.id" class="category-row">
        <template v-if="editingId === row.category.id">
          <input
            v-model="editingName"
            class="form-input category-row__input"
            type="text"
            :aria-label="t('bank.categories.nameLabel', { name: row.category.name })"
            @keyup.enter="saveName(row.category)"
          />
          <AppButton size="sm" :disabled="busyId !== null" @click="saveName(row.category)">
            {{ t('editor.save') }}
          </AppButton>
          <AppButton variant="ghost" size="sm" :disabled="busyId !== null" @click="cancelEditing">
            {{ t('editor.cancel') }}
          </AppButton>
        </template>

        <template v-else>
          <span class="category-row__name">
            <span v-if="row.parentName !== null" class="category-row__parent">
              {{ row.parentName }}{{ t('documentDetail.chunks.categorySeparator') }}
            </span>
            {{ row.category.name }}
          </span>
          <AppButton
            variant="secondary"
            size="sm"
            :disabled="busyId !== null"
            @click="startEditing(row.category)"
          >
            {{ t('bank.categories.rename') }}
          </AppButton>
          <AppButton
            variant="ghost"
            size="sm"
            :disabled="busyId !== null"
            @click="removeCategory(row.category)"
          >
            {{ t('bank.categories.delete') }}
          </AppButton>
        </template>
      </li>
    </ul>

    <template #actions>
      <AppButton variant="secondary" @click="emit('close')">{{ t('common.close') }}</AppButton>
    </template>
  </AppModal>
</template>

<style scoped>
.category-list {
  display: flex;
  flex-direction: column;
  margin-top: var(--space-3);
  padding: 0;
  list-style: none;
}

.category-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.category-row:last-child {
  border-bottom: none;
}

.category-row__name {
  flex: 1;
  min-width: 10rem;
  color: var(--color-heading);
  overflow-wrap: anywhere;
}

.category-row__parent {
  color: var(--color-text-muted);
}

.category-row__input {
  flex: 1;
  min-width: 10rem;
}
</style>
