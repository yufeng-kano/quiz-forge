/**
 * State of the 題庫選題助手 column on `/questions`.
 *
 * It is a Pinia store rather than component state because a turn is a
 * background job that outlives any one render: collapsing the column mid-turn
 * must keep `pendingTurn`. Polling itself is mounted on the bank page (even
 * when the column is collapsed), not here and not in `App.vue`; leaving
 * `/questions` is what stops it
 * (docs/decisions/2026-08-17-bank-on-questions-page.md D10).
 *
 * Which conversation is open is owned by this store (`activeId`). The bank
 * page seeds it from a stored preference or from an old `/conversations/:id`
 * redirect (`?conversation=`), then keeps the route at `/questions`.
 *
 * What it deliberately does not do is touch the export selection. The agent
 * only ever proposes ids (docs/decisions/2026-08-17-bank-agent-semantic-
 * selection.md D5); this store reads the selection to give the agent context
 * and never writes to it. Opening a proposal is the bank page's job.
 *
 * Read failures are kept as messages (`conversationsError` / `messagesError`)
 * because the page still renders around them; the mutating actions throw, so
 * the control that triggered one reports the server's own wording in a toast.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  ApiError,
  createConversation,
  deleteConversation,
  getConversation,
  getQuestion,
  listConversations,
  postConversationMessage,
  type Conversation,
  type ConversationMessage,
  type QuestionListItem,
} from '@/api'
import { translateApiError } from '@/i18n/errors'
import { useExportSelectionStore } from './exportSelection'

/** The turn currently being computed by a `bank_agent_turn` job. */
interface PendingTurn {
  conversationId: number
  jobId: number
}

