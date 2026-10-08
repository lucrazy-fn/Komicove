# Komicove website

The public site is `index.html` with no build step or runtime dependencies.
Existing technical documentation, release notes, and image assets are retained.

## Files

- `styles.css`: existing shared layout and interaction styles, formatted for maintenance.
- `design.css`: visual refinements, real app previews, language selector, platform downloads, and responsive layouts.
- `translations.js`: shared English and Brazilian Portuguese messages.
- `app.js`: translation, saved language preference, mobile navigation, gallery tabs, image fallback, dialog, and FAQ interactions.
- `novidades.html`: short bilingual release page for version 0.2.1.1.
- `news.js`: language handling for the release page.
- `assets/social-card.png`: 1200 x 630 preview used when the site is shared.

English is the default. The EN / PT-BR selector saves the preference in
`localStorage` under `komicove.site.language`. If storage is unavailable,
switching still works for the current visit. Changes propagate to other open
tabs. Titles, descriptions, image alternatives, and accessibility labels are
translated alongside visible content. Original app screenshots retain their
original language; this is explained beside the previews.

Download totals come from the public GitHub Releases API. The site sums the
assets for each platform and caches the result for 15 minutes in local storage.
If the API is unavailable, the counters stay hidden or use the last cached value.

For new interface copy, add the same message key in both dictionaries and use
`data-i18n="key"`, `data-i18n-alt="key"`, or `data-i18n-aria-label="key"`.
Use `t('key')` for dynamically generated controls. Keep the static HTML in English
so content and the real library screenshot remain available without JavaScript.

## Preview and verification

From the repository root:

```sh
node tools/preview-site.cjs
node tools/verify-site.cjs
```

Preview: `http://127.0.0.1:4173`.
Static verification checks translation parity, required sections, local assets,
internal anchors, unique ids, and JavaScript syntax.

Browser verification covered English and PT-BR, persistence after reload,
keyboard gallery navigation, screenshot expansion and Escape, FAQ disclosure,
mobile menu navigation, and layouts at desktop, 390px, and 320px widths.
Downloads preserve the existing official GitHub release destinations; package
availability is decided by those release pages. No deployment is required to
review the local changes.
