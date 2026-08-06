# Nanopub Skill — Operational Addendum

**Author:** Erik Schultes
**Date:** 2026-06-01
**Context:** Observations from the MAC FDT v2 cleanup pass, Stage 3 catalogue re-mint with `/`-form addressing convention.
Companion to the prior PR #1 nanopub-skill addition (https://github.com/knowledgepixels/nanopub-skill/pull/1) — publisher-facing vs admin-derived retraction distinction.

These four operational findings emerged during the cleanup pass from PROMPTs 1.5 through 3 (May 31 – June 1, 2026). They are offered as input to the nanopub-skill maintenance work, not yet vetted against the broader ecosystem.

---

## Section 1 — `npx:retracts` subject convention

**Observation.** nanopub-java's `retract` subcommand emits

```turtle
<publisher-ORCID> npx:retracts <target-Trusty> .
```

where the **subject is the publisher's ORCID**, not the retracting nanopub itself. Manually constructed retraction nanopubs using

```turtle
this: npx:retracts <target-Trusty> .
```

(subject = retraction nanopub) were **registry-rejected** during the upstream cleanup pass (PROMPT 1.5 / PROMPT 2.0). All three registries returned:

```
HTTP 400 — Error processing nanopub: Nanopublication not supported
```

The auto-retract form succeeded immediately. The convention check is registry-side, not signature-side: the nanopub validates cryptographically but is refused on policy grounds.

This empirically confirms PR #1's publisher-facing convention as the operational truth.

**Suggested skill addition.** An explicit example of the correct subject form for hand-authored retraction TriGs:

```turtle
# Correct (registry-accepted)
sub:assertion {
  <https://orcid.org/your-orcid> npx:retracts <https://w3id.org/np/RA...target> .
}
```

```turtle
# Incorrect (registry-rejected as "Nanopublication not supported")
sub:assertion {
  this: npx:retracts <https://w3id.org/np/RA...target> .
}
```

*Origin: PROMPTs 1.5 / 2.0 — upstream `#`-form defective Project + 2 Dataset retraction work.*

---

## Section 2 — Content-negotiation for registry GET

**Observation.** The nanopub registry (`registry.petapico.org`, `registry.knowledgepixels.com`, and `w3id.org/np/<Trusty>`) returns an HTML viewer page by default — a browser-oriented wrapper around the nanopub display. Raw TriG content requires an explicit `Accept` header.

During Pass-1 verification, the first GET on the freshly-published Alpha-RBD-Variant Trusty URI was misclassified as a failure because the verifier read the HTML wrapper's `<title>Nanopublication RA... - Nanopub Registry</title>` rather than the TriG body. Switching to:

```bash
curl -s -H "Accept: application/trig" -L "https://w3id.org/np/<Trusty>"
```

returns the raw TriG, beginning with `@prefix this: <https://w3id.org/np/<Trusty>>`.

This matters for any verification script that wants to check substantive content (not just HTTP 200): the registry returns 200 with an HTML 404 page for non-existent nanopubs, so HTTP status alone is not a liveness indicator.

**Suggested skill addition.** A one-line note in the registry-GET example specifying `Accept: application/trig` for content-level verification.

*Origin: PROMPT 3 PHASE 2 — Pass-1 publish-verify loop, Alpha-RBD-Variant first verification.*

---

## Section 3 — SPARQL `DISTINCT` on `/repo/full`

**Observation.** The `/repo/full` SPARQL endpoint (at `query.knowledgepixels.com`) indexes the same triple across multiple graph views — empirically observed: 3× per triple, consistent with per-server cache views being indexed alongside the canonical assertion graph.

PROMPT 3 Q1 (`npx:supersedes` verification across 38 v2 mints) returned a raw `COUNT(*)` of **114** = 38 × 3. The `SELECT DISTINCT ?new ?old` formulation correctly yielded **38**. Without `DISTINCT`, count-based verification queries will systematically over-report by an integer multiplier.

This is not a bug — the multi-graph indexing is a feature for queries that join across cache and admin views — but it is a footgun for verification scripts that expect unique-triple counts.

**Suggested skill addition.** `DISTINCT` is **recommended** (not optional) for any count-based verification query against `/repo/full`. Example:

```sparql
# Correct: yields the actual number of distinct supersession pairs
SELECT (COUNT(*) AS ?n) WHERE {
  SELECT DISTINCT ?new ?old WHERE {
    GRAPH ?g { ?new npx:supersedes ?old }
  }
}

# Misleading: returns a multiple of the actual count
SELECT (COUNT(*) AS ?n) WHERE {
  GRAPH ?g { ?new npx:supersedes ?old }
}
```

*Origin: PROMPT 3 PHASE 4 — Q1 supersession verification on `/repo/full`.*

---

## Section 4 — Publish-to-GET propagation lag

**Observation.** Immediate HTTP GET on a freshly published Trusty URI returned **404 in 2 of 8** Pass-1 publishes during PROMPT 3 PHASE 2. The publish-side registry (`registry.petapico.org`) confirmed the nanopub was published; the read-side resolution (via `w3id.org/np/<Trusty>` redirecting to one of the registry mirrors) hadn't yet propagated.

A 10-second wait + retry resolved both first-attempt failures. Pass-2 (30 instances) used a pre-emptive 5-second wait between publish and GET, with optional 10-second retry on 404; all 30 verified on first or second try. No third-retry was needed across the 38-instance batch.

