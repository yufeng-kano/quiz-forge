/**
 * Category path helpers for the chunk list.
 *
 * `categories` is hierarchical (topic's parent is the subject), but
 * `GET /api/v1/documents/{id}` only embeds the chunk's own category node with
 * a `parent_id` — the parent's *name* is not part of the response and there is
 * no categories endpoint to look it up. So the path is resolved from the nodes
 * the response does contain: every category referenced by the document's
 * chunks. An ancestor that is not among them is left out rather than being
 * guessed at or shown as a bare id.
 */

import type { Category, DocumentChunk } from '@/api'

/** Index every category node that appears in this document's chunks, by id. */
export function buildCategoryIndex(chunks: readonly DocumentChunk[]): Map<number, Category> {
  const index = new Map<number, Category>()
  for (const chunk of chunks) {
    if (chunk.category !== null) {
      index.set(chunk.category.id, chunk.category)
    }
  }
  return index
}

/**
 * Names from the outermost resolvable ancestor down to `category` itself.
 * Returns an empty array for an unclassified chunk.
 */
export function resolveCategoryPath(
  category: Category | null,
  index: ReadonlyMap<number, Category>,
): string[] {
  if (category === null) {
    return []
  }
  const path: string[] = [category.name]
  const visited = new Set<number>([category.id])
  let parentId = category.parent_id
  while (parentId !== null) {
    // A cycle can only come from bad data, but it must not hang the render.
    if (visited.has(parentId)) {
      break
    }
    const parent = index.get(parentId)
    if (parent === undefined) {
      break
    }
    visited.add(parent.id)
    path.unshift(parent.name)
    parentId = parent.parent_id
  }
  return path
}
