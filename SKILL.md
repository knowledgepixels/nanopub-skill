---
name: nanopub
description: Create, sign, publish, query, or retract nanopublications
argument-hint: [nanopub URL, description, or action]
---

Help the user work with nanopublications. This includes creating new nanopubs, fetching and inspecting existing ones, superseding or retracting nanopubs, and publishing to the test server or live network.

## Creating an Agent/Bot Identity

To publish nanopubs on behalf of a software agent (bot), you need to create a dedicated identity with its own key pair and introduction nanopub.

### Generate an RSA key pair

```bash
openssl genrsa -out ~/.nanopub/<agent>_id_rsa 2048
openssl rsa -in ~/.nanopub/<agent>_id_rsa -pubout -outform PEM -out ~/.nanopub/<agent>_id_rsa.pub
```

Extract the public key as a single-line base64 string (needed for the introduction nanopub):

```bash
grep -v '^\-' ~/.nanopub/<agent>_id_rsa.pub | tr -d '\n'
```

**Never delete or alter key files in `~/.nanopub/`** — they are required to sign and retract nanopubs published with that identity. Losing a key means losing the ability to manage those nanopubs.

### Create an introduction nanopub

The introduction nanopub declares the agent's identity, links it to an owner (via ORCID), and registers its public key. The agent's IRI is typically a sub-IRI of this nanopub itself (e.g. `sub:agent-name`), which gets resolved to a full trusty URI after signing.

```turtle
@prefix this: <http://purl.org/nanopub/temp/np001/> .
@prefix sub: <http://purl.org/nanopub/temp/np001/> .
@prefix np: <http://www.nanopub.org/nschema#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix npx: <http://purl.org/nanopub/x/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix orcid: <https://orcid.org/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .

sub:Head {
  this: a np:Nanopublication ;
    np:hasAssertion sub:assertion ;
    np:hasProvenance sub:provenance ;
    np:hasPublicationInfo sub:pubinfo .
}

sub:assertion {
  sub:agent-name a npx:Bot, npx:SoftwareAgent ;
    foaf:name "Agent Display Name" ;
    <http://purl.org/vocab/frbr/core#owner> orcid:OWNER-ORCID .

  sub:decl npx:declaredBy sub:agent-name ;
    npx:hasAlgorithm "RSA" ;
    npx:hasPublicKey "PUBLIC-KEY-BASE64" .
}

sub:provenance {
  sub:assertion prov:wasAttributedTo orcid:OWNER-ORCID .
}

sub:pubinfo {
  this: dct:created "TIMESTAMP"^^xsd:dateTime ;
    rdfs:label "Agent Display Name" ;
    dct:creator sub:agent-name ;
    dct:license <https://creativecommons.org/licenses/by/4.0/> ;
    npx:hasNanopubType npx:declaredBy ;
    npx:introduces sub:agent-name .

  orcid:OWNER-ORCID foaf:name "Owner Name" .
}
```

### Sign and publish the introduction

Sign the introduction with the **agent's own key** (not the owner's key):

```bash
java -jar "$JAR" sign -k ~/.nanopub/<agent>_id_rsa -o tmp/<agent>-intro-signed.trig tmp/<agent>-intro.trig
java -jar "$JAR" publish tmp/<agent>-intro-signed.trig
```

After publishing, note the trusty URI — the agent's IRI becomes `<trusty-uri>/<agent-name>` (e.g. `https://w3id.org/np/RAxxxxx/agent-name`). Use this IRI as `dct:creator` and for `-s` when signing/retracting nanopubs with this agent.

### Using the agent identity

When creating nanopubs as this agent, sign with `-k` and use the agent IRI as creator:

```bash
java -jar "$JAR" sign -k ~/.nanopub/<agent>_id_rsa -o tmp/<name>-signed.trig tmp/<name>.trig
```

When retracting, specify the agent as signer:

```bash
java -jar "$JAR" retract -i <nanopub-uri> -k ~/.nanopub/<agent>_id_rsa -s <agent-IRI> -p
```

## Nanopublication Structure

Every nanopub (`.trig` file) contains four named graphs:

1. **Head** — links to the other three graphs
2. **Assertion** — the semantic claims (domain-specific RDF triples)
3. **Provenance** — attribution and source references (e.g. `prov:wasAttributedTo`, `prov:wasDerivedFrom`)
4. **PublicationInfo** — metadata (creator, timestamp, license), and RSA signature (in signed versions)

