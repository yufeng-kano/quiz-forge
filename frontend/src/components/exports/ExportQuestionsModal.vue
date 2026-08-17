<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { ExportPoints, QuestionType } from '@/api'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import type { SelectedQuestionRow } from '@/composables/useSelectedQuestions'
import {
  distributePoints,
  inheritedPoints,
  parsePointsInput,
  toScoredQuestions,
  totalPoints,
} from '@/export/scoring'
import { useAppI18n } from '@/i18n'
import { formatCount } from '@/i18n/number'
import { QUESTION_TYPE_LABEL_KEYS, questionTypeLabel } from '@/questions/labels'
import { questionPreview } from '@/questions/preview'
import { useExportSelectionStore } from '@/stores/exportSelection'

/**
 * 題目與配分 — the selected questions and every scoring decision of one paper,
 * in one dialog (docs/decisions/2026-08-17-professional-form-pages.md D29).
 *
 * It is a modal rather than part of the form because the list grows with the
 * selection: on the page it would push the submit button below two hundred
 * rows, here it scrolls inside a bounded box while the dialog keeps its size
 * (docs/frontend.md 清單有界原則). Each row carries its own remove button, so
 * trimming the paper and scoring it are the same pass over the same list.
 *
 * Two layers of scoring, resolved the way the backend resolves them: a default
 * per question type (`exportPrefs`, persisted), and an override per question
 * (`exportSelection`, this paper only — D30) that wins over it. A blank
 * override field therefore means 「跟著題型走」, and its placeholder shows the
 * value it would inherit so that blank is never ambiguous.
 *
 * The fields keep their own raw text while the committed values stay numbers:
 * a half-typed 「1」 on the way to 「12」 belongs on screen, but only a positive
 * whole number is a score the backend accepts, so anything else simply drops
 * the entry. Every keystroke commits, which is what keeps the running total in
 * the footer live.
 */
const props = defineProps<{
  open: boolean
  rows: readonly SelectedQuestionRow[]
  /** The question types present in the selection, in the fixed type order. */
  types: readonly QuestionType[]
}>()

const emit = defineEmits<{ close: [] }>()

const typePoints = defineModel<ExportPoints>('typePoints', { required: true })

const { t } = useAppI18n()
const selection = useExportSelectionStore()

/** Raw field text, keyed the same way as the committed values. */
const typeInput = ref<Partial<Record<QuestionType, string>>>({})
const questionInput = ref<Record<number, string>>({})
/** 依目標總分平均分配 target; client-side only, never sent anywhere. */
const targetInput = ref('')

const scored = computed(() => toScoredQuestions(props.rows))

const total = computed(() => totalPoints(scored.value, typePoints.value, selection.questionPoints))

const hasOverrides = computed(() => Object.keys(selection.questionPoints).length > 0)

interface QuestionRowView {
  id: number
  /** Position on the paper, which is the order the questions were picked in. */
  no: number
  /** `null` marks a question that is no longer in the approved bank. */
  typeLabel: string | null
  preview: string
  /** What the empty field would inherit, shown as its placeholder. */
  placeholder: string
}

const rowViews = computed<QuestionRowView[]>(() =>
  props.rows.map((row, index) => {
    const question = row.question
    const scoredQuestion = scored.value[index] ?? { id: row.id, type: null }
    const inherited = inheritedPoints(scoredQuestion, typePoints.value)
    return {
      id: row.id,
      no: index + 1,
      typeLabel: question === null ? null : questionTypeLabel(question.type),
      preview: question === null ? t('exports.selection.unavailable') : questionPreview(question),
      // Plain digits, not a grouped number: the placeholder shows what the
      // field would hold if it were typed in.
      placeholder: inherited === null ? t('exports.scoring.inheritNone') : String(inherited),
    }
  }),
)

const targetTotal = computed(() => parsePointsInput(targetInput.value))

/**
 * Every question has to end up with at least one point, so a target below the
 * question count cannot be split — the button stays disabled.
 */
const canDistribute = computed(
  () =>
    props.rows.length > 0 && targetTotal.value !== null && targetTotal.value >= props.rows.length,
)

