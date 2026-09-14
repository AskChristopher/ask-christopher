# Handoff: Ask Christopher — ChristopherMathews.com

## Overview

ChristopherMathews.com is not a portfolio site with a chatbot attached. **Ask Christopher is the portfolio.** The governing concept — `DON'T READ MY WEBSITE. ASK IT.` — is literal: there are no conventional section pages. A visitor arrives at a question field, asks something, gets a conversational answer, and the relevant work surfaces visually in a showcase rail beside the conversation. A browse route (**All the Work**) exists for visitors who don't want to start by asking, and it feeds back into the same conversation.

The interaction loop the implementation must protect:

```
ASK    → UNDERSTAND → SHOW → DISCUSS → CONVERT
BROWSE → DISCOVER   → ASK  → DISCUSS → CONVERT
```

The conversation must never feel like it disappears because the visitor is browsing or reading a project.

**Business context that affects priorities:** Ask Christopher is itself one of Christopher's portfolio pieces and a demonstration of a product he intends to sell (a DIY package, and a done-for-you build service for coaches, local businesses, real-estate professionals and other independent professionals). The site sells by being used. **Implementation priority is therefore the working Ask Christopher experience, not filling portfolio slots.**

---

## About the design files

The files in this bundle are **design references created in HTML** — a prototype showing intended look, structure and behaviour. They are **not production code to copy**.

`ChristopherMathews.dc.html` is authored in a bespoke HTML template runtime (`<sc-for>`, `<sc-if>`, `{{ value }}` holes, a `Component extends DCLogic` logic class). **Do not try to port that runtime.** Read it as a specification and rebuild the design in the target codebase's own environment using its established patterns. If no codebase exists yet, React (Vite or Next.js) with plain CSS custom properties is the closest match to how this prototype is structured — all styling here is inline against CSS variables, with no utility framework and no component library beyond the design system.

`support.js` is the prototype runtime. It is included only so the HTML opens and can be inspected in a browser. **It has no counterpart in production.**

## Fidelity

**High fidelity.** Colours, typography, spacing, borders, shadows, motion durations and easing are final and come from the bound Christopher Mathews Design System. Layout proportions, type sizes and interaction states should be reproduced closely.

The exception is **content**, which is mostly placeholder — see *Content status* below, and read it before building anything data-driven.

---

## Content status — READ THIS FIRST

| Real | Placeholder / invented by the designer |
|---|---|
| The three-column architecture and all interaction behaviour | **Every portfolio item.** All 16 works in `WORKS` — titles, clients, sectors, dates, metrics, case-study prose, track lists, counts |
| The brand voice, provocations and CTA language (`START A PROJECT`, "Don't bring us a course request. Bring us the problem.", "Sometimes the answer isn't training.") | **Every number.** `6m 10s → 0m 40s`, `11 weeks → 6 weeks`, `0.71 correlation`, `62% fewer calls`, `18 projects`, `180+ pieces`, `24 identities` etc. |
| The method language `PROBLEM → SYSTEM → PROTOTYPE → PROVE` and the five diagnosis factors (person, knowledge, workflow, technology, environment) | **Every answer body.** The six answer functions are hand-written demo copy, not model output and not Christopher's writing |
| The category taxonomy (AI · LEARNING · WEB · DESIGN · ART · MUSIC · VIDEO · EXPERIMENT) | **All imagery.** There are no images at all. Every media area is an empty drop target |
| The AES positioning (company, "WE SOLVE", not an eLearning vendor or AI consultancy) | The 7-part case-study structure is real as a *template*; the filled-in instances are not |

**Do not ship any of the placeholder content.** Two consequences for implementation:

1. **Seed small.** Christopher does not yet have enough finished material to justify 16 items. Ship with however many real pieces exist — the layouts are designed to hold 1 item as gracefully as 40 (see *Growth and empty states*). Delete the rest rather than porting them.
2. **Content lives in data, not in components.** See `CONTENT-MODEL.md` for the shape each item needs. Adding a piece later must mean adding one record, with no layout work.

Also unresolved and flagged by the design system itself: there is **no logotype** (the name is set in display type), fonts are Google Fonts substitutions, and the signal colour `#F03D14` is a proposal.

---

## Layout — the three-column shell

One persistent shell wraps every state. Nothing navigates away from it; only the centre column's content changes.

