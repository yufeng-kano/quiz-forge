/**
 * Icon set of the design system.
 *
 * Icons are inline SVG path data rather than an icon package: the app ships as
 * a static bundle behind nginx and must not pull a font or a sprite from a
 * CDN, and this way an icon costs a few hundred bytes instead of a dependency.
 *
 * Every icon is drawn on a 24×24 grid, stroked (never filled) with
 * `currentColor`, so one definition works at any size and in any tone.
 */

export const ICON_PATHS = {
  /* Navigation */
  dashboard: ['M4 4h6v6H4z', 'M14 4h6v4h-6z', 'M14 12h6v8h-6z', 'M4 14h6v6H4z'],
  documents: ['M13 3H6v18h12V8z', 'M13 3v5h5'],
  generate: [
    'M12 3l1.7 4.3L18 9l-4.3 1.7L12 15l-1.7-4.3L6 9l4.3-1.7z',
    'M17.5 15l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9z',
  ],
  review: ['M9 4h6v3H9z', 'M15 5.5h4V21H5V5.5h4', 'M8.5 13l2.5 2.5L16 10'],
  questions: ['M12 3l9 5-9 5-9-5z', 'M3 13l9 5 9-5'],
  exports: ['M12 4v10', 'M8 11l4 4 4-4', 'M5 20h14'],
  jobs: ['M3 12h4l2.5 7 4-14 2.5 7H21'],
  usage: ['M5 20V10', 'M12 20V4', 'M19 20v-7'],

  /* Controls */
  chevronLeft: ['M14.5 6l-6 6 6 6'],
  chevronRight: ['M9.5 6l6 6-6 6'],
  chevronDown: ['M6 9.5l6 6 6-6'],
  chevronUp: ['M6 14.5l6-6 6 6'],
  close: ['M6 6l12 12', 'M18 6L6 18'],
  upload: ['M12 15V3', 'M8 7l4-4 4 4', 'M4 15v5h16v-5'],
  link: ['M14 4h6v6', 'M20 4l-8.5 8.5', 'M18 14.5V20H4V6h5.5'],
  trash: ['M4.5 7h15', 'M9.5 7V4.5h5V7', 'M6.5 7l1 13h9l1-13'],
  refresh: ['M20 12a8 8 0 11-2.4-5.7', 'M20.5 3.5V9h-5.5'],

  /* Feedback */
  success: ['M12 4a8 8 0 100 16 8 8 0 000-16z', 'M8.5 12.3l2.4 2.4 4.6-5.1'],
  error: ['M12 4a8 8 0 100 16 8 8 0 000-16z', 'M12 8.2v4.6', 'M12 15.6v.4'],
  info: ['M12 4a8 8 0 100 16 8 8 0 000-16z', 'M12 11.2v4.6', 'M12 8.4v.4'],
} as const

export type IconName = keyof typeof ICON_PATHS
