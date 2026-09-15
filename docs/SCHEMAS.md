# Contracts and schemas

Every type here is a Pydantic v2 model in `src/rupantar/core/`. Request/job types live in
`core/schemas.py`; artefact types live in `core/artefacts.py`. **Both files are frozen at the end
of Phase 0.** Any change after that requires a `MEMORY.md` deviation entry explaining why.

Each artefact model's JSON Schema is handed to llama-server as a `response_format: json_schema`
constraint (see `MEMORY.md` §9, 2026-09-06 grammar investigation), so keep them shallow:
objects, arrays of objects, strings, ints, enums. No unions, no optionals-of-objects, no recursion.

Grammar-constrained small models get numeric sequences wrong often enough that each wrong value
costs a retry, so **artefact list items carry no `index` field** — array order is the order.
Renderers use `enumerate()`.

---

## Request and job types (`core/schemas.py`)

```
SourceInput
  kind: enum[text, file]
  text: str | None       # set when kind == text
  path: str | None        # set when kind == file
  # exactly one of text/path is set; enforced by a model_validator

TransformRequest
  sources: list[SourceInput]        # non-empty
  output_types: list[ArtefactType]  # non-empty, de-duplicated, order preserved
  params: GenerationParams
  operator: str | None = None       # who ran the job; falls back to $USER then "unknown" (runner.resolve_operator)

ArtefactType  (enum)
  executive_summary | advisory | linkedin_post | x_thread
  presentation | infographic_spec | video_package

JobStatus  (enum)
  PENDING | RUNNING | SUCCEEDED | FAILED | CANCELLED
  # CANCELLED covers acquire-timeout and a batch aborted mid-swap

Job
  id: str
  transform_id: str          # the parent Transform (batch) this job belongs to
  artefact_type: ArtefactType
  model_key: str             # what the scheduler groups by, e.g. "brain"
  status: JobStatus
  depends_on: list[str]      # ids of jobs that must finish first
  error: str | None
  artefact_path: str | None  # set once the artefact file is written
  created_at: datetime
  updated_at: datetime
```

**Two entities, two names.** A **Transform** is one operator request (the batch). A **Job** is one
artefact within it. The planner emits `list[Job]`; the scheduler groups jobs by `model_key`.
Routes: `POST /transforms`, `GET /transforms/{id}`, `GET /transforms/{id}/artefacts`, `GET /jobs/{id}`.

---

## GenerationParams (`core/schemas.py`)

```
audience: enum[general_public, technical, executive, policy_maker, media, internal]
tone: enum[neutral, formal, urgent, reassuring, promotional, analytical]
language: str = "en"
detail: enum[brief, standard, deep]
objective: enum[inform, warn, persuade, instruct, announce, summarise]
style: enum[plain, narrative, bulleted, technical]
template: str = "ntro-formal"
```

**Template handling.** `template` selects a document template (a real `.potx`/`.dotx` file,
declared in `configs/templates/templates.yaml`) for `presentation`/`advisory`/`executive_summary`
output — see `docs/TEMPLATES.md`. It is a free string, not an enum, so a new template needs no
schema change; an unknown id, a missing template file, or a template missing a required layout
or named style degrades to the built-in renderer output with a warning recorded on the
artefact's provenance manifest (`Manifest.render_warnings`) — it never fails the job. Added
after the Phase 0 freeze (deviation, `MEMORY.md`).

**Language handling.** The brain model (Qwen) is multilingual, so text artefacts honour `language`
on a best-effort basis. ASR (`faster-whisper *.en`) and TTS (`piper en_US-*`) are English-only in
both hardware profiles. When `language != "en"` and a job needs ASR or TTS, the job proceeds and a
`language_limitation` warning is written into that artefact's manifest — it never fails the job.
Tested values are `en` and `hi`; any other value is accepted and treated as best-effort.

---

## SourceDossier (`core/schemas.py`)

