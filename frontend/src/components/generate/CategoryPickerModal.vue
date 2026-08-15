<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useAppI18n } from '@/i18n'
import { useCategoriesStore } from '@/stores/categories'
import type { CategoryNode } from '@/utils/categoryTree'
import { matchesQuery, normalizeQuery } from '@/utils/search'

/**
 * Category half of the 出題 scope, as a modal picker over the subject → topic
 * tree.
 *
 * Ticking a subject ticks its topics rather than sending the subject id itself
 * — `backend.questions.selection` matches `chunks.category_id` and a chunk is
 * always classified at topic level, so a bare subject id would match nothing.
 * A subject with no topics is selectable on its own, the one case where its own
 * id can match a chunk.
 *
 * While a search is active the subject row acts on the topics still visible
 * under it, so ticking a filtered subject never selects topics the user cannot
 * see; with an empty search that is the whole subject, exactly as before.
 */
const props = defineProps<{ open: boolean }>()

const emit = defineEmits<{ close: [] }>()

const selectedIds = defineModel<number[]>('selectedIds', { required: true })

const { t } = useAppI18n()
const store = useCategoriesStore()

const search = ref('')

watch(
  () => props.open,
  async (open) => {
    if (!open) {
      return
    }
    search.value = ''
    await store.ensureLoaded()
  },
)

const query = computed(() => normalizeQuery(search.value))

/** Subjects whose own name matches keep all their topics; others keep the matching ones. */
const filteredTree = computed<CategoryNode[]>(() => {
  const normalized = query.value
  if (normalized === '') {
    return store.tree
  }
  const nodes: CategoryNode[] = []
  for (const node of store.tree) {
    if (matchesQuery(node.category.name, normalized)) {
      nodes.push(node)
      continue
    }
    const children = node.children.filter((child) => matchesQuery(child.name, normalized))
    if (children.length > 0) {
      nodes.push({ category: node.category, children })
    }
  }
  return nodes
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

function clearAll(): void {
  selectedIds.value = []
}
</script>

<template>
  <AppModal
    :open="props.open"
    size="lg"
    :title="t('generate.scope.categories.modalTitle')"
    @close="emit('close')"
  >
    <div class="picker">
      <label class="form-field">
        <span class="form-label">{{ t('generate.scope.categories.search') }}</span>
        <input
          v-model="search"
          class="form-input"
          type="search"
          :placeholder="t('generate.scope.categories.searchPlaceholder')"
        />
      </label>

      <p v-if="store.loading && store.tree.length === 0" class="form-hint">
        {{ t('generate.scope.categories.loading') }}
      </p>
      <p v-else-if="store.loadError !== null" class="form-error">{{ store.loadError }}</p>
      <p v-else-if="store.tree.length === 0" class="form-hint">
        {{ t('generate.scope.categories.empty') }}
      </p>
      <p v-else-if="filteredTree.length === 0" class="form-hint">
        {{ t('generate.scope.categories.noMatch') }}
      </p>

      <ul v-else class="picker__list">
        <li v-for="node in filteredTree" :key="node.category.id" class="picker__subject">
          <label class="picker__row">
            <input
              type="checkbox"
              :checked="isSubjectSelected(node)"
              :indeterminate="isSubjectPartiallySelected(node)"
              :aria-label="t('generate.scope.categories.selectSubject')"
              @change="toggleSubject(node)"
            />
            <span class="picker__title text-ellipsis" :title="node.category.name">
              {{ node.category.name }}
            </span>
          </label>

          <ul v-if="node.children.length > 0" class="picker__topics">
            <li v-for="topic in node.children" :key="topic.id">
              <label class="picker__row">
                <input
                  type="checkbox"
                  :checked="isSelected(topic.id)"
                  @change="toggleCategory(topic.id)"
                />
                <span class="picker__topic text-ellipsis" :title="topic.name">{{
                  topic.name
                }}</span>
              </label>
            </li>
          </ul>
        </li>
      </ul>

      <p class="form-hint">{{ t('generate.scope.categories.hint') }}</p>
    </div>

    <template #actions>
      <AppButton variant="ghost" :disabled="selectedIds.length === 0" @click="clearAll">
        {{ t('generate.scope.clear') }}
      </AppButton>
      <AppButton @click="emit('close')">{{ t('generate.scope.done') }}</AppButton>
    </template>
  </AppModal>
</template>

<style scoped>
.picker {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* Bounded box: the search field stays put and only the tree scrolls */
.picker__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-height: min(24rem, 50vh);
  overflow-y: auto;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  list-style: none;
}

.picker__subject {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.picker__row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  cursor: pointer;
}

.picker__title {
  min-width: 0;
  color: var(--color-heading);
  font-weight: 600;
}

.picker__topic {
  min-width: 0;
}

.picker__topics {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-left: 1.4rem;
  list-style: none;
}
</style>
