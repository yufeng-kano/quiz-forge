/**
 * One-line preview of a question, for lists that identify a question without
 * rendering it (匯出頁 配分設定 rows).
 *
 * Every type but `analogy` stores a stem; `analogy` composes one from its slots
 * the same way `AnalogyQuestion.vue` does, so the same wording appears in both
 * places. Whitespace is collapsed because the preview is a single ellipsised
 * line whose full text lives in a `title` tooltip
 * (docs/frontend.md 清單有界原則) — a stem with newlines must not become a
 * multi-line row.
 */

import type { QuestionListItem } from '@/api'
import { translate } from '@/i18n'
import { toTypedPayload } from './payload'

function singleLine(text: string): string {
  return text.replace(/\s+/g, ' ').trim()
}

/**
 * The preview text; a payload that does not match its type yields the same
 * 「內容格式無法解析」 wording the question card shows, never an empty row.
 */
export function questionPreview(question: QuestionListItem): string {
  const typed = toTypedPayload(question)
  if (typed === null) {
    return translate('questions.card.unreadableTitle')
  }
  if (typed.type === 'analogy') {
    const { a, b, c } = typed.payload
    return singleLine(translate('questions.analogy.stem', { a, b, c }))
  }
  const preview = singleLine(typed.payload.stem)
  return preview === '' ? translate('questions.card.emptyStem') : preview
}
