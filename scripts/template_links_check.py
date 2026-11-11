#!/usr/bin/env python3
"""Check that a nanopub's template links point to templates of the right kind.

nt:wasCreatedFromTemplate has to name an assertion template, nt:wasCreatedFromProvenanceTemplate
a provenance template and nt:wasCreatedFromPubinfoTemplate a publication info template. The
assertion templates that *make* provenance and pubinfo templates ("Defining a provenance
template" RA-yPZEY…, "Defining a publication info template" RA4o9JqS…) are none of the latter
two, though they are easily taken for them; hand-authored nanopubs have named them in those
slots. Nanodash passes over such a link since nanodash#909, so a form filled from the nanopub
falls back to generic templates, and before that it showed those whole template-making forms
in the provenance and pubinfo sections.

Each linked template is fetched and its template node typed, the way Nanodash finds it: the
node a link names, or for a link naming a nanopub, the assertion graph (legacy shape) or else
the one embedded template node.
  template links      every link names a template of the right kind
  WARNING template    a link names something else: an assertion template in a provenance or
                      pubinfo slot, or no template at all
  NOTE template       a provenance or pubinfo link is missing, or a linked template could
                      not be fetched

Used by check-nanopub-conformance.py (a WARNING fails the check) and
check-template-conformance.py. The lookup needs the network; set SKIP_TEMPLATE_LINKS_CHECK=1
to skip it.

Usage on its own: template_links_check.py <file.trig> [...]   (exit code 1 on a WARNING)
"""
import os, re, sys
from rdflib import Dataset, URIRef, RDF
from governance_check import nanopub_graphs
from supersede_check import fetch

NT = "https://w3id.org/np/o/ntemplate/"
NP = "http://www.nanopub.org/nschema#"
KINDS = {URIRef(NT + "AssertionTemplate"): "assertion", URIRef(NT + "ProvenanceTemplate"): "provenance",
         URIRef(NT + "PubinfoTemplate"): "publication info"}
SLOTS = [(URIRef(NT + "wasCreatedFromTemplate"), "assertion"),
         (URIRef(NT + "wasCreatedFromProvenanceTemplate"), "provenance"),
         (URIRef(NT + "wasCreatedFromPubinfoTemplate"), "publication info")]
SUGGEST = {"provenance": 'e.g. RA7lSq6MuK_TIC6JMSHvLtee3lpLoZDOqLJCLXevnrPoU "Attributed to myself/others"',
           "publication info": 'e.g. RACJ58Gvyn91LqCKIO9zu1eijDQIeEff28iyDrJgjSJF8 "License" and '
                               'RA-N4_kFxcruvBTlo1yJv29E4SLOXsx5KO_th69PprMrA "Creator"'}
_kinds = {}


def template_kinds(ref):
    """The template kinds of the node a link names, or None if its nanopub could not be fetched."""
    if ref in _kinds:
        return _kinds[ref]
    code = re.search(r'RA[A-Za-z0-9_-]{43}', str(ref))
    d = fetch(URIRef("https://w3id.org/np/" + code.group(0))) if code else None
    if d is None:
        _kinds[ref] = None
        return None
    np_iri, ag, _ = nanopub_graphs(d)
    suffix = str(ref)[str(ref).index(code.group(0)) + len(code.group(0)):]
    if suffix in ("", "/", "#"):
        typed = {s for s, _, o in ag.triples((None, RDF.type, None)) if o in KINDS}
        nodes = [ag.identifier] if ag.identifier in typed else sorted(typed)
        node = nodes[0] if len(nodes) == 1 else None
    else:
        node = URIRef(str(np_iri) + suffix)
    kinds = {KINDS[o] for o in ag.objects(node, RDF.type) if o in KINDS} if node is not None else set()
    _kinds[ref] = kinds
    return kinds


def label(ref, kinds):
    if kinds is None:
        return "could not be fetched"
    return " and ".join(sorted(kinds)) + " template" if kinds else "no template"


def report(path):
    """Print whether the template links name templates of the right kind; False on a wrong one."""
    if os.environ.get("SKIP_TEMPLATE_LINKS_CHECK"):
        return True
    d = Dataset()
    d.parse(path, format='trig')
    np_iri, _, pg = nanopub_graphs(d)
    ok, notes, count = True, [], 0
    for pred, want in SLOTS:
        refs = sorted(pg.objects(np_iri, pred))
        if not refs and want != "assertion":
            notes.append(f"   NOTE template links: no nt:{pred.split('/')[-1]}; name the {want} template(s) "
                         f"the {want.replace('publication info', 'pubinfo')} graph follows ({SUGGEST[want]})")
        for ref in refs:
            count += 1
            kinds = template_kinds(ref)
            if kinds is None:
                notes.append(f"   NOTE template links: could not fetch {ref}, so its kind is unchecked")
            elif want not in kinds:
                ok = False
                hint = f" ({SUGGEST[want]})" if want in SUGGEST else ""
                notes.append(f"   WARNING template links: nt:{pred.split('/')[-1]} names {ref}, which is "
                             f"{'an' if label(ref, kinds)[0] in 'aeiou' else 'a'} {label(ref, kinds)}, not a "
                             f"{want} template. Name the {want} template actually used instead{hint}")
    if ok and count:
        print("   template links: " + ("the one link names a template" if count == 1 else
                                      f"all {count} name templates") + " of the right kind")
    for n in notes:
        print(n)
    return ok


if __name__ == '__main__':
    allok = True
    for p in sys.argv[1:]:
        print(os.path.basename(p) + ":")
        if not report(p):
            allok = False
    sys.exit(0 if allok else 1)
