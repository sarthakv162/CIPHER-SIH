# Artefact schemas

These are the contracts every agent must produce and every renderer must consume. Implement as Pydantic v2 models in `src/rupantar/core/artefacts.py` during Phase 0, then **freeze**.

Each model gets a GBNF grammar generated from its JSON Schema, so keep them shallow: objects, arrays of objects, strings, ints, enums. Avoid unions, optionals-of-objects, and recursion.

---

## Shared

```
GenerationParams
  audience: enum[general_public, technical, executive, policy_maker, media, internal]
  tone: enum[neutral, formal, urgent, reassuring, promotional, analytical]
  language: str = "en"
  detail: enum[brief, standard, deep]
  objective: enum[inform, warn, persuade, instruct, announce, summarise]
  style: enum[plain, narrative, bulleted, technical]

SourceDossier
  id, created_at, sha256
  text_blocks: list[{source_name, text}]
  image_insights: list[{source_name, caption, extracted_text, notable_elements[]}]
  transcripts: list[{source_name, text, segments[{start, end, text}]}]
  metadata: dict[str, str]

ArtefactBase        # every artefact inherits
  artefact_type: str
  title: str
  confidence_notes: str   # what the model could not determine from the source
```

---

## ExecutiveSummary
```
headline: str
key_points: list[str]            # 3–6
context: str
implications: list[str]          # 2–4
recommended_actions: list[str]   # 0–5
one_line_takeaway: str
```

## Advisory
```
advisory_id: str
severity: enum[informational, low, medium, high, critical]
issued_for: str
summary: str
background: str
technical_details: list[{heading, body}]
affected_entities: list[str]
indicators: list[{type, value, note}]     # may be empty
recommended_actions: list[{priority, action}]
references: list[str]
handling_caveat: str
```

## LinkedInPost
```
body: str                # <= 2800 chars
hook: str                # first 2 lines, must stand alone
hashtags: list[str]      # 3–6, no '#' prefix in the value
call_to_action: str
suggested_image_brief: str
```

## XThread
```
tweets: list[{index, text}]      # each text <= 275 chars, 3–8 tweets
hashtags: list[str]              # 1–3
thread_hook: str
```

## Presentation
```
slides: list[{
  index, layout: enum[title, bullets, two_column, quote, closing],
  title, bullets: list[str], speaker_notes: str
}]                               # 5–12 slides
deck_summary: str
```

## InfographicSpec
```
headline: str
subhead: str
sections: list[{heading, stat_value, stat_label, body}]   # 3–5
key_messages: list[str]                                    # 2–4
layout_recommendation: enum[vertical_flow, three_column, timeline, comparison, hub_spoke]
colour_intent: str
icon_suggestions: list[str]
footer: str
```

## VideoPackage
```
runtime_seconds_target: int
logline: str
scenes: list[{
  index, duration_seconds, scene_description, on_screen_text,
  narration: str, visual_recommendation: str, b_roll_suggestions: list[str]
}]                               # 4–8 scenes
full_narration: str              # concatenated, used for TTS
subtitle_hint: str
```

---

## Validation rules the agent layer enforces after schema validation

- `XThread.tweets[].text` length ≤ 275 → else retry with the violation in the prompt
- `LinkedInPost.body` length ≤ 2800
- `Presentation.slides` count within 5–12
- No artefact field may be empty string where the schema requires content
- Every list with a stated min/max is enforced in `field_validator`, not just documented here
