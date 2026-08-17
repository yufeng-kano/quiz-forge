<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { QuestionType } from '@/api'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import type { SelectedQuestionRow } from '@/composables/useSelectedQuestions'
import {
  distributePoints,
  parsePercentInput,
  parsePointsInput,
  percentShares,
  totalPoints,
} from '@/export/scoring'
import { useAppI18n } from '@/i18n'
import { formatCount } from '@/i18n/number'
import { questionTypeLabel } from '@/questions/labels'
import { questionPreview } from '@/questions/preview'
import { useExportPrefsStore } from '@/stores/exportPrefs'
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
 * Scoring is the per-question map in `exportSelection` and nothing else
 * (docs/decisions/2026-08-18-generate-row-difficulty-percent-scoring.md D33).
 * The tools at the top only write that map: 全部平均 splits the target total
 * evenly over every question, 依比例分配 gives each question type its
 * percentage of the target (a habit, persisted in `exportPrefs`) and splits
 * evenly inside the type. The per-question fields stay editable for manual
 * fine-tuning afterwards.
 *
 * The fields keep their own raw text while the committed values stay numbers:
 * a half-typed 「1」 on the way to 「12」 belongs on screen, but only a positive
 * whole number is a value worth committing, so anything else simply drops the
 * entry. Every keystroke commits, which is what keeps the running total in the
 * footer live. All numeric fields read `element.value` instead of `v-model`
 * (D34 — `v-model` on a number input auto-casts to `number`).
 */
const props = defineProps<{
  open: boolean
  rows: readonly SelectedQuestionRow[]
  /** The question types present in the selection, in the fixed type order. */
  types: readonly QuestionType[]
}>()

const emit = defineEmits<{ close: [] }>()

const { t } = useAppI18n()
const prefs = useExportPrefsStore()
const selection = useExportSelectionStore()

/** Raw field text, keyed the same way as the committed values. */
const targetInput = ref('')
const percentInput = ref<Partial<Record<QuestionType, string>>>({})
const questionInput = ref<Record<number, string>>({})

const selectedIds = computed(() => props.rows.map((row) => row.id))

const total = computed(() => totalPoints(selectedIds.value, selection.questionPoints))

const hasOverrides = computed(() => Object.keys(selection.questionPoints).length > 0)

interface QuestionRowView {
  id: number
  /** Position on the paper, which is the order the questions were picked in. */
  no: number
  /** `null` marks a question that is no longer in the approved bank. */
  typeLabel: string | null
  preview: string
}

const rowViews = computed<QuestionRowView[]>(() =>
  props.rows.map((row, index) => {
    const question = row.question
    return {
      id: row.id,
      no: index + 1,
      typeLabel: question === null ? null : questionTypeLabel(question.type),
      preview: question === null ? t('exports.selection.unavailable') : questionPreview(question),
    }
  }),
)

/** The 依比例分配 groups: each present type with its questions in paper order. */
const typeGroups = computed(() =>
  props.types.map((type) => ({
    type,
    label: questionTypeLabel(type),
    ids: props.rows
      .filter((row) => row.question !== null && row.question.type === type)
      .map((row) => row.id),
    percent: prefs.typePercents[type] ?? null,
  })),
)

const percentSum = computed(() =>
  typeGroups.value.reduce((sum, group) => sum + (group.percent ?? 0), 0),
)

const allPercentsSet = computed(
  () => typeGroups.value.length > 0 && typeGroups.value.every((group) => group.percent !== null),
)

/**
 * Every question has to end up with at least one point, so a target below the
 * question count cannot be split — the button stays disabled.
 */
const canDistributeAll = computed(
  () => props.rows.length > 0 && prefs.targetTotal >= props.rows.length,
)

/**
 * The minimum is only worth a line once a target has actually been typed that
 * cannot be split; a permanent hint would say nothing the empty field does not
 * (docs/frontend.md 設計節制原則).
 */
const targetTooSmall = computed(() => props.rows.length > 0 && !canDistributeAll.value)

/** One integer share per group, only meaningful while the percents sum to 100. */
const groupShares = computed<number[] | null>(() => {
  if (!allPercentsSet.value || percentSum.value !== 100) {
    return null
  }
  return percentShares(
    prefs.targetTotal,
    typeGroups.value.map((group) => group.percent ?? 0),
  )
})

/** The first type whose share cannot give each of its questions one point. */
const shareTooSmall = computed(() => {
  const shares = groupShares.value
  if (shares === null) {
    return null
  }
  for (const [index, group] of typeGroups.value.entries()) {
    const share = shares[index] ?? 0
    if (group.ids.length > 0 && share < group.ids.length) {
      return { label: group.label, share, count: group.ids.length }
    }
  }
  return null
})