```
┌──────────────┬─────────────────────────────────┬──────────────────┐
│ NAV/SESSION  │ ASK CHRISTOPHER (primary)       │ SHOWCASE         │
│              │                                 │                  │
│ wordmark     │  ┌ scrolling view region ────┐  │ heading + sub    │
│ New question │  │ arrival | thread |        │  │                  │
│ This session │  │ artifact | browse | start │  │ visual cards     │
│ Or just read │  └───────────────────────────┘  │ (newest first)   │
│ ...          │  ── ask bar (always docked) ──  │ footer note      │
│ Start a proj │                                 │                  │
└──────────────┴─────────────────────────────────┴──────────────────┘
```

- Outer: `display: grid; height: 100vh; overflow: hidden; background: var(--paper-000)`
- Columns: `clamp(180px, 18vw, 264px) minmax(0, 1fr) clamp(236px, 24vw, 348px)`
- Left column: `border-right: 1px solid var(--border-hairline); background: var(--paper-050); padding: 22px 20px 18px; display: flex; flex-direction: column; gap: 24px; overflow: auto`
- Centre column: `display: flex; flex-direction: column; overflow: hidden; container-type: inline-size; min-width: 0`. **The container query is load-bearing** — all display type is sized in `cqi` against this column, not the viewport.
- Centre scroll region: `flex: 1; overflow: auto`. The ask bar sits outside it as a sibling so it never scrolls away.
- Right column: `border-left: 1px solid var(--border-hairline); background: var(--paper-050); padding: 22px 20px; overflow: auto; display: flex; flex-direction: column; gap: 16px`
- Centre content padding: `clamp(24px, 4vw, 64px)` horizontally, `40–64px` top depending on view. Max text measure `780px` (conversation), `800px` (artifact), full width (browse grid).
- Mode: the whole shell sits inside `data-mode="ask"` (design-system mode scope: expressiveness MEDIUM, 64px page margin, grid used conservatively).

**Any child of a flex column that has `overflow: hidden` must also carry `flex-shrink: 0`** — without it the rail's flex layout crushes cards to a few pixels. This bit us in the prototype; it is not a theoretical note.

---

## Screens / views

The centre column renders exactly one of five views. `view` ∈ `ask | artifact | index | start`, with `ask` splitting into arrival and thread by whether the thread is empty.

### 1. Arrival (`view: ask`, empty thread)

**Purpose:** state the concept, and get the first question asked.

- Mono label `01 — KNOWLEDGE INTERFACE` with hairline rule.
- H1: `DON'T READ / MY WEBSITE. / ASK IT.` — `var(--font-display)` 900, uppercase, `font-size: clamp(34px, 9.8cqi, 76px)`, `line-height: .9`, `letter-spacing: -.035em`, `margin-left: -4px` (optical hang). "Ask it." is `var(--signal-500)`.
- Standfirst: `var(--font-body)` 20px/1.6, `var(--text-secondary)`, max 54ch.
- **Five suggested questions**, stacked, `gap: 8px`, max-width 620px. Each: `background: var(--paper-050)`, `1px solid var(--border-hairline)`, radius 2px, padding `13px 15px`, `var(--font-ui)` 15px, with a right-aligned mono kind label. Hover → `background: var(--paper-100)`, 130ms.
- Footer strip: mono line (era/count facts) + a margin `Annotation` reading "This is one of the systems I build. You are evaluating the work by using it."

Suggested-question copy is real brand-voice work and can ship, **but the kind labels reference placeholder counts** ("3 case studies") — regenerate from real data.

### 2. Conversation thread (`view: ask`, non-empty thread)

The hero recedes entirely; the thread replaces it. Each exchange:

1. **Question restated** — left rule `3px solid var(--ink-900)`, `padding-left: 16px`, mono index `01 — ASKED`, then the question in display 700 uppercase `clamp(19px, 3.5cqi, 27px)`.
2. **AES voice-shift banner** (only when the question is commercial) — `background: var(--paper-050)`, left rule `3px solid var(--signal-500)`, mono `VOICE SHIFT — I → WE` plus a plain-language explanation. This is a real behaviour: Christopher answers as *I*, AES answers as *we*.
3. **Answer prose** — `var(--font-body)` 19px/1.6, max 62ch, paragraphs `margin-bottom: 16px`. Conversational and enthusiastic first; explanation before evidence.
4. **Optional evidence blocks**, any combination:
   - `StepFlow` diagram in a `var(--paper-050)` panel (method questions)
   - Stat row — display 900 34px figure with the unit in signal, mono label + method beneath. **Every figure carries its method; never a bare number.** Top rule `3px solid var(--ink-900)`
   - Experience records table — ink header row, hairline-separated rows, `era / what / medium`
