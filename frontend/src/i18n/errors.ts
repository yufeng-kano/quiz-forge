/**
 * Turns an `ApiError` into a string that can be displayed as-is.
 *
 * It lives in the i18n layer rather than the API layer: `src/api/` only
 * classifies failures (`ApiError.code`), while all wording stays in the locale
 * file. Stores and components therefore receive an already-localised message.
 */

import { ApiError } from '@/api'
import { translate } from './index'

export function translateApiError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return translate('errors.unknown')
  }
  switch (error.code) {
    case 'network':
      return translate('errors.network')
    case 'invalid_response':
      return translate('errors.invalidResponse')
    case 'http':
      return error.detail === null
        ? translate('errors.http', { status: error.status })
        : translate('errors.httpWithDetail', { status: error.status, detail: error.detail })
  }
}
