# E.D.I.T.H. — Agent Spec

This file is the single source of truth for what E.D.I.T.H. is and why. Any future
build session should read this first before touching code.

## Identity

**Name:** E.D.I.T.H.

**What it's for:** E.D.I.T.H. is the 8th founding team member of **ELP (ESports League
Pakistan)** — an AI cofounder, not a bolted-on tool. It exists to help a 7-person
founding team launch a real eSports tournament.

**Personality:** Professional but playful. It should sound like a sharp, slightly witty
teammate who takes the work seriously without taking itself too seriously. Consistent
everywhere — system prompt, voice, proactive notices.

**Who it's for (v1):** Single-user for RUNNING/TALKING TO E.D.I.T.H. and for
CONFIRMATION authority (see "Multi-user note" below — that part is still open).
Memory itself (Tier 4) was explicitly decided to be TEAM-FACING, not personal: one flat
list of facts about ELP and its people, visible to whoever's using E.D.I.T.H., no
per-person attribution field — see Tier 4's section below for the actual design.
This creates a real, acknowledged asymmetry worth naming plainly: memory already
thinks in team terms; confirmation authority and proactive-notice routing do not yet.
That's not a contradiction to silently resolve — it's the actual, current state,
and Tiers 5/6 will need their own explicit decisions when they're built, not an
assumption that Tier 4's answer already covers them.

## First three capabilities

These are the seed capabilities the first tools in Tier 2 should be built around.
They're intentionally broad right now — they get sharpened into concrete, individually
testable tools once we're actually building Tier 2.

1. **Streamline team workflows** — help the founding team coordinate, track what's
   moving and what's stuck, reduce coordination overhead.
2. **Prepare strong roadmaps** — help build and maintain the tournament launch roadmap:
   milestones, dependencies, what's next.
3. **Digital/foundational work for ELP's launch** — the ground-level digital work of
   getting the tournament stood up (drafting, organizing, prepping materials).

## Stack

- **Language/runtime:** Python
- **Model provider:** Gemini via the Google AI Studio API (free tier). Kept behind a
  thin seam (see engineering notes) so it can be swapped later if the free tier's
  limits become a real constraint.
- **Where it runs:** Laptop, to start. The heartbeat (Tier 5) is built so it *can*
  relocate to an always-on machine later without a rewrite — but that's a later step,
  not a v1 requirement.

## How you'll talk to it

- **Typed first** (Tiers 1–2). This stays alive forever as the debug path and fallback.
- **Push-to-talk voice** on top once the brain is solid (Tier 3). Open-mic wake word is
  explicitly out of scope for now.

## Boundaries — never without asking first

Default list, per the harness's Tier 6 confirmation gate:
- Sending a message (email, chat, DM, etc.) on the team's or ELP's behalf
- Spending money
- Deleting data
- Changing a setting

Any tool that does one of these must stop and get explicit yes before running, stating
plainly what it's about to do.

## Proactive behavior

**Yes, proactive — quiet by default.** E.D.I.T.H. earns the right to interrupt; it
doesn't assume it. Most background checks should produce nothing most of the time.
Genuine interruptions are reserved for things that actually warrant one; everything
else accumulates in a calm log.

## Future item: full chat transcript logging (not yet built)

Asked whether full chat history (not just extracted facts) can be saved.
Tier 4's memory.json stores durable FACTS (remember_fact), not verbatim
conversation logs — different thing, already working. A full transcript
log is a real, separate feature: its own storage file, wiring into
Brain across all four entry points (main.py, main_voice.py,
main_voice_local.py, live_explore.py), and the same verification rigor
as everything else here. Not built yet — flagged as a natural fit for
Tier 6's "visible audit trail" idea (a log of what E.D.I.T.H. did and
why) rather than bolted on hastily. Start there next time.

The harness as built (Tiers 4 and 6 especially) started single-user: one memory store,
one person's confirmation authorizes an action. ELP's founding team is 7 people, and
the long-term intent is for E.D.I.T.H. to feel like *the team's* cofounder, not just
yours.

The original three open questions here, and their current status:
- **Whose facts does memory store, and who can see/edit them?** RESOLVED for Tier 4:
  team-facing, one flat list, no per-person attribution, visible to whoever's using
  E.D.I.T.H. See Tier 4's section below for the actual design and reasoning.
- **Who can confirm a consequential action — just you, or any of the 7?** STILL OPEN.
  This is Tier 6's question, not Tier 4's — memory being team-facing does NOT
  automatically mean confirmation authority is. Don't assume this is answered until
  Tier 6 makes its own explicit decision.
- **If proactive notices surface something, who do they surface to?** STILL OPEN.
  This is Tier 5's question. Same caveat as above.

Don't silently expand Tier 4's team-facing memory decision into "Tier 5/6 are also
solved" as those tiers get built. When Tier 5 and Tier 6 are reached, each needs its
own deliberate decision about multi-user handling — retrofitting it later, after
building single-user assumptions into either, is exactly the kind of rewrite this
harness is designed to avoid elsewhere.

## Engineering notes carried from the harness doc

- One shared agent core. Typed turns, spoken turns, and heartbeat-initiated turns all
  flow through the same brain. Never fork the agent logic for voice.
- Provider (Gemini) sits behind a thin seam: one function, "send this conversation,
  get back a reply or a tool-use request." Nothing else touches the SDK directly.
- Secrets (Gemini API key, later Deepgram/ElevenLabs keys) live in environment
  variables / a git-ignored secrets file from the first commit. Never in source.
- Build and verify one tier at a time. Don't fuse tiers together.

## Status

