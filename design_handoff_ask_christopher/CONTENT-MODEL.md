# Content model

The whole point of this shape: **adding a portfolio piece later must mean adding one record, with no layout work.** Nothing in the UI should read from a hard-coded list.

Everything in the prototype's `WORKS` object is placeholder written by the designer. Use the shape, discard the content.

---

## A portfolio piece

```ts
type Work = {
  id: string;              // slug, stable — used in URLs and slot ids
  n: string;               // "01" — display numeral on cards. Sequence only, not a ranking
  cat: Category;           // drives the filter row and the card's category label
  media: MediaType;        // drives the thumbnail treatment and expanded layout
  ref: string;             // "2025 · Utilities" — date and context, top right of cards
  title: string;           // problem-led, never named after software
  railTitle: string;       // ~24 chars, for the session list
  blurb: string;           // one sentence, on cards
  headline: string;        // the single result line, in signal. "In build" is a valid value
  frameLabel: string;      // what belongs in the empty media slot, until an image exists
  eyebrow: string;         // "Knowledge system · Utilities" — above the H1
  standfirst: string;      // 2–3 sentences of context, top of the expanded view
  meta: { k: string, v: string }[];        // 2–4 pairs
  ratio: "16 / 10" | "16 / 9" | "1 / 1" | "4 / 5";
  layout: "doc" | "gallery";
  sections: Section[];     // 2–7. Seven is the full case-study form
  plates?: Plate[];        // gallery layouts and extra screens
  tracks?: Track[];        // music only
};

type Category  = "AI" | "LEARNING" | "WEB" | "DESIGN" | "ART" | "MUSIC" | "VIDEO" | "EXPERIMENT";
type MediaType = "software" | "learning" | "web" | "design" | "art" | "music" | "video";

type Section = {
  n: string;               // "01"
  h: string;               // "The problem" — for case studies use the canonical seven
  paras: string[];
  frame?: string;          // caption for an inline figure; omit for text-only
};

type Plate = { slot: string, cap: string, ratio: string };
type Track = { t: string, d: string, use: string };   // title, duration, context
```

**Media type → treatment**

| `media` | Thumbnail | Aspect | Expanded body |
|---|---|---|---|
| `software` | window chrome, mono `PROTOTYPE` | 16/10 | documentary |
| `web` | window chrome, mono `PROTOTYPE` | 16/10 | documentary |
| `learning` | window chrome, mono `COURSE PLAYER` | 16/9 | documentary or plates |
| `video` | window chrome `FILM` + centred play button | 16/9 | plates ("Stills and sequences") |
| `design` | four-swatch strip beneath | 1/1 | plates ("Selected pieces") |
| `art` | full-bleed, no chrome | 4/5 | plates ("Plates") |
| `music` | play badge + scrub bar + track count | 1/1 | track list with playback |

**The canonical case-study structure** (`layout: "doc"`), used when the piece warrants it:
`THE PROBLEM · THE CONSTRAINTS · THE THINKING · THE SYSTEM · THE BUILD · THE RESULT · WHAT I LEARNED`.
Fewer sections is fine. Never name a piece after software.

**Rules the design assumes and the content layer should enforce**

- Every figure in `meta`, `headline` or a stat carries its method — population, duration, instrument. A number without a method doesn't ship.
- Work in progress says so (`headline: "In build"`) rather than borrowing a number.
- `railTitle` stays short or the session list wraps badly.
- One image field per slot id: `card-{id}`, `gal-{id}`, `hero-{id}`, `pl-{id}-{n}`, `sec-{id}-{n}`.
- A category with no work should not produce a filter chip.

---

## An answer

```ts
type Answer = {
  question: string;
  paragraphs: string[];      // conversational; explanation before evidence
  isAes?: boolean;           // true → the I → we voice-shift banner
  stats?: { value: string, unit: string, label: string, method: string }[];
  records?: { era: string, what: string, medium: string }[];
  showMethodDiagram?: boolean;                 // PROBLEM → SYSTEM → PROTOTYPE → PROVE
  offer?: {
    line: string;            // "I can show you that one properly…"
    accept: string;          // "Yes — show me the projects"
    decline: string;         // a real alternative question, not a dismissal
    workIds: string[];       // what lands in the showcase
    reply: string;           // shown in place of the offer once accepted
  };
  facets?: string[];         // re-ask the same topic, cut differently
  followups?: string[];      // narrow toward a decision
};
```

**Voice**: first person for Christopher, *we* for AES, *you/your* for the visitor's situation. Never third-person self-description. Sentence case for reading copy; uppercase only for display provocations and mono labels. No emoji. Lead with the problem, not the deliverable.

**Answer guardrails** (design requirements): never claim a citation the backend can't support; never invent a metric; refuse rather than guess; carry the method with every figure.

An offer whose `workIds` don't resolve should simply not render — that way answers can ship before the work they'd like to show does.
