/**
 * Locale keys for the question vocabulary.
 *
 * Backend values (`comparison`, `easy`, …) never appear on screen; a component
 * looks the value up here and resolves the key through `t()`, so all wording
 * stays in `src/locales/`.
 */

import type { QuestionType } from '@/api'
import type { MessageKey } from '@/i18n'

export const QUESTION_TYPE_LABEL_KEYS: Record<QuestionType, MessageKey> = {
  comparison: 'questions.type.comparison',
  analogy: 'questions.type.analogy',
  single_choice: 'questions.type.singleChoice',
  true_false: 'questions.type.trueFalse',
  fill_blank: 'questions.type.fillBlank',
  short_answer: 'questions.type.shortAnswer',
}

/**
 * The difficulty vocabulary of this system.
 *
 * `questions.difficulty` is a free-text column: whatever the 出題 request sends
 * is interpolated into the generation prompt
 * (`backend.questions.prompts._DIFFICULTY_LINE_TEMPLATE`). The three levels
 * offered here are the same ones chunk classification is restricted to
 * (`backend.ingestion.prompts.CLASSIFICATION_PROMPT_TEMPLATE`), so a question's
 * difficulty reads the same as its source material's.
 *
 * Because the stored value is Chinese prompt text, the value sent to the API is
 * the resolved label itself — `difficultyValue()` below is the only place that
 * conversion happens, and the wording still lives in the locale file.
 */
export const DIFFICULTY_LEVELS = ['easy', 'medium', 'hard'] as const

export type DifficultyLevel = (typeof DIFFICULTY_LEVELS)[number]

export const DIFFICULTY_LABEL_KEYS: Record<DifficultyLevel, MessageKey> = {
  easy: 'questions.difficulty.easy',
  medium: 'questions.difficulty.medium',
  hard: 'questions.difficulty.hard',
}