- [x] Tier 0 — Interview + this spec
- [x] Tier 1 — The brain (text conversation loop). Verified working on Pydroid 3
      (Acode's Python plugin) on Android, in addition to a standard Linux/Python
      environment. Run via Pydroid's Terminal with `python -m edith.main` from
      the project root — not the single-file Run button, which doesn't reliably
      resolve the package-relative import.
- [x] Tier 2 — The hands (tools). First tool: the ELP roadmap (add/view/update
      milestones), stored in `roadmap.json` at the project root — plain,
      human-readable, hand-editable, and deliberately separate from Tier 4's
      future memory store (that's for facts about people; this is project
      data). Verified end-to-end against a scripted stub: successful tool
      calls, an unregistered-tool request, and a genuine tool failure (bad
      milestone id) all confirmed to reach the model as plain-language
      results without crashing the loop.
      NOTE on streaming: a turn where the model uses a tool does a brief
      non-streamed round-trip to detect+run the call, then the model's
      final answer streams normally. A turn with no tool call streams from
      the first token, same as Tier 1. This is inherent to how function
      calling works (a tool call needs its complete arguments before it can
      run), not a shortcut — see the docstring on Brain.send() in brain.py.
      BUG FOUND ON FIRST REAL RUN (fixed): tool declarations were built as
      raw dicts with a stray "type": "function" key, which crashed on
      startup with a pydantic ValidationError the moment a real
      google-genai client tried to construct types.Tool(...) — the SDK's
      types are strict (extra='forbid'), so an unrecognized field is
      rejected outright rather than ignored. The offline stub used during
      development was too permissive to catch this: it accepted any dict
      shape, so the bug only surfaced against the real SDK. Fixed by
      building a real types.FunctionDeclaration(name=, description=,
      parameters=) instead of a hand-rolled dict, confirmed against three
      independent current sources before changing the code a second time.
      Re-verified with a *strict* stub built specifically to mimic
      pydantic's extra='forbid' behavior, which — checked — does correctly
      reproduce the original crash against the old code and does pass
      against the fix. Lesson for future tiers: an offline stub is only as
      good as its strictness: a stub that accepts more than the real
      dependency does can hide exactly this class of bug.
      CONFIRMED WORKING against the real, live Gemini API on-device
      (Pydroid/Android): all three tools (add_milestone, view_roadmap,
      update_milestone) accessible and callable by the model in a real
      conversation. This is the first point where the SDK's documented
      behavior has been checked against Gemini's actual live responses,
      not just research and stubs — closes out the main open risk noted
      after the initial build.
      SECOND BUG FOUND, AND MY FIRST FIX WAS ALSO WRONG: the function-
      response message sent back to the model after a tool call originally
      used types.Content(role='user', ...), which raised. Research across
      three sources showed a canonical role='tool' Content pattern, so
      that was tried next — and ALSO raised, with a much more informative
      error: "Message must be a valid part type: typing.Union[str, File,
      Part]... got <class 'google.genai.types.Content'>". That error
      revealed the real problem: chat.send_message()'s `message` parameter
      has its own narrow type (confirmed directly from the SDK's own
      source, chats.py, surfaced via someone else's GitHub issue showing
      the identical traceback) — list[PartUnionDict] | PartUnionDict. It
      does not accept a Content object AT ALL, regardless of role. The
      role='tool' research was accurate for a DIFFERENT method
      (client.models.generate_content()'s contents=[...] parameter, which
      does take a list of Content objects representing a full
      conversation) — it just wasn't the method being called here. Fixed
      by passing a bare list of Part objects directly, which matches
      send_message's actual documented parameter type exactly. Verified
      against a stub whose validation logic mirrors the real chats.py
      source line, not an inferred shape.
      Lesson, stated plainly: two wrong fixes in a row came from correctly
      researching a pattern and then applying it to the wrong call site —
      client.models.generate_content and chat.send_message look similar
      but have different accepted input types, and confirming a shape is
      "documented and canonical" isn't the same as confirming it's
      documented for the specific method actually being called. The thing
      that finally resolved it was the SDK's own runtime error message,
      not another round of example-matching. When an error message states
      a type union explicitly, that's higher-confidence evidence than any
      number of adjacent doc examples.
      RPD QUOTA HIT, MODEL SWITCHED: shortly after confirming the above
      fix worked live, hit a 429 "quota exceeded" (RPD, not RPM — these
      are different limits with different meanings: RPD means the DAILY
      cap is spent and won't reset until midnight Pacific; RPM clears in
      under a minute). AI Studio showed gemini-2.5-flash at a 20 RPD
      ceiling for this project — general web research suggested figures
      as high as 250-1500 RPD for the same model, which turned out
      unreliable; free-tier numbers vary by project/region/account state
      in ways aggregator articles don't capture, so AI Studio's own
      dashboard for the actual project is the only trustworthy source
      going forward, not blog posts (including any research summarized in
      this file before a given date — recheck the dashboard directly if
      quota issues recur).
      Considered switching to the Gemini "Live" API (real-time audio/video
      runtime) after seeing "unlimited RPD" claimed for it — didn't find
      that specific claim confirmed anywhere, and more importantly it's a
      structurally different interaction model (chat.send_message vs a
      WebSocket-based streaming session) that would mean rewriting the
      whole brain, and it's explicitly preview-only / not for production.
      Wrong tool for a text-only Tier 2 problem — noted here so it isn't
      reconsidered for the wrong reasons later. Voice, when it comes in
      Tier 3, does NOT need to mean adopting this API; that's a separate
      decision to make deliberately when we get there.
      Also considered Gemma models (26B/31B showed 1.5k RPD in AI Studio —
      genuinely higher). Checked its function-calling mechanism before
      switching: Gemma has no response.function_calls field at all: it
      returns tool calls as literal Python wrapped in a
      ```tool_code``` markdown block that the caller is expected to
      eval() (Gemma 3) or parse via regex (Gemma 4 — the mechanism isn't
      even stable across Gemma's own model generations). Switching would
      mean rewriting Brain's entire tool-detection logic, not a model-name
      swap, plus taking on real code-execution security considerations
      the Gemma docs themselves flag. Not worth it for a quota problem
      alone — if E.D.I.T.H. later needs that much daily throughput,
      revisit as its own deliberate tier.
      RESOLVED: switched MODEL_NAME to gemini-3.1-flash-lite (500 RPD per
      AI Studio, confirmed directly in the dashboard) — same Gemini
      family, same SDK surface, same response.function_calls mechanism
      already verified working. Pure model-name change; nothing else in
      brain.py needed to change. Re-verified full tool-call loop against
      the strict stub after the swap, including confirming the new model
      string actually reaches the SDK's chats.create() call and isn't
      silently dropped or overridden.
- [x] Tier 3 — EARS (speech-to-text) half. Based on the pipeline confirmed
      working live on-device via Termux (see the Termux research section
      above): termux-microphone-record -> ffmpeg decode -> Deepgram
      WebSocket, wrapped in a single listen() seam at edith/voice/ears.py.
      Feeds into the EXACT SAME Brain/registry as main.py (extracted
      shared setup into edith/setup.py so main.py and the new
      main_voice.py can't drift apart) — per the doc's "never fork the
      agent logic for voice." Entry point: edith/main_voice.py.
      Honest note on "push-to-talk": this is Enter-to-start-a-fixed-
      duration-recording, not true hold-a-key-while-speaking as the doc
      describes — that needs raw terminal input handling, real, separate
      work not yet built. Documented as a deliberate simplification in
      main_voice.py's own docstring.
      REAL BUGS FOUND AND FIXED along the way, in order: (1) requirements
      install failures on Termux specifically — cryptography and
      pydantic-core both needed native-toolchain workarounds, documented
      in requirements.txt and the Termux dependency section above; (2)
      termux-microphone-record doesn't block until recording finishes —
      it's asynchronous, `-l` is a ceiling not a wait, and the original
      code's fixed 1-second sleep raced against a still-in-progress
      background recording, producing ffmpeg's "moov atom not found" on
      an incomplete M4A file. Fixed by sleeping the real duration and
      explicitly sending `-q` to stop/finalize the recording, matching
      Termux:API's own documented usage pattern.
      CONFIRMED WORKING END-TO-END ON-DEVICE, user-verified, after all of
      the above: recording, conversion, transcription, and delivery into
      Brain.send() all completed successfully with a real spoken query.
      Transcription quality was "a bit messy" — open item, not yet
      root-caused, see note above; not treated as a blocker.

- [x] Tier 3 — MOUTH (text-to-speech) half. ElevenLabs free tier confirmed
      directly against the user's own dashboard (not aggregator research):
      10,000 credits/month, API access included, non-commercial only.
      Model: eleven_flash_v2_5, not eleven_v3 — chosen for lower latency
      (~75ms inference, ~150-300ms time-to-first-audio per multiple
      current sources) and lower credits/character, both of which matter
      given voice's real-time nature and the monthly credit ceiling.
      Voice: user browsed ElevenLabs' own voice library and selected
      voice_id "uYXf8XasLslADfZ2MB4u" themselves — deliberately NOT
      defaulted to a value picked without the user's input, per this
      file's own earlier note that this should be an explicit choice.
      Seam: edith/voice/mouth.py — speak(text) saves an mp3 via the
      ElevenLabs Python SDK (client.text_to_speech.convert, confirmed
      current shape via 3 independent sources: official GitHub repo,
      ElevenLabs' own docs mirror, a REST cheat-sheet); play_audio(path)
      plays it via termux-media-player.
      PROACTIVE DESIGN DECISION based on ears.py's async-recording bug:
      termux-media-player exposes separate play/pause/stop commands, the
      same structural shape that turned out to mean
      termux-microphone-record was asynchronous rather than blocking.
      Rather than assume termux-media-player blocks (unconfirmed either
      way from research) OR assume it doesn't and guess a fixed sleep
      duration (the exact mistake that caused the recording bug),
      play_audio() gets the audio's ACTUAL duration via ffprobe (already
      available since ffmpeg is a required dependency) and waits that out
      explicitly. Should be correct regardless of whether the command
      actually blocks or not.
      Integration: main_voice.py now speaks replies aloud in addition to
      printing them. Honest about NOT doing true incremental streaming
      TTS (starting speech on the first sentence while the rest is still
      being generated, which the original design doc describes as
      ideal) — accumulates the full streamed reply from Brain.send(),
      then speaks it once, all at once. A real, reasonable simplification,
      documented as such in main_voice.py's own docstring, not silently
      passed off as the more advanced version.
      VERIFICATION STATUS: main_voice.py's control-flow logic (calling
      speak()+play_audio() at the right time, a SpeakingError not erasing
      the already-printed text reply, the loop continuing correctly after
      a speech failure) verified against scripted stubs for both
      edith.voice.ears and edith.voice.mouth — same discipline as
      brain.py's tool-loop testing.
      CONFIRMED WORKING END-TO-END ON-DEVICE, user-verified: the real
      ElevenLabs API call, real audio generation, and real
      termux-media-player playback through the phone's actual speaker all
      completed successfully — a spoken question produced a spoken reply,
      genuinely closing the loop the original design doc describes for
      Tier 3. The ffprobe-based duration-wait approach in play_audio()
      (built proactively, before hitting a problem, based on the lesson
      from ears.py's async-recording bug) did not need debugging — worked
      correctly on the first real attempt.

**TIER 3 COMPLETE — both EARS and MOUTH confirmed working end-to-end,
live, on-device.** The harness doc's core Tier 3 goal — "I press and hold
a key, speak, release, and the assistant hears me, runs the same brain
and tools, and speaks its reply aloud" — is genuinely met, with two
documented, deliberate simplifications (Enter-to-record instead of true
hold-to-talk; accumulate-then-speak instead of true incremental streaming
TTS), both explained in main_voice.py's own docstring rather than quietly
passed off as the full thing.
- [x] Tier 4 — The memory. Team-facing per explicit decision (see "Who
      it's for" above and the Multi-user note): one flat list of durable
      facts, no per-person attribution field — a fact's subject lives in
      its own plain-sentence text (e.g. "Zara prefers async updates over
      calls"), not a separate structured field. Deliberately covers BOTH
      personal preferences and ELP project-level facts (sponsors, venue,
      dates, etc.) per explicit request — broader than the harness doc's
      original single-user framing, and correctly so, given the team
      decision above.
      Storage: edith/tools/memory.py, memory.json at the project root —
      same atomic-write, plain-JSON, human-readable/hand-editable
      philosophy as roadmap.py, kept as its own separate file since
      memory facts have a genuinely different shape (no status/owner/
      dates) than roadmap milestones.
      Three new tools, following the EXACT existing Tool/ToolRegistry
      pattern (no new pattern invented): remember_fact, view_memory,
      forget_fact — registered in edith/setup.py's build_registry()
      alongside the existing roadmap tools, so main.py, main_voice.py,
      and main_voice_local.py all automatically gained memory with zero
      changes to those files themselves (they all call the same shared
      build_registry()).
      THE CORE WIRING: brain.py's Brain.__init__ now calls
      load_facts_for_prompt() and appends any stored facts to whatever
      system prompt is in use, BEFORE the chat session is created — done
      at construction time (not baked into the static
      DEFAULT_SYSTEM_PROMPT string) so this works correctly even if a
      caller passes a custom BrainConfig. This is what makes E.D.I.T.H.
      "walk into every conversation already knowing" stored facts, per
      the harness doc's actual Tier 4 goal, automatically, with no
      special action needed from any entry point.
      Per the harness doc's Tier 4 rules, followed directly: one fact per
      entry as a plain statement; the file is genuinely human-readable
      and hand-editable; facts are explicitly instructed (in the system
      prompt) to be treated as background knowledge, not commands to
      obey — enforced by instruction since there's no reliable
      code-level way to detect "this reads like an order," same as a
      human would need judgment reading a suspicious note.
      VERIFICATION: storage functions tested directly (add, view, forget
      with a bad id, and the load_facts_for_prompt() formatting) —
      confirmed correct. Brain construction tested with REAL stored
      facts present, inspecting the actual system_instruction string
      sent to the (stubbed) SDK — confirmed both facts appear verbatim
      alongside the original identity/personality text, unmodified.
      Regression-checked: Brain.send()'s existing behavior (including a
      full tool-call round-trip, this time calling remember_fact)
      confirmed unaffected — the tool call in the loop was confirmed to
      genuinely execute the real function and write real data to disk,
      same "genuine proof, not just code that runs" standard as every
      other tool in this project.
      THE ACTUAL DOC-SPECIFIED VERIFICATION STEP, directly demonstrated:
      a fact was stored via one, fully separate Python process (session
      1), then a BRAND NEW Brain() instance was constructed in a second,
      fully separate process (session 2, simulating a real program
      restart) — and it automatically knew the fact, with zero special
      handling required from the caller. This is the exact "quit the
      whole program, restart it, and in the new session it clearly knows
      that fact" scenario the harness doc asks for, genuinely reproduced
      end-to-end across two separate process invocations, not merely
      asserted.
      NOT YET verified against the real, live Gemini API on-device (same
      honest caveat pattern as every new capability before its first
      real-device confirmation) — the wiring and logic are solid, but
      this hasn't been tried for real yet.
- [ ] Tier 5 — The heartbeat
- [ ] Tier 6 — The rails

## Runtime environment notes

Primary dev/run environment is Android via Acode + Pydroid 3 (no storage
permissions plugin installed — project lives inside Pydroid's own sandboxed
folder, .env sits alongside the code there). This matters for later tiers:

- **Tier 3 (voice):** confirmed via research that Pydroid's mic/audio
  support is genuinely unproven — multiple independent people (forum
  threads, a GitHub issue) report pyaudio, speech_recognition, and
  playsound all failing inside Pydroid specifically, with no working
  solution surfacing anywhere. This looks like a real limitation of
  Pydroid's sandboxed execution model, not a gap in research. DECISION:
  split environments going forward. Tiers 1-2 (text) stay on the phone via
  Pydroid, unchanged. Tier 3 (voice) is built and run on laptop instead —
  a genuine second interface into the same Brain/tool registry, not a
  fork of them, matching the doc's "one shared agent core, many ways in
  and out" principle. Each environment gets its own independent
  roadmap.json (path is relative to the file, per-machine) since there's
  no sync mechanism yet — a milestone added via laptop voice won't show
  up on phone text until Tier 4 or a later sync step addresses this;
  noted here so it isn't a surprise.
  Termux (a proper Linux terminal emulator for Android, distinct from
  Pydroid) was also researched as a phone-native alternative — its
  termux-microphone-record shell command has strong, consistent
  documentation across multiple independent sources, genuinely more
  promising than Pydroid. Not pursued for now per explicit preference for
  laptop; worth revisiting if voice ever needs to be phone-native.
- **Tier 5 (heartbeat):** an always-on background loop fights Android's
  battery/process-management model hard (the OS will kill or suspend
  backgrounded apps). Given the Tier 3 split above, the heartbeat likely
  belongs on whichever machine ends up "always-on" for this project —
  revisit explicitly at Tier 5, don't assume it'll just work on phone.

## Tier 3 provider research (before writing code)

**Speech-to-text: Deepgram** (per original design doc).
- Pricing: NOT a resetting free tier like Gemini's. $200 one-time free
  credit, no card required, then usage-based (~$0.0065-0.0077/min).
  $200 is substantial runway (hundreds of hours) but is a depleting
  balance, not something that resets daily/monthly — different shape
  than Gemini's quota, worth remembering so it isn't assumed to reset.
- SDK: current package is `deepgram` (not an older `deepgram-sdk`
  naming), current shape uses `client.listen.v2.connect()` for
  streaming per the SDK's GitHub README. An older API shape
  (`deepgram.transcription.live(...)`, hand-rolled `websockets` +
  `pyaudio` against `wss://api.deepgram.com/v1/listen`) also appears
  across various docs/blog posts/tutorials — these are DIFFERENT SDK
  generations, not interchangeable; brain.py's earlier bugs came from
  exactly this kind of cross-version blending, so Tier 3's STT seam
  will be built against the current README's shape specifically, not
  whichever example surfaces first in search.
- Before writing E.D.I.T.H.'s own STT integration: verify laptop mic +
  Deepgram connectivity using Deepgram's own official "Live Streaming
  Starter Kit" (confirmed current, live on Deepgram's own docs site;
  repo at github.com/deepgram/streaming-test-suite/) completely
  decoupled from any of my code. This isolates "does the mic/API work
  at all" from "is my integration code correct" — if the starter kit
  fails, that's an environment problem to solve before any of
  E.D.I.T.H.'s own code is written, not a bug to debug in brain.py-style
  code.

**Text-to-speech: ElevenLabs** (per original design doc) — NOT YET
COMMITTED. Free-tier API access is genuinely unclear from research:
sources conflict on whether free tier includes real API access at all.
One source describes a UI-plan free tier (10,000 characters/month) as if
it includes API access; a more API-specific source describes a SEPARATE
"API" tier system where the API-specific free tier is 10 credits/month
(not 10,000) — two orders of magnitude apart, and clearly not just
rounding/imprecision. Multiple other sources say standard API access only
starts at the paid Starter tier. Given this real conflict, decided NOT to
build ElevenLabs integration on an assumption — user will check their own
account/dashboard directly (same discipline as checking Gemini's AI
Studio dashboard directly rather than trusting aggregator estimates)
before this is committed to. Speech OUTPUT (Tier 3's "mouth" half) is
deliberately sequenced AFTER speech input is fully verified, specifically
so this open question doesn't block STT progress. Until resolved, E.D.I.T.H.'s
laptop voice interface will use speech input + printed text output —
a legitimate, testable intermediate state, not a workaround.

## Termux dependency note: native-compilation build failures (found and fixed, twice)

When actually running `pip install -r requirements.txt` on Termux for the
first time (previously only verified: syntax, and Pydroid's install of
these same three top-level packages — Pydroid and Termux are NOT the same
environment and don't share a verified install history), hit real build
failures TWICE in a row, same underlying category both times:

1. **cryptography** — pulled in via google-auth (an optional extra,
   activated by google-genai's specific auth path). Failed with `Target
   triple not supported by rustup: aarch64-unknown-linux-android`.
2. **pydantic_core** — pulled in via pydantic, which is a REQUIRED direct
   dependency of google-genai itself (confirmed via google-genai's own
   PyPI-listed dependency list), not just an optional extra. Same failure
   category: native Rust code, no prebuilt wheel for Termux's
   aarch64-linux-android target, Termux's Rust/maturin toolchain doesn't
   recognize the triple.

Both confirmed via multiple independent, converging sources (GitHub
issues against pydantic-core, python-kasa, spotDL, aiogram all hitting
the identical maturin/Rust-on-Termux failure with different top-level
packages — this is a general Termux/Rust-Python-package issue, not
specific to anything Gemini-related).

FIX for both, same pattern: install via Termux's own package manager
BEFORE running pip, so pip sees the requirement already satisfied and
skips the source build that fails:
    pkg install python-cryptography python-pydantic
Documented directly in requirements.txt as a comment (the file format
can't express "install this first via a different tool") and here.

CHECKED FOR MORE: went through google-genai's full required-dependency
list from its own PyPI page (anyio, distro, google-auth, httpx, pydantic,
requests, sniffio, tenacity, typing-extensions, websockets) and reasoned
through each — the rest are all long-established, pure-Python packages
with no known native-compilation history. Not an absolute guarantee
(dependency trees can surprise), but a real check rather than continuing
to only discover these reactively one at a time.

Honest self-assessment: this happened twice in a row, and google-auth +
cryptography's Termux-native-compilation issue is well-documented enough
that it — and by extension the sibling risk with pydantic, given both are
required/near-required dependencies of the same package — should have
been checked proactively as a pair the first time, rather than fixed
individually as each was hit. Noted for future tiers: when a new
dependency is added to requirements.txt, check its FULL dependency tree
for known native-compilation packages (cryptography, pydantic-core,
numpy, pillow, lxml are common ones) up front, not just the top-level
package name.

Explored whether the earlier "Pydroid can't do audio, use laptop" decision
could be avoided by running the voice layer on Termux (a proper Linux
userland for Android, distinct from Pydroid's sandbox) instead — since
Deepgram itself is just a WebSocket API and doesn't inherently care what
OS opens the connection.

CONFIRMED: `termux-microphone-record` genuinely works for raw mic capture
(user-verified: recorded and played back successfully).

BUG FOUND AND FIXED: initial integration script sent the recorded file's
raw bytes to Deepgram's WebSocket URL with `encoding=linear16&sample_rate=
16000` — declaring the payload as headerless raw PCM. Result: Deepgram's
own dashboard showed audio duration of 0. Root cause, confirmed via two
independent sources (a termux-api GitHub issue explicitly requesting WAV
support — implying its absence; a separate real working project's
documented architecture describing the identical problem and fix):
`termux-microphone-record` ALWAYS outputs AAC audio in an M4A container,
regardless of the filename/extension given to it — there is no WAV/raw-
PCM option in its interface at all (`-e` only accepts aac/amr_wb/amr_nb).
A `.wav`-named file was still AAC-encoded bytes inside; sending those to
a URL declaring raw PCM meant Deepgram tried to interpret compressed
audio as literal sample values and found nothing coherent.
FIX: added a required `ffmpeg` decode step (`ffmpeg -i input.m4a -ar
16000 -ac 1 -f s16le output.pcm`) between recording and sending, so the
bytes actually sent match what the URL declares. `ffmpeg` confirmed
available/working in Termux via a separate independent source. NOT yet
confirmed end-to-end by the user as of this note — awaiting a retest with
the corrected script.
Also worth noting for whoever reads this next: my own instructions
initially told the user to name the file `test.wav`/`recording.wav`,
which was itself part of the problem (a misleading name obscuring the
real format) — corrected to `.m4a` for the raw capture and `.pcm` for
the post-ffmpeg file, so filenames now honestly reflect their actual
contents.

**CONFIRMED WORKING END-TO-END, user-verified on-device:** record via
termux-microphone-record -> convert via ffmpeg -> stream to Deepgram ->
correct transcript returned. One follow-on hiccup along the way, also
resolved: `ffmpeg` was first installed via `pip install ffmpeg`, which
does not install the actual ffmpeg binary (pip installs Python code;
ffmpeg is a standalone system program) — this is a well-documented,
common mixup, confirmed via multiple independent sources, not specific
to this project. Fixed with `pkg install ffmpeg` (Termux's actual system
package manager) instead.

BUG FOUND AND FIXED IN edith/voice/ears.py ITSELF (not the original
manually-tested pipeline): the actual project file's _record_audio()
called termux-microphone-record via subprocess.run() and assumed it
blocks until the recording finishes (i.e. that -l seconds means "wait
this long, then return"). This is WRONG, confirmed via Termux:API's own
documented usage pattern, which explicitly shows starting a recording,
then LATER running a separate `termux-microphone-record -q` command to
stop it. The command starts an asynchronous background recording and
returns to the shell almost immediately — subprocess.run() only waits
for that near-instant process launch, not for actual audio capture.
The bug manifested as ffmpeg failing with "moov atom not found" — an
MP4/M4A container's index (moov atom) is only written when a recording
is properly finalized, and the code was handing ffmpeg a file still being
actively written by a separate, still-running background process,
because the only wait in the original code was a flat time.sleep(1)
utterly disconnected from whether the recording had actually progressed
or finished.
Worth noting why the ORIGINAL manual verification (the one that first
confirmed this pipeline works, described above) didn't hit this: doing
it by hand naturally involves real human seconds elapsing between
starting the recording and running the next command, which was enough
time for the background recording to finish on its own. The bug was
specific to how the Python code compressed that same sequence into
near-zero real elapsed time internally.
FIX: explicitly sleep for the real recording duration in Python (not a
fixed short buffer), THEN explicitly send `termux-microphone-record -q`
to stop and finalize the recording (rather than just letting -l expire
on its own and hoping the file is ready), THEN a short additional
settle-pause before handing the file to ffmpeg. This should close the
race condition rather than paper over it with a longer guess-timeout.
CONFIRMED WORKING on-device after this fix: recording, conversion, and
transcription all completed successfully, text reached Brain.send()
correctly. Transcription quality was noted as "a bit messy" — see the
audio-quality note below for what's suspected and what's NOT yet
investigated.

## Local/offline voice alternatives (explored, built, NOT yet on-device tested)

User asked specifically about open-source alternatives to Deepgram and
ElevenLabs, to make the setup "always free" rather than dependent on
provider free tiers that can change (directly motivated by today's real
experience: Gemini's actual RPD turned out far lower than general
research suggested, and ElevenLabs' free-tier API access was genuinely
unclear until checked directly).

**STT: Vosk** — offline, local, Kaldi-based. Chosen over whisper.cpp/
faster-whisper specifically because multiple independent sources
converge on Vosk as the right choice for CPU-only, no-GPU, mobile/
embedded use ("best for lightweight offline devices," explicit Android
support in vosk-api's own GitHub description) — whisper.cpp is more
accurate but every source wants real GPU compute, wrong shape for a
phone. Real tradeoff, stated plainly: multiple sources describe Vosk as
less accurate than transformer-based models, especially with background
noise — given Deepgram's transcripts were already "a bit messy," this
matters, not a footnote.

**TTS: Piper** — offline, local, VITS-based ONNX models. Chosen for the
same CPU/no-GPU/lightweight reasoning — "the model to run when you have
almost no compute," real-time on a Raspberry Pi 5 with no GPU, an actual
working Android app (VoxSherpa) already exists using Piper voices.
License note: the actively-maintained fork (OHF-Voice/piper1-gpl, what
`pip install piper-tts` installs) is GPL-3.0, not the original repo's
MIT — doesn't matter for personal local use, would matter if ever
distributed as closed-source software.

**Built as fully PARALLEL files, not replacements** — ears.py, mouth.py,
main_voice.py are completely untouched and still work exactly as
before:
- edith/voice/ears_local.py — listen_local(), Vosk-based
- edith/voice/mouth_local.py — speak_local()/play_audio_local(),
  Piper-based
- edith/main_voice_local.py — structurally identical to main_voice.py,
  only the ears/mouth imports differ, so comparing the two is an
  apples-to-apples test of the voice layer alone.
Reuses the exact same termux-microphone-record -> ffmpeg capture
pipeline as the cloud version (that part is proven on-device already,
no reason to touch it) — only the transcription/synthesis step differs
per file. play_audio_local() reuses the identical ffprobe-duration-wait
approach as mouth.py's play_audio(), for the same async-command-risk
reason.

**GENUINE, EXPLICITLY UNRESOLVED RISK, same shape as the pydantic_core
saga:** PyPI wheels for BOTH vosk (manylinux2014_aarch64) and piper-tts
(manylinux_2_17/manylinux2014 + macOS) are tagged for standard glibc
Linux, NOT Termux's actual android_*_arm64_v8a tag family (confirmed
directly via this project's own `pip debug --verbose` output earlier).
This may hit the identical platform-tag wall pydantic_core did. NOT
glossed over or assumed away — flagged in requirements.txt, in both
_local.py files' module docstrings, and here. `pip install vosk
piper-tts` (tried alone, separate from the rest of requirements.txt) is
the actual first real test, before any of the speech logic matters.

**VERIFICATION STATUS:** Vosk's core transcription-assembly logic
(chunk reading, JSON parsing, accumulating partial + final results) was
tested against a real, valid synthetic WAV file and a scripted stub
standing in for the actual vosk package, and confirmed to work
correctly. Piper's loading/download API shape was NOT fully pinned down
during research — multiple sources showed slightly different patterns
(bare PiperVoice.load(name) vs. a separate download_voice() step) and
this wasn't resolved to a single confirmed-current answer; flagged
directly in mouth_local.py's own comments as something to check if
voice-loading fails rather than presented as settled.

**CONFIRMED BLOCKED on Termux, user-tested:** `pip install vosk` failed
with `Could not find a version that satisfies the requirement vosk (from
versions: none)` — pip couldn't find ANY candidate wheel to consider at
all (a different, more absolute failure than pydantic_core's "found
wheels, rejected them as incompatible"). This matches the flagged risk
exactly: no PyPI artifact exists for Termux's actual tag family. Given
pydantic_core needed a genuine multi-hour investigation to resolve via a
native source build, and vosk's failure mode here looks like there's no
artifact to even attempt building from in the same way, this path is
being treated as a likely dead end via pip on Termux specifically — not
pursued further via source-build workarounds unless priorities change.
piper-tts was not separately tested after this (same underlying risk
already confirmed via vosk; no reason to expect a different outcome
without new information).

## Gemini Live API exploration (built, genuinely NOT yet run — different
## risk profile from everything else in this project)

User asked whether Google's own built-in audio features could replace
the external providers entirely, after the Vosk/Piper path hit a dead
end. Investigated three distinct Gemini capabilities, not one:
1. Gemini's audio *understanding* (analyze/transcribe an uploaded
   file) — Google's OWN docs explicitly redirect real-time STT use
   cases elsewhere ("For dedicated speech to text models with support
   for real-time transcription, use the Google Cloud Speech-to-Text
   API") — not the right tool for this project's real-time loop.
2. Gemini's standalone TTS (gemini-3.1-flash-tts-preview via
   client.interactions.create) — real, but Preview, and Google's own
   docs list a current, expected-not-edge-case bug: "the model
   occasionally returns text tokens instead of audio tokens, causing
   the server to fail the request with a 500 error... implement
   automated retry logic."
3. **Gemini Live API** — a fundamentally different architecture: one
   continuous, bidirectional audio-in/audio-out WebSocket session with
   the model itself, no separate STT/TTS steps. This is the one
   actually explored further, per explicit user interest even knowing
   it would mean touching brain.py's core architecture.

**Why this is built as edith/live_explore.py, a fully STANDALONE file,
NOT integrated into Brain/ToolRegistry:**
1. Confirmed directly from Google's own docs: "Unlike the
   generateContent API, the Live API doesn't support automatic tool
   response handling. You must handle tool responses manually in your
   client code." This needs its own tool_call/send_tool_response loop —
   structurally different from brain.py's response.function_calls/
   Part-list pattern (verified across three real bugs in Tier 2), not a
   reuse of it.
2. Explicitly Preview, with real, CURRENT naming inconsistency across
   Google's own docs: gemini-3.1-flash-live-preview (AI Studio's own
   dedicated "Get started" page — treated as the most authoritative,
   current source found) vs. gemini-live-2.5-flash-native-audio
   (Vertex-specific docs) — and one older live model variant is
   confirmed being deprecated March 19, 2026 per Google Cloud's own
   docs. This is less stable ground than anything else built in this
   project so far, including the regular Gemini chat API which has been
   solid throughout.
3. Async (asyncio, WebSocket session) vs. brain.py's synchronous
   design — a real structural difference, not a small adapter.

Given all three, live_explore.py exists to answer ONE question — does
Live's tool-calling work well enough to be worth a deeper integration —
without touching anything already proven (brain.py, main.py,
main_voice.py, main_voice_local.py all completely untouched).

Reuses roadmap.py's REAL functions directly (_run_add_milestone,
_run_view_roadmap, _run_update_milestone — the actual functions
main.py's tools call, not reimplemented), so a genuine roadmap check
would prove real value if tried, not a toy example.

Confirmed via research: client.aio.live is a standard property of the
already-installed google-genai package (async_client.live: AsyncLive,
documented alongside .chats/.models/.files in the SDK's own submodule
reference) — no new dependency or version bump needed.

**VERIFICATION STATUS — genuinely more limited than anything else in
this project:** the tool-dispatch logic (TOOL_MAPPING calling the REAL
roadmap.py functions) was tested directly and confirmed correct — same
real add/view/update-with-bad-id checks as everywhere else, writing to
a real roadmap.json.

**FIRST REAL ON-DEVICE RUN, real bug found and fixed:** hit
`websockets.exceptions.ConnectionClosedError: received 1007 (invalid
frame payload data) Request contains an invalid argument` within a
second of sending a message. Traced (not guessed) via fetching Google's
own current, dedicated "Get started with Gemini Live API" page in full
(ai.google.dev/gemini-api/docs/live-api/get-started-sdk, last updated
2026-03-26): that page shows ONLY `session.send_realtime_input(text=...)`
for sending a simple text turn — never `send_client_content(turns=...)`,
which is what live_explore.py originally used. That shape had been
copied from a DIFFERENT doc page (the Tool-use guide, which does show
send_client_content in one of its own examples) without cross-checking
against this more authoritative, dedicated getting-started page first —
same mistake pattern as conflating client.models.generate_content's and
chat.send_message's different accepted input types earlier in Tier 2.
Separately, also corrected: reading model output text from
response.server_content.output_transcription.text (confirmed via the
same page's "Receiving text" section), not a bare response.text, which
doesn't exist on this API's actual response shape and would have
silently printed nothing even if the send had succeeded.
General research supported this diagnosis further: searching the exact
error text surfaced a dozen independent GitHub issues/forum threads, all
hitting the identical generic 1007 message for many DIFFERENT underlying
causes (malformed fields, wrong modality for a given model, unsupported
config options) — confirming this is a broad, unhelpful catch-all
server-side validation error, not a signal of any specific problem on
its own; the specific cause has to be traced from what's actually being
sent, not inferred from the error text alone.
FIXED, but NOT yet re-run on-device as of this note — the tool-dispatch
logic was independently re-verified after this change (still correct),
but the actual corrected send_realtime_input/output_transcription path
has not been confirmed working for real yet. This is genuinely less
proven than ears.py/mouth.py were even after their own first bug fix —
treat as still actively unverified until confirmed via a real run.

**CONFIRMED WORKING ON-DEVICE after the fix, user-verified:** the
session connects, sends/receives text correctly via
send_realtime_input/output_transcription, and — the harder, more
uncertain half — tool-calling over Live's manual protocol works
correctly: the model requests real roadmap tools, live_explore.py
dispatches to the REAL roadmap.py functions, and results correctly
return to the model via send_tool_response. This is genuine proof Live's
tool-calling is viable for E.D.I.T.H.'s actual capabilities, not just
that the connection itself works.

## Gemini Live: real audio I/O (CONFIRMED WORKING END-TO-END ON-DEVICE)

Pushed further into building real mic input and real spoken output for
Live, per explicit user interest even knowing it meant touching this
still-Preview surface further. Two parallel efforts happened:

1. This session drafted an audio-I/O version based on converged research
   (6+ sources) on Live's confirmed audio format specs (input: 16-bit
   PCM, 16kHz mono; output: 16-bit PCM, 24kHz mono — different rates,
   easy to mix up) and Google's own best-practices guidance (send small
   chunks, avoid buffering a full utterance before sending). This
   version used send_realtime_input(audio=...) and chunked sending.
2. SEPARATELY, the user worked directly with Gemini to debug a version,
   iterating live against the real API and real device — and arrived at
   a genuinely different, WORKING approach.

**The user's version is what's in the codebase now — real, working
evidence beats untested reasoning-from-docs.** Key differences from this
session's draft, and what they revealed:

- **send_client_content(turns=[...], turn_complete=True), NOT
  send_realtime_input(audio=...).** The working version's own comment:
  "bypasses VAD hanging issues" — a real, concrete failure mode (the
  server's Voice Activity Detection waiting for an end-of-speech signal
  that a batch-recorded, already-complete file can't naturally provide)
  that this session's draft hadn't accounted for.
- **Sends the whole recording as one Blob, not chunked** — directly
  contrary to Google's own best-practices guidance, and it worked anyway
  for this turn-based (not continuous-streaming) use case.
- **Reuses ears.py's actual private functions directly**
  (_record_audio, _convert_to_pcm, _check_ffmpeg_available) rather than
  duplicating that logic — an improvement over this session's draft,
  which had re-implemented capture separately.

**A REAL, DOCUMENTED TENSION, checked and confirmed via further
research, not glossed over:** Google's own capabilities guide states,
SPECIFICALLY for gemini-3.1-flash-live-preview (the exact model in use):
"send_client_content is only supported for seeding initial context
history... After the first model turn, use send_realtime_input...
instead." Three more independent sources (the official gemini-skills
repo, Firebase's AI SDK docs, a third-party Elixir client's docs) all
state the identical rule, one as an explicit warning: "Do not use it to
send new user messages during the conversation." The working code does
exactly what this documented rule says not to do, and it works on-device
regardless. This is being kept as-is specifically BECAUSE real, working,
on-device evidence outweighs unverified documentation — but it's
recorded here plainly, including the real risk that Live's Preview
status means enforcement could tighten later and this could stop
working after previously working. If that happens, this specific
documented constraint is the first thing to revisit.

A second, smaller point of real ambiguity, also checked rather than
assumed: the tool-response wrapping (response={"result": result}) matches
Google's own official cookbook notebook exactly, but a real, open GitHub
issue (google-gemini/cookbook#906) shows someone else reporting this
same shape failing for raw WebSocket use specifically (a different call
path than this project's SDK-based send_tool_response() approach, which
may handle serialization differently). Not changed, since this exact
code is confirmed working on this project's actual device through the
SDK layer — noted for awareness, not treated as an active bug.

**STATUS: this is now the most functionally complete voice path in the
project** — real audio in, real audio out, tool-calling, all in one
continuous session, confirmed working on-device. It remains a STANDALONE
file (live_explore.py), not integrated into Brain/ToolRegistry — that
remains a separate, real decision given Live's different tool-calling
protocol, Preview status, and async architecture, per the reasoning
above. main.py, main_voice.py, and main_voice_local.py are all still
completely untouched and functional. Turn-based only — no mid-sentence
barge-in/interruption handling built yet, a known, deliberate limitation
matching what was agreed before building this.

After the async-recording fix above, the pipeline works end-to-end but
the transcript came back "a bit messy." Not yet root-caused. Real
candidates, roughly most-to-least likely, NONE confirmed:
1. termux-microphone-record's default audio quality settings (sample
   rate, bitrate, encoder) may be low by default — the command supports
   -r (sample rate) and -b (bitrate) flags that haven't been explored;
   currently using all defaults.
2. Phone mic hardware/positioning during casual speech, independent of
   software.
3. ffmpeg's resample step (-ar 16000 -ac 1) could theoretically introduce
   quality loss if the source recording's actual sample rate is very
   different from 16000, though downsampling alone shouldn't cause
   noticeable garbling.
4. Possibly nothing actually wrong — Deepgram transcripts on casual,
   unscripted speech are often imperfect even with good audio; "messy"
   may be a reasonable result for a first real test, not necessarily a
   bug to chase.
Worth checking termux-microphone-record's -r/-b default values and
whether explicitly setting a higher quality changes anything, next time
this comes up as a priority — not chased further now since the user
reported it as a minor note, not a blocker.

**DECISION: Termux wins over laptop for Tier 3's voice input.** The
earlier split-environment plan (phone for text via Pydroid, laptop for
voice) is superseded — Termux successfully does BOTH mic capture and
Deepgram connectivity, phone-native, no laptop required for this piece.
Track A (laptop) was never actually run by the user ("I'll check laptop
later") — Track B resolved first and resolved completely, so it's the
path going forward. The whole project can now plausibly stay phone-only,
matching the original Tier 0 interview preference ("mobile if possible")
that was set aside earlier in favor of laptop-first specifically because
Pydroid's audio situation looked unworkable. Termux turned out to be the
answer to that concern, not laptop.
Practical implication for E.D.I.T.H.'s actual code structure: the
STT seam should be built to shell out to termux-microphone-record +
ffmpeg the way this test script did, NOT assume a desktop-style
pyaudio/sounddevice mic-capture library — that path was never proven and
the working path is meaningfully different in shape (subprocess calls to
external tools, not a Python audio library call).

## Future direction: hosted web app + JARVIS-style UI (not yet started)

Real, substantial next step, genuinely possible but NOT a small addition —
distinct from Tiers 5/6 above, likely comes after or alongside them.
Three separate layers of real work:
1. **Hosting**: Brain/ToolRegistry/tool logic is already provider-agnostic
   and portable — the actual new work is exposing it via a real server
   API (WebSocket, given Live's audio loop is already async) instead of
   a local script. Needs a real host (not the phone) and real deployment
   decisions.
2. **Frontend**: a JARVIS-style UI (waveform, live transcript, visual
   presence) is a genuinely different skill from anything built in this
   project so far — most naturally a React app talking to that
   WebSocket. Nothing here yet.
3. **Multi-user, for real this time**: the "single confirmation
   authority" gap noted throughout this file (see Multi-user note) stops
   being deferrable the moment this is a hosted web app rather than a
   personal phone tool — who can log in, whose facts are whose, who
   confirms actions all become immediate, real questions, not later ones.
Start here next time: scope which of the three layers to tackle first
(likely hosting, since UI needs something real to talk to) before
writing any code — same interview-first discipline as Tier 0.

## Concrete next steps: hosting (start here)

1. Wrap Brain in a small FastAPI + WebSocket app — reuse
   edith/setup.py's build_registry() exactly as-is, don't rewrite Brain.
2. Push to GitHub; deploy on Render's free tier (no card required; sleeps
   on inactivity, wakes on request — acceptable for now). Set the same
   env vars from .env in Render's dashboard.
3. Test with a plain WebSocket client BEFORE building any UI — isolates
   hosting bugs from frontend bugs.
Settle auth (who can connect) before step 1's code, not after.

## Hosting: Render asked for a card (known issue, not user error)

Render's own docs and most sources say no card needed, but a real,
matching report exists in Render's own community forum (a user hitting
the identical "payment information required" wall) — this is a known,
inconsistent gap between Render's stated and actual signup flow, not
something done wrong.
Checked Railway and Fly.io as alternatives: BOTH now run on
trial/usage-based credit models, not permanent free tiers, per multiple
2026 sources including one explicit "2026 Update" flagging this change.
Neither is a real fix for "always free."
PythonAnywhere is the one option confirmed free without a card across
sources — but WebSocket support there is UNVERIFIED, worth checking
before committing time. Start here next: confirm PythonAnywhere
actually supports WebSocket connections for server/main.py before
attempting to deploy there.

## Vercel: checked, real capability, wrong fit

Vercel's own current WebSocket doc (June 2026) confirms native WebSocket
support now exists for Python/FastAPI — contradicts some older
competitor blog posts saying "no WebSocket support," which were likely
describing a past state. BUT Vercel's serverless model means each
message could hit a DIFFERENT function instance (own docs: "not
guaranteed to reach the same Vercel Function instance"), which would
silently drop server/main.py's per-session Brain instance mid-
conversation — Vercel's own fix is external Redis, real added
infrastructure, not free. Wrong fit for this server's design as-is.
Sticking with PythonAnywhere as the next thing to verify (see prior
note) rather than Vercel.

## Vercel: confirmed dead end for Python WebSockets

"Connection refused" traced to Vercel's WebSocket feature being gated
behind an account-level permission ("Permissions Required: WebSockets")
that doesn't appear as a self-service toggle in project settings (user
confirmed: Fluid compute was on, no WebSockets setting found anywhere).
Fetched Vercel's own dedicated WebSocket doc directly — its metadata
shows last_updated: 2018-10-20, and EVERY code example on it (ws,
Express, Hono, Socket.IO, Nitro, Next.js) is JavaScript/TypeScript. No
Python example exists on this page at all, despite a one-line claim
elsewhere ("FastAPI also work with WebSockets") that isn't backed up
here. CONCLUSION: Vercel's WebSocket support is built/demonstrated for
Node.js, not Python — not something fixable via more config from our
side. Vercel is now also ruled out. Genuinely free, always-on Python
WebSocket hosting doesn't have a clean answer among the platforms
checked so far (Render: card-gated for some accounts; Railway/Fly.io:
trial-credit models, not permanent free; PythonAnywhere: free tier
explicitly excludes ASGI/WebSocket apps per their own docs; Vercel:
WebSockets are Node-oriented and permission-gated).
Real remaining options next time: retry Render (the card ask may be
account-specific — some users report not hitting it); or accept a small
one-time/low cost on a platform actually built for persistent Python
processes (Fly.io's now-paid tier, a cheap VPS, etc.) — see the earlier
"proceed" decision where a tiny cost was already accepted as reasonable.

## Additional confirmation: no Start Command field on Vercel

User clarified there's no Start Command field at all in Vercel's deploy
settings (only Build Command) — confirms the WebSocket dead-end
conclusion above from a second angle: Vercel doesn't run persistent
processes at all (serverless, invoke-per-request), so there's no
"keep uvicorn running" concept to expose a Start Command for. This
isn't a missing setting to find — it's structural. Two independent
signals (the WebSocket permission gate + no persistent-process model)
now confirm Vercel is not viable for this server as designed. Stop
trying to configure around it; move to Render retry or a paid VPS/PaaS
per the prior note.

## Correction: Vercel is NOT confirmed Node-only for WebSockets

Retracting the earlier "Vercel WebSockets are Node-oriented, Python
unsupported" conclusion — that was wrong, based on conflating two
different Vercel doc pages. The user correctly quoted real Vercel docs:
"Python frameworks like FastAPI also work with WebSockets on Vercel
Functions... Add a WebSocket library (websockets, wsproto, or just
uvicorn[standard])" — this IS real, current Vercel documentation
(appears to live on the Python Runtime doc page, not the general
WebSockets doc page fetched earlier, which is Node-focused but doesn't
mean Python is unsupported).
What's STILL confirmed and unresolved: the general WebSockets doc page
(vercel.com/docs/functions/websockets) shows "🔒 Permissions Required:
WebSockets" directly under the title, on every fetch. This gate is real
and account-level, not project-settings-level — user confirmed no
toggle exists in project settings despite Fluid compute being on. HOW to
actually request/unlock this permission is the genuine open question —
not whether Python is supported. Next step: look specifically for how
to request this permission (likely via Vercel support, a dashboard
banner, or account upgrade) rather than debug FastAPI compatibility
further, since that part is not actually in question.

## RESOLVED: the whole Vercel "connection refused" saga was a URL typo

After chasing WebSocket permissions, Fluid compute, and Node-vs-Python
support theories (several dead ends recorded above, one of which — "Vercel
WebSockets are Node-only" — was flat-out WRONG and later retracted), the
actual cause was simple: the WebSocket client was connecting to
`https://edith-flame.vercel.app/` (wrong protocol — https instead of wss;
wrong path — root instead of /ws) instead of the correct
`wss://edith-flame.vercel.app/ws`. CONFIRMED WORKING once the correct URL
was used.
Lesson for next time: when a connection is refused, check the exact
client URL (protocol + path) FIRST, before escalating to platform-level
theories. Several messages of legitimate-sounding research (permissions
gates, persistent-process models, Node-vs-Python docs) were spent before
this simple check happened — worth doing cheap, boring checks before
expensive research ones.
VERCEL DEPLOYMENT NOW CONFIRMED WORKING for this server, including
WebSockets, Python/FastAPI, Fluid compute — for real, on the actual
deployed edith-flame.vercel.app. The earlier session-instance-dropping
risk (per Vercel's own docs on "not guaranteed to reach the same
instance") remains a real, unresolved, untested risk for LONGER
conversations specifically — the instance_id check only confirmed
stability across quick page refreshes so far, not across an extended,
multi-message WebSocket session. Worth testing a longer back-and-forth
conversation next, watching for a Brain instance silently resetting
mid-conversation.

## Frontend: JARVIS/Homecoming HUD (built, visually validated via static preview)

frontend/src/EdithHUD.jsx — real React component, connects to the deployed
WebSocket server, styled per Spider-Man: Homecoming's E.D.I.T.H. HUD
specifically (not generic "AI dashboard"). Design plan per the
frontend-design skill's process: named palette (void #0A0A0C, steel
#3D4147, glow #00D4FF, stark-red #C4001A, paper #E8E8E8), radial/circular
layout instead of chat bubbles, signature element = a reactive glowing
core ring with tick-mark instrumentation.
VALIDATION METHOD: since this sandbox can't run a full React build, built
a static-HTML proof of the same visual logic, rendered it with
wkhtmltoimage, and ACTUALLY LOOKED at the screenshots before calling
anything done — caught and fixed two real problems this way that would
have shipped unnoticed otherwise:
  1. CSS text-shadow/box-shadow barely registered as a glow in render —
     replaced with a real SVG filter (feGaussianBlur + feMerge), confirmed
     via a focused isolated test image before rolling into the full design.
  2. Centered stacked "E.D.I.T.H." label read as a logo lockup, disconnected
     from the ring — moved to an arc-integrated textPath sitting ON the
     ring geometry, more authentic to real HUD instrumentation. This left
     the core's center empty, caught in a close-up crop, fixed by adding a
     small diagnostic readout line ("LINK STABLE"/"SESSION ...") rather
     than leaving it bare.
Ported the validated static-preview choices into the real .jsx afterward.
NOT YET DONE: an actual `npm install && npm run build` / real browser
render of EdithHUD.jsx itself — the static preview proves the VISUAL
LOGIC, not that this exact React file compiles and behaves identically
in a real build. Structural brace/paren balance checked only, not a real
JSX compile. Test this for real (locally, `npm create vite` + drop this
component in) before assuming it's deploy-ready.

## Frontend: CONFIRMED WORKING END-TO-END (real React build, real WebSocket)

Tested on playcode.io (a real React sandbox), closing the one gap flagged
at the end of the last frontend session: EdithHUD.jsx now confirmed to
actually compile in a real React environment (not just structurally
balanced braces/parens), renders correctly (matching the visually-
validated static preview), and successfully connects to the real,
deployed wss://edith-flame.vercel.app/ws server — receiving and
displaying an actual Brain response. Full chain now proven live: React
UI -> WebSocket -> Vercel-hosted FastAPI server -> Brain -> Gemini ->
reply back to the browser. This is the JARVIS-in-the-cloud goal from
several sessions ago, genuinely realized end-to-end.

## Next up: voice over the browser (not started, scoped for next session)

Frontend currently only sends/receives TEXT over the WebSocket
(EdithHUD.jsx -> server/main.py -> Brain.send(), text only). Adding real
browser voice needs, concretely:
1. Browser mic capture via the MediaRecorder API in EdithHUD.jsx,
   producing audio chunks (verify actual output format/codec first,
   same "check before assuming" discipline as ears.py's M4A discovery).
2. A new WebSocket message type carrying audio bytes (not just plain
   text) - server/main.py's websocket_endpoint needs to distinguish text
   vs. audio messages and route audio into Deepgram or Live's audio path
   instead of straight to Brain.send().
3. Audio OUT: server sends synthesized speech bytes back; browser plays
   them (Web Audio API), a genuinely different mechanism than
   termux-media-player.
Start here next: confirm MediaRecorder's actual output format in a real
browser FIRST (small, isolated test), before touching server/main.py -
same lesson as every audio format mismatch hit earlier in this project.

## Browser voice over Gemini Live (built, genuinely untested — real audio APIs involved)

Built per explicit choice: Live over Deepgram/ElevenLabs for the browser
specifically, since Live was already the most functionally complete
proven voice path and is free under the existing Gemini key (an explicit
"always free" priority) rather than adding a third/fourth provider.

SERVER: server/main.py gained a new /ws/live endpoint, alongside the
untouched /ws text endpoint. Ported directly from live_explore.py's
CONFIRMED-WORKING Live logic (same model, same tool registry, same
send_client_content/turn_complete pattern, same response={"result":...}
tool-response shape) — not re-derived, specifically to avoid
reintroducing bugs that took real debugging to resolve there. Swaps
Termux-specific I/O (mic recording via termux-microphone-record,
playback via termux-media-player) for binary WebSocket frames to/from
the browser. Protocol: client sends binary PCM chunks (16kHz) then a
text "END_TURN" signal; server replies with JSON control messages
interleaved with one binary PCM frame (24kHz) per turn.

BROWSER: EdithHUD.jsx gained a separate "Live Voice" panel (connect,
then press-to-record/stop-to-send — turn-based, not continuous).
REAL RESEARCH FINDING, applied proactively: MediaRecorder (the obvious
first choice) CANNOT produce raw PCM at all — confirmed via multiple
independent sources — only compressed formats. Same category of problem
as termux-microphone-record only producing AAC/M4A, not raw PCM,
which needed ffmpeg to bridge. The browser equivalent fix is
AudioWorklet (a low-level, separate-thread audio processing API) doing
the Float32-to-Int16 PCM conversion directly, loaded as a Blob URL
(worklets must be separate modules, confirmed via research) so the
whole component stays self-contained for single-file test environments
like PlayCode. Playback of the 24kHz reply uses the Web Audio API
(AudioBuffer + BufferSource), converting PCM back to Float32 the other
direction.

VERIFICATION STATUS — explicitly the least-proven part of this whole
project so far: no network access in the environment that built this,
so NEITHER the new /ws/live server endpoint NOR the AudioWorklet/Web
Audio browser code has been run for real, on any device, at all. This
is fundamentally different from every other "untested" note in this
file — those were built on top of proven pipelines with only integration
untested; this involves a new, unverified server endpoint AND new,
unverified low-level browser audio APIs simultaneously. Test on
PlayCode (or a real deployed build) next, and expect real bugs — same
likelihood as every other first attempt at a new audio pipeline in this
project (ears.py's M4A/PCM mismatch, the async-recording race condition,
etc.). Start by checking: does the AudioWorklet actually load and
produce audio data at all (console.log the worklet's port messages
before worrying about correctness); does the server's /ws/live endpoint
even accept a connection; does audio format matching hold up
(16kHz in, 24kHz out — this exact rate mismatch has caused real bugs
before in this project, watch for it here too).