5. **The offer** — the mechanism that drives SHOW. Panel: `1px solid var(--border-default)`, left rule `3px solid var(--signal-500)`, `background: var(--paper-050)`, padding `20px 22px`. Body copy in `var(--font-body)` 19px. Two buttons: accept (`background: var(--signal-500)`, white, mono 11px uppercase, hover `--signal-600`) and decline (transparent, `1px solid var(--border-default)`, hover `--paper-100`). Copy pattern: *"I can show you that one properly … along with two others that took completely different shapes."* / `YES — SHOW ME THE PROJECTS →`
6. **Accepted reply** — replaces the offer once accepted. Two-column: mono `SHOWING →` in signal, then a line telling the visitor what landed and where to start.
7. **Facet chips** (`CUT IT DIFFERENTLY:`) — mono 10px, `var(--paper-050)` fill; re-ask narrower questions.
8. **Follow-ups** (`NARROW IT DOWN`) — mono 11px, transparent with `1px solid var(--border-default)`.

Answers are keyword-routed in the prototype to six hand-written bodies. **In production this is where the real answer engine goes** — see *Answer generation* below.

### 3. Opened piece (`view: artifact`)

**Purpose:** see the work, read concise context, and keep asking. This is the SHOW → DISCUSS hinge; it must never read as a separate page.

- **Sticky header** — `rgba(255,255,255,.88)` + `backdrop-filter: blur(10px)`, hairline bottom, padding `14px clamp(24px,4vw,64px)`, `flex-wrap: wrap`. Left (`flex: 1 1 260px`): mono signal `{CATEGORY} · {REF}`, then `Opened from: "{the question or 'All the work'}"` in `var(--font-ui)` 13px — this line wraps rather than truncating. Right: `Back to the conversation` (ghost) + `Ask about this` (secondary).
- Mono label `{n}` + eyebrow, then H1 display 900 uppercase `clamp(26px, 6.8cqi, 52px)`, then standfirst `var(--font-body)` 21px/1.55 max 56ch.
- **Hero media**, framed by type:
  - software / web / learning / video → window chrome strip (three `7px` dots + a mono label: `PROTOTYPE`, `COURSE PLAYER`, `FILM`) above the media
  - video → a 62px `rgba(20,19,16,.72)` circular play button centred over the media, `pointer-events: none`
  - music → a track list beneath the media: per row a 32px round play button (`--ink-900`, `--signal-500` while playing), title, 3px progress bar, use context, duration
  - Aspect ratios by type: `16/10` software & web, `16/9` learning & video, `1/1` design & music, `4/5` art
- Meta strip — 2–4 `key / value` pairs between hairlines, mono key + `var(--font-ui)` value.
- **Body**, one of two shapes:
  - *Documentary* (AI systems, web, learning): the 7-part structure — `THE PROBLEM · THE CONSTRAINTS · THE THINKING · THE SYSTEM · THE BUILD · THE RESULT · WHAT I LEARNED`. Two columns: a sticky `minmax(110px,150px)` label column (mono number, display 700 heading, and an **`Ask about this part`** button) and the prose column at `var(--font-body)` 18px/1.62 max 60ch, with optional captioned figures. Sections may be fewer than seven — 2–3 is fine and expected for lighter pieces.
  - *Gallery* (design, art, music, video): hero, short context, then a plate grid `repeat(auto-fill, minmax(228px, 1fr))`, each plate a captioned media frame. Section label varies: `SELECTED PIECES` / `PLATES` / `SCREENS AND MEDIA` / `STILLS AND SEQUENCES`.
- **Questions-while-you're-here band** — `1px solid var(--border-default)`, left rule signal, `var(--paper-050)`. Copy: *"Anything you want to know about this — how it was built, what it cost, whether it would work for you — just ask. I'm still right here."* Three one-tap prompts (`How was this built?`, `What did it cost?`, `Would this work for us?`) that carry the piece's title into the thread.
- Footer actions: `Start a project` (primary) · `Back to the conversation` (outline) · `All the work` (ghost).

