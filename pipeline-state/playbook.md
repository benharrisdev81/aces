format-version: playbook-v1

# Generator Playbook

The Generator's cross-build memory: lessons distilled from completed builds
so quality compounds. This is the defensive mirror of the discriminators'
`attack-library.md` — it stores **what passed review and why**, never
reviewer probe strategies. Reviewers do not read this file; keeping it out
of their working sets preserves the adversarial game's independence.

## Who reads and writes this file

- **Read by**: the Generator only, at Session Startup (step 4a), before any
  code is written.
- **Written by**: the orchestrator at the end of each build (after
  `RETROSPECTIVE.md` exists), distilling that build's lessons — especially
  its "Persistent Failure Patterns" — into entries here. Builds run in
  per-build clones, so new lessons return to the template through the
  harvest-back protocol (CLAUDE.md Responsibility #17).

## Entry policy (append, dedup, retire)

- One lesson per entry, with a one-line summary on top. Record corrections
  and confirmed approaches alike, including **why** they mattered.
- Don't save what the spec, the repo, or the current build's reports already
  record — only lessons that transfer across builds.
- A new lesson that duplicates an existing one is not added; instead
  increment the existing entry's `Seen:` count.
- An entry that proves wrong is deleted, not amended into mush.
- Entries are ordered stable-first (oldest entries on top, never reordered)
  so the prompt-cache prefix stays byte-stable across builds.

## Schema

```
### lesson-<slug>
- **Added**: <build date>
- **Source**: <which build / which reviewer finding taught this>
- **Seen**: <count of builds where this lesson applied>
- **Lesson**: <one sentence — the transferable practice or pitfall>
- **Why it matters**: <the failure it prevents or the review it satisfies>
- **How to apply**: <concrete, build-agnostic guidance>
```

---

<!-- append new lessons below; never reorder existing entries -->

### lesson-mobile-viewport-before-handoff
- **Added**: 2026-06-11 (backfill from pre-protocol builds)
- **Source**: Design Critic round-1 FAILs in math-runner (4 CRITICAL), Cipher Diary (1 CRITICAL), Parlour card-game suite (2 CRITICAL)
- **Seen**: 3
- **Lesson**: The single most common round-1 FAIL across builds is the Design Critic landing CRITICALs at the smallest viewport — verify the 375px experience before handoff, not after.
- **Why it matters**: Three of the first six builds lost round 1 to mobile-layout CRITICALs (clipped hand fans, input-swallowing overlays, broken touch flows), each costing a full revision pass.
- **How to apply**: Before writing VERIFY_NOTES.md, walk every primary flow at 375×667 in both empty and populated states; confirm each load-bearing control is visible (`getBoundingClientRect()` inside the viewport) and actually receives clicks/taps (`document.elementFromPoint` hit-test), then re-check at 768 and 1440.

### lesson-thread-the-seeded-rng-everywhere
- **Added**: 2026-06-11 (backfill from pre-protocol builds)
- **Source**: Architect MODERATEs in math-runner (unseeded boss attack picking) and Parlour card-game suite (Gin `Math.random` leak; duplicated UI PRNG)
- **Seen**: 2
- **Lesson**: When the spec asserts any determinism or reproducibility invariant, every randomness consumer must thread the single canonical seeded RNG — no `Math.random`, `Date.now`-derived choices, or private PRNG copies anywhere in domain logic.
- **Why it matters**: A single unseeded call on a secondary branch (easy difficulty, fallback path, visual variant) silently breaks "bit-for-bit restore" claims and reliably surfaces as an Architect MODERATE that suppresses the Acceptance Score.
- **How to apply**: Put the seeded RNG in one module, inject it into every consumer (including UI-side cosmetic randomness if it feeds persisted state), and grep the domain layer for `Math.random|Date.now|getRandomValues|performance.now` as a pre-handoff gate.

### lesson-custom-error-handler-before-review
- **Added**: 2026-06-11 (backfill from pre-protocol builds)
- **Source**: Cipher Diary Evaluator finding E1 (pre-auth stack-trace/path disclosure via Express default error handler)
- **Seen**: 1
- **Lesson**: Install a custom production error handler (uniform, body-free error shape; no stack, no paths) as part of server scaffolding, before any endpoint is written.
- **Why it matters**: Framework default error handlers (Express/body-parser et al.) return stack traces with absolute filesystem paths on malformed input — reachable pre-auth, this is information disclosure to any network client and a guaranteed Evaluator security finding.
- **How to apply**: Add the error-handling middleware in the same commit as the server skeleton; verify by sending `{bad json` with `Content-Type: application/json` to an unauthenticated endpoint and confirming the response contains no stack frames or paths.

### lesson-hidden-attribute-loses-to-display-css
- **Added**: 2026-06-11 (backfill from pre-protocol builds)
- **Source**: Cipher Diary Design Critic CRITICAL C1 (lock overlay swallowed all pointer/touch input)
- **Seen**: 1
- **Lesson**: Never toggle visibility with the HTML `hidden` attribute on an element whose CSS also sets `display` — the class rule overrides the UA's `[hidden]{display:none}` and the "hidden" element stays painted and intercepting input.
- **Why it matters**: A nominally hidden full-viewport overlay (`position:fixed; inset:0`) that keeps `pointer-events` makes every control beneath it unreachable — fatal on touch viewports, and it reads as totally broken to a reviewer even though the DOM "looks" right.
- **How to apply**: Drive view/overlay toggling with explicit `display:none` utility classes or by mounting/unmounting nodes; if `hidden` is used anyway, add a guard style `[hidden]{display:none !important}` and hit-test primary controls after every overlay state change.

### lesson-frame-fit-needs-per-element-proof
- **Added**: 2026-06-11 (backfill from pre-protocol builds)
- **Source**: Parlour card-game suite Design Critic CRITICAL (hand fans clipped off-frame at 375px under `overflow:hidden`)
- **Seen**: 1
- **Lesson**: A "fills the frame / never scrolls / nothing clipped" requirement cannot be verified with page-level scroll metrics — `overflow:hidden` containers swallow clipped content silently, so prove frame-fit per element.
- **Why it matters**: Page-level checks (`scrollWidth == clientWidth`) pass while required interactive content (the player's own cards) sits unreachable past a hidden-overflow fold, which the Design Critic scores CRITICAL.
- **How to apply**: At the smallest required viewport, enumerate load-bearing elements and assert each `getBoundingClientRect()` lies inside the viewport box, in both empty and populated states (resume banners and toasts are what push the last item over the fold).

### lesson-measure-contrast-both-schemes
- **Added**: 2026-06-12 (build: Streakline)
- **Source**: Streakline Design Critic MODERATEs ×2 (light-mode primary button 3.67:1; unchecked check-control border ~1.3:1 in both schemes)
- **Seen**: 1
- **Lesson**: Measure WCAG contrast per element, in BOTH color schemes, before handoff — accent-on-light button text (4.5:1 floor) and subtle non-text control boundaries (3:1 floor) are the two reliable failure spots.
- **Why it matters**: A warm accent that passes against a dark background routinely fails against white, and a "minimal" unchecked-state border can be near-invisible — each lands a Design Critic MODERATE, and the signature control reading as whitespace undermines the product's core interaction.
- **How to apply**: Compute ratios from rendered `getComputedStyle` colors (not design-token intentions) for every accent-colored text element and every state-bearing control boundary, in light and dark modes; keep a per-scheme token (e.g. `--check-border`) so fixing one scheme cannot regress the other.

### lesson-focus-management-breaks-when-code-moves
- **Added**: 2026-06-12 (build: Streakline)
- **Source**: Streakline retrospective — 3 focus MINORs in Round 1, then 2 NEW focus MINORs introduced by the Round 2 module extraction (dialog focus-restore targeting an element inside an already-hidden menu)
- **Seen**: 1
- **Lesson**: Focus behavior is the most regression-prone property when DOM-owning code moves between modules — re-test focus flows after any frontend restructuring, even one that changes no visible behavior.
- **Why it matters**: Native focus-restore targets the element that opened a dialog; after refactoring, that element may live inside a container that is hidden by close time, silently dropping focus to `<body>` — invisible in mouse testing, a guaranteed reviewer MINOR (or worse) under keyboard audit.
- **How to apply**: After moving or extracting view code, walk every dialog/menu open-close cycle with keyboard only and assert `document.activeElement` lands on a visible, sensible control; prefer explicitly focusing a stable anchor (e.g. the menu button) on close over relying on native restore.

### lesson-frontend-boundaries-mirror-backend
- **Added**: 2026-06-12 (build: Streakline)
- **Source**: Streakline Architect MODERATE (606-line today.js absorbing menu/Lock/Change-PIN — Access-module concerns the backend kept in a separate router)
- **Seen**: 1
- **Lesson**: Give the frontend the same module boundaries the backend already has — when a server cleanly separates domains (access vs. data), a client view file that absorbs both becomes the build's god-module.
- **Why it matters**: The Architect reviews pattern coherence across the stack; a backend/frontend boundary mismatch is an easy MODERATE that then costs a structural revision round, and the extraction itself risks new regressions (see [[lesson-focus-management-breaks-when-code-moves]]).
- **How to apply**: Before writing frontend views, list the backend's router/domain boundaries and create one client module per boundary up front; treat any view file trending past ~400 lines as a boundary smell, not a formatting issue.
