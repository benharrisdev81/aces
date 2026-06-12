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

---

## Shard: Structural  (Architect)

<!-- seed: the Architect's six dimensions live in architect.md;
     probes that land confirmed structural defects are distilled here.
     append new Structural probes below -->
