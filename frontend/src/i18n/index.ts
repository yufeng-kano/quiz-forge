/**
 * vue-i18n setup.
 *
 * Traditional Chinese is the only locale (see docs/frontend.md): the point is
 * to keep every user-visible string in one file, not to support switching.
 * Composition API only — `legacy: false` and `useI18n()`, never the legacy `$t`.
 *
 * Components use `useAppI18n()`, non-component code (stores, utilities) uses
 * `translate()`. Both take a `MessageKey` derived from the locale file, so a
 * mistyped key is a compile error. vue-i18n's own `t()` accepts any string and
 * would let such a typo through silently, which is why it is wrapped here.
 */

import { createI18n, useI18n } from 'vue-i18n'
import zhHantTW from '@/locales/zh-Hant-TW.json'

export const APP_LOCALE = 'zh-Hant-TW' as const

export type MessageSchema = typeof zhHantTW

/** Flattens the nested locale object into the union of valid `a.b.c` keys. */
type MessagePath<T> = {
  [K in keyof T & string]: T[K] extends string ? K : `${K}.${MessagePath<T[K]>}`
}[keyof T & string]

export type MessageKey = MessagePath<MessageSchema>

/** Named placeholders inside a message, e.g. `{current} / {total}`. */
export type MessageParams = Record<string, string | number>

export const i18n = createI18n<[MessageSchema], typeof APP_LOCALE>({
  legacy: false,
  locale: APP_LOCALE,
  fallbackLocale: APP_LOCALE,
  messages: {
    [APP_LOCALE]: zhHantTW,
  },
})

/** Resolve a message outside of a component setup (stores, utilities). */
export function translate(key: MessageKey, params?: MessageParams): string {
  return params === undefined ? i18n.global.t(key) : i18n.global.t(key, params)
}

export interface AppI18n {
  t: (key: MessageKey, params?: MessageParams) => string
}

/** i18n entry point for components. */
export function useAppI18n(): AppI18n {
  const { t } = useI18n()
  return {
    t: (key, params) => (params === undefined ? t(key) : t(key, params)),
  }
}
