<script setup lang="ts">
import { useAppI18n } from '@/i18n'
import { optionLetter } from '@/questions/options'

/**
 * The option list of a single-choice-style question, used by both
 * `single_choice` and an `analogy` that carries options. The correct option is
 * marked rather than only stated in the answer block, so a reviewer can check
 * the marking without cross-referencing.
 *
 * `answerIndex` may be out of range for a payload the backend has not
 * re-validated since an earlier edit; in that case no option is marked instead
 * of the list refusing to render.
 */
defineProps<{ options: readonly string[]; answerIndex: number | null }>()

const { t } = useAppI18n()
</script>

<template>
  <ol class="option-list">
    <li
      v-for="(option, index) in options"
      :key="index"
      class="option-list__item"
      :class="{ 'is-correct': index === answerIndex }"
    >
      <span class="option-list__marker">
        {{ t('questions.option.marker', { letter: optionLetter(index) }) }}
      </span>
      <span class="option-list__text">{{ option }}</span>
      <span v-if="index === answerIndex" class="option-list__correct">
        {{ t('questions.option.correct') }}
      </span>
    </li>
  </ol>
</template>

<style scoped>
.option-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0;
  list-style: none;
}

.option-list__item {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  overflow-wrap: anywhere;
}

.option-list__item.is-correct {
  background: var(--color-status-done-bg);
}

.option-list__marker {
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}

.option-list__text {
  flex: 1;
}

.option-list__correct {
  color: var(--color-status-done-text);
  font-weight: 600;
  white-space: nowrap;
}
</style>
