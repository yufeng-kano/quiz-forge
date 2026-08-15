/**
 * Library folders, shared by the 文件庫 sidebar and its 移至資料夾 picker.
 *
 * It is a Pinia store for the same reason `stores/categories.ts` is: two parts
 * of the page need the same short, rarely changing list, and `ensureLoaded()`
 * fetches it once per session instead of blanking out on every visit.
 *
 * Read failures land in `loadError` (the sidebar renders around them); the
 * mutating actions throw, so the control that triggered one can toast the
 * server's own message — a duplicate name comes back as 409 with a `detail`
 * that names the conflict, which is what the user needs to see.
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { createFolder, deleteFolder, listFolders, renameFolder, type Folder } from '@/api'
import { translateApiError } from '@/i18n/errors'

export const useFoldersStore = defineStore('folders', () => {
  const folders = ref<Folder[]>([])
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  const loaded = ref(false)

  async function load(): Promise<void> {
    loading.value = true
    try {
      folders.value = await listFolders()
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

  /** Create a folder; the server's row (with its trimmed name) is what is kept. */
  async function create(name: string): Promise<Folder> {
    const created = await createFolder({ name })
    folders.value = [...folders.value, created]
    return created
  }

  /** Rename a folder; a name another folder already holds throws a 409. */
  async function rename(folderId: number, name: string): Promise<Folder> {
    const updated = await renameFolder(folderId, { name })
    folders.value = folders.value.map((folder) => (folder.id === updated.id ? updated : folder))
    return updated
  }

  /**
   * Delete a folder. The backend never refuses and unfiles the documents that
   * were inside, so the caller must refresh the document list afterwards — the
   * rows still carry the now-dead `folder_id` until it does.
   */
  async function remove(folderId: number): Promise<void> {
    await deleteFolder(folderId)
    folders.value = folders.value.filter((folder) => folder.id !== folderId)
  }

  function nameOf(folderId: number): string | null {
    return folders.value.find((folder) => folder.id === folderId)?.name ?? null
  }

  return {
    folders,
    loading,
    loadError,
    loaded,
    load,
    ensureLoaded,
    create,
    rename,
    remove,
    nameOf,
  }
})
