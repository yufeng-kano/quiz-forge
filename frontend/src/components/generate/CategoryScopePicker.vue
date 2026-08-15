<script setup lang="ts">
import { onMounted } from 'vue'

import { useAppI18n } from '@/i18n'
import { useCategoriesStore } from '@/stores/categories'
import type { CategoryNode } from '@/utils/categoryTree'

/**
 * Category half of the 出題 scope: subjects with their topics.
 *
 * Ticking a subject ticks its topics rather than sending the subject id
 * itself — `backend.questions.selection` matches `chunks.category_id`, and a
 * chunk is always classified at topic level, so a bare subject id would match
 * nothing. A subject with no topics is selectable on its own, which is the only
 * case where its own id can match a chunk.
 */
const selectedIds = defineModel<number[]>({ required: true })

const { t } = useAppI18n()
const store = useCategoriesStore()

onMounted(async () => {
  await store.ensureLoaded()
})

/** The ids a subject row stands for: its topics, or itself when it has none. */
function scopeIdsOf(node: CategoryNode): number[] {
  return node.children.length === 0 ? [node.category.id] : node.children.map((child) => child.id)
}

function isSelected(categoryId: number): boolean {
  return selectedIds.value.includes(categoryId)
}

function isSubjectSelected(node: CategoryNode): boolean {
  return scopeIdsOf(node).every((id) => isSelected(id))
}

function isSubjectPartiallySelected(node: CategoryNode): boolean {
  const ids = scopeIdsOf(node)
  return ids.some((id) => isSelected(id)) && !ids.every((id) => isSelected(id))
}

function toggleCategory(categoryId: number): void {
  selectedIds.value = isSelected(categoryId)
    ? selectedIds.value.filter((id) => id !== categoryId)
    : [...selectedIds.value, categoryId]
}

function toggleSubject(node: CategoryNode): void {
  const ids = scopeIdsOf(node)
  if (isSubjectSelected(node)) {
    selectedIds.value = selectedIds.value.filter((id) => !ids.includes(id))
    return
  }
  const added = ids.filter((id) => !isSelected(id))
  selectedIds.value = [...selectedIds.value, ...added]
}
</script>

<template>
  <div class="form-field">
    <span class="form-label">{{ t('generate.form.categories') }}</span>

    <p v-if="store.loading" class="form-hint">{{ t('generate.form.categoriesLoading') }}</p>
    <p v-else-if="store.loadError !== null" class="form-error">{{ store.loadError }}</p>
    <p v-else-if="store.tree.length === 0" class="form-hint">
      {{ t('generate.form.categoriesEmpty') }}
    </p>

    <ul v-else class="category-tree">
      <li v-for="node in store.tree" :key="node.category.id" class="category-tree__subject">
        <label class="category-tree__item">
          <input
            type="checkbox"
            :checked="isSubjectSelected(node)"
            :indeterminate="isSubjectPartiallySelected(node)"
            :aria-label="t('generate.form.selectSubject')"
            @change="toggleSubject(node)"
          />
          <span class="category-tree__subject-name">{{ node.category.name }}</span>
        </label>

        <ul v-if="node.children.length > 0" class="category-tree__topics">
          <li v-for="topic in node.children" :key="topic.id">
            <label class="category-tree__item">
              <input
                type="checkbox"
                :checked="isSelected(topic.id)"
                @change="toggleCategory(topic.id)"
              />
              <span>{{ topic.name }}</span>
            </label>
          </li>
        </ul>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.category-tree {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  max-height: 16rem;
  overflow-y: auto;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-background);
  list-style: none;
}

.category-tree__subject {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.category-tree__item {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  cursor: pointer;
  overflow-wrap: anywhere;
}

.category-tree__subject-name {
  color: var(--color-heading);
  font-weight: 600;
}

.category-tree__topics {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding-left: 1.4rem;
  list-style: none;
}
</style>
