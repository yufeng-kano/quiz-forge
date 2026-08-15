<script setup lang="ts">
import { computed } from 'vue'

import {
  GENERATE_COUNT_DEFAULT,
  GENERATE_COUNT_MAX,
  GENERATE_COUNT_MIN,
  QUESTION_TYPES,
  isQuestionType,
  type GenerateItem,
  type QuestionType,
} from '@/api'
import AppButton from '@/components/AppButton.vue'
import { useAppI18n } from '@/i18n'
import { QUESTION_TYPE_LABEL_KEYS } from '@/questions/labels'

/**
 * The 題型 × 數量 rows of the 出題 form (docs/question-bank.md 出題流程 step 1 —
 * 多個「題型 × 數量」項目，一個 job 出完).
 *
 * One request must not repeat a question type (`GenerateIn` rejects it with
 * 422), so a row's select offers every type except the ones the other rows
 * already took, and 新增題型 stops once all six are in use. That makes the
 * server rule unreachable from the form instead of only reporting it after a
 * failed request.
 */
const items = defineModel<GenerateItem[]>({ required: true })

const { t } = useAppI18n()

/** Types taken by every row but this one, so a row can keep its own value. */
function typesTakenExcept(index: number): Set<QuestionType> {
  return new Set(
    items.value.filter((_, position) => position !== index).map((item) => item.question_type),
  )
}

function availableTypes(index: number): readonly QuestionType[] {
  const taken = typesTakenExcept(index)
  return QUESTION_TYPES.filter((type) => !taken.has(type))
}

const unusedTypes = computed<readonly QuestionType[]>(() => {
  const used = new Set(items.value.map((item) => item.question_type))
  return QUESTION_TYPES.filter((type) => !used.has(type))
})

const canAdd = computed(() => unusedTypes.value.length > 0)

/** The last row stays: a request needs at least one item. */
const canRemove = computed(() => items.value.length > 1)

function replaceAt(index: number, item: GenerateItem): void {
  items.value = items.value.map((existing, position) => (position === index ? item : existing))
}

function onTypeChange(index: number, event: Event): void {
  const target = event.target
  const current = items.value[index]
  if (!(target instanceof HTMLSelectElement) || current === undefined) {
    return
  }
  if (isQuestionType(target.value)) {
    replaceAt(index, { question_type: target.value, count: current.count })
  }
}

function onCountInput(index: number, event: Event): void {
  const target = event.target
  const current = items.value[index]
  if (!(target instanceof HTMLInputElement) || current === undefined) {
    return
  }
  const parsed = Number.parseInt(target.value, 10)
  const count = Number.isNaN(parsed)
    ? GENERATE_COUNT_MIN
    : Math.min(GENERATE_COUNT_MAX, Math.max(GENERATE_COUNT_MIN, parsed))
  replaceAt(index, { question_type: current.question_type, count })
}

function addRow(): void {
  const next = unusedTypes.value[0]
  if (next === undefined) {
    return
  }
  items.value = [...items.value, { question_type: next, count: GENERATE_COUNT_DEFAULT }]
}

function removeRow(index: number): void {
  if (!canRemove.value) {
    return
  }
  items.value = items.value.filter((_, position) => position !== index)
}
</script>

<template>
  <div class="combos">
    <ul class="combos__rows">
      <li v-for="(item, index) in items" :key="item.question_type" class="combos__row">
        <label class="form-field combos__type">
          <span class="form-label">{{ t('generate.form.type') }}</span>
          <select
            class="form-select"
            :value="item.question_type"
            @change="onTypeChange(index, $event)"
          >
            <option v-for="type in availableTypes(index)" :key="type" :value="type">
              {{ t(QUESTION_TYPE_LABEL_KEYS[type]) }}
            </option>
          </select>
        </label>

        <label class="form-field combos__count">
          <span class="form-label">{{ t('generate.form.count') }}</span>
          <input
            class="form-input"
            type="number"
            inputmode="numeric"
            :min="GENERATE_COUNT_MIN"
            :max="GENERATE_COUNT_MAX"
            :value="item.count"
            @input="onCountInput(index, $event)"
          />
        </label>

        <AppButton
          variant="ghost"
          size="sm"
          class="combos__remove"
          :disabled="!canRemove"
          @click="removeRow(index)"
        >
          {{ t('generate.form.removeItem') }}
        </AppButton>
      </li>
    </ul>

    <div class="combos__footer">
      <AppButton variant="secondary" size="sm" :disabled="!canAdd" @click="addRow">
        {{ t('generate.form.addItem') }}
      </AppButton>
      <span class="form-hint">
        {{
          canAdd
            ? t('generate.form.countHint', { min: GENERATE_COUNT_MIN, max: GENERATE_COUNT_MAX })
            : t('generate.form.addItemFull')
        }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.combos {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.combos__rows {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: 0;
  list-style: none;
}

.combos__row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-2) var(--space-3);
}

.combos__type {
  flex: 1 1 12rem;
  min-width: 0;
}

.combos__count {
  flex: 0 0 7rem;
}

.combos__remove {
  /* Sits on the same baseline as the two fields, whose labels add a line above */
  margin-bottom: 0.25rem;
}

.combos__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}
</style>
