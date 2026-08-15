/**
 * Locale keys for the background-task vocabulary.
 *
 * `jobs.kind` is a plain string column, so a kind this build does not know is
 * displayed with the raw backend value instead of being hidden or renamed.
 */

import { isJobKind, type JobKind } from '@/api'
import { translate, type MessageKey } from '@/i18n'

export const JOB_KIND_LABEL_KEYS: Record<JobKind, MessageKey> = {
  parse_document: 'job.kind.parseDocument',
  parse_page: 'job.kind.parsePage',
  rechunk_document: 'job.kind.rechunkDocument',
  generate_questions: 'job.kind.generateQuestions',
  export_docx: 'job.kind.exportDocx',
}

/** Name of a `jobs.kind` value, falling back to the value itself. */
export function jobKindLabel(kind: string): string {
  return isJobKind(kind) ? translate(JOB_KIND_LABEL_KEYS[kind]) : kind
}
