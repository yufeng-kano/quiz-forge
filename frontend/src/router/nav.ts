/**
 * Main navigation items.
 *
 * `/documents/:id` has no nav entry — a link cannot be built without an id, so
 * that page is reached from the document list. `matches` keeps the document
 * list highlighted while the user is on a document detail page.
 */

import type { RouteName } from './routes'

export interface NavItem {
  /** Route name this item navigates to. */
  readonly routeName: RouteName
  /** Key of the label in the locale file. */
  readonly labelKey: `nav.${string}`
  /** Routes that count as "this item is active". */
  readonly matches: readonly RouteName[]
}

export const NAV_ITEMS = [
  {
    routeName: 'documents',
    labelKey: 'nav.documents',
    matches: ['documents', 'document-detail'],
  },
  { routeName: 'review', labelKey: 'nav.review', matches: ['review'] },
  { routeName: 'questions', labelKey: 'nav.questions', matches: ['questions'] },
  { routeName: 'generate', labelKey: 'nav.generate', matches: ['generate'] },
  { routeName: 'exports', labelKey: 'nav.exports', matches: ['exports'] },
  { routeName: 'usage', labelKey: 'nav.usage', matches: ['usage'] },
] as const satisfies readonly NavItem[]
