# nanopub-skill

A [Claude Code](https://claude.com/claude-code) skill for working with
[nanopublications](https://nanopub.net): creating, signing, publishing,
querying, superseding and retracting nanopubs, plus the assertion templates,
query templates, resource views and Spaces that make up the
[Nanodash](https://nanodash.knowledgepixels.com) ecosystem.

The skill itself is the single file [`SKILL.md`](SKILL.md). The rest of the
repository is reference material the skill points to: a local mirror of every
published assertion template, query template and resource view, and a few
helper scripts.

## What it does

Invoked as `/nanopub`, the skill guides Claude through the full workflow:

- **Create** a nanopub from a description or an existing template, as a TriG
  file, with the right provenance and pubinfo (creator ORCID, timestamp,
  labels, `npx:introduces` / `npx:embeds`, nanopub types).
- **Validate and sign** it with the `nanopub-java` CLI and the user's key.
- **Publish** to the test server or the live network, only on explicit request.
- **Fetch, inspect and query** nanopubs through Nanopub Query and its
  grlc-style query API.
- **Supersede or retract** earlier versions with the right key and links.
- **Author ecosystem artifacts**: assertion templates, query templates,
  resource views (tabular, plain-paragraph, header, SVG views), view
  displays, Spaces, roles, memberships and nanopub indexes.
- **Set up a bot identity** with its own key pair and introduction nanopub.

The skill never publishes on its own. After signing and testing it stops and
waits for an explicit instruction, and then asks whether the target is the
test server or the live network.

## Installation

Clone the repository and link it into the skills directory. Linking the whole
repository (not just `SKILL.md`) keeps the relative links to the reference
folders and scripts working.

User-level, available in every project:

```bash
git clone https://github.com/knowledgepixels/nanopub-skill.git
mkdir -p ~/.claude/skills
ln -s "$PWD/nanopub-skill" ~/.claude/skills/nanopub
```

Project-level, for one repository:

```bash
mkdir -p .claude/skills
ln -s /path/to/nanopub-skill .claude/skills/nanopub
```

Working inside this repository needs no setup: `.claude/skills/nanopub/SKILL.md`
is already a symlink to the root `SKILL.md`.

## Usage

Start Claude Code and invoke the skill with a nanopub URI, a description, or
an action:

```
/nanopub https://w3id.org/np/RA...
/nanopub create a nanopub stating that malaria is transmitted by mosquitoes
/nanopub retract https://w3id.org/np/RA...
/nanopub make a resource view listing the members of a space
```

Claude reads `SKILL.md`, decides which action applies, writes the TriG file
under `tmp/`, validates and signs it, and reports back before anything is
published.

## Prerequisites

- **Java** runtime able to run the `nanopub-java` CLI. The current jars are
  built for JDK 23.
- **The nanopub CLI jar** (`nanopub-<version>-jar-with-dependencies.jar`).
  The skill downloads the latest release from Maven Central into the working
  directory when it is missing. Jars are gitignored.
- **A nanopub profile** in `~/.nanopub/`: `profile.yaml` with the user's
  `orcid_id` and an RSA key pair (`id_rsa`, `id_rsa.pub`), as set up by
  Nanodash or by `java -jar nanopub-*.jar mkkeys`. Never delete or alter these
  key files; they are needed to supersede or retract anything signed with them.
- **curl** for the download scripts and ad-hoc queries.
- **Python 3 with `rdflib`** for the checker scripts:

  ```bash
  pip install rdflib
  ```

## Repository layout

| Path | Contents |
| --- | --- |
| `SKILL.md` | The skill: workflow, conventions, vocabulary, and known pitfalls. |
| `assertion-templates/` | Mirror of all published assertion template nanopubs, one TriG file each. |
| `queries/` | Mirror of all published query template nanopubs. |
| `resource-views/` | Mirror of all published resource view nanopubs. |
| `scripts/` | Download and conformance-checking helpers (see below). |
| `.claude/skills/nanopub/` | Symlink making the skill active inside this repository. |
| `tmp/` | Scratch space for TriG files in progress. Gitignored. |

Files in the three mirror folders are named `<artifact-code>_<label>.trig`,
where the artifact code is the trusty URI suffix (`RA` plus 43 characters) and
the label is the nanopub's `rdfs:label` slugified.

## Keeping the mirrors in sync

The three download scripts fetch the current list of published artifacts from
Nanopub Query, download any nanopub not yet present, and delete local files
whose artifact code is no longer listed (usually because a newer version
superseded it):

```bash
bash scripts/download-assertion-templates.sh
bash scripts/download-queries.sh
bash scripts/download-resource-views.sh
```

The scripts delete without asking. If the listing is incomplete for any
reason, live artifacts disappear locally, so review `git status` after a run
and confirm that every deleted file has a superseding replacement before
committing.

## Checker scripts

```bash
python3 scripts/check-nanopub-conformance.py <file.trig> [...]   # a nanopub vs. the template it declares
python3 scripts/check-template-conformance.py <template.trig>    # a template vs. the meta-template
python3 scripts/show-template.py <artifact-code>                 # a template's statements, author-friendly
```

`check-nanopub-conformance.py` is for ordinary nanopubs (views, queries,
instances). It reports false positives on template nanopubs, which use grouped
statement patterns; use `check-template-conformance.py` for those.

## Contributing

`SKILL.md` is the source of truth. When upstream behaviour changes
(`nanopub-java`, Nanodash, Nanopub Query), document the new behaviour there,
noting the version it applies from, rather than in side files. Keep mirror
refreshes in their own commits so documentation changes stay reviewable.
