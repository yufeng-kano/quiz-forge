/** Review queue and question-bank endpoints, see docs/question-bank.md 審題流程. */

import { apiDelete, apiGet, apiPatch, apiPost } from './client'
import type { QueryParams } from './client'
import type {
  QuestionDetail,
  QuestionListItem,
  QuestionListPage,
  QuestionListQuery,
  QuestionPatch,
} from './types'

/**
 * `GET /api/v1/questions` — newest first, payload included, wrapped in the
 * `{ items, total, limit, offset }` pagination envelope.
 *
 * Every filter is optional and an omitted one is left out of the query string
 * entirely (the backend treats a missing parameter as "no filter").
 */
export function listQuestions(query: QuestionListQuery = {}): Promise<QuestionListPage> {
  const params: QueryParams = {
    status: query.status,
    type: query.type,
    difficulty: query.difficulty,
    category_id: query.category_id,
  }
  return apiGet<QuestionListPage>('/questions', params)
}

/** `GET /api/v1/questions/{id}` — includes the full text of the source chunks. */
export function getQuestion(questionId: number): Promise<QuestionDetail> {
  return apiGet<QuestionDetail>(`/questions/${encodeURIComponent(questionId)}`)
}

/**
 * `PATCH /api/v1/questions/{id}` — edit payload and/or difficulty. The payload
 * is re-validated server-side against the type's schema; a shape violation
 * comes back as HTTP 422.
 */
export function patchQuestion(questionId: number, patch: QuestionPatch): Promise<QuestionListItem> {
  return apiPatch<QuestionListItem>(`/questions/${encodeURIComponent(questionId)}`, patch)
}

/** `POST /api/v1/questions/{id}/approve` — `draft -> approved`; anything else is a 409. */
export function approveQuestion(questionId: number): Promise<QuestionListItem> {
  return apiPost<QuestionListItem>(`/questions/${encodeURIComponent(questionId)}/approve`)
}

/**
 * `POST /api/v1/questions/{id}/reject` — `draft`/`approved -> rejected`, and
 * pressing it again on an already rejected question restores it to `draft`.
 */
export function rejectQuestion(questionId: number): Promise<QuestionListItem> {
  return apiPost<QuestionListItem>(`/questions/${encodeURIComponent(questionId)}/reject`)
}

/** `DELETE /api/v1/questions/{id}` — responds 204 with no body. */
export function deleteQuestion(questionId: number): Promise<void> {
  return apiDelete(`/questions/${encodeURIComponent(questionId)}`)
}
