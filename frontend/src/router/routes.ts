/** Route definitions, one per row of the page list in docs/frontend.md. */

import type { RouteRecordRaw } from 'vue-router'

import type { MessageKey } from '@/i18n'
import DashboardView from '@/views/DashboardView.vue'

declare module 'vue-router' {
  interface RouteMeta {
    /** i18n key for the page tab title; absent on redirect routes. */
    titleKey?: MessageKey
  }
}

export const ROUTE_NAMES = [
  'dashboard',
  'documents',
  'document-detail',
  'jobs',
  'review',
  'questions',
  'conversations',
  'conversation',
  'generate',
  'exports',
  'usage',
] as const

export type RouteName = (typeof ROUTE_NAMES)[number]

/**
 * Everything except the landing route is lazily imported, so a cold visit only
 * downloads the Dashboard chunk. `props: true` on `document-detail` and
 * `conversation` feeds `:id` straight into the component.
 *
 * `/conversations` routes stay registered so old bookmarks do not 404; they
 * `replace` onto `/questions` (with `?conversation=` when `:id` is a positive
 * integer) rather than rendering a standalone chat page.
 */
export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'dashboard',
    component: DashboardView,
    meta: { titleKey: 'nav.dashboard' },
  },
  {
    path: '/documents',
    name: 'documents',
    component: () => import('@/views/DocumentListView.vue'),
    meta: { titleKey: 'nav.documents' },
  },
  {
    path: '/documents/:id',
    name: 'document-detail',
    component: () => import('@/views/DocumentDetailView.vue'),
    props: true,
    meta: { titleKey: 'pages.documentDetail.title' },
  },
  {
    path: '/jobs',
    name: 'jobs',
    component: () => import('@/views/JobsView.vue'),
    meta: { titleKey: 'nav.jobs' },
  },
  {
    path: '/review',
    name: 'review',
    component: () => import('@/views/ReviewView.vue'),
    meta: { titleKey: 'nav.review' },
  },
  {
    path: '/questions',
    name: 'questions',
    component: () => import('@/views/QuestionBankView.vue'),
    meta: { titleKey: 'nav.questions' },
  },
  {
    path: '/conversations',
    name: 'conversations',
    component: () => import('@/views/ConversationsRedirect.vue'),
  },
  {
    path: '/conversations/:id',
    name: 'conversation',
    component: () => import('@/views/ConversationsRedirect.vue'),
    props: true,
  },
  {
    path: '/generate',
    name: 'generate',
    component: () => import('@/views/GenerateView.vue'),
    meta: { titleKey: 'nav.generate' },
  },
  {
    path: '/exports',
    name: 'exports',
    component: () => import('@/views/ExportsView.vue'),
    meta: { titleKey: 'nav.exports' },
  },
  {
    path: '/usage',
    name: 'usage',
    component: () => import('@/views/UsageView.vue'),
    meta: { titleKey: 'nav.usage' },
  },
]