/**
 * The minimum is only worth a line once a target has actually been typed that
 * cannot be split; a permanent hint would say nothing the empty field does not
 * (docs/frontend.md 設計節制原則).
 */
const targetTooSmall = computed(
  () => props.rows.length > 0 && targetInput.value.trim() !== '' && !canDistribute.value,
)

/** Rebuilds the raw fields from the committed values, dropping stale text. */
function syncQuestionInput(): void {
  const next: Record<number, string> = {}
  for (const row of props.rows) {
    const points = selection.questionPoints[row.id]
    if (points !== undefined) {
      next[row.id] = String(points)
    }
  }
  questionInput.value = next
}

function syncInputs(): void {
  const next: Partial<Record<QuestionType, string>> = {}
  for (const type of props.types) {
    const points = typePoints.value[type]
    if (points !== undefined) {
      next[type] = String(points)
    }
  }
  typeInput.value = next
  syncQuestionInput()
  targetInput.value = ''
}

// Each opening starts from what is actually committed: the selection may have
// changed while the dialog was closed.
watch(
  () => props.open,
  (open) => {
    if (open) {
      syncInputs()
    }
  },
)

function onTypeInput(type: QuestionType, event: Event): void {
  const element = event.target
  if (!(element instanceof HTMLInputElement)) {
    return
  }
  const nextInput: Partial<Record<QuestionType, string>> = { ...typeInput.value }
  nextInput[type] = element.value
  typeInput.value = nextInput

  const parsed = parsePointsInput(element.value)
  const nextPoints: ExportPoints = { ...typePoints.value }
  if (parsed === null) {
    delete nextPoints[type]
  } else {
    nextPoints[type] = parsed
  }
  typePoints.value = nextPoints
}

function onQuestionInput(questionId: number, event: Event): void {
  const element = event.target
  if (!(element instanceof HTMLInputElement)) {
    return
  }
  questionInput.value = { ...questionInput.value, [questionId]: element.value }
  selection.setQuestionPoints(questionId, parsePointsInput(element.value))
}

/**
 * 依目標總分平均分配 — writes the split as per-question overrides so it survives
 * the type defaults and is exactly what the paper will carry.
 */
function distribute(): void {
  const wanted = targetTotal.value
  if (wanted === null || !canDistribute.value) {
    return
  }
  const shares = distributePoints(wanted, props.rows.length)
  const next: Record<number, number> = {}
  props.rows.forEach((row, index) => {
    const share = shares[index]
    if (share !== undefined) {
      next[row.id] = share
    }
  })
  selection.replaceQuestionPoints(next)
  syncQuestionInput()
}

/** Drops every override, leaving each question on its type's default again. */
function clearOverrides(): void {
  selection.clearQuestionPoints()
  questionInput.value = {}
}
</script>

