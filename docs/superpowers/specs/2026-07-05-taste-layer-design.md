# Taste Layer — Design Scope

**Date:** 2026-07-05
**Status:** Design scope (no implementation yet)
**Context:** The strategic moat. The MCP wrapper is a commodity; *curation quality* is not.

## The problem

When a user says *"make me a rainy-Sunday playlist,"* today's flow is: the LLM reads track **names and artists** from `music_search` and picks by reasoning over text. It has no idea what the songs *sound like* — tempo, energy, mood, key. So the result is thematically plausible but **sonically random**: a 180-BPM banger can land next to an ambient drone because both "feel rainy" by title. Good human playlists have *flow* — an energy arc, compatible keys, coherent mood, no jarring jumps.

## The insight

Split the labor by what each side is good at:

- **The LLM does semantics.** It's excellent at turning a vague brief into structured intent: *"rainy Sunday"* → low energy, acoustic, minor-leaning, 70–95 BPM, few vocals, ~45 min.
- **An engine does grounding + math.** It filters the library by those acoustic constraints, weights by the user's own taste, and **sequences** the result for flow.

Neither alone is enough. Pure-LLM is sonically blind. Pure-algorithm has no idea what "rainy Sunday" means. **The combination is the product** — and it's currently unbuilt for Apple Music.

## Signal — what's actually available

**Tier 0 — free, local, available in the current AppleScript world (no new API).**
Verified live on the target machine (2026-07-05):
- **Reliable behavioural signal:** `played count`, `skipped count`, `rating`, `favorited`, `year`, `date added`, `played date`, `duration`, `genre` — all present and populated. This is a strong foundation for a **taste profile**.
- **BPM is present but usually empty:** the `bpm` property exists but returns `0` for streamed catalog tracks (Apple doesn't populate it). So BPM is *not* a dependable Tier-0 sequencing signal — treat it as enrichment.
- **`loved` is gone** — use `favorited` (already what the server reads).

Net: Tier 0 is strong for *who you are* (behaviour) but weak for *what a track sounds like* (acoustics). So a v1 taste profile is fully buildable now; v1 sequencing leans on genre + behaviour + recency, and true sonic flow waits for Tier 1.

**Tier 1 — enrichment (external audio features):**
Apple's own API is metadata-light — it does **not** expose Spotify-style audio features (energy, valence, danceability, key, mode). To sequence on real sonic qualities we enrich each track from an external source (Spotify's `audio-features`, matched by ISRC or title/artist), cached locally so it's computed once. This is the classic move and it's where sequencing gets genuinely good.

## Architecture

Five components, each independently testable, exposed to Claude as a small set of new tools.

1. **Taste profile builder** — derive the user's profile from library signal: top genres / artists / decades weighted by `played count` × `rating`, an affinity score per artist and genre, and typical BPM bands. Cached. Unlocks *"play something I'd actually like."*

2. **Feature store** — a local SQLite cache keyed by persistent ID → `{bpm, genre, energy, valence, key, mode, tags}`. Populated from Music.app (bpm/genre, Tier 0) and, when enabled, external enrichment (Tier 1). Compute-once, read-many. Fully local; the only thing that ever leaves the machine is a track identifier sent to the features provider, and only when the user opts in.

3. **Candidate selector** — given structured intent from the LLM (mood, energy window, genre set, exclusions, target minutes), narrow the library to a candidate pool: filter by feature windows, honour constraints (no explicit, instrumental only), weight by user affinity, drop recently-played.

4. **Sequencer** — the DJ secret sauce. Order the pool for flow: an energy arc (ramp-up or wind-down), harmonic compatibility via Camelot-wheel key adjacency, smooth BPM transitions, no same-artist clustering, fit to target duration. A small local optimisation over the candidate set — no ML required for a strong v1.

5. **Tool surface** — keep the model in the loop:
   - `music_taste_profile()` → the user's profile (top genres/artists/decades, affinities).
   - `music_recommend(brief, minutes, constraints)` → a **sequenced** track list (persistent IDs + why-picked), which the model then turns into a playlist via the existing `music_create_playlist`.
   - `music_similar(track_id, limit)` → neighbours in feature space.

## Phasing

- **v1 — Tier 0, no new API.** Taste profile from library behaviour + BPM/genre; `recommend` + `sequence` on BPM, genre, affinity, recency. Ships in today's AppleScript server. Proves the concept and is immediately useful.
- **v2 — Tier 1 enrichment.** Add the external audio-feature cache (energy/valence/key). Real harmonic + energy sequencing. Needs a features provider account (e.g. Spotify client credentials).
- **v3 — feedback loop.** Learn from which recommended tracks the user keeps vs. skips; feed that back into affinity. This is the part that compounds with use — the actual defensibility.

## Open questions / risks (resolve before building)

- **ISRC access — resolved: NOT available.** Verified live: Music.app's AppleScript dictionary does not expose `isrc`. So Tier-1 enrichment must match on fuzzy `title + artist + album`, which is noisy (live versions, remasters, features). Mitigations: match on the (title, primary artist, duration±3s) triple, keep a manual override cache, and store a confidence score so low-confidence matches can be excluded from sequencing. If ISRC ever matters enough, Phase 2's Apple Music API *does* return ISRC for catalog tracks — enrich via the API by persistent-ID → catalog-ID → ISRC → provider, sidestepping AppleScript entirely.
- **External provider dependency.** Spotify's features API needs its own auth and has rate limits and (evolving) access terms. It adds an account + a network surface (revisit the A10/SSRF posture — allow-list the provider host only). Keep Tier 1 optional so v1 never depends on it.
- **Cold start.** Sparse library or few plays → fall back to genre/editorial seeds rather than behaviour.
- **Cost/latency.** Enrichment is O(library size) on first run — batch, cache hard, and enrich lazily (only tracks that enter a candidate pool).
- **Privacy.** Profile + feature cache stay on device; enrichment is opt-in and sends only identifiers. State this explicitly in the README when built.

## Why this is the moat

Anyone can wrap the Apple API. What's hard is making the output *good*, and better the more you use it. Components 1, 2 and 5 (v3) accumulate a private, per-user taste model that a fork can't copy. That's the difference between "organises my library" and "is my AI DJ."
