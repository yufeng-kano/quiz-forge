<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { isTerminalJobStatus } from '@/api'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import BankAgentColumn from '@/components/bank-agent/BankAgentColumn.vue'
import BankQuestionCard from '@/components/questions/BankQuestionCard.vue'
import CategoryManagerModal from '@/components/questions/CategoryManagerModal.vue'
import ExportSelectionBar from '@/components/questions/ExportSelectionBar.vue'
import QuestionCreateModal from '@/components/questions/QuestionCreateModal.vue'
import QuestionEmbedNotice from '@/components/questions/QuestionEmbedNotice.vue'
import QuestionFilters from '@/components/questions/QuestionFilters.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import AppPagination from '@/components/ui/AppPagination.vue'
import AppSkeleton from '@/components/ui/AppSkeleton.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useSelectedQuestions } from '@/composables/useSelectedQuestions'
import { useAppI18n } from '@/i18n'
import { formatCount } from '@/i18n/number'
import { readBankAgentPrefs, writeBankAgentPrefs } from '@/questions/bankAgentPrefs'
import { useBankAgentStore } from '@/stores/bankAgent'
import { useExportSelectionStore } from '@/stores/exportSelection'
import { useQuestionsStore, type QuestionBankFilters } from '@/stores/questions'
import { useToastsStore } from '@/stores/toasts'

type BankView = 'bank' | 'selected'

interface BankBrowseSnapshot {
  filters: QuestionBankFilters
  page: number
  scrollTop: number
}

const CONVERSATION_QUERY_KEY = 'conversation'

/**
 * 題庫工作區 — 左欄瀏覽／已選，右欄選題助手
 * (docs/decisions/2026-08-17-bank-on-questions-page.md D10–D12).
 *
 * Filters and the current page live in the store and are watched here: any
 * change refetches silently, so the previous result stays on screen until the
 * new one arrives. The list is a real page of the server's
 * `{ items, total, limit, offset }` envelope — `total` is the whole result, not
 * what is on screen.
 *
 * Selecting questions for the Word export writes to the export-selection store,
 * which is what `/exports` reads later. The 已選 view lists those ids in pick
 * order with the same `BankQuestionCard`. There is no select-all.
 *
 * A running turn is collected here via `useJobPolling`, even when the right
 * column is collapsed. Leaving `/questions` is what stops the poll.
 */
const { t } = useAppI18n()
const route = useRoute()
const router = useRouter()
const store = useQuestionsStore()
const agent = useBankAgentStore()
const selection = useExportSelectionStore()
const toasts = useToastsStore()
const {
  rows: selectedRows,
  loading: selectedLoading,
  loadError: selectedLoadError,
  reload: reloadSelected,
} = useSelectedQuestions()

const prefs = readBankAgentPrefs()

/** Placeholder cards while the first page loads. */
const SKELETON_CARDS = 3

const createOpen = ref(false)
const categoriesOpen = ref(false)
const leftView = ref<BankView>('bank')
const agentOpen = ref(prefs.agentOpen)
/** When set, the bank list shows only this proposal so the person can read it. */
const focusedQuestionId = ref<number | null>(null)
/** Browse state from just before the last proposal jump; Esc puts it back. */
const browseSnapshot = ref<BankBrowseSnapshot | null>(null)
const restoringBrowse = ref(false)
const listWrap = ref<HTMLElement | null>(null)

const pageTitle = computed(() =>
  leftView.value === 'selected'
    ? t('bank.pageTitleSelected', { count: formatCount(selection.count) })
    : t('bank.pageTitle', { count: formatCount(store.bankTotal) }),
)

function conversationQuery(): string | null {
  const raw = route.query[CONVERSATION_QUERY_KEY]
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value : null
}