<template>
  <AppModal
    :open="props.open"
    size="lg"
    :title="t('exports.questions.modalTitle')"
    @close="emit('close')"
  >
    <div class="scoring">
      <section class="scoring__section">
        <h3 class="scoring__heading">{{ t('exports.scoring.typeSection') }}</h3>

        <p v-if="props.types.length === 0" class="muted-text">
          {{ t('exports.scoring.noTypes') }}
        </p>

        <div v-else class="scoring__types">
          <label v-for="type in props.types" :key="type" class="scoring__type">
            <span class="scoring__type-label">{{ t(QUESTION_TYPE_LABEL_KEYS[type]) }}</span>
            <input
              class="form-input scoring__input"
              type="number"
              min="1"
              step="1"
              inputmode="numeric"
              :value="typeInput[type] ?? ''"
              @input="onTypeInput(type, $event)"
            />
          </label>
        </div>
      </section>

      <section class="scoring__section">
        <div class="scoring__question-head">
          <h3 class="scoring__heading">{{ t('exports.scoring.questionSection') }}</h3>

          <div class="scoring__distribute">
            <input
              v-model="targetInput"
              class="form-input scoring__input"
              type="number"
              min="1"
              step="1"
              inputmode="numeric"
              :aria-label="t('exports.scoring.targetLabel')"
              :placeholder="t('exports.scoring.targetPlaceholder')"
            />
            <AppButton variant="secondary" size="sm" :disabled="!canDistribute" @click="distribute">
              {{ t('exports.scoring.distribute') }}
            </AppButton>
          </div>
        </div>

        <p v-if="targetTooSmall" class="form-error">
          {{ t('exports.scoring.distributeMin', { count: props.rows.length }) }}
        </p>

        <p v-if="rowViews.length === 0" class="muted-text">{{ t('exports.scoring.noRows') }}</p>

        <ul v-else class="scoring__list">
          <li v-for="row in rowViews" :key="row.id" class="scoring__row">
            <span class="scoring__no">{{ t('exports.scoring.questionNo', { no: row.no }) }}</span>

            <template v-if="row.typeLabel !== null">
              <span class="scoring__row-type">{{ row.typeLabel }}</span>
              <span class="scoring__preview text-ellipsis" :title="row.preview">
                {{ row.preview }}
              </span>
              <input
                class="form-input scoring__input"
                type="number"
                min="1"
                step="1"
                inputmode="numeric"
                :value="questionInput[row.id] ?? ''"
                :placeholder="row.placeholder"
                :aria-label="t('exports.scoring.questionInputLabel', { no: row.no })"
                @input="onQuestionInput(row.id, $event)"
              />
            </template>

            <!-- No score field: this row is what would fail the export, and the
                 remove button beside it is the fix -->
            <span v-else class="scoring__unavailable">{{ row.preview }}</span>

            <AppButton
              variant="ghost"
              icon
              size="sm"
              :aria-label="t('exports.selection.remove', { id: row.id })"
              :title="t('exports.selection.remove', { id: row.id })"
              @click="selection.deselect(row.id)"
            >
              <AppIcon name="close" :size="16" />
            </AppButton>
          </li>
        </ul>
      </section>
    </div>

    <template #actions>
      <span class="scoring__total">
        {{ t('exports.scoring.total', { total: formatCount(total) }) }}
      </span>
      <AppButton variant="ghost" :disabled="!hasOverrides" @click="clearOverrides">
        {{ t('exports.scoring.clear') }}
      </AppButton>
      <AppButton variant="ghost" :disabled="selection.count === 0" @click="selection.clear()">
        {{ t('exports.selection.clear') }}
      </AppButton>
      <AppButton @click="emit('close')">{{ t('exports.scoring.done') }}</AppButton>
    </template>
  </AppModal>
</template>

<style scoped>
.scoring {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.scoring__section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.scoring__heading {
  font-size: var(--font-size-base);
}

.scoring__types {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
}

.scoring__type {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  white-space: nowrap;
}

.scoring__type-label {
  color: var(--color-text);
}

/* The split writes per-question overrides, so it sits on the heading line of
   the list it rewrites instead of being a section of its own */
.scoring__question-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2) var(--space-3);
}

.scoring__distribute {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.scoring__input {
  width: 5.5rem;
  flex: none;
}

/* The one part of the dialog that grows with the selection, so it is the one
   part that scrolls (docs/frontend.md 清單有界原則) */
.scoring__list {
  display: flex;
  flex-direction: column;
  max-height: min(24rem, 55vh);
  overflow-y: auto;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  list-style: none;
}

.scoring__row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-hairline);
}

.scoring__list > li:last-child {
  border-bottom: none;
}

.scoring__no {
  flex: none;
  width: 4.5rem;
  color: var(--color-text-muted);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

/* Question type: a closed set of short words, so plain text in the heading
   tone rather than a pill (docs/frontend.md 設計節制原則) */
.scoring__row-type {
  flex: none;
  width: 5rem;
  color: var(--color-heading);
  white-space: nowrap;
}

.scoring__preview {
  flex: 1;
  min-width: 0;
  color: var(--color-text);
}

.scoring__unavailable {
  flex: 1;
  min-width: 0;
  color: var(--color-status-failed-text);
}

/* Sits at the left end of the dialog's action row, opposite the buttons */
.scoring__total {
  margin-right: auto;
  align-self: center;
  color: var(--color-heading);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
</style>
