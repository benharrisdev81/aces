format-version: attack-library-v2

# Adversarial Attack Library

The discriminators' growing test set. Confirmed flaws landed in any round of
any build are distilled into reusable probes here, so the test surface grows
across builds and the Generator cannot converge on a fixed beatable rubric.

Builds run in per-build clones of the template repo: new probes return to
the template through the harvest-back protocol (CLAUDE.md Responsibility
#17) as a reviewable PR. Harvest-time dedup is checked against the
template's current `main`, not the clone's snapshot.

## How reviewers read this file (sharded — do not load the whole file)

The library is **sharded by dimension** so each reviewer loads only its slice
rather than the entire file. As the library grows across many builds, loading
everything would dilute attention and waste context; read only your section:

- **Evaluator** → the **Security** and **Failure Modes / Functional** shards.
- **Design Critic** → the **Accessibility / UX** and **Failure Modes / Functional** shards.
- **Architect** → the **Structural** shard.

Within your shard, run every probe not marked `RETIRED` or `N/A` for this
build's spec. A probe's `Dimension` field is authoritative for which shard it
belongs to.

## Ordering for prompt caching

Probes are ordered **stable-first**: seed probes and long-lived probes appear
at the top of each shard and are never reordered; newly acquired probes are
appended at the bottom of their shard. Keeping the high-frequency prefix
byte-stable lets the harness reuse the prompt cache across rounds and builds.
Do not reorder or rewrite existing probes — append only.

## Retirement and dedup policy

"Append-only" is not "grow forever":

- A probe a build has **passed 3 consecutive rounds** may be marked
  `Status: dormant` for the remainder of that build — still listed, not
  re-run every round — and reactivated on any related revision.
- A probe that **duplicates** an existing one (same defect signature) is not
  added; instead increment the existing probe's `Seen:` count.
- A probe superseded by a stricter probe is marked `RETIRED` with a pointer
  to its replacement. Retirement is the only permitted weakening, and only
  the template author (not a reviewer mid-run) performs it.

---

## Schema

```
### probe-<slug>
- **Added**: <round / build date>
- **Source**: <which reviewer landed it the first time>
- **Dimension**: <Security | Failure Modes | Accessibility | Structural | Naming | Coupling | Spec Compliance | ...>
- **Shard**: <Security | Failure Modes/Functional | Accessibility/UX | Structural>
- **Status**: <active | dormant | RETIRED→probe-slug>
- **Seen**: <count of builds where this defect class has appeared>
- **Probe**: <how a reviewer reproduces this test>
- **What it looks for**: <the defect signature>
- **Severity if confirmed**: <CRITICAL | MODERATE | MINOR>
- **N/A condition**: <when this probe does not apply, if any>
- **Refusal-risk**: <none | low | high — optional; Security shard only.
  Likelihood the probe's own content trips a Fable 5 safety-classifier
  refusal. `high` probes are run on claude-opus-4-8 via the orchestrator's
  refusal-handling responsibility, not by a Fable 5 reviewer.>
```

---

## Shard: Security  (Evaluator)

### probe-sql-injection-text-input
- **Added**: seed
- **Source**: Evaluator (built-in)
- **Dimension**: Security
- **Shard**: Security
- **Status**: active
- **Seen**: seed
- **Probe**: Enter a string containing single quotes, double quotes, and a
  semicolon (e.g. `'; DROP TABLE users; --`) into the most prominent
  free-text input.
- **What it looks for**: A server crash, a 500 response, or evidence of an
  actually-executed query. The app should accept it as literal text
  (displayed correctly or rejected with validation).
- **Severity if confirmed**: CRITICAL (Tier 1)
- **Refusal-risk**: high

### probe-unauthenticated-protected-endpoint
- **Added**: seed
- **Source**: Evaluator (built-in)
- **Dimension**: Security
- **Shard**: Security
- **Status**: active
- **Seen**: seed
- **Probe**: Pick one protected endpoint and issue a request with no
  credentials (via `curl` or browser dev tools).
- **What it looks for**: A 200 with real data. 401/403 is correct.
- **Severity if confirmed**: CRITICAL (Tier 1)
- **N/A condition**: spec explicitly designates the product as public/unauthenticated.
- **Refusal-risk**: low

### probe-idor-identifier-swap
- **Added**: seed
- **Source**: Evaluator (built-in)
- **Dimension**: Security
- **Shard**: Security
- **Status**: active
- **Seen**: seed
- **Probe**: Find any URL or API path containing an entity identifier. Modify
  the identifier to one belonging to a different user/context and re-issue.
- **What it looks for**: Read or modify another user's data.
- **Severity if confirmed**: CRITICAL (Tier 1)
- **N/A condition**: no per-entity identifiers anywhere in URLs or API calls.
- **Refusal-risk**: low

### probe-default-error-handler-stack-leak
- **Added**: Round 1 / 2026-06-01 (build: Cipher Diary)
- **Source**: Evaluator
- **Dimension**: Security
- **Shard**: Security
- **Status**: active
- **Seen**: 1
- **Probe**: Send a deliberately malformed JSON body (e.g. `{bad json`) with
  `Content-Type: application/json` to a JSON-accepting endpoint — including an
  **unauthenticated** one (login/unlock/setup). Inspect the full response body.
- **What it looks for**: The framework's default/development error handler
  returning an HTML page (or JSON) containing a stack trace with absolute
  server filesystem paths, dependency module paths, and runtime internals
  (e.g. `SyntaxError ... at /Users/.../node_modules/body-parser/...`). The
  signature is the absence of a custom production error handler: any thrown
  error (body-parser parse error, unhandled exception) escapes as a stack to
  the client. Reachable pre-auth makes it information disclosure to any
  network client. Severe for security-first products even when no domain data
  leaks, because it exposes paths/versions for targeting.
- **Severity if confirmed**: MODERATE (escalates if the leaked stack contains
  any sensitive domain data — then Tier 1)
- **N/A condition**: app has a custom error handler that returns a uniform,
  body-free error shape and never emits a stack to the client.
- **Refusal-risk**: low

---

## Shard: Failure Modes / Functional  (Evaluator + Design Critic)

### probe-i18n-non-ascii-emoji
- **Added**: seed
- **Source**: Design Critic (built-in)
- **Dimension**: Failure Modes
- **Shard**: Failure Modes/Functional
- **Status**: active
- **Seen**: seed
- **Probe**: Enter a non-ASCII string with emoji (`你好 🎉 لطيف`) into the most
  prominent free-text input.
- **What it looks for**: Layout breakage, character corruption, encoding errors.
- **Severity if confirmed**: MODERATE

### probe-i18n-500-character-string
- **Added**: seed
- **Source**: Design Critic (built-in)
- **Dimension**: Failure Modes
- **Shard**: Failure Modes/Functional
- **Status**: active
- **Seen**: seed
- **Probe**: Enter a 500-character string (lorem ipsum is fine) into the most
  prominent free-text input.
- **What it looks for**: Layout breakage, unexpected truncation, server errors.
- **Severity if confirmed**: MODERATE

<!-- append new Failure Modes / Functional probes below -->

---

## Shard: Accessibility / UX  (Design Critic)

<!-- seed: the Design Critic's built-in WCAG checks live in design-critic.md;
     probes that land confirmed accessibility defects are distilled here.
     append new Accessibility / UX probes below -->

### probe-hidden-attr-overridden-by-display
- **Added**: Round 1 / 2026-06-01 (build: Cipher Diary)
- **Source**: Design Critic
- **Dimension**: Accessibility
- **Shard**: Accessibility/UX
- **Status**: active
- **Seen**: 1
- **Probe**: For each element that toggles visibility via the HTML `hidden`
  attribute (gate screens, app shell, splash/boot, modal/lock overlays),
  read its computed `display` while it carries `hidden`. Then, for the
  app's primary interactive controls on each screen, hit-test the center of
  each control's bounding box with `document.elementFromPoint(x,y)` and
  confirm it resolves to the control itself (not to an overlay or a
  sibling). Confirm with a real pointer click + type that input lands.
- **What it looks for**: An element with the `hidden` attribute whose
  computed `display` is not `none` (a class/ID rule set `display:flex`/etc.
  that overrode the UA `[hidden]{display:none}` default), so the element is
  still laid out and painted. The decisive failure signature is a
  fixed/absolute full-viewport overlay (`position:fixed; inset:0;
  z-index:high; pointer-events:auto`) that, while nominally hidden,
  intercepts all pointer/touch events — controls hit-test to the overlay and
  real clicks/taps never reach the intended element (especially fatal on
  touch-only phone viewports).
- **Severity if confirmed**: CRITICAL
- **N/A condition**: app never uses the HTML `hidden` attribute for
  view/overlay toggling (e.g. visibility is driven purely by mounting/
  unmounting nodes or by `display:none`-only utility classes).

### probe-frame-fit-hidden-overflow-clip
- **Added**: Round 1 / 2026-06-08 (build: Parlour card-game suite)
- **Source**: Design Critic
- **Dimension**: Accessibility / UX (frame-fit / responsive layout)
- **Shard**: Accessibility/UX
- **Status**: active
- **Seen**: 1
- **Probe**: When the spec promises a "fills the frame / never scrolls / nothing
  clipped" layout, do NOT trust a page-level overflow check
  (`document.documentElement.scrollWidth == clientWidth`) as proof. Such a check
  passes even when content is clipped, because a container set to
  `overflow:hidden` swallows the excess instead of scrolling it. At the SMALLEST
  required viewport (e.g. 375×667), enumerate the load-bearing content — every
  player/opponent card in a hand fan, every primary list entry/control — and
  measure each element's `getBoundingClientRect()` against the viewport box.
  Flag any element whose left < 0, top < 0, right > innerWidth, or bottom >
  innerHeight while its containing scroll region is `overflow:hidden`. Test both
  the empty AND the populated state (e.g. with a resume/banner present) — the
  extra inserted block is what pushes the last item past a hidden-overflow fold.
- **What it looks for**: Required, interactive content (a player's own cards, a
  launchable game entry, a primary action) positioned outside the visible frame
  inside an `overflow:hidden` region, making it unreachable by any means — a
  silent frame-fit failure that page-level scroll metrics report as "fine".
- **Severity if confirmed**: CRITICAL when it renders a core action unreachable
  (hand unplayable, game unlaunchable); MODERATE when it only clips a secondary
  control.
- **N/A condition**: spec does not assert a frame-fit / no-scroll / no-clip
  layout requirement.

---

## Shard: Structural  (Architect)

<!-- seed: the Architect's six dimensions live in architect.md;
     probes that land confirmed structural defects are distilled here.
     append new Structural probes below -->

### probe-determinism-invariant-leak
- **Added**: Round 1 / 2026-06-08 (build: Parlour card-game suite)
- **Source**: Architect
- **Dimension**: Pattern Coherence
- **Shard**: Structural
- **Status**: active
- **Seen**: 2
- **Probe**: When the spec or BUILD_NOTES asserts a determinism/reproducibility
  invariant (e.g. "bit-for-bit restore", "bot behaviour reproducible from
  state", "only randomness is the seeded shuffle"), grep the engine/domain
  layer for `Math.random`, `Date.now`, `crypto.getRandomValues`, `performance.now`
  and any hand-rolled PRNG that does NOT thread the persisted seed. Check
  every difficulty/branch path, not just the primary one — the leak is often
  on a secondary (easy/fallback) branch.
- **What it looks for**: A non-state-seeded entropy source inside logic the
  codebase claims is deterministic, OR a private copy of the core seeded-RNG
  algorithm duplicated outside the canonical RNG module (so a future seed
  change desyncs the copies).
- **Severity if confirmed**: MODERATE (CRITICAL if it sits on a `must`-tier
  primary path such that bit-for-bit restore is broken for normal play).
- **N/A condition**: spec asserts no determinism/reproducibility requirement.
