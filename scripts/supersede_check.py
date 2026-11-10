#!/usr/bin/env python3
"""Check that a new version keeps the IRIs that the version it supersedes introduces.

npx:introduces declares a resource's stable identity, so a nanopub that supersedes another
has to introduce the same IRIs again, written as the full URI of the earlier version. Written
as sub:name instead, the IRI takes the new nanopub's trusty URI, and every version introduces
a different resource: links from other nanopubs keep pointing at the old one, and queries
that pick the latest version per resource see each version as a resource of its own.

For each npx:supersedes target, the earlier version is fetched (live network first, then the
test registry) and its npx:introduces compared with this nanopub's:
  WARNING re-minted   an IRI it introduces is gone, and this nanopub introduces a new one under
                      its own URI instead: the identity was re-minted, almost always by mistake
  NOTE introduces     an IRI it introduces is gone with no replacement (e.g. moved to
                      npx:embeds), which can be deliberate; or the re-minted resource is a
                      grlc query, which is version-specific by design (views reference the exact
                      version), so the fix there is npx:embeds rather than keeping the IRI

Used by check-nanopub-conformance.py (a WARNING fails the check) and
check-template-conformance.py. The lookup needs the network; set SKIP_SUPERSEDE_CHECK=1 to
skip it.

Usage on its own: supersede_check.py <file.trig> [...]   (exit code 1 on a WARNING)
"""
import os, re, sys, urllib.request
from rdflib import Dataset, URIRef, RDF
from governance_check import nanopub_graphs

INTRODUCES = URIRef("http://purl.org/nanopub/x/introduces")
SUPERSEDES = URIRef("http://purl.org/nanopub/x/supersedes")
GRLC_QUERY = URIRef("https://w3id.org/kpxl/grlc/grlc-query")
TEST_REGISTRY = os.environ.get("TEST_REGISTRY", "https://test.registry.knowledgepixels.com/")


def fetch(np_uri):
    """The nanopub as a Dataset, from its own URI or else the test registry; None if neither has it."""
    urls = [str(np_uri)]
    code = re.search(r'RA[A-Za-z0-9_-]{43}', str(np_uri))
    if code:
        urls.append(TEST_REGISTRY.rstrip('/') + '/np/' + code.group(0))
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'Accept': 'application/trig'})
            d = Dataset()
            d.parse(data=urllib.request.urlopen(req, timeout=30).read().decode(), format='trig')
            return d
        except Exception:
            continue
    return None


def report(path):
    """Print the IRIs a superseded version introduces that this nanopub drops; False on a re-mint."""
    if os.environ.get("SKIP_SUPERSEDE_CHECK"):
        return True
    d = Dataset()
    d.parse(path, format='trig')
    np_iri, ag, pg = nanopub_graphs(d)
    introduced = set(pg.objects(np_iri, INTRODUCES))
    minted_here = sorted(i for i in introduced if str(i).startswith(str(np_iri)))
    queries_only = minted_here and all((i, RDF.type, GRLC_QUERY) in ag for i in minted_here)
    ok = True
    for old in sorted(pg.objects(np_iri, SUPERSEDES)):
        od = fetch(old)
        if od is None:
            print(f"   NOTE introduces: could not fetch {old}, so whether this version keeps its introduced IRIs is unchecked")
            continue
        old_np, _, old_pg = nanopub_graphs(od)
        before = set(old_pg.objects(old_np, INTRODUCES))
        if not before:
            continue
        gone = sorted(before - introduced)
        if not gone:
            print(f"   introduces: keeps every IRI that {old} introduces ({len(before)})")
        elif queries_only:
            print(f"   NOTE introduces: {', '.join(map(str, minted_here))} is a query and is re-minted on every version. "
                  f"That is right for a query (views reference the exact version), but declare it with npx:embeds, "
                  f"not npx:introduces")
        elif minted_here:
            ok = False
            print(f"   WARNING re-minted: {old} introduces {', '.join(map(str, gone))}, and this version introduces "
                  f"{', '.join(map(str, minted_here))} instead. A new version keeps an introduced IRI: write the "
                  f"earlier IRI in full, in the assertion and in npx:introduces, rather than as sub:…")
        else:
            print(f"   NOTE introduces: {old} introduces {', '.join(map(str, gone))}, which this version no longer "
                  f"introduces. Fine if deliberate (e.g. moved to npx:embeds); otherwise introduce it again")
    return ok


if __name__ == '__main__':
    allok = True
    for p in sys.argv[1:]:
        print(os.path.basename(p) + ":")
        if not report(p):
            allok = False
    sys.exit(0 if allok else 1)
