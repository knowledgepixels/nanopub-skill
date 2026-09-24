#!/usr/bin/env python3
"""Report whether the space-governed definitions in a nanopub have their kind registered.

A definition version declaring dct:isVersionOf <kind> and gen:governedBy <space> on a node
the nanopub npx:embeds is resolved space-based (any current member of the space can publish
its next version) only once an admin of the space has registered the kind:
<kind> a gen:MaintainedResource ; gen:isMaintainedBy <space>. Until then gen:governedBy has
no effect and the version updates only through its own npx:supersedes chain; up to Nanodash
5.15.0 a reference to such a version even stays on exactly that version (nanodash#732).

Used by check-nanopub-conformance.py and check-template-conformance.py. It prints notes only
and never fails a check. The lookup needs the network; set SKIP_GOVERNANCE_CHECK=1 to skip it.

Usage on its own: governance_check.py <file.trig> [...]
"""
import json, os, sys, urllib.parse, urllib.request
from rdflib import Dataset, URIRef

NP = "http://www.nanopub.org/nschema#"
IS_VERSION_OF = URIRef("http://purl.org/dc/terms/isVersionOf")
GOVERNED_BY = URIRef("https://w3id.org/kpxl/gen/terms/governedBy")
EMBEDS = URIRef("http://purl.org/nanopub/x/embeds")
SUPERSEDES = URIRef("http://purl.org/nanopub/x/supersedes")
ADMIN_NS = "http://purl.org/nanopub/admin/"
REGISTRATION_TEMPLATE = "RAuoIiBPtkpMCALeI5AWNlQHoXdBfqZwqj_sVHiBGbfQo"
# The spaces repo of each public Nanopub Query instance, tried in turn: any one of them can be
# slow or down at a given moment, and the generic w3id route forwards to a single one.
SPACES_REPOS = os.environ.get("SPACES_REPOS",
    "https://query.nanodash.net/repo/spaces https://query.knowledgepixels.com/repo/spaces "
    "https://query.petapico.org/repo/spaces").split()


def nanopub_graphs(d):
    """(nanopub IRI, assertion graph, pubinfo graph), found through the head graph."""
    has_assertion = URIRef(NP + "hasAssertion")
    head = next(g for g in d.graphs() if (None, has_assertion, None) in g)
    np_iri = next(head.subjects(has_assertion, None))
    return (np_iri, d.graph(next(head.objects(np_iri, has_assertion))),
            d.graph(next(head.objects(np_iri, URIRef(NP + "hasPublicationInfo")))))


def maintaining_spaces(kind):
    """The spaces the kind is a validated maintained resource of, or None if no instance answered."""
    q = ("PREFIX npa: <http://purl.org/nanopub/admin/>\n"
         "SELECT DISTINCT ?space WHERE {\n"
         "  GRAPH npa:graph { npa:thisRepo npa:hasCurrentSpaceState ?g . }\n"
         f"  GRAPH ?g {{ <{kind}> npa:isMaintainedBy ?space . }}\n}}")
    for repo in SPACES_REPOS:
        try:
            req = urllib.request.Request(repo + "?" + urllib.parse.urlencode({'query': q}),
                                         headers={'Accept': 'application/sparql-results+json'})
            rows = json.loads(urllib.request.urlopen(req, timeout=15).read())['results']['bindings']
        except Exception:
            continue
        # npa:isMaintainedBy also points at the space refs (admin IRIs); keep the space IRIs
        return {r['space']['value'] for r in rows if not r['space']['value'].startswith(ADMIN_NS)}
    return None


def superseded_kinds(pg, np_iri):
    """The kinds declared by the versions this nanopub supersedes, as {superseded nanopub: kinds}."""
    result = {}
    for old in pg.objects(np_iri, SUPERSEDES):
        try:
            req = urllib.request.Request(str(old), headers={'Accept': 'application/trig'})
            d = Dataset()
            d.parse(data=urllib.request.urlopen(req, timeout=30).read().decode(), format='trig')
            _, old_ag, _ = nanopub_graphs(d)
        except Exception:
            continue
        result[old] = set(old_ag.objects(None, IS_VERSION_OF))
    return result


def report(path):
    """Print one line per governed definition in the nanopub at path."""
    if os.environ.get("SKIP_GOVERNANCE_CHECK"):
        return
    d = Dataset()
    d.parse(path, format='trig')
    np_iri, ag, pg = nanopub_graphs(d)
    embedded = set(pg.objects(np_iri, EMBEDS))
    published = str(np_iri).startswith("https://w3id.org/np/RA")
    earlier = None   # kinds of the superseded versions, fetched only for a governed definition
    for node in sorted(set(ag.subjects(GOVERNED_BY, None))):
        kinds = sorted(ag.objects(node, IS_VERSION_OF))
        for space in sorted(ag.objects(node, GOVERNED_BY)):
            if not kinds:
                print(f"   NOTE governed: {node} declares gen:governedBy but no dct:isVersionOf, so it is not governed")
                continue
            if node not in embedded:
                print(f"   NOTE governed: {node} is not npx:embeds'd by the nanopub, so Nanodash ignores its gen:governedBy")
                continue
            for kind in kinds:
                minted_here = str(kind).startswith(str(np_iri))
                if earlier is None:
                    earlier = superseded_kinds(pg, np_iri)
                remint = [(old, ks) for old, ks in earlier.items() if ks and kind not in ks]
                if remint:
                    old, ks = remint[0]
                    print(f"   NOTE governed: {kind} is not the kind of the version this nanopub supersedes "
                          f"({old} is a version of {', '.join(sorted(ks))}). A new version has to keep the kind IRI "
                          f"(and npx:introduces it), otherwise it starts a separate line that governed resolution of "
                          f"the earlier versions does not see; republish with the earlier kind rather than registering this one")
                    continue
                if minted_here and not published:
                    print(f"   NOTE governed: this nanopub mints the kind {kind}, so it can only be registered with "
                          f"{space} once published; until then gen:governedBy has no effect "
                          f"(an admin of the space registers it with the maintained-resource template {REGISTRATION_TEMPLATE})")
                    continue
                spaces = maintaining_spaces(kind)
                if spaces is None:
                    print(f"   NOTE governed: could not check whether {kind} is registered with {space} (no query instance answered)")
                elif str(space) in spaces:
                    print(f"   governed: {kind} is registered with {space}: its members can publish the next versions")
                else:
                    elsewhere = f" (it is registered with {', '.join(sorted(spaces))})" if spaces else ""
                    when = " (after this nanopub is published, since it mints the kind)" if minted_here else ""
                    print(f"   NOTE governed: {kind} is not registered as a maintained resource of {space}{elsewhere}, "
                          f"so gen:governedBy has no effect yet: versions update only through their own npx:supersedes "
                          f"chain, and up to Nanodash 5.15.0 a reference stays on exactly this version. An admin of the "
                          f"space registers it{when} with the maintained-resource template {REGISTRATION_TEMPLATE}")


if __name__ == '__main__':
    for p in sys.argv[1:]:
        print(os.path.basename(p) + ":")
        report(p)