function parseConversationId(raw: string | null): number | null {
  if (raw === null) {
    return null
  }
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function stripConversationQuery(): void {
  if (conversationQuery() === null) {
    return
  }
  const query = { ...route.query }
  delete query[CONVERSATION_QUERY_KEY]
  void router.replace({ query })
}

function persistPrefs(): void {
  writeBankAgentPrefs({
    agentOpen: agentOpen.value,
    activeConversationId: agent.activeId,
  })
}

function openAgent(): void {
  agentOpen.value = true
  persistPrefs()
}

function closeAgent(): void {
  agentOpen.value = false
  persistPrefs()
}

function showSelected(): void {
  leftView.value = 'selected'
}

const focusedQuestion = computed(() => {
  const id = focusedQuestionId.value
  if (id === null) {
    return undefined
  }
  const fromBank = store.bank.find((question) => question.id === id)
  if (fromBank !== undefined) {
    return fromBank
  }
  return agent.proposedQuestion(id)
})

function questionAnchorId(questionId: number): string {
  return `bank-question-${questionId}`
}

async function scrollToQuestion(questionId: number): Promise<void> {
  await nextTick()
  document.getElementById(questionAnchorId(questionId))?.scrollIntoView({
    block: 'start',
    behavior: 'smooth',
  })
}

function copyFilters(filters: QuestionBankFilters): QuestionBankFilters {
  return {
    type: filters.type,
    difficulty: filters.difficulty,
    subjectId: filters.subjectId,
    categoryId: filters.categoryId,
    search: filters.search,
    similarTo: filters.similarTo,
  }
}

function captureBrowseSnapshot(): void {
  browseSnapshot.value = {
    filters: copyFilters(store.filters),
    page: store.bankPage,
    scrollTop: listWrap.value?.scrollTop ?? 0,
  }
}

async function restoreBrowseSnapshot(): Promise<void> {
  const snapshot = browseSnapshot.value
  if (snapshot === null) {
    focusedQuestionId.value = null
    return
  }
  restoringBrowse.value = true
  focusedQuestionId.value = null
  leftView.value = 'bank'
  store.setFilters(copyFilters(snapshot.filters))
  store.setBankPage(snapshot.page)
  await store.loadBank({ silent: true })
  await nextTick()
  if (listWrap.value !== null) {
    listWrap.value.scrollTop = snapshot.scrollTop
  }
  browseSnapshot.value = null
  restoringBrowse.value = false
}

/**
 * Show one proposed question on the left. The previous filters, page and
 * scroll position are kept so Esc can put them back
 * (docs/decisions/2026-08-17-bank-on-questions-page.md D14 / D15).
 */
async function onOpenProposal(questionId: number): Promise<void> {
  if (focusedQuestionId.value === null) {
    captureBrowseSnapshot()
  }
  leftView.value = 'bank'
  focusedQuestionId.value = questionId
  await scrollToQuestion(questionId)
}

function showBank(): void {
  if (focusedQuestionId.value !== null) {
    void restoreBrowseSnapshot()
    return
  }
  leftView.value = 'bank'
}

function isOverlayOpen(): boolean {
  return (
    createOpen.value ||
    categoriesOpen.value ||
    document.querySelector('[role="dialog"], [role="menu"]') !== null
  )
}

function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape' || event.isComposing || event.defaultPrevented) {
    return
  }
  if (focusedQuestionId.value === null || isOverlayOpen()) {
    return
  }
  event.preventDefault()
  void restoreBrowseSnapshot()
}

/**
 * Prefer the in-flight turn, whichever conversation started it, so switching
 * chats does not drop the poll. With no pending turn, retry still needs the
 * failed job on the conversation currently open in the column.
 */
const watchedJobId = computed<number | null>(() => {
  if (agent.pendingTurn !== null) {
    return agent.pendingTurn.jobId
  }
  const id = agent.activeId
  if (id === null) {
    return null
  }
  if (agent.failedTurn?.conversationId === id) {
    return agent.failedTurn.jobId
  }
  return null
})

const { status, progress, error, requestError, retry } = useJobPolling(watchedJobId)

watch(
  () => agent.activeId,
  () => {
    persistPrefs()
  },
)

watch(conversationQuery, (raw) => {
  const id = parseConversationId(raw)
  if (id === null) {
    return
  }
  agentOpen.value = true
  persistPrefs()
  void agent.selectConversation(id)
  stripConversationQuery()
})

// The turn's job is the only thing that says the reply exists; a status that
// reached a terminal state hands back to the store, which rereads the
// conversation on success and keeps the failure readable otherwise.
watch(
  status,
  (value, previous) => {
    if (value === previous || agent.pendingTurn === null) {
      return
    }
    if (value === 'done') {
      void agent.finishTurn(true)
      toasts.success(t('bankAgent.turn.done'))
      return
    }
    if (value === 'failed') {
      void agent.finishTurn(false)
      toasts.error(t('bankAgent.turn.failedNoDetail'))
    }
  },
  // Cached terminal status after leaving mid-turn will not change again, so
  // the first run has to collect it.
  { immediate: true },
)

/**
 * Put a failed turn back in the queue. The job store swallows a failed retry
 * request into `requestError` rather than throwing, so the outcome is read
 * from the job's own status: only a job that actually left its terminal state
 * counts as pending again — otherwise the composer would stay locked waiting
 * for a turn that was never requeued.
 */
async function onRetryTurn(): Promise<void> {
  await retry()
  const current = status.value
  if (current === null || isTerminalJobStatus(current)) {
    toasts.error(t('bankAgent.turn.retryFailed'))
    return
  }
  agent.resumeFailedTurn()
  toasts.success(t('bankAgent.turn.retried'))
}

