/** Category endpoint; the hierarchy itself is rebuilt client-side. */

import { apiGet } from './client'
import type { Category } from './types'

/**
 * `GET /api/v1/categories` — every category as a flat list with its
 * `parent_id`, ordered by id. The subject/topic tree is built from it in
 * `src/utils/categoryTree.ts`.
 */
export function listCategories(): Promise<Category[]> {
  return apiGet<Category[]>('/categories')
}
