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
import AppIcon from '@/components/ui/AppIcon.vue'
import { useAppI18n } from '@/i18n'
import {
  DIFFICULTY_LABEL_KEYS,
  DIFFICULTY_LEVELS,
  QUESTION_TYPE_LABEL_KEYS,
} from '@/questions/labels'

/**
 * The 題目設定 section of the 出題 form: 題型 × 數量 × 難度 rows
 * (docs/question-bank.md 出題流程 step 1;
 * docs/decisions/2026-08-18-generate-row-difficulty-percent-scoring.md D31).
 *
 * The section heading and its add trigger live here too, because adding a row
 * is this section's own action: the plus icon sits right of the title (D32).
 *
 * One request must not repeat a question type (`GenerateIn` rejects it with
 * 422), so a row's select offers every type except the ones the other rows
 * already took, and the add trigger stops once all six are in use. That makes
 * the server rule unreachable from the form instead of only reporting it after
 * a failed request.
 *
 * `difficulty` is free text on the backend and goes straight into the prompt,
 * so the option values are the localised level names themselves — see
 * `src/questions/labels.ts`.
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
    replaceAt(index, { ...current, question_type: target.value })
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
  replaceAt(index, { ...current, count })
}

function onDifficultyChange(index: number, event: Event): void {
  const target = event.target
  const current = items.value[index]
  if (!(target instanceof HTMLSelectElement) || current === undefined) {
    return
  }
  const next: GenerateItem = { question_type: current.question_type, count: current.count }
  if (target.value !== '') {
    next.difficulty = target.value
  }
  replaceAt(index, next)
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
    <div class="combos__head">
      <h2 class="form-section__title">{{ t('generate.sections.settings') }}</h2>
      <AppButton
        variant="ghost"
        icon
        size="sm"
        :disabled="!canAdd"
        :aria-label="t('generate.form.addItem')"
        :title="t('generate.form.addItem')"
        @click="addRow"
      >
        <AppIcon name="plus" :size="16" />
      </AppButton>
    </div>

    <ul class="combos__rows">
      <li v-for="(item, index) in items" :key="item.question_type" class="combos__row">
        <label class="form-field combos__type">
          <span v-if="index === 0" class="form-label">{{ t('generate.form.type') }}</span>
          <select
            class="form-select"
            :value="item.question_type"
            :aria-label="t('generate.form.type')"
            @change="onTypeChange(index, $event)"
          >
            <option v-for="type in availableTypes(index)" :key="type" :value="type">
              {{ t(QUESTION_TYPE_LABEL_KEYS[type]) }}
            </option>
          </select>
        </label>

        <label class="form-field combos__count">
          <span v-if="index === 0" class="form-label">{{ t('generate.form.count') }}</span>
          <input
            class="form-input"
            type="number"
            inputmode="numeric"
            :min="GENERATE_COUNT_MIN"
            :max="GENERATE_COUNT_MAX"
            :value="item.count"
            :aria-label="t('generate.form.count')"
            @input="onCountInput(index, $event)"
          />
        </label>

        <label class="form-field combos__difficulty">
          <span v-if="index === 0" class="form-label">{{ t('generate.form.difficulty') }}</span>
          <select
            class="form-select"
            :value="item.difficulty ?? ''"
            :aria-label="t('generate.form.difficulty')"
            @change="onDifficultyChange(index, $event)"
          >
            <option value="">{{ t('generate.form.difficultyAny') }}</option>
            <option
              v-for="level in DIFFICULTY_LEVELS"
              :key="level"
              :value="t(DIFFICULTY_LABEL_KEYS[level])"
            >
              {{ t(DIFFICULTY_LABEL_KEYS[level]) }}
            </option>
          </select>
        </label>

        <!-- md square: the same height as the controls it stands beside -->
        <AppButton
          variant="ghost"
          icon
          :disabled="!canRemove"
          :aria-label="t('generate.form.removeItem')"
          :title="t('generate.form.removeItem')"
          @click="removeRow(index)"
        >
          <AppIcon name="close" :size="16" />
        </AppButton>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.combos {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.combos__head {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.combos__rows {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: 0;
  list-style: none;
}

/* One row, always: 題型｜題數｜難度｜移除 never wrap apart */
.combos__row {
  display: flex;
  flex-wrap: nowrap;
  align-items: flex-end;
  gap: var(--space-2);
}

/* Field widths follow their content (D28): three-character type names, a
   number of at most two digits, three-character difficulty words */
.combos__type {
  flex: 0 0 7rem;
}

.combos__count {
  flex: 0 0 4.5rem;
}

.combos__difficulty {
  flex: 0 0 7.5rem;
}
</style>