const canDistributeByPercent = computed(
  () => groupShares.value !== null && shareTooSmall.value === null && selectedIds.value.length > 0,
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
  targetInput.value = String(prefs.targetTotal)
  const next: Partial<Record<QuestionType, string>> = {}
  for (const type of props.types) {
    const percent = prefs.typePercents[type]
    if (percent !== undefined) {
      next[type] = String(percent)
    }
  }
  percentInput.value = next
  syncQuestionInput()
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

function onTargetInput(event: Event): void {
  const element = event.target
  if (!(element instanceof HTMLInputElement)) {
    return
  }
  targetInput.value = element.value
  const parsed = parsePointsInput(element.value)
  if (parsed !== null) {
    prefs.targetTotal = parsed
  }
}

function onPercentInput(type: QuestionType, event: Event): void {
  const element = event.target
  if (!(element instanceof HTMLInputElement)) {
    return
  }
  percentInput.value = { ...percentInput.value, [type]: element.value }

  const parsed = parsePercentInput(element.value)
  const next = { ...prefs.typePercents }
  if (parsed === null) {
    delete next[type]
  } else {
    next[type] = parsed
  }
  prefs.typePercents = next
}

function onQuestionInput(questionId: number, event: Event): void {
  const element = event.target
  if (!(element instanceof HTMLInputElement)) {
    return
  }
  questionInput.value = { ...questionInput.value, [questionId]: element.value }
  selection.setQuestionPoints(questionId, parsePointsInput(element.value))
}

/** 全部平均 — the target split evenly over every selected question. */
function distributeAll(): void {
  if (!canDistributeAll.value) {
    return
  }
  const shares = distributePoints(prefs.targetTotal, props.rows.length)
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

/** 依比例分配 — each type gets its percentage, split evenly inside the type. */
function distributeByPercent(): void {
  const shares = groupShares.value
  if (shares === null || !canDistributeByPercent.value) {
    return
  }
  const next: Record<number, number> = {}
  typeGroups.value.forEach((group, groupIndex) => {
    const groupPoints = distributePoints(shares[groupIndex] ?? 0, group.ids.length)
    group.ids.forEach((id, index) => {
      const points = groupPoints[index]
      if (points !== undefined) {
        next[id] = points
      }
    })
  })
  selection.replaceQuestionPoints(next)
  syncQuestionInput()
}

/** Drops every score, leaving the paper back on hand-filled 配分 blanks. */
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
        <h3 class="scoring__heading">{{ t('exports.scoring.toolsSection') }}</h3>

        <div class="scoring__target">
          <label class="scoring__target-field">
            <span>{{ t('exports.scoring.targetLabel') }}</span>
            <input
              class="form-input scoring__input"
              type="number"
              min="1"
              step="1"
              inputmode="numeric"
              :value="targetInput"
              @input="onTargetInput"
            />
          </label>
          <AppButton
            variant="secondary"
            size="sm"
            :disabled="!canDistributeAll"
            @click="distributeAll"
          >
            {{ t('exports.scoring.distributeAll') }}
          </AppButton>
        </div>

        <p v-if="targetTooSmall" class="form-error">
          {{ t('exports.scoring.distributeMin', { count: props.rows.length }) }}
        </p>

        <template v-if="typeGroups.length > 0">
          <div class="scoring__percents">
            <label v-for="group in typeGroups" :key="group.type" class="scoring__percent">
              <span class="scoring__percent-label">
                {{ t('exports.scoring.percentOf', { type: group.label, count: group.ids.length }) }}
              </span>
              <input
                class="form-input scoring__input scoring__input--percent"
                type="number"
                min="1"
                max="100"
                step="1"
                inputmode="numeric"
                :value="percentInput[group.type] ?? ''"
                :aria-label="t('exports.scoring.percentInputLabel', { type: group.label })"
                @input="onPercentInput(group.type, $event)"
              />
              <span class="scoring__percent-sign">%</span>
            </label>
          </div>

          <div class="scoring__percent-actions">
            <span
              class="scoring__percent-sum"
              :class="{ 'scoring__percent-sum--off': allPercentsSet && percentSum !== 100 }"
            >
              {{ t('exports.scoring.percentSum', { sum: percentSum }) }}
            </span>
            <AppButton
              variant="secondary"
              size="sm"
              :disabled="!canDistributeByPercent"
              @click="distributeByPercent"
            >
              {{ t('exports.scoring.distributeByPercent') }}
            </AppButton>
          </div>

          <p v-if="shareTooSmall !== null" class="form-error">
            {{
              t('exports.scoring.percentShareTooSmall', {
                type: shareTooSmall.label,
                share: shareTooSmall.share,
                count: shareTooSmall.count,
              })
            }}
          </p>
        </template>
      </section>

      <section class="scoring__section">
        <h3 class="scoring__heading">{{ t('exports.scoring.questionSection') }}</h3>

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
                :placeholder="t('exports.scoring.inheritNone')"
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

.scoring__target {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.scoring__target-field {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  white-space: nowrap;
}

.scoring__percents {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
}

.scoring__percent {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  white-space: nowrap;
}

.scoring__percent-label {
  color: var(--color-text);
}

.scoring__percent-sign {
  color: var(--color-text-muted);
}

.scoring__percent-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}

.scoring__percent-sum {
  font-variant-numeric: tabular-nums;
  color: var(--color-text-muted);
}

/* Percents are typed toward 100: being off it is the one live validation the
   sum line carries */
.scoring__percent-sum--off {
  color: var(--color-status-failed-text);
}

.scoring__input {
  width: 5.5rem;
  flex: none;
}

.scoring__input--percent {
  width: 4.5rem;
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