**Suggested skill addition.** Recommended publish-verify pattern:

```bash
java -jar nanopub-1.88.0-jar-with-dependencies.jar publish <signed.trig>
sleep 5
curl -sI -H "Accept: application/trig" \
  -o /dev/null -w "%{http_code}\n" \
  "https://w3id.org/np/<expected-Trusty>"
# If 404, sleep 10 and retry once. Both retries succeeded across the
# 38-instance PROMPT 3 batch.
```

The receiving registry is `registry.petapico.org`. Read-side resolution may reach any of the registered mirrors; propagation between them takes seconds, not minutes, but is non-zero.

*Origin: PROMPT 3 PHASE 2 — Pass-1 Epsilon-RBD-Variant first verification (404 on immediate GET, resolved on retry); pattern formalized for Pass-2.*

---

## Section 5 — Future-dated `dct:created` is registry-rejected as "Nanopublication not supported"

**Observation.** When hand-authoring a TriG with a hand-chosen `dct:created` timestamp that turns out to be in the future relative to the registry's wall clock at the moment of publish, all three registries reject with:

```
HTTP 400 — Error processing nanopub: Nanopublication not supported
```

The error message is misleading: it suggests structural unsupportedness (the same wording that surfaces for other policy violations, e.g., the `npx:retracts` subject-form rejection in Section 1), but the actual gate is purely temporal.

Empirical reproduction from KP Office Hours 2026-06-03:

- **Reject 1** (`RAuBX8xpaOsxfO8WvzFo0xpkTwFjLkmnAsYE1IRpNTOjE`): correct `gen:StatusUpdate` template, `dct:created "2026-06-03T12:30:00Z"` — about 25 minutes in the future at sign time. Rejected by all three registries.
- **Reject 2** (`RAgdgiB6u3qSqiWF_3_GY0sEA0ToW3I1xzxN_lcBcONPY`): structurally narrowed to match a known-working reference nanopub, `dct:created "2026-06-03T12:45:00Z"` — still ~10 minutes future. Rejected.
- **Success** (`RAE9JU48QNC6cejadZoXte7JX1C2eEiYFjUv6to3w2Hec`): identical structure to Reject 2, `dct:created` set by `date -u` immediately before `nanopub-java sign` → `2026-06-03T12:56:33Z`, NOT future-dated. Published cleanly on first publish attempt; appeared in the Status Updates view within 60 seconds (matching the indexing-lag estimate in Section 4).

The same RSA-1024 signing key signed all three attempts. `nanopub-java check` reported `1 trusty with signature` for all three (signature validates locally regardless of timestamp). So the gate is registry-side and timestamp-only.

This is **not** what Erik initially hypothesized when the rejections first surfaced — RSA key length and NanoDash-pipeline-required signing were ruled out by the eventual success on the third attempt with the same key and the same signing pipeline. Surfacing it here for two reasons: (i) the misleading error message wasted significant diagnostic effort that a clearer message (e.g., "future-dated dct:created not allowed") would have saved; (ii) the failure mode is easy to trip on accidentally when scripted timestamps are baked into a TriG template at code-write time rather than injected at sign time.

**Suggested skill additions.**

1. **Registry error message clarity.** The `400 Nanopublication not supported` error masks a class of distinct registry-side policy rejections (Section 1's `npx:retracts` subject-form gate is another). Where the gate is identifiable, the message should reflect it — e.g., `400 Nanopublication rejected: dct:created in the future` for this case.

2. **Skill guidance on timestamp injection.** Recommend `date -u` at sign time rather than hand-written timestamps. For pipelines that produce unsigned TriG from templates, the `dct:created` field should be a placeholder filled at sign time, not at template-write time. Example pattern:

```bash
# In the unsigned TriG, leave a placeholder:
#   this: dct:created "TIMESTAMP_PLACEHOLDER"^^xsd:dateTime ;
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
sed -i "s/TIMESTAMP_PLACEHOLDER/$NOW/" unsigned.trig
java -jar nanopub-1.88.0-jar-with-dependencies.jar sign unsigned.trig
java -jar nanopub-1.88.0-jar-with-dependencies.jar publish signed.unsigned.trig
```

3. **Skill guidance on small clock skew.** Even a non-malicious local clock that is a few minutes fast relative to NTP can produce this rejection silently. A `date -u` command run on a machine with a synced clock is the safe default.

*Origin: PROMPT 6 post-mortem — KP Office Hours 2026-06-03 status update three-attempt sequence. Tobias diagnosed the root cause live at the office hours; v4 mint succeeded with `date -u`-injected timestamp on the next attempt.*

---

## Closing

These observations are offered as input to the nanopub-skill maintenance work; they are not yet vetted against the broader ecosystem (other registry mirrors, other client implementations, other jar versions). Operationally validated against:

- `nanopub-java 1.88.0` (signing, retract, publish, check subcommands)
- `registry.petapico.org` (publish-side)
- `registry.knowledgepixels.com` (resolution-side, also SPARQL endpoint)
- `w3id.org/np/<Trusty>` (canonical resolution alias)
- JDK 21 (the jar requires class file version 65)
- Registry timestamp policy for `dct:created` (Section 5; observed during KP Office Hours 2026-06-03)

Contact: Erik Schultes <https://orcid.org/0000-0001-8888-635X>