export const useBankAgentStore = defineStore('bankAgent', () => {
  const conversations = ref<Conversation[]>([])
  const conversationsLoading = ref(false)
  const conversationsError = ref<string | null>(null)
  const conversationsLoaded = ref(false)

  const activeId = ref<number | null>(null)
  const messages = ref<ConversationMessage[]>([])
  const messagesLoading = ref(false)
  const messagesError = ref<string | null>(null)

  const sending = ref(false)
  const pendingTurn = ref<PendingTurn | null>(null)
  /**
   * The last turn whose job failed. It is kept after the turn stops being
   * pending so the chat page can still show why and offer the job's own retry
   * (.rule 使用者體驗規則 — 任務失敗必須可以最小單位重試); a failed turn does
   * not keep the composer locked.
   */
  const failedTurn = ref<PendingTurn | null>(null)

  /**
   * Questions behind the ids an assistant message proposed. A message carries
   * ids only, so the proposal rows have to look them up; `null` means the id is
   * gone from the bank (deleted or discarded since the turn ran), which the
   * row shows instead of a blank line.
   */
  const proposedQuestions = ref<Record<number, QuestionListItem | null>>({})
  const proposedQuestionsError = ref<string | null>(null)
  /** Ids with a request in flight, so a re-render cannot ask for them twice. */
  const inFlightQuestionIds = new Set<number>()

  const activeConversation = computed<Conversation | null>(
    () => conversations.value.find((conversation) => conversation.id === activeId.value) ?? null,
  )

  /** Whether the turn on this conversation is the one running. */
  const isActiveTurnPending = computed(
    () => pendingTurn.value !== null && pendingTurn.value.conversationId === activeId.value,
  )

  const hasActiveTurnFailed = computed(
    () => failedTurn.value !== null && failedTurn.value.conversationId === activeId.value,
  )

  /** One turn at a time, so send() cannot overwrite another conversation's job. */
  const isBusy = computed(() => sending.value || pendingTurn.value !== null)

  async function loadMessages(options: { silent?: boolean } = {}): Promise<void> {
    const conversationId = activeId.value
    if (conversationId === null) {
      messages.value = []
      messagesError.value = null
      return
    }
    if (!(options.silent ?? false)) {
      messagesLoading.value = true
    }
    try {
      const detail = await getConversation(conversationId)
      // The conversation can have been switched while the request was out;
      // dropping a stale response keeps the chat from showing another
      // conversation's messages under the current title.
      if (activeId.value !== conversationId) {
        return
      }
      messages.value = detail.messages
      messagesError.value = null
      upsertConversation(detail)
    } catch (error) {
      if (activeId.value !== conversationId) {
        return
      }
      messagesError.value = translateApiError(error)
    } finally {
      if (activeId.value === conversationId) {
        messagesLoading.value = false
      }
    }
  }

  function upsertConversation(conversation: Conversation): void {
    const next: Conversation = {
      id: conversation.id,
      title: conversation.title,
      created_at: conversation.created_at,
      updated_at: conversation.updated_at,
    }
    const index = conversations.value.findIndex((row) => row.id === next.id)
    if (index === -1) {
      conversations.value = [next, ...conversations.value]
      return
    }
    const copy = [...conversations.value]
    copy[index] = next
    conversations.value = copy
  }

  /**
   * Bind the store to one conversation in the bank column. Messages already
   * on screen stay put while a silent refresh runs.
   */
  async function selectConversation(conversationId: number): Promise<void> {
    const same = activeId.value === conversationId
    activeId.value = conversationId
    if (!same) {
      messages.value = []
      messagesError.value = null
    }
    await loadMessages({ silent: same && messages.value.length > 0 })
  }

  async function loadConversations(): Promise<void> {
    conversationsLoading.value = true
    try {
      conversations.value = await listConversations()
      conversationsLoaded.value = true
      conversationsError.value = null
    } catch (error) {
      conversationsError.value = translateApiError(error)
    } finally {
      conversationsLoading.value = false
    }
  }

  async function ensureLoaded(): Promise<void> {
    if (conversationsLoaded.value) {
      return
    }
    await loadConversations()
  }

  /** Create an empty conversation; the bank page then selects it in the column. */
  async function create(): Promise<Conversation> {
    const conversation = await createConversation()
    conversations.value = [conversation, ...conversations.value]
    conversationsLoaded.value = true
    return conversation
  }

  /**
   * Delete a conversation with its messages. A turn still running in it is
   * forgotten: its job will finish writing a message into a conversation that
   * no longer exists, and nothing on screen may keep waiting for it.
   */
  async function remove(conversationId: number): Promise<void> {
    await deleteConversation(conversationId)
    conversations.value = conversations.value.filter(
      (conversation) => conversation.id !== conversationId,
    )
    if (pendingTurn.value?.conversationId === conversationId) {
      pendingTurn.value = null
    }
    if (failedTurn.value?.conversationId === conversationId) {
      failedTurn.value = null
    }
    if (activeId.value === conversationId) {
      activeId.value = null
      messages.value = []
      messagesError.value = null
    }
  }

  /**
   * Send one message: it is stored immediately and its reply is computed by
   * the `bank_agent_turn` job whose id is returned here for the bank page to
   * poll (docs/question-bank.md — 一個回合＝一個 job).
   *
   * The currently selected export ids travel with it as context only.
   */
  async function send(content: string): Promise<number> {
    const conversationId = activeId.value
    if (conversationId === null) {
      throw new Error('send() called with no active conversation')
    }
    if (pendingTurn.value !== null && pendingTurn.value.conversationId !== conversationId) {
      throw new Error('send() called while another conversation still has a pending turn')
    }
    const selection = useExportSelectionStore()
    sending.value = true
    try {
      const result = await postConversationMessage(conversationId, {
        content,
        selected_question_ids: [...selection.selectedIds],
      })
      pendingTurn.value = { conversationId, jobId: result.job_id }
      failedTurn.value = null
      // Show the user's own message straight away; the assistant's row appears
      // when the turn finishes.
      await loadMessages({ silent: true })
      return result.job_id
    } finally {
      sending.value = false
    }
  }

  /**
   * The pending turn reached a terminal state. On success the assistant's
   * message is read back (and the list re-sorted, since `updated_at` moved);
   * on failure the turn moves to `failedTurn`, which keeps the job's own error
   * and its retry button on screen without locking the composer.
   */
  async function finishTurn(succeeded: boolean): Promise<void> {
    const turn = pendingTurn.value
    pendingTurn.value = null
    if (!succeeded) {
      failedTurn.value = turn
      return
    }
    failedTurn.value = null
    if (turn === null) {
      return
    }
    if (activeId.value === turn.conversationId) {
      await loadMessages({ silent: true })
    }
    try {
      const listed = await listConversations()
      conversations.value = listed
    } catch (error) {
      conversationsError.value = translateApiError(error)
    }
  }

  /**
   * A failed turn's job was put back into the queue: it counts as pending
   * again, so the composer locks and the bank page resumes showing its progress.
   */
  function resumeFailedTurn(): void {
    if (failedTurn.value === null) {
      return
    }
    pendingTurn.value = failedTurn.value
    failedTurn.value = null
  }

  /**
   * Resolve the questions behind a message's proposal, skipping the ids
   * already known or already being fetched. A 404 is not an error but the
   * answer "this id is no longer in the bank"; anything else is reported once
   * and leaves the id unresolved so a later attempt can still succeed.
   */
  async function ensureProposedQuestions(questionIds: readonly number[]): Promise<void> {
    const wanted = questionIds.filter(
      (id) => proposedQuestions.value[id] === undefined && !inFlightQuestionIds.has(id),
    )
    if (wanted.length === 0) {
      return
    }
    for (const id of wanted) {
      inFlightQuestionIds.add(id)
    }
    await Promise.all(
      wanted.map(async (id) => {
        try {
          proposedQuestions.value[id] = await getQuestion(id)
          proposedQuestionsError.value = null
        } catch (error) {
          if (error instanceof ApiError && error.status === 404) {
            proposedQuestions.value[id] = null
            return
          }
          proposedQuestionsError.value = translateApiError(error)
        } finally {
          inFlightQuestionIds.delete(id)
        }
      }),
    )
  }

  /** The row behind a proposed id: `undefined` while unresolved, `null` when gone. */
  function proposedQuestion(questionId: number): QuestionListItem | null | undefined {
    return proposedQuestions.value[questionId]
  }

  return {
    conversations,
    conversationsLoading,
    conversationsError,
    conversationsLoaded,
    activeId,
    activeConversation,
    messages,
    messagesLoading,
    messagesError,
    sending,
    pendingTurn,
    failedTurn,
    isActiveTurnPending,
    hasActiveTurnFailed,
    isBusy,
    proposedQuestionsError,
    ensureLoaded,
    loadConversations,
    loadMessages,
    selectConversation,
    create,
    remove,
    send,
    finishTurn,
    resumeFailedTurn,
    ensureProposedQuestions,
    proposedQuestion,
  }
})
