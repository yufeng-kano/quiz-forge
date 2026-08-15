/** Route definitions, one per row of the page list in docs/frontend.md. */

import type { RouteRecordRaw } from 'vue-router'

import DocumentListView from '@/views/DocumentListView.vue'

export const ROUTE_NAMES = [
  'documents',
  'document-detail',
  'review',
  'questions',
  'generate',
  'exports',
  'usage',
] as const

export type RouteName = (typeof ROUTE_NAMES)[number]

/**
 * Everything except the landing route is lazily imported, so a cold visit only
 * downloads the document list chunk. `props: true` on `document-detail` feeds
 * `:id` straight into the component, which then needs no `useRoute()`.
 */
export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'documents',
    component: DocumentListView,
  },
  {
    path: '/documents/:id',
    name: 'document-detail',
    component: () => import('@/views/DocumentDetailView.vue'),
    props: true,
  },
  {
    path: '/review',
    name: 'review',
    component: () => import('@/views/ReviewView.vue'),
  },
  {
    path: '/questions',
    name: 'questions',
    component: () => import('@/views/QuestionBankView.vue'),
  },
  {
    path: '/generate',
    name: 'generate',
    component: () => import('@/views/GenerateView.vue'),
  },
  {
    path: '/exports',
    name: 'exports',
    component: () => import('@/views/ExportsView.vue'),
  },
  {
    path: '/usage',
    name: 'usage',
    component: () => import('@/views/UsageView.vue'),
  },
]
