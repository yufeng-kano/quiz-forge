/**
 * Builds the subject/topic tree from the flat `GET /api/v1/categories` list.
 *
 * Ingestion classifies every chunk into two levels — a subject (`parent_id`
 * null) and a topic under it (`backend.ingestion.classification`) — but the
 * endpoint returns the rows flat with their `parent_id`, so the hierarchy is
 * rebuilt here once and shared by the 出題 scope picker and the 題庫 filter.
 *
 * A row that cannot be placed under a subject — its parent is missing from the
 * list, or the data is deeper than the two levels ingestion produces — is kept
 * as a root instead of being dropped: losing a category would silently hide
 * the questions under it.
 */

import type { Category } from '@/api'

export interface CategoryNode {
  category: Category
  children: Category[]
}

export function buildCategoryTree(categories: readonly Category[]): CategoryNode[] {
  const byId = new Map<number, Category>(categories.map((category) => [category.id, category]))
  const subjects = new Map<number, CategoryNode>()
  const roots: CategoryNode[] = []

  function addRoot(category: Category): void {
    const node: CategoryNode = { category, children: [] }
    subjects.set(category.id, node)
    roots.push(node)
  }

  for (const category of categories) {
    const parentId = category.parent_id
    if (parentId === null || !byId.has(parentId)) {
      addRoot(category)
    }
  }

  for (const category of categories) {
    const parentId = category.parent_id
    if (parentId === null || subjects.has(category.id)) {
      continue
    }
    const subject = subjects.get(parentId)
    if (subject === undefined) {
      addRoot(category)
      continue
    }
    subject.children.push(category)
  }

  return roots
}

/** Every category id in a subtree: the node itself plus its topics. */
export function categoryIdsOfNode(node: CategoryNode): number[] {
  return [node.category.id, ...node.children.map((child) => child.id)]
}
