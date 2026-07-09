# ADR-0005: i18n is deferred

## Status

Accepted.

## Context

The transplanted apparatus arrived with a full i18n enforcement suite: gettext extraction
checks on the backend, catalogue validation, a hardcoded-string ratchet with a committed
baseline, and message compilation on the frontend. It was built for a product that ships in four
languages.

Zita ships in none. There is no i18n library, no message catalogue, no `.po` file, no locale
routing.

But it is not monolingual either. The navigation labels are Kinyarwanda. The phone validator
rejects a bad number with *"Nimero Igomba kuba 07X XXX XXX cg +250 7XX XXX XXX"*. The chat
feature is called Tubaze. Prices render in RWF. The strings are simply hardcoded, mixed in
with English, wherever they happen to be needed.

Running those gates here would have checked catalogues that do not exist — the precise failure of
[ADR-0009](0009-a-gate-must-be-seen-to-fail.md).

## Decision

**Delete the i18n gates. Do not adopt an i18n library yet.**

Removed: `check_translations.py`, `compile-i18n.js`, `validate-translations.js`,
`check-i18n-hardcoded.mjs`, `check-i18n-imports.sh`, `i18n-hardcoded-baseline.json`, and the
`i18n-check` / `i18n-hardcoded` Makefile targets on both sides.

## Consequences

Kinyarwanda strings keep accumulating in components, and extracting them later will be
tedious in proportion to how long we wait. That is a known, accepted debt.

The gate we did not take — a hardcoded-string ratchet with a baseline, failing only on *new*
hardcoded strings — was the tempting middle path. It was rejected because a ratchet against a
codebase with no catalogue has nothing to ratchet toward: every string is "hardcoded", so the
baseline is the entire UI, and the gate degenerates into a list.

We revisit this the moment either becomes true:

- The shop needs English and Kinyarwanda **selectable**, rather than mixed. That is a product
  decision, not a technical one.
- A third language is requested.

At that point: pick a library (`next-intl` is the obvious fit for App Router), extract, and
*then* install the ratchet — pointed at a catalogue that exists.
