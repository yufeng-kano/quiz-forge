/**
 * Sidebar navigation items, in the order they appear.
 *
 * The order follows the working sequence of docs/overview.md 核心流程
 * (總覽 → 文件 → 出題 → 審題 → 題庫 → 匯出) with the two cross-cutting
 * views (任務、用量) last. 選題助手 is a column on 題庫, not a ninth item
 * (docs/decisions/2026-08-17-bank-on-questions-page.md D10).
 *
 * `/documents/:id` has no nav entry — a link cannot be built without an id.
 * `matches` keeps the same item highlighted on the matching detail route.
 */

import type { IconName } from '@/components/ui/icons'
import type { RouteName } from './routes'

export interface NavItem {
  /** Route name this item navigates to. */
  readonly routeName: RouteName
  /** Key of the label in the locale file. */
  readonly labelKey: `nav.${string}`
  /** Icon shown next to the label, and alone in the collapsed sidebar. */
  readonly icon: IconName
  /** Routes that count as "this item is active". */
  readonly matches: readonly RouteName[]
}

export const NAV_ITEMS = [
  {
    routeName: 'dashboard',
    labelKey: 'nav.dashboard',
    icon: 'dashboard',
    matches: ['dashboard'],
  },
  {
    routeName: 'documents',
    labelKey: 'nav.documents',
    icon: 'documents',
    matches: ['documents', 'document-detail'],
  },
  { routeName: 'generate', labelKey: 'nav.generate', icon: 'generate', matches: ['generate'] },
  { routeName: 'review', labelKey: 'nav.review', icon: 'review', matches: ['review'] },
  { routeName: 'questions', labelKey: 'nav.questions', icon: 'questions', matches: ['questions'] },
  { routeName: 'exports', labelKey: 'nav.exports', icon: 'exports', matches: ['exports'] },
  { routeName: 'jobs', labelKey: 'nav.jobs', icon: 'jobs', matches: ['jobs'] },
  { routeName: 'usage', labelKey: 'nav.usage', icon: 'usage', matches: ['usage'] },
] as const satisfies readonly NavItem[]