### 4. All the Work (`view: index`)

**Purpose:** visual browsing for visitors who don't want to open with a question — without becoming a generic portfolio grid or feeling like a database.

- Mono `02 — ALL THE WORK`, H1 `EVERYTHING, IF YOU'D / RATHER JUST LOOK.` at `clamp(25px, 6cqi, 46px)`.
- Two-up intro: standfirst + an `Annotation` reading "The conversation doesn't close while you browse. It's still at the bottom of this column." Grid `repeat(auto-fit, minmax(280px,1fr))` so it stacks on narrow centres.
- **Filter row** — one quiet mono row, `gap: 7px`, wrapping. Each chip: mono 10px uppercase, `1px solid var(--border-default)`, radius 2px, padding `8px 11px`, with its count at `opacity: .55`. Active chip inverts to `background: var(--ink-900); color: var(--paper-000)`. First chip is `EVERYTHING`.
- **The anti-database device:** below the filters sits a **curatorial line in Christopher's voice that changes per filter**, at `var(--font-body)` 17px above a hairline — e.g. DESIGN → *"Marks, type systems and publications. The reason the AI work looks like something."* Never a result count as the only feedback. These lines ship as real voice, but must be rewritten for whatever categories actually have work.
- **Grid** — `repeat(auto-fill, minmax(272px, 1fr))`, `gap: 22px`. The first item of any filter with 3+ results is promoted: `grid-column: 1 / -1` (**never `span 2`** — that fabricates an implicit content-sized track and collapses the other cards) plus an ink banner reading `START HERE` / `PICK OF THE {CATEGORY}`.
- **Card** — `1px solid var(--border-hairline)`, top rule `3px solid var(--ink-900)`, radius 2px, `overflow: hidden`, flex column. Media area with the type affordance (chrome dots / play overlay / play bar + track count / four-swatch strip `--ink-900, --signal-500, --paper-200, --ink-700`), then padding 16px: mono category (signal) + ref, `● OPENED THIS SESSION` if applicable, display 700 17px title, `var(--font-body)` 15px blurb, and a two-button row pinned to the bottom above a hairline: **`Open`** (outline, hover inverts to ink) and **`Ask about this`** (hover `--paper-100`).
- Empty filter → a panel offering to ask instead, plus `Show everything`.

### 5. Start a project (`view: start`)

- H1 `YOU'VE ALREADY / DESCRIBED THE PROBLEM.`
- **Carried-session panel** — signal left rule, listing every question asked (`ASKED`) and piece opened (`OPENED`) as the brief's context. Empty variant: "You came straight here without asking anything. That's allowed — write the problem below instead."
- Fields: *What isn't happening that needs to happen?* (textarea, 4 rows) · *Who is affected, and how many* · *Constraint that matters most* · Name · Email. Inputs: `1px solid var(--border-default)`, radius 2px, padding `11px 13px`, `var(--font-ui)` 15px; focus → `box-shadow: var(--shadow-focus); border-color: var(--ink-900)`.
- Submit `SEND THE PROBLEM` + "Reply within two working days" — **confirm this promise before shipping.**
- Escape hatch: `← Keep asking instead`.

---

## Left column — navigation and session

Non-chat navigation is mandatory: the visitor does not have to use Ask Christopher.

- **Wordmark** — `CHRISTOPHER / MATHEWS` display 900 18px uppercase (no logo exists), sub-line mono `ASK CHRISTOPHER — THE SITE`. Click resets to arrival.
- **`New question`** — outline button, full width, plus icon. Clears thread, opened list and showcase back to featured.
- **`THIS SESSION`** — flat list of rows. Question rows: `var(--font-ui)` 13px, `border-left: 2px solid` (signal for the current turn, hairline otherwise), `padding-left: 10px`. Pieces opened from a question nest beneath **that question** as mono 10px `↳ {short title}` rows at `padding-left: 22px`. Pieces opened from browsing group separately under a mono `BROWSED FROM ALL THE WORK` header. Empty state: "Nothing asked yet. Your questions become the navigation."
- **`OR JUST READ`** — `About Christopher`, `AES services`, `All the work {count}`. `var(--font-ui)` 13px with `border-bottom: 1px solid var(--border-default)`.
- **`Start a project`** — primary button, pinned with `margin-top: auto`.
- Footer line: "Bring the problem you arrived with. I'll tell you what I'd build."

