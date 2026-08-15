/**
 * Wording for the Word export vocabulary.
 *
 * A paper size is stored as its bare name (`A4`), while the page shows the name
 * together with the millimetres it renders at. The dimensions come from
 * `src/api/config.ts` and the phrasing from the locale file, so neither is
 * written into a component.
 */

import { findPaperSize } from '@/api'
import { translate } from '@/i18n'

/**
 * `A4（210 × 297 mm）`.
 *
 * A name outside the three supported sizes is returned verbatim: `paper_size`
 * is a plain string column, and showing what is actually stored beats hiding
 * the row behind a guess.
 */
export function paperSizeLabel(name: string): string {
  const spec = findPaperSize(name)
  if (spec === null) {
    return name
  }
  return translate('exports.paperOption', {
    name: spec.name,
    width: spec.widthMm,
    height: spec.heightMm,
  })
}