## Workflow

### 1. Determine the action

The user may want to:
- **Create** a new nanopub from RDF content, a claim, a shape, or other structured content
- **Fetch/inspect** an existing nanopub by URL or trusty ID
- **Query** nanopubs via Nanopub Query (the grlc-based SPARQL query API)
- **Supersede** an existing nanopub with updated content
- **Retract** a published nanopub

If the argument is `$ARGUMENTS`, use that as the starting point.

#### Fetching an existing nanopub

Fetch via HTTP GET with `Accept: application/trig`:

```bash
curl -s -L -H "Accept: application/trig" "<nanopub-url>"
```

Display the nanopub URI, full TriG content, and a summary of the named graphs.

#### Querying nanopubs via Nanopub Query

Nanopub Query is a grlc-based API that exposes published SPARQL query templates as REST endpoints. The base instance is at `https://query.knowledgepixels.com/`.

**Discovering available queries:**

To list all available queries at the current point in time, use the `get-queries` meta-query:

```bash
curl -s "https://query.knowledgepixels.com/api/RAQqjXQYlxYQeI4Y3UQy9OrD5Jx1E3PJ8KwKKQlWbiYSw/get-queries"
```

This returns all published query templates and can be used as a starting point to find queries relevant to a given task.

**Downloading all query templates locally:**

Run the [download script](scripts/download-queries.sh) to fetch all query template nanopublications as individual TriG files into the [queries/](queries/) folder:

```bash
bash scripts/download-queries.sh
```

This is useful for browsing, searching, or analyzing the full set of available queries offline. Files are named `<trusty-id>_<label>.trig`. Re-running the script skips already-downloaded files.

**Downloading all assertion templates locally:**

Similarly, run the [assertion template download script](scripts/download-assertion-templates.sh) to fetch all assertion template nanopublications into the [assertion-templates/](assertion-templates/) folder:

```bash
bash scripts/download-assertion-templates.sh
```

Assertion templates define the structure for creating nanopubs of a specific type (e.g. expressing a claim, defining a class, declaring event participation). They can be listed via the API:

```bash
curl -s "https://query.knowledgepixels.com/api/RA6bgrU3Ezfg5VAiLru0BFYHaSj6vZU6jJTscxNl8Wqvc/get-assertion-templates"
```

**Downloading all resource views locally:**

Run the [resource view download script](scripts/download-resource-views.sh) to fetch all resource view nanopublications into the [resource-views/](resource-views/) folder:

```bash
bash scripts/download-resource-views.sh
```

Resource views define how data is displayed on resource pages (user/space/maintained resource pages). They specify a query, view type (tabular, list, nanopub set, etc.), and optional action templates. When creating a new resource view, prefix its `dct:title` with a thematically matching emoji (e.g. "📢 My posts", "📚 My Papers", "🎤 Presentations"). Every resource view **must** include `gen:appliesToInstancesOf` with one or more of `gen:IndividualAgent`, `gen:Space`, or `gen:MaintainedResource` to specify which types of resource pages the view should appear on. If no specific type applies, use `gen:MaintainedResource` (and possibly `gen:Space`). They can be listed via the API:

```bash
curl -s "https://query.knowledgepixels.com/api/RAcyg9La3L2Xuig-jEXicmdmEgUGYfHda6Au1Pfq64hR0/get-all-resource-views"
```

To browse the OpenAPI spec for a specific published query:

```
https://query.knowledgepixels.com/openapi/?url=spec/<ARTIFACT-CODE>/<query-local-name>
```

Where `<ARTIFACT-CODE>` is the trusty ID (e.g. `RAxxx...`) and `<query-local-name>` is the query's local name from the assertion.

**grlc query template syntax:**

Nanopub SPARQL templates use an extended version of the grlc syntax for placeholders:

- **Required placeholders** start with a single underscore: `?_name` (literal) or `?_resource_iri` (IRI, suffix `_iri`)
- **Optional placeholders** start with two underscores: `?__filter_iri` or `?__filtertext` — these don't need to be filled before running the query
- **Multi-value placeholders** have the suffix `_multi` (literal) or `_multi_iri` (IRI), e.g. `?_resource_multi_iri`. These accept 1 or more values and require a `values ?_resource_multi_iri {}` statement in the SPARQL to indicate where values are filled in
- **Optional multi-value placeholders** combine both: `?__resource_multi_iri` accepts 0 or more values