**No system/database language anywhere** — no corpus counts, no source or evidence records, no "system online", no question quotas, no method-note inventory. This was an explicit correction; don't reintroduce it.

---

## Right column — the Showcase

**The showcase is a visual showcase controlled by the conversation. It is not an evidence rail, a citation panel or a source list.** The current Ask Christopher backend provides no sentence- or answer-level provenance, so **no interface copy may claim that answers cite their sources**, and nothing in this rail may be presented as supporting evidence for an answer.

- Heading `SHOWCASE` with hairline rule + count (`5 pieces`). Sub-line changes by state: `A few pieces to start with — ask and I'll bring up more.` / `Just added to the showcase.` / `Everything you open while browsing lands here too.`
- **Cards, newest group first.** Freshly added items appear at the top in their given order, everything earlier below in reverse-chronological order of adding.
- Card: `1px solid` + `border-top: 3px solid` (both `--signal-500` when just-added or open, else `--border-default`), radius 2px, `overflow: hidden`, **`flex-shrink: 0`**. Media area = drop target at the piece's aspect ratio with the project numeral overlaid bottom-left (display 900 30px `--ink-700`, `pointer-events: none`) plus the type affordance. Body: mono category (signal) + ref, display 700 15px title, `var(--font-body)` 14px blurb, then a hairline-separated row with the headline result in signal and `OPEN →`.
- Hover: `box-shadow: var(--shadow-lift); transform: translateY(-2px)`, 130ms.
- Footer note names the range of media the showcase can hold.
- **Empty/arrival state** shows a short invitation plus a one-line "what's in here" — never statistics.

---

## Interactions & behaviour

| Trigger | Result |
|---|---|
| Suggested question / facet / follow-up / `Ask about this` / `Ask about this part` | `ask(text)` — switches to `view: ask`, sets `pending`, clears the draft and `justAdded`, then resolves an answer |
| Ask bar submit | same as above with the typed draft |
| Offer accept | appends the offer's items to `showcase`, marks them `justAdded`, records the turn as accepted so the offer is replaced by its reply. **No navigation** |
| Offer decline | asks the decline question — a normal turn, not a dismissal |
| Showcase card / gallery `Open` / `About Christopher` / `AES services` | `view: artifact`; records `{id, turn}` in `opened` (turn = current turn index, or `"browse"` when opened from All the work / About / AES services); adds the piece to the showcase if absent |
| Gallery `Ask about this` | `ask("Tell me about {title}.")` — returns to the conversation |
| Filter chip | sets `filter`; swaps the curatorial line; re-promotes the first card |
| Music play button | toggles `playing` index; icon `▶ ⇄ ❚❚`, button fills signal, progress bar advances |
| `Back to the conversation` | `view: ask`, `artifactId: null`. Thread is intact |
| Session row | returns to that turn (or the browse group) |

**Loading:** the pending question renders immediately with a signal left rule and muted heading, a mono `READING THE ARTIFACTS` line with three pulsing dots (`900ms`, staggered 150ms), and three skeleton bars in `--paper-100`. Prototype delay 950ms.
*Rename that loading string* — "artifacts" is internal vocabulary; use something like `LOOKING THROUGH THE WORK`.

**Error:** a `Callout` (`tone: danger`) — "The answer didn't come back." The question is preserved in the field; actions are `Ask again` and `Browse the index instead`.

**Usage limit:** a panel headed by mono `SESSION LIMIT — 20 OF 20`, explaining that answering costs real compute so the interface caps itself rather than degrading, and that reading stays open. The ask bar is replaced by a locked strip: "Asking is paused for this session. Reading stays open." + `Start a project`. **The cap number is a placeholder — set it from real economics.**

**Motion:** entrances `190ms cubic-bezier(.16,1,.3,1)` with an 8px rise; hover/focus `130ms cubic-bezier(.2,0,0,1)`; press 1px translate; no bounce, spring, parallax or ambient loops. `@media (prefers-reduced-motion: reduce)` zeroes every animation — already in the prototype, keep it.

**Focus:** `box-shadow: var(--shadow-focus)` (2px signal ring offset by a 2px page-coloured gap) on every interactive element. Never remove it.

---