```
id: str
created_at: datetime
sha256: str
text_blocks: list[{source_name: str, text: str,
                   evidence_id: str = "", page: int | None = None, heading: str = ""}]
image_insights: list[{source_name: str, caption: str, extracted_text: str,
                      notable_elements: list[str], evidence_id: str = ""}]
transcripts: list[{source_name: str, text: str,
                   segments: list[{start: float, end: float, text: str, evidence_id: str = ""}]}]
video_events: list[{source_name: str, start: float, end: float,
                    transcript: str = "", caption: str = "", evidence_id: str = ""}]
metadata: dict[str, str]

# method: to_prompt_text() -> str   — each evidence unit prefixed [En]; video/audio spans as m:ss–m:ss

# Evidence IDs (evidence_id = E1, E2, ...) are assigned in order at dossier assembly across
# text_blocks, image_insights, video_events and transcript segments. Added after the Phase 0
# freeze (deviation, MEMORY.md 2026-09-06). page/heading/video_events also added then.
```

---

## ArtefactBase (`core/artefacts.py`)

Every artefact inherits this.

```
artefact_type: Literal[...]   # fixed per subclass, e.g. Literal["advisory"]
title: str                    # required, non-empty
confidence_notes: str = ""    # what the model could not determine from the source; may be ""
sources: list[str] = []       # dossier evidence IDs (E1, E2, ...) the artefact draws on.
                              # Added after the Phase 0 freeze (deviation, MEMORY.md 2026-09-06);
                              # the agent populates it; prerequisite for Phase 8.5 verification.
```

---

## ExecutiveSummary  — `artefact_type = "executive_summary"`
```
headline: str
key_points: list[str]            # 3–6
context: str
implications: list[str]          # 2–4
recommended_actions: list[str]   # 0–5
one_line_takeaway: str
```

## Advisory  — `artefact_type = "advisory"`
```
advisory_id: str
severity: enum[informational, low, medium, high, critical]
issued_for: str
summary: str
background: str
technical_details: list[{heading: str, body: str}]
affected_entities: list[str]
indicators: list[{ioc_type: enum[ipv4, ipv6, domain, url, sha256, md5, email, filename, other],
                  value: str, note: str}]        # may be empty; Python field name ioc_type,
                                                 # JSON/schema key "type" via alias
recommended_actions: list[{priority: enum[immediate, high, medium, low], action: str}]
references: list[str]                             # may be empty
handling_caveat: str
```

## LinkedInPost  — `artefact_type = "linkedin_post"`
```
body: str                # <= 2800 chars
hook: str                # first 2 lines, must stand alone
hashtags: list[str]      # 3–6, no '#' prefix in the value
call_to_action: str
suggested_image_brief: str
```

## XThread  — `artefact_type = "x_thread"`
```
tweets: list[{text: str}]    # 3–8 tweets, each text <= 275 chars
hashtags: list[str]          # 1–3
thread_hook: str
```

## Presentation  — `artefact_type = "presentation"`
```
slides: list[{
  layout: enum[title, bullets, two_column, quote, closing],
  title: str, bullets: list[str], speaker_notes: str
}]                               # 5–12 slides
deck_summary: str
```

## InfographicSpec  — `artefact_type = "infographic_spec"`
```
headline: str
subhead: str
sections: list[{heading: str, stat_value: str, stat_label: str, body: str}]   # 3–5
key_messages: list[str]                                                        # 2–4
layout_recommendation: enum[vertical_flow, three_column, timeline, comparison, hub_spoke]
colour_intent: str
icon_suggestions: list[str]
footer: str
```

## VideoPackage  — `artefact_type = "video_package"`
```
runtime_seconds_target: int
logline: str
scenes: list[{
  duration_seconds: int, scene_description: str, on_screen_text: str,
  narration: str, visual_recommendation: str, b_roll_suggestions: list[str]
}]                               # 4–8 scenes
full_narration: str              # concatenated, used for TTS
subtitle_hint: str
```

`runtime_seconds_target` vs the sum of `scenes[].duration_seconds` is advisory only: a mismatch
writes a warning into the manifest and never fails the job.

---

## Validation rules the agent layer enforces after schema validation

- `XThread.tweets[].text` length ≤ 275 → else retry with the violation in the prompt
- `LinkedInPost.body` length ≤ 2800 → else retry
- `Presentation.slides` count within 5–12
- No artefact field may be an empty string where the schema requires content
  (`confidence_notes` is exempt — it may be "")
- Every list with a stated min/max is enforced in a `field_validator`, not just documented here
- `Advisory.indicators[].ioc_type` and `recommended_actions[].priority` must be valid enum members
