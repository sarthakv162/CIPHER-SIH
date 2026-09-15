# Rupantar interface

The studio uses the arrangement in the user's reference,
`974b9bd591e4958af0e543d0cca186cb.jpg`: a rounded frame, collapsible sidebar,
centered composer, luminous orb, and three-column feature cards. Translucent
surfaces, inset highlights, visible borders, and category colors carry through
the library, converter, settings, and artifact viewers.

The latest direction adds expressive effects and color themes to the existing
composer and conversation workflow. Decorative visuals are local CSS and SVG.

## Appearance and classification

- Dark is the initial appearance. The header toggle switches light/dark; the
  palette button also offers System, which follows live operating-system changes.
- Aurora, Iris, Ocean, and Ember work in either mode. Preferences persist in
  `rupantar:appearance` in local storage, with an in-memory fallback if unavailable.
- Ambient effects can be disabled. Operating-system reduced-motion preferences
  disable continuous motion and card lift effects regardless of that setting.
- All seven artifact formats are selectable cards, grouped into Documents,
  Social, and Visual & video. Filtering never clears selected formats or source
  drafts. Sidebar category links and workspace filters share the category URL.
- The library combines category, status, and text filters. Cards show the actual
  formats and run status; their small vector illustrations are format previews,
  not generated output thumbnails.

## Readability and interaction

- Main source input: 18px. Document body: 16px. Navigation and controls: 13–14px.
  Compact labels and format metadata are smaller, with explicit focus indicators.
- Output selection and generation settings are labelled, keyboard-accessible
  dialogs. Escape dismisses them. Appearance restores focus to its trigger.
- Enter generates; Shift+Enter adds a line. IME composition does not submit.
- File attachment works through browsing, drag-and-drop, or a local path.
- New transform clears the source draft and resets the output selection.
- Source text shown in a new run is retained only in browser session storage.
  Historical runs remain usable when that session context is absent.
- Verification, provenance, downloads, conversion, and system checks continue to
  use the existing local backend.

## Offline deployment

Fonts, icons, scripts, and styles are local. No new frontend dependencies were
added. The production content security policy allows resources and connections
only from the same origin (plus inline styles and local data/blob media).

Run `scripts/vendor_frontend.sh` to rebuild `frontend/dist/` and check for remote
assets. Serve the result through the existing FastAPI process. The offline machine
does not need Node, an asset CDN, or a UI API service.

Converter uploads use `/sources?purpose=conversion` with a separate file-type
allowlist. The source-ingestion allowlist and filename containment checks still
apply independently to their respective modes.
