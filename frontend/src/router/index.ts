import { createRouter, createWebHistory } from 'vue-router'

import { translate } from '@/i18n'
import { routes } from './routes'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

/** Set the tab title per route: `page title · QuizForge`, fallback `QuizForge`. */
router.afterEach((to) => {
  const titleKey = to.meta.titleKey
  document.title =
    titleKey === undefined
      ? translate('app.title')
      : `${translate(titleKey)} · ${translate('app.title')}`
})

export default router
