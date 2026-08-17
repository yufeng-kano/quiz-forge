/**
 * 題庫選題助手 conversation endpoints (docs/question-bank.md 題庫選題助手（對話
 * agent）相關 API).
 *
 * Sending a message never produces a reply here: it stores the user's message
 * and queues one `bank_agent_turn` job, whose id the caller polls before
 * reading the conversation again (docs/question-bank.md — 一個回合＝一個 job).
 */

import { apiDelete, apiGet, apiPost } from './client'
import type {
  Conversation,
  ConversationDetail,
  ConversationMessageRequest,
  PostConversationMessageResult,
} from './types'

/** `GET /api/v1/conversations` — every conversation, latest activity first. */
export function listConversations(): Promise<Conversation[]> {
  return apiGet<Conversation[]>('/conversations')
}

/**
 * `POST /api/v1/conversations` — an empty conversation; no body is sent, and
 * its `title` stays blank until the first message names it server-side.
 */
export function createConversation(): Promise<Conversation> {
  return apiPost<Conversation>('/conversations')
}

/** `GET /api/v1/conversations/{id}` — the conversation with every message. */
export function getConversation(conversationId: number): Promise<ConversationDetail> {
  return apiGet<ConversationDetail>(`/conversations/${encodeURIComponent(conversationId)}`)
}

/**
 * `DELETE /api/v1/conversations/{id}` — responds 204 with no body. The
 * messages go with it (`ON DELETE CASCADE`); nothing else references them.
 */
export function deleteConversation(conversationId: number): Promise<void> {
  return apiDelete(`/conversations/${encodeURIComponent(conversationId)}`)
}

/**
 * `POST /api/v1/conversations/{id}/messages` — store the user's message and
 * queue this turn's `bank_agent_turn` job.
 *
 * The reply is not in the response: it is written by the job, so the caller
 * polls `GET /api/v1/jobs/{job_id}` and rereads the conversation once it is
 * done.
 */
export function postConversationMessage(
  conversationId: number,
  request: ConversationMessageRequest,
): Promise<PostConversationMessageResult> {
  return apiPost<PostConversationMessageResult>(
    `/conversations/${encodeURIComponent(conversationId)}/messages`,
    request,
  )
}