onMounted(async () => {
  document.addEventListener('keydown', onDocumentKeydown)
  await store.loadBank({ silent: store.bankLoaded })
  await agent.ensureLoaded()
  const fromQuery = parseConversationId(conversationQuery())
  if (fromQuery !== null) {
    agentOpen.value = true
    persistPrefs()
    await agent.selectConversation(fromQuery)
    stripConversationQuery()
    return
  }
  const storedId = prefs.activeConversationId
  if (storedId !== null && agent.conversations.some((row) => row.id === storedId)) {
    await agent.selectConversation(storedId)
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', onDocumentKeydown)
})

watch([() => store.filters, () => store.bankPage], () => {
  if (restoringBrowse.value) {
    void store.loadBank({ silent: true })
    return
  }
  focusedQuestionId.value = null
  browseSnapshot.value = null
  void store.loadBank({ silent: true })
})

/** A new question only belongs here when it was saved as approved. */
function onCreated(): void {
  void store.loadBank({ silent: true })
}

/** The copy is a draft, so this page is unchanged; only the queue count moves. */
function onDuplicated(): void {
  void store.loadDrafts({ silent: true })
}

/** A renamed or deleted category can change what the current filter matches. */
function onCategoriesChanged(): void {
  void store.loadBank({ silent: true })
}
</script>

<template>
  <div class="page page--workspace">
    <PageHeader :title="pageTitle">
      <template #actions>
        <AppButton
          v-if="!agentOpen"
          variant="secondary"
          :aria-label="t('bank.agent.open')"
          :title="t('bank.agent.open')"
          @click="openAgent"
        >
          <AppIcon name="conversations" :size="16" />
          <span>{{ t('bank.agent.title') }}</span>
        </AppButton>
        <AppButton variant="secondary" @click="categoriesOpen = true">
          {{ t('bank.categories.action') }}
        </AppButton>
        <AppButton @click="createOpen = true">{{ t('bank.create.action') }}</AppButton>
      </template>
    </PageHeader>

    <div class="bank" :class="{ 'is-collapsed': !agentOpen }">
      <div class="bank__main">
        <div class="bank__toolbar">
          <div class="bank__views" role="group">
            <button
              class="bank__view"
              type="button"
              :aria-pressed="leftView === 'bank'"
              :class="{ 'is-active': leftView === 'bank' }"
              @click="showBank"
            >
              {{ t('bank.views.bank') }}
            </button>
            <button
              class="bank__view"
              type="button"
              :aria-pressed="leftView === 'selected'"
              :class="{ 'is-active': leftView === 'selected' }"
              @click="leftView = 'selected'"
            >
              {{ t('bank.views.selected') }}
            </button>
          </div>

          <QuestionFilters v-if="leftView === 'bank' && focusedQuestionId === null" />

          <ExportSelectionBar @view-selected="showSelected" />

          <QuestionEmbedNotice v-if="leftView === 'bank' && focusedQuestionId === null" />

          <p v-if="leftView === 'bank' && store.bankError !== null" class="error-banner">
            {{ store.bankError }}
            <AppButton variant="secondary" @click="store.loadBank()">
              {{ t('bank.reload') }}
            </AppButton>
          </p>

          <p v-if="leftView === 'selected' && selectedLoadError !== null" class="error-banner">
            {{ selectedLoadError }}
            <AppButton variant="secondary" @click="reloadSelected()">
              {{ t('bank.reload') }}
            </AppButton>
          </p>
        </div>

        <div ref="listWrap" class="bank__list-wrap">
          <template v-if="leftView === 'bank'">
            <ul v-if="store.bankLoading && store.bankCount === 0" class="bank__list">
              <li v-for="index in SKELETON_CARDS" :key="`skeleton-${index}`" class="bank__skeleton">
                <AppSkeleton width="30%" />
                <AppSkeleton />
                <AppSkeleton width="70%" />
              </li>
            </ul>

            <ul
              v-else-if="focusedQuestionId !== null && focusedQuestion !== undefined && focusedQuestion !== null"
              class="bank__list"
            >
              <li :id="questionAnchorId(focusedQuestion.id)">
                <BankQuestionCard :question="focusedQuestion" @duplicated="onDuplicated" />
              </li>
            </ul>

            <p
              v-else-if="focusedQuestionId !== null && focusedQuestion === null"
              class="bank__unavailable"
            >
              {{ t('bank.selection.unavailable', { id: focusedQuestionId }) }}
            </p>

            <ul v-else-if="store.bankCount > 0" class="bank__list">
              <li
                v-for="question in store.bank"
                :id="questionAnchorId(question.id)"
                :key="question.id"
              >
                <BankQuestionCard :question="question" @duplicated="onDuplicated" />
              </li>
            </ul>

            <EmptyState
              v-else-if="store.bankLoaded"
              :title="t('bank.emptyTitle')"
              :description="t('bank.emptyDescription')"
            >
              <template #actions>
                <RouterLink class="bank__link" :to="{ name: 'review' }">
                  {{ t('bank.goReview') }}
                </RouterLink>
              </template>
            </EmptyState>
          </template>

          <template v-else>
            <ul v-if="selectedLoading && selection.count > 0" class="bank__list">
              <li
                v-for="index in SKELETON_CARDS"
                :key="`selected-skeleton-${index}`"
                class="bank__skeleton"
              >
                <AppSkeleton width="30%" />
                <AppSkeleton />
                <AppSkeleton width="70%" />
              </li>
            </ul>

            <ul v-else-if="selection.count > 0" class="bank__list">
              <li v-for="row in selectedRows" :key="row.id">
                <BankQuestionCard
                  v-if="row.question !== null"
                  :question="row.question"
                  @duplicated="onDuplicated"
                />
                <p v-else class="bank__unavailable">
                  {{ t('bank.selection.unavailable', { id: row.id }) }}
                </p>
              </li>
            </ul>

            <EmptyState
              v-else
              :title="t('bank.emptySelectedTitle')"
              :description="t('bank.emptySelectedDescription')"
            />
          </template>
        </div>

        <AppPagination
          v-if="leftView === 'bank' && focusedQuestionId === null && store.bankPageCount > 1"
          :page="store.bankPage"
          :page-count="store.bankPageCount"
          :total="store.bankTotal"
          :disabled="store.bankLoading"
          @change="store.setBankPage($event)"
        />
      </div>

      <aside v-if="!agentOpen" class="bank__rail">
        <AppButton
          variant="ghost"
          size="sm"
          :aria-label="t('bank.agent.open')"
          :title="t('bank.agent.open')"
          @click="openAgent"
        >
          <AppIcon name="chevronLeft" :size="16" />
        </AppButton>
      </aside>

      <BankAgentColumn
        v-else
        class="bank__agent"
        :turn-status="status"
        :turn-progress="progress"
        :turn-error="error"
        :turn-request-error="requestError"
        @collapse="closeAgent"
        @retry-turn="onRetryTurn"
        @open-proposal="onOpenProposal"
      />
    </div>

    <QuestionCreateModal :open="createOpen" @close="createOpen = false" @created="onCreated" />
    <CategoryManagerModal
      :open="categoriesOpen"
      @close="categoriesOpen = false"
      @changed="onCategoriesChanged"
    />
  </div>
</template>

<style scoped>
.bank {
  display: grid;
  flex: 1;
  grid-template-columns: minmax(0, 1fr) 22rem;
  grid-template-rows: minmax(0, 1fr);
  align-items: stretch;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.bank.is-collapsed {
  grid-template-columns: minmax(0, 1fr) auto;
}

.bank__main,
.bank__agent,
.bank__rail {
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.bank__main {
  display: flex;
  flex-direction: column;
}

.bank__toolbar {
  flex: none;
}

.bank__views {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-3) 0 0;
}

.bank__view {
  padding: var(--space-1) var(--space-3);
  border: none;
  border-bottom: 2px solid transparent;
  background: none;
  color: var(--color-text-muted);
  font: inherit;
  font-size: var(--font-size-md);
  cursor: pointer;
}

.bank__view:hover {
  color: var(--color-heading);
}

.bank__view.is-active {
  border-bottom-color: var(--color-heading);
  color: var(--color-heading);
  font-weight: 600;
}

.bank__list-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.bank__list {
  display: flex;
  flex-direction: column;
  padding: 0;
  list-style: none;
}

.bank__skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.bank__unavailable {
  padding: var(--space-4) 0;
  border-bottom: 1px solid var(--color-hairline);
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
}

.bank__list > li {
  scroll-margin-top: var(--space-3);
}

.bank__link {
  color: var(--color-accent);
}

.bank__rail {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: var(--space-3) var(--space-1);
  border-left: 1px solid var(--color-border);
}

.bank__agent {
  border-left: 1px solid var(--color-border);
}

.bank :deep(.pagination) {
  flex: none;
  padding: var(--space-3) 0 var(--space-2);
}

@media (max-width: 640px) {
  .bank,
  .bank.is-collapsed {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(0, 1fr) auto;
  }

  .bank__agent,
  .bank__rail {
    height: min(28rem, 50vh);
    border-left: none;
    border-top: 1px solid var(--color-border);
  }
}
</style>