## Answer generation

The prototype fakes this with keyword routing into six hand-written bodies. It is the **one genuinely unresolved product decision** and it changes the build:

- **Authored answers** — a fixed set of Q→answer records, each optionally carrying evidence blocks and an offer. Fast, exact, on-voice, no drift, no hallucination risk. Handles the top ~30 questions and needs a graceful "I don't have an answer for that" path.
- **Model-generated over Christopher's own material** — open-ended, needs retrieval, guardrails, refusal behaviour, cost control and an eval loop.

Either way the contract the UI depends on is the same, so build against it:

```ts
type Answer = {
  paragraphs: string[];              // conversational, explanation before evidence
  isAes?: boolean;                   // renders the I → we voice-shift banner
  stats?: { value, unit, label, method }[];   // method is REQUIRED
  records?: { era, what, medium }[];
  showMethodDiagram?: boolean;
  offer?: { line, accept, decline, workIds: string[], reply };
  facets?: string[];
  followups?: string[];
};
```

Guardrails that are design requirements, not nice-to-haves: never claim a citation the backend can't support; never invent a metric; refuse rather than guess; every figure carries its method.

---

## State management

```ts
view: "ask" | "artifact" | "index" | "start"
thread: Answer[]            // one entry per answered question
pending: string | null      // question in flight → loading state
draft: string               // ask bar
accepted: number[]          // turn indices whose offer was accepted
showcase: string[]          // work ids in the rail, oldest first
justAdded: string[]         // highlighted + sorted to top
opened: { id: string, turn: number | "browse" }[]
artifactId: string | null
openedBy: string            // provenance line in the artifact header
filter: string              // "ALL" | category
playing: number             // music track index, -1 = none
```

Notes: `justAdded` clears on the next question. `opened` **must** store the turn — a flat id list mis-attributes browsed pieces to whatever question was last asked. Deep-linkable URLs per piece (`/work/{id}`) are recommended and were never resolved in the prototype; the artifact view is designed to read standalone, which also covers SEO and recruiter scanning.

---

## Growth and empty states

Christopher will add work over time. Everything is designed to hold a small collection:

- Feature promotion only fires at **3+ items** in a filter; below that all cards are equal.
- Filter chips should render **only for categories that have work** — hide empty ones rather than showing `0`.
- The showcase rail is happy with 1–2 featured pieces; its featured set is just a list of ids.
- Case-study sections are variable-length; 2 is legitimate, 7 is the full form.
- Plate grids reflow from 1 plate upward.
- Offers reference work ids; an offer whose ids don't exist should simply not render.

Ship with the real pieces only, and let the taxonomy shrink to match.

---

## Design tokens

From the bound **Christopher Mathews Design System** (`_ds/christopher-mathews-design-system-…/`). Link the token CSS and use the variables; don't hard-code hexes.

**Colour** (only these are used by this design)

| Token | Value |
|---|---|
| `--ink-900` | `#141310` |
| `--ink-700` | `#38352F` |
| `--paper-000` | `#FFFFFF` |
| `--paper-050` | `#FAF8F3` |
| `--paper-100` | `#F2EEE5` |
| `--paper-200` | `#E6E1D6` |
| `--signal-500` | `#F03D14` |
| `--signal-600` | `#C82E0B` |
| `--text-primary` | `#141310` |
| `--text-secondary` | `#57534B` |
| `--text-muted` | `#7C776D` |
| `--text-signal` | `#C82E0B` |
| `--border-hairline` | `#E6E1D6` |
| `--border-default` | `#CFC9BC` |

Signal must stay ≤5% of any composition: primary CTA, active rules, section numbers, result figures. Never a background wash, never a gradient. Two blur usages only — sticky header (88% + 10px) and modal scrim (ink 55% + 8px).

**Type**

| Role | Family | Usage here |
|---|---|---|
| `--font-display` | Archivo 700/900 | Provocations, headings, project numerals, result figures. Uppercase, `letter-spacing: -.02 to -.035em`, `line-height: .85–1.15` |
| `--font-body` | Newsreader 400/500 | Answers, standfirsts, case-study prose. 14–21px, `line-height: 1.5–1.62`, measure 54–62ch |
| `--font-ui` | IBM Plex Sans | Nav rows, inputs, card titles in the rail, meta values. 13–17px |
| `--font-mono` | IBM Plex Mono | Labels, categories, refs, counts, buttons, state. 9–11px, uppercase, `letter-spacing: .05–.08em` |

