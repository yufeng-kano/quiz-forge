/**
 * The blank payload a manually authored question starts from
 * (docs/question-bank.md 手動建題).
 *
 * Every field is empty: this is the shape of the form, not content. What it
 * does decide is how many rows the form opens with, and that follows the
 * backend's own minimums (`backend.questions.schemas`) so the first thing the
 * author sees is a form that can be filled in without hunting for an add
 * button — two options for a single choice, one difference row for a
 * comparison, one key point for a short answer.
 *
 * `fill_blank` is the exception: its `answers` count must equal the number of
 * `____` markers in the stem, and an empty stem has none, so it starts with no
 * answer rows and the editor's own counter guides the rest.
 */

import type { QuestionType, TypedQuestionPayload } from '@/api'

/** How many empty options a new single-choice question offers. */
const SINGLE_CHOICE_OPTION_COUNT = 4

export function emptyPayload(type: QuestionType): TypedQuestionPayload {
  switch (type) {
    case 'comparison':
      return {
        type: 'comparison',
        payload: {
          stem: '',
          subject_a: '',
          subject_b: '',
          aspects: [''],
          model_answer: { similarities: [], differences: [{ aspect: '', a: '', b: '' }] },
        },
      }
    case 'analogy':
      return {
        type: 'analogy',
        payload: { a: '', b: '', c: '', answer: '', options: null, explanation: null },
      }
    case 'single_choice':
      return {
        type: 'single_choice',
        payload: {
          stem: '',
          options: Array.from({ length: SINGLE_CHOICE_OPTION_COUNT }, () => ''),
          answer_index: 0,
          explanation: null,
        },
      }
    case 'true_false':
      return { type: 'true_false', payload: { stem: '', answer: true, explanation: null } }
    case 'fill_blank':
      return { type: 'fill_blank', payload: { stem: '', answers: [] } }
    case 'short_answer':
      return { type: 'short_answer', payload: { stem: '', model_answer: '', key_points: [''] } }
  }
}

/** What the 新增題目 type picker starts on: the most common type of the six. */
export const DEFAULT_NEW_QUESTION_TYPE: QuestionType = 'single_choice'
