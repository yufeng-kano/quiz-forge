/**
 * Markdown -> sanitized HTML for page content produced by the vision pipeline.
 *
 * Two rules matter here:
 * - The Markdown comes from an LLM, so it is untrusted: `html: false` keeps raw
 *   HTML in the source escaped, and every rendered string still goes through
 *   DOMPurify before a component hands it to `v-html`.
 * - Figures are already rewritten to same-origin `/api/v1/assets/{id}` URLs
 *   (`backend.ingestion.pipeline`), so images are kept as real `<img>` tags and
 *   only constrained by CSS.
 *
 * The renderer is module-level: one instance is shared by every page of every
 * document instead of being rebuilt per component.
 */

import DOMPurify from 'dompurify'
import markdownit from 'markdown-it'

/** Wrapper class that gives a wide table its own horizontal scroll area. */
export const MARKDOWN_SCROLL_CLASS = 'markdown-scroll'

const md = markdownit({ html: false, linkify: true, breaks: false })

md.renderer.rules.table_open = () => `<div class="${MARKDOWN_SCROLL_CLASS}"><table>`
md.renderer.rules.table_close = () => '</table></div>'

// Source documents link out to the open web; opening those in the SPA tab
// would throw away the user's place in the app.
md.renderer.rules.link_open = (tokens, idx, options, _env, self) => {
  const token = tokens[idx]
  if (token !== undefined) {
    token.attrSet('target', '_blank')
    token.attrSet('rel', 'noopener noreferrer')
  }
  return self.renderToken(tokens, idx, options)
}

export function renderMarkdown(source: string): string {
  return DOMPurify.sanitize(md.render(source), {
    USE_PROFILES: { html: true },
    ADD_ATTR: ['target'],
  })
}