Fluid display sizes use `cqi` against the centre column: H1 arrival `clamp(34px, 9.8cqi, 76px)`, artifact `clamp(26px, 6.8cqi, 52px)`, browse `clamp(25px, 6cqi, 46px)`, question restatement `clamp(19px, 3.5cqi, 27px)`.

**Other:** radius 2px everywhere (3px on the mobile frame; pill only for status dots and switch tracks). Shadows `--shadow-lift: 0 10px 28px -14px rgba(20,19,16,.42)` on hover and dialogs, `--shadow-focus` on focus. Spacing runs on a 4px base; the recurring values are 6/7/8/10/13/16/20/22/26/28/34/44/64.

---

## Design-system components to reuse

Available from the design-system bundle and already used here: `Button` (primary / secondary / outline / ghost, sizes sm/md), `MetaLabel` (the mono label with optional number and hairline rule — the most-used device in the design), `Statement`, `Annotation` (margin marginalia), `StepFlow` (the `PROBLEM → SYSTEM → PROTOTYPE → PROVE` diagram), `Callout` (error), `Icon` (Lucide, outline, 1.5px). Icons are outline-only, monochrome, inherit text colour, and never the sole carrier of meaning. **No emoji, ever.**

New patterns this design introduces, worth building as components in the target codebase: `AnswerBlock`, `OfferPanel`, `ShowcaseCard` (typed media variants), `WorkCard` (browse), `ArtifactHeader`, `SessionList`, `AskBar`, `FilterRow`, `TrackList`.

---

## Assets

**There are no image assets.** Every media area is an empty, labelled drop target — the prototype uses an `<image-slot>` web component whose only production requirement is that each slot maps to one image field on a work record. Slot ids follow `card-{id}` (rail), `gal-{id}` (browse), `hero-{id}`, `pl-{id}-{n}` (plates), `sec-{id}-{n}` (case-study figures).

What each slot needs, from the design system's imagery direction: things being built rather than people pretending to work — prototypes, screens, interfaces, diagrams, workspaces, hands, artifacts, system maps. Warm-neutral, slightly desaturated, monochrome or duotone-to-ink preferred; grain acceptable when it reads as print. **Banned:** office meetings, handshakes, robots, glowing brains, holograms, circuit-board faces, stock "AI".

No logo file exists. Fonts are Google Fonts (Archivo, Newsreader, IBM Plex Sans, IBM Plex Mono) — self-host if licensed families arrive. Icons are Lucide 0.462 via CSS mask.

---

## Responsive expectations

Desktop is the designed target and the only state approved so far.

- **≥1280px** — the design's intended proportions.
- **1050–1280px** — rails narrow via their `clamp()`s; the centre column shrinks and `cqi` type follows it. No layout change.
- **900–1050px** — still three columns. Verify the browse grid resolves to a single track and that no card falls below its 272px minimum (this was a real bug: the feature card must use `grid-column: 1 / -1`).
- **<900px** — **not designed yet, and out of scope for this handoff.** The prototype contains an annotated mobile specification (one column, both rails collapsed, session history as a drawer behind the wordmark, showcase as a counted accordion under each answer, ask bar fixed above the home indicator, 48px minimum hit targets) reachable via the `defaultScreen` prop. Treat it as intent, not approved design; get mobile signed off before building it.

---

## Files

| File | What it is |
|---|---|
| `ChristopherMathews.dc.html` | The full interactive prototype — every view and state. Read as specification |
| `support.js` | Prototype template runtime. **No production counterpart** |
| `image-slot.js` | The drop-target placeholder component used for all media |
| `CONTENT-MODEL.md` | The data shape for a portfolio piece and an answer, for building the CMS/content layer |
| `design-system-tokens/` | The design system's token CSS, copied verbatim — colours, type, spacing, borders, motion, modes, resets. Link these rather than transcribing values. The full design system (component bundle + brand readme) lives in the project at `_ds/christopher-mathews-design-system-…/` |

To explore the prototype: open `ChristopherMathews.dc.html` in a browser. It opens mid-conversation on "Show me the AI projects." Accept the offer to watch the showcase fill, open a piece from the rail, then use `All the work` in the left rail for the browse route.
