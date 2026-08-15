/**
 * Wording for `llm_usage.purpose`.
 *
 * The backend writes a purpose per call site — `vision_parse_page`,
 * `classify_chunk`, `embed_chunk`, `summarize_url_document` and one
 * `generate_question_{type}` per question type (`backend.llm.client` callers).
 * A purpose this build does not know is shown exactly as the server sent it
 * instead of being dropped or renamed, so a new call site still appears in the
 * table the moment it records usage.
 */

import { isQuestionType } from '@/api'
import { translate } from '@/i18n'
import type { MessageKey } from '@/i18n'
import { QUESTION_TYPE_LABEL_KEYS } from '@/questions/labels'

/** Purposes with a fixed wording of their own. */
const PURPOSE_LABEL_KEYS: Record<string, MessageKey> = {
  vision_parse_page: 'usage.purpose.visionParsePage',
  classify_chunk: 'usage.purpose.classifyChunk',
  embed_chunk: 'usage.purpose.embedChunk',
  summarize_url_document: 'usage.purpose.summarizeUrlDocument',
}

/** `backend.questions.generation` builds its purpose as this prefix + the type. */
const GENERATE_QUESTION_PREFIX = 'generate_question_'

/** Localised name of a purpose, or the raw string when it is not recognised. */
export function purposeLabel(purpose: string): string {
  const key = PURPOSE_LABEL_KEYS[purpose]
  if (key !== undefined) {
    return translate(key)
  }
  if (purpose.startsWith(GENERATE_QUESTION_PREFIX)) {
    const type = purpose.slice(GENERATE_QUESTION_PREFIX.length)
    if (isQuestionType(type)) {
      return translate('usage.purpose.generateQuestion', {
        type: translate(QUESTION_TYPE_LABEL_KEYS[type]),
      })
    }
  }
  return purpose
}
