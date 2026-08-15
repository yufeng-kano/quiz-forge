/**
 * Tab definitions for `AppTabs.vue`.
 *
 * A tab carries its already-localised `label` (the component resolves no
 * locale keys) and an `id` that is both the value of the `v-model` and the
 * name of the panel slot, so a page cannot end up with a tab whose panel is
 * missing.
 */

export interface AppTabItem<Id extends string = string> {
  /** Unique within the tab set; also the name of the panel slot. */
  readonly id: Id
  /** Localised tab text. */
  readonly label: string
  /** Short count shown after the label (e.g. how many parses are running). */
  readonly badge?: string
}
