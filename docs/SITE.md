# Komicove website

The public site is static HTML with no build step or runtime dependencies.
Existing technical documentation, release notes, and image assets are retained.

## Files

- `styles.css`: existing shared layout and interaction styles, formatted for maintenance.
- `cinematic.css`: visual system shared by every public page, including responsive layouts.
- `mobile.css`: phone-specific navigation, Android-first downloads, guide layouts, and touch spacing.
- `help.css` and `help-hub.js`: the Reader's Desk layout for Docs, Tutorials, and Downloads, with a sticky grouped index, topic finder, and a phone drawer.
- `download-versions.css` and `download-versions.js`: version selection on the homepage and download page, release asset links, package availability, and per-version counts. The catalog also includes earlier PANEL releases and counts every release asset in the project total.
- `home-url.js`, `sitemap.xml`, and `robots.txt`: clean homepage URLs, direct file preview links, and search discovery for the canonical domain.
- `assets/hero-noir.webp` and `assets/comic-cover.webp`: existing Komicove artwork optimized for the cover and feature story.
- `assets/logo.png` and `assets/komicove.ico`: official Komicove artwork used in the site identity and favicon.
- `assets/komicove-preview.mp4` and `assets/komicove-preview.webp`: 25-second, silent desktop tour cut from the supplied screen recording and its poster.
- `assets/komicove-android-preview.mp4` and `assets/komicove-android-preview.webp`: 13-second, silent Android tour cut from the supplied mobile recording and its poster.
- `translations.js`: shared English and Brazilian Portuguese messages.
- `theme.js`: system theme detection, saved theme choice, theme controls, and tab synchronization.
- `app.js`: translation, saved language preference, grouped mobile navigation, gallery tabs, image fallback, dialog, and FAQ interactions.
- `novidades.html`: short bilingual release page for version 0.2.1.1.
- `news.js`: language handling for the release page.
- `docs.html`, `tutoriais.html`, `download.html`, and `apoie.html`: device guides, six complete text tutorials ready for future videos, an official package download index, and support information with Pix and the known annual domain cost.
- `GRAVACOES_TUTORIAIS.md`: the creator's two-day recording checklist for site review and tutorial footage.
- `guide.js`: language, navigation, and Pix copy interactions for the guide pages.
- `assets/social-card.png`: 1200 x 630 preview used when the site is shared.

English is the default. The EN / PT-BR selector saves the preference in
`localStorage` under `komicove.site.language`. If storage is unavailable,
switching still works for the current visit. Changes propagate to other open
tabs. Titles, descriptions, image alternatives, and accessibility labels are
translated alongside visible content. Original app screenshots retain their
original language; this is explained beside the previews.

The first visit follows the system's light or dark setting. An inline head script
sets the theme before styles load, avoiding a flash of the other theme. The toggle
saves the choice under `komicove.site.theme` and applies it across all public
pages. The administration page uses the same preference.

The homepage leads from the full-width cover to task-based quick paths and
downloads, then moves through desktop and Android video previews, screenshots, features, formats, installation
notes, community, news, roadmap, project information, support, and FAQ. The
header keeps the app, docs, tutorials, support, and a dedicated download index one click away;
the mobile menu uses the same destinations. On phones, Android is the first
download and the cover offers a direct APK link. The support page shows the
confirmed R$ 7.08 yearly cost of the komicove.online domain and explains other
proposed uses without claiming a fixed budget or allocation.
Docs, Tutorials, and Downloads share the Reader's Desk. Its topic finder filters
the visible navigation labels, `/` focuses it, and Escape closes the phone
drawer. The article remains available as ordinary HTML if JavaScript is off.
The homepage download section and its original anchors remain available.
Once the quick-path strip leaves the viewport, a floating three-line control
opens the same four destinations. It closes on Escape, outside click, or when
the original strip returns, and respects reduced-motion preferences.
The desktop and Android tours sit side by side on large screens. Android leads
when they stack on smaller screens. Only the video preferred for the viewport
starts automatically while visible; both pause when the page is hidden, and
neither starts automatically when reduced motion is preferred. Native video
controls remain available for manual playback and fullscreen viewing.

The homepage and download page share a saved release selection. The menu uses
the public GitHub Releases API to add releases with downloadable files,
including earlier PANEL versions. It updates links to the actual assets,
hides missing package types, and shows counts for the selected release and
every public release asset combined. The catalog is cached
for 15 minutes in local storage. Seventeen confirmed versions and their links are
bundled for offline or rate-limited access. If live counts are unavailable,
the counters stay hidden or use the last cached values. The unselected latest
release remains usable without JavaScript.

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
Static verification checks translation parity, section order, download destinations,
local assets, internal anchors, unique ids, JavaScript syntax, and theme behavior.

When reviewing a visual change, check English and PT-BR, persistence after reload,
keyboard gallery navigation, screenshot expansion and Escape, FAQ disclosure,
mobile menu navigation, and layouts at desktop, 390px, and 320px widths.
Downloads preserve the existing official GitHub release destinations; package
availability is decided by those release pages. No deployment is required to
review the local changes.
