/** Option markers shared by the single-choice and analogy renderers. */

const OPTION_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

/**
 * The letter shown in front of an option, `A` for the first one. Beyond the
 * alphabet it falls back to the 1-based position, so an unusually long option
 * list still numbers every entry instead of repeating letters.
 */
export function optionLetter(index: number): string {
  return OPTION_LETTERS[index] ?? String(index + 1)
}