**API parameter naming:** The SPARQL variable name is stripped of its prefix and suffix to form the API parameter name. For example, `?_user_iri` becomes just `user` in the API, not `_user_iri`.

**Date/time parameters:** Literal placeholders (e.g. `?_startDate`) are substituted as untyped string literals by grlc. When comparing against `xsd:dateTime` values (e.g. `dct:created`), always cast using `xsd:dateTime(?_startDate)` in the filter — otherwise the typed/untyped mismatch silently produces no results. The parameter value passed by the user must also be a full ISO 8601 datetime string (e.g. `2026-03-01T00:00:00Z`); bare date strings like `2026-03-01` will cause the cast to fail.

**Result column labels:** When a result column holds a URI, the UI renders it nicely if there is a companion `?<name>_label` variable. For example, a `?view` column with a `?view_label` variable will display the label text linked to the URI. For nanopub URI columns, use `("^" as ?np_label)` to show a short clickable symbol instead of the full URI. Always place `?np` and `?np_label` as the last two columns in the SELECT clause, in that order (`?np` before `?np_label`).

**Multi-value result columns:** Result columns (not placeholders) can use the `_multi`, `_multi_iri`, and `_multi_val` suffixes to hold concatenated values produced by `group_concat`:

- **`_multi_iri`** — all values are URIs, separated by any whitespace (spaces, newlines, or tabs). Example: `(group_concat(str(?item); separator=" ") as ?items_multi_iri)`
- **`_multi`** — all values are literals, separated by newlines, with escaping. Example: `(group_concat(replace(replace(?text, "\\\\", "\\\\\\\\"), "[\r\n]+", "\\\\n"); separator="\n") as ?texts_multi)`
- **`_multi_val`** — values can be a mix of URIs and literals, separated by newlines, with escaping. Each value is checked individually: URIs (matching `https?://`) are rendered as links, literals are rendered as text or sanitized HTML. Example: `(group_concat(replace(replace(str(?val), "\\\\", "\\\\\\\\"), "[\r\n]+", "\\\\n"); separator="\n") as ?values_multi_val)`

