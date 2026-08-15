/**
 * The category hierarchy, shared by the 出題 scope picker and the 題庫 filter.
 *
 * It lives in Pinia because both pages need the same list and it barely ever
 * changes: `ensureLoaded()` fetches once per session, later visits render from
 * what is already there instead of blanking out.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { deleteCategory, listCategories, renameCategory, type Category } from '@/api'
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

  /**
   * Rename one category. The server's own row is written back rather than the
   * requested name, so a name it trimmed is what the list then shows. A 409
   * (a sibling already has the name) is thrown to the caller.
   */
  async function rename(categoryId: number, name: string): Promise<Category> {
    const updated = await renameCategory(categoryId, { name })
    categories.value = categories.value.map((category) =>
      category.id === updated.id ? updated : category,
    )
    return updated
  }

  /**
   * Delete one category. The backend refuses with 409 while chunks reference it
   * or it still has children, so this only removes it locally once the request
   * has actually succeeded.
   */
  async function remove(categoryId: number): Promise<void> {
    await deleteCategory(categoryId)
    categories.value = categories.value.filter((category) => category.id !== categoryId)
  }

  return { categories, loading, loadError, loaded, tree, load, ensureLoaded, rename, remove }
})
