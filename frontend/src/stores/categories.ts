/**
 * The category hierarchy, shared by the 出題 scope picker and the 題庫 filter.
 *
 * It lives in Pinia because both pages need the same list and it barely ever
 * changes: `ensureLoaded()` fetches once per session, later visits render from
 * what is already there instead of blanking out.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { listCategories, type Category } from '@/api'
import { translateApiError } from '@/i18n/errors'
import { buildCategoryTree, type CategoryNode } from '@/utils/categoryTree'

export const useCategoriesStore = defineStore('categories', () => {
  const categories = ref<Category[]>([])
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  const loaded = ref(false)

  /** Subjects with their topics, rebuilt whenever the flat list changes. */
  const tree = computed<CategoryNode[]>(() => buildCategoryTree(categories.value))

  async function load(): Promise<void> {
    loading.value = true
    try {
      categories.value = await listCategories()
      loaded.value = true
      loadError.value = null
    } catch (error) {
      loadError.value = translateApiError(error)
    } finally {
      loading.value = false
    }
  }

  async function ensureLoaded(): Promise<void> {
    if (loaded.value) {
      return
    }
    await load()
  }

  return { categories, loading, loadError, loaded, tree, load, ensureLoaded }
})
