/** Category endpoint; the hierarchy itself is rebuilt client-side. */

import { apiDelete, apiGet, apiPatch } from './client'
import type { Category, CategoryPatch } from './types'

/**
 * `GET /api/v1/categories` — every category as a flat list with its
 * `parent_id`, ordered by id. The subject/topic tree is built from it in
 * `src/utils/categoryTree.ts`.
 */
export function listCategories(): Promise<Category[]> {
  return apiGet<Category[]>('/categories')
}

/**
 * `PATCH /api/v1/categories/{id}` — rename. A sibling that already carries the
 * new name is a 409, whose `detail` names the conflict.
 */
export function renameCategory(categoryId: number, patch: CategoryPatch): Promise<Category> {
  return apiPatch<Category>(`/categories/${encodeURIComponent(categoryId)}`, patch)
}

/**
 * `DELETE /api/v1/categories/{id}` — responds 204 with no body, but only when
 * nothing references the category: chunks classified into it or child
 * categories under it both make it a 409 that says how many.
 */
export function deleteCategory(categoryId: number): Promise<void> {
  return apiDelete(`/categories/${encodeURIComponent(categoryId)}`)
}