The escaping pattern `replace(replace(?val, "\\\\", "\\\\\\\\"), "[\r\n]+", "\\\\n")` should always be applied when concatenating literals with a newline separator: first escape existing backslashes (`\` → `\\`), then replace any sequence of CR/LF characters with the two-character escape `\n`.

The `_label` naming convention also applies to multi-value columns. For a `?things_multi_iri` column holding concatenated URIs, use `?things_label_multi` as its label companion holding the corresponding concatenated literal labels. For example: `?authors_multi_iri` (whitespace-separated ORCIDs) paired with `?authors_label_multi` (newline-separated names with escaping).

**Calling a query via the API:**

```bash
curl -s "https://query.knowledgepixels.com/api/<ARTIFACT-CODE>/<query-local-name>?<param1>=<value1>&<param2>=<value2>"
```

- The response is typically CSV or JSON depending on the `Accept` header
- Add `Accept: text/csv` for CSV or `Accept: application/json` for JSON results

**Testing an unpublished query template:**

Before publishing a query template nanopub, you can test it by base64url-encoding the signed TriG and passing it as the `_nanopub_trig` parameter:

```bash
# Base64url-encode the signed nanopub
NP_B64=$(base64 -w0 tmp/<name>-signed.trig | tr '+/' '-_' | tr -d '=')

# Extract the artifact code from the signed file
ARTIFACT=$(head -1 tmp/<name>-signed.trig | grep -oP 'RA[A-Za-z0-9_-]{43}')

# Call the API with the encoded nanopub
curl -s "https://query.knowledgepixels.com/api/${ARTIFACT}/<query-local-name>?<param>=<value>&_nanopub_trig=${NP_B64}"
```

Or open the OpenAPI UI for interactive testing in the user's browser:

```bash
NP_B64=$(base64 -w0 tmp/<name>-signed.trig | tr '+/' '-_' | tr -d '=')
ARTIFACT=$(head -1 tmp/<name>-signed.trig | grep -oP 'RA[A-Za-z0-9_-]{43}')
xdg-open "https://query.knowledgepixels.com/openapi/?url=spec/${ARTIFACT}/<query-local-name>&_nanopub_trig=${NP_B64}"
```

**Previewing any signed nanopub in Nanodash:**

You can preview any signed (but unpublished) nanopub in Nanodash by base64url-encoding the signed TriG and passing it as the `_nanopub_trig` parameter:

```bash
NP_B64=$(base64 -w0 tmp/<name>-signed.trig | tr '+/' '-_' | tr -d '=')
xdg-open "https://nanodash.knowledgepixels.com/view?_nanopub_trig=${NP_B64}"
```

**Constructing a Nanodash publish URL with pre-filled values:**

You can construct a URL that opens a Nanodash publish form with a specific template and pre-filled placeholder values. This is useful for migrating nanopubs to a new template, or for sharing a ready-to-publish link with someone.

The URL format is:

```
https://nanodash.knowledgepixels.com/publish?template=<TEMPLATE-URI>&param_<placeholder1>=<value1>&param_<placeholder2>=<value2>&...
```

- `template` — the assertion template URI to use
- `param_<name>` — fills the template placeholder named `sub:<name>`. For example, `param_headline=Hello` fills the `sub:headline` placeholder
- Values should be URL-encoded (use `urllib.parse.urlencode` in Python or equivalent)
- For IRI placeholders (e.g. `sub:space` being a `GuidedChoicePlaceholder`), pass the full URI as the value
- Optional placeholders (like `sub:datePublished` or `sub:externalUrl`) can simply be omitted if empty
- The base URL can be any Nanodash instance (e.g. `https://nanodash.petapico.org/publish`, `http://localhost:37373/publish`)

Example — pre-filling a news article template:

```
https://nanodash.knowledgepixels.com/publish?template=https%3A%2F%2Fw3id.org%2Fnp%2FRAxxxxx&param_headline=My+News+Title&param_body=Article+body+text&param_datePublished=2026-01-15&param_space=https%3A%2F%2Fw3id.org%2Fspaces%2Fmy-space
```

### 2. Check the user's profile

Before creating the TriG file, read `~/.nanopub/profile.yaml` to get the user's ORCID:

```bash
cat ~/.nanopub/profile.yaml
```

If `orcid_id` is missing or empty, warn the user: without it, the `sign` command will omit `npx:signedBy` from the signature, which makes the nanopub unlinked from a person. Ask the user to add their ORCID to the profile before proceeding.

### 3. Create the TriG file

Write the nanopub directly as a TriG file in `tmp/`. Use a placeholder base URI with a trailing slash — the `sign` command will replace it with the trusty URI everywhere.

Get the current UTC timestamp by running:

```bash
date -u +"%Y-%m-%dT%H:%M:%SZ"
```

Template:

```turtle
@prefix this: <http://purl.org/nanopub/temp/np001/> .
@prefix sub: <http://purl.org/nanopub/temp/np001/> .
@prefix np: <http://www.nanopub.org/nschema#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix npx: <http://purl.org/nanopub/x/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix orcid: <https://orcid.org/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
# ... add any domain-specific prefixes needed for the assertion ...

sub:Head {
  this: a np:Nanopublication ;
    np:hasAssertion sub:assertion ;
    np:hasProvenance sub:provenance ;
    np:hasPublicationInfo sub:pubinfo .
}

sub:assertion {
  # ... assertion triples ...
}

sub:provenance {
  # Use one or both depending on the origin of the assertion content:
  # If content was derived/extracted from an external source:
  # sub:assertion prov:wasDerivedFrom <source-url> .
  # If the user authored the content:
  # sub:assertion prov:wasAttributedTo orcid:USER-ORCID .
  # If both (e.g. user modified content from an external source), include both triples.
}

sub:pubinfo {
  this: dct:created "TIMESTAMP"^^xsd:dateTime ;  # ← replace with current UTC time
    rdfs:label "short human-readable label" ;  # can be omitted if an introduced resource already has an rdfs:label in the assertion
    dct:creator orcid:USER-ORCID ;
    dct:license <https://creativecommons.org/licenses/by/4.0/> .
    # only if the nanopub supersedes an earlier one (requires same signing key as the original):
    # npx:supersedes <original-nanopub-uri> .
    # only if the nanopub introduces a new concept/resource as its main element:
    # npx:introduces <main-element-IRI> .
    # only if created at a specific tool instance (e.g. nanodash):
    # npx:wasCreatedAt <https://nanodash.knowledgepixels.com/> .
    # Always add template links (do NOT skip these):
    # nt:wasCreatedFromTemplate <assertion-template-uri> .
    # nt:wasCreatedFromProvenanceTemplate <provenance-template-uri> .
    # nt:wasCreatedFromPubinfoTemplate <pubinfo-template-uri1>, <pubinfo-template-uri2> .
}
```

### 4. Validate and sign

First, ensure the nanopub CLI jar is available. If not already present, download the latest release from Maven Central:

```bash
NP_VERSION=$(curl -s "https://repo1.maven.org/maven2/org/nanopub/nanopub/maven-metadata.xml" | grep -o '<release>[^<]*</release>' | sed 's/<[^>]*>//g')
JAR="nanopub-${NP_VERSION}-jar-with-dependencies.jar"
if [ ! -f "$JAR" ]; then
  curl -L -o "$JAR" "https://repo1.maven.org/maven2/org/nanopub/nanopub/${NP_VERSION}/${JAR}"
fi
```

**Validate** the TriG file before signing to catch structural errors early:

```bash
java -jar "$JAR" check tmp/<name>.trig
```

**Sign** with the default user key (from `~/.nanopub/profile.yaml`):

```bash
java -jar "$JAR" sign -o tmp/<name>-signed.trig tmp/<name>.trig
```

To sign with a **specific key** (e.g. for a bot identity):

```bash
java -jar "$JAR" sign -k ~/.nanopub/<bot>_id_rsa -o tmp/<name>-signed.trig tmp/<name>.trig
```

**After signing, always verify** that `npx:signedBy` is present before publishing:

```bash
grep "signedBy" tmp/<name>-signed.trig
```

If `npx:signedBy` is absent, the user's ORCID was not found in the profile. Stop, ask the user to add it to `~/.nanopub/profile.yaml`, and re-sign.

### 5. Test query template nanopubs before publishing

If the nanopub contains a grlc query template (i.e. has a `grlc:sparql` predicate in its assertion), **always test it before publishing** using the unpublished query testing method described in the "Querying nanopubs via Nanopub Query" section above. Verify the results look correct before proceeding to publish.

### 6. Publish an example nanopub for new types

When creating a new assertion template that introduces a new nanopub type (e.g. `wd:Q604733` for presentations), the nanopub registries only set up a type-specific triple store once the first nanopub of that type is published (see the list at https://query.knowledgepixels.com/types). Until then, queries targeting that type will not work (the `full` repo could be used but doesn't scale).

To bootstrap a new type, publish an **example nanopub** that follows the template:

- Create a nanopub with realistic sample data following the template's structure
- Mark it with `npx:hasNanopubType npx:ExampleNanopub` in pubinfo so it is excluded from real result listings
- Prefix the `rdfs:label` with "Example: " and mention it's an example in the description
- Include `nt:wasCreatedFromTemplate`, `nt:wasCreatedFromProvenanceTemplate`, and `nt:wasCreatedFromPubinfoTemplate` references in pubinfo to link it back to the templates it was created from

This ensures the type-specific triple store is created and queries for that type start working immediately.

### 7. Wait for explicit publishing instruction

Do **not** publish automatically. After signing and testing, **stop and present the results to the user**. Wait for the user to explicitly ask you to publish. Do not interpret positive feedback about test results as a publishing instruction. When the user explicitly asks to publish, ask: **test server or live network?**

```bash
# Test server
java -jar $JAR publish -u https://test.registry.knowledgepixels.com/ tmp/<name>-signed.trig

# Live network
java -jar $JAR publish tmp/<name>-signed.trig
```

### 8. Retract a nanopub (if a bad version was published)

```bash
# Retract using the default user key:
java -jar $JAR retract -i <nanopub-uri> -p

# Retract using a specific key (e.g. for bot nanopubs) — requires -s <signer-IRI>:
java -jar $JAR retract -i <nanopub-uri> -k ~/.nanopub/<bot>_id_rsa -s <signer-IRI> -p
```

The `-p` flag publishes the retraction immediately. When using a specific key (`-k`), you must also specify the signer IRI (`-s`), which can be an ORCID or a bot IRI.

### 9. Create a nanopub index

A nanopub index groups multiple nanopubs under a single entry point:

```bash
java -jar $JAR mkindex -o index.trig -t "Index title" file1.trig file2.trig ...
```

To supersede an existing index:

```bash
java -jar $JAR mkindex -x <old-index-uri> -o new-index.trig -t "Index title" file1.trig file2.trig ...
```

The `-x` flag automatically adds the `npx:supersedes` link. After creating, sign and publish as usual.

### 10. Report result

Show:
- The new nanopub trusty URI
- If supersedes: confirm the `npx:supersedes` link
- If introduces: note the introduced resource

## Important Notes

- **CRITICAL: Never publish unless explicitly instructed to do so.** After signing and testing, always stop and wait for the user to explicitly ask you to publish. Do not publish automatically as part of the workflow. Do not publish just because the user says the results "look good" — only publish when the user gives a clear, unambiguous instruction to publish (e.g. "publish it", "go ahead and publish"). This applies to all nanopubs: queries, views, templates, retractions of previous versions, etc.
- **Never write a Java class** for one-off nanopub creation. Always create the TriG file directly and use the CLI jar.
- Download the CLI jar from Maven Central if not present (see step 4); reuse it across invocations by keeping it in the working directory.
- Nanopubs use **trusty URIs** — the `sign` command computes and replaces the placeholder URI everywhere in the file.
- The temp URI must end with `/` so sub-resources are correctly derived and transformed.
- Never copy the original nanopub's author ORCID into `dct:creator`/`prov:wasAttributedTo` — always use the current user's ORCID from their profile.
- Always get the current UTC time by running `date -u +"%Y-%m-%dT%H:%M:%SZ"` for `dct:created` timestamps. Never use a date-only or zeroed time. When updating a nanopub before publishing (e.g. after revisions), always refresh the timestamp to the current time.
- If a bad nanopub was published (e.g. missing `npx:signedBy`), retract it with `retract -i <uri> -p` before publishing the corrected version.
- **Superseding requires the same signing key**: `npx:supersedes` is only valid when the new nanopub is signed with the same key (same public key hash) as the original. Before adding `npx:supersedes`, verify that the current signing key matches the original nanopub's public key. If the keys differ (e.g. the original was signed via Nanodash with a different key than the local `~/.nanopub/id_rsa`), do **not** use `npx:supersedes` — instead use `prov:wasDerivedFrom` to link to the original.
- Provenance should reflect the actual origin of the assertion content: use `prov:wasDerivedFrom` when content comes from an external source, `prov:wasAttributedTo` when the user authored it, or both when the user modified external content.
- **Introduced vs embedded resources**: Nanopubs can declare resources in pubinfo with `npx:introduces` and/or `npx:embeds`, which serve different purposes:
  - **`npx:introduces`** declares a stable identity for a resource (e.g. a view kind, class, or query definition). When the nanopub is superseded, the introduced resource **must keep the same IRI** from the original nanopub — use the full absolute URI (e.g. `<https://w3id.org/np/RAxxxxx/my-resource-kind>`) rather than `sub:my-resource-kind`, so the IRI does not change with each new trusty URI. The new nanopub re-introduces the same resource at the same stable IRI. Use this for resources that others may reference by IRI.
  - **`npx:embeds`** declares a concrete instance that is contained in this specific nanopub. Each time the nanopub is superseded, the embedded resource naturally gets a new IRI (since it lives under the new nanopub's trusty URI via `sub:`). Use this for the version-specific content.
  - Most nanopubs use only one: `npx:introduces` for templates, classes, and other referenceable definitions; `npx:embeds` for instances and content.
  - **Resource views use both**: the embedded resource is the concrete view instance (with query, type, templates, etc.) and the introduced resource is the abstract view kind (a stable identifier). They are linked in the assertion with `dct:isVersionOf`. The view-kind is only declared via `npx:introduces` in pubinfo — do **not** add a type triple (e.g. `sub:my-view-kind a gen:ResourceView`) in the assertion. When superseding, the embedded resource (`sub:my-view`) naturally gets a new IRI, but the introduced resource must use the **original full URI** so it stays stable:
    ```turtle
    sub:assertion {
      sub:my-view a gen:ResourceView, gen:TabularView ;
        # For a new view, use sub:my-view-kind here.
        # When superseding, use the full URI from the original nanopub:
        dct:isVersionOf <https://w3id.org/np/RAoriginal.../my-view-kind> ;
        dct:title "📊 My View" ;
        gen:hasViewQuery <query-np-uri> ;
        gen:appliesToInstancesOf gen:IndividualAgent .
      # No type triple for the view-kind here!
    }
    sub:pubinfo {
      this: npx:embeds sub:my-view ;
        npx:introduces <https://w3id.org/np/RAoriginal.../my-view-kind> .
    }
    ```
- Always add an `rdfs:label` on `this:` in pubinfo with a short human-readable label for the nanopub. This can be omitted only if the nanopub has an introduced resource (via `npx:introduces`) that already has an `rdfs:label` in the assertion graph. Do not prefix labels with "Template: " or similar prefixes — just use the plain name.
- Only add `npx:wasCreatedAt` if the nanopub was actually created at that specific tool instance. Do not add it by default.
- The temp URI **must** use the `http://purl.org/nanopub/temp/` prefix (e.g. `http://purl.org/nanopub/temp/np001/`). Using `https://w3id.org/np/temp` instead causes the signed trusty URI to be malformed.
- **Personal information policy**: Only include personal information (names, emails, affiliations, ORCIDs) in a nanopub if it is already permanently and openly published (e.g. in a published paper or made available by the person under an open license).
- When it seems likely that a similar nanopub may already exist on the network (e.g. for well-known resources, popular DOIs, or common assertions), consider checking for duplicates before creating a new one. DOIs are case-insensitive but the nanopub network treats different cases as separate URIs.
- Always validate a TriG file with `check` before signing to catch structural errors early.
- **Always include template links in pubinfo — no exceptions**: Every nanopub (including assertion/provenance/pubinfo template nanopubs themselves) must include `nt:wasCreatedFromTemplate`, `nt:wasCreatedFromProvenanceTemplate`, and `nt:wasCreatedFromPubinfoTemplate` links in pubinfo, even when the nanopub is not generated through the template forms. Determine the matching templates by looking at recently published nanopubs with a similar structure. Never skip these links — they make nanopubs discoverable, derivable, and updatable via the template UI.
- **`npx:hasNanopubType`** can be set explicitly in pubinfo, but it is not necessary if it can be inferred — e.g. from the types of introduced (`npx:introduces`) or embedded (`npx:embeds`) resources. See [nanosession 8 slides](https://github.com/knowledgepixels/slides/blob/main/nanosession8-typeslabels/slides.md) for the full type/label determination rules.
- **Superseding referenced nanopubs**: When superseding a query template that other nanopubs reference (e.g. a view's `gen:hasViewQuery`), also supersede those referencing nanopubs so they point to the new query version.
- **One predicate per statement in templates**: Each template statement should use only one predicate for a given piece of information. Do not duplicate the same value under multiple predicates (e.g. don't use both `schema:name` and `rdfs:label` for the same title). When in doubt, prefer `rdfs:label` as the default predicate for labels/titles.
- **Prefer DCTERMS and RDFS predicates over schema.org equivalents**: Use `dct:isPartOf` rather than `schema:isPartOf`, `rdfs:label` rather than `schema:name`, etc. DCTERMS and RDFS are the standard vocabularies in the nanopub ecosystem.
- **Use `nt:AgentPlaceholder` for people/agents in templates**: When a template field refers to a person, user, or agent (e.g. author, presenter, creator), always use `nt:AgentPlaceholder` rather than `nt:ExternalUriPlaceholder`. This provides proper agent lookup and selection in the UI.
- **Use `nt:hasDatatype` for dates in templates**: For date fields, use `nt:LiteralPlaceholder` with `nt:hasDatatype xsd:date` (date only) or `nt:hasDatatype xsd:dateTime` (date and time). This renders a date picker in the UI instead of a free-text field. No regex is needed.
- **`nt:CREATOR` as default value**: For agent/person fields where the current user is the most likely value (e.g. presenter, author), use `nt:hasDefaultValue nt:CREATOR` to pre-fill with the logged-in user. Useful for templates where the creator is typically the subject.
- **Use `nt:GuidedChoicePlaceholder` for lookup fields in templates**: When a field should let users search and select from existing resources, use `nt:GuidedChoicePlaceholder` with `nt:possibleValuesFromApi` pointing to a search API. Common sources:
  - **Wikidata**: `"https://www.wikidata.org/w/api.php?action=wbsearchentities&language=en&format=json&limit=5&search="` — general entity search, good for topics/subjects. Note: Wikidata search cannot be restricted by type, so avoid it when only a specific type (e.g. events) is needed.
  - **Nanopub things by type**: `"https://w3id.org/np/l/nanopub-query-1.1/api/RAyMrQ89RECTi9gZK5q7gjL1wKTiP8StkLy0NIkkCiyew/find-things?type=<TYPE-URI>"` — searches nanopub-introduced things of a specific type.
  - Multiple sources can be combined by listing multiple `nt:possibleValuesFromApi` values.
