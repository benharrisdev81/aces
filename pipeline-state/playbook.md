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
  its "Persistent Failure Patterns" — into entries here.

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
