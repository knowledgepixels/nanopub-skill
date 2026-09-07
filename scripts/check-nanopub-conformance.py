#!/usr/bin/env python3
"""Check that a nanopub's assertion conforms to the assertion template it declares.

Usage: check-nanopub-conformance.py <signed-or-unsigned.trig> [...]

Reports, per nanopub:
  - assertion triples that match no statement of the declared template
    (these are what Nanodash renders as "unmatched statements")
  - non-optional template statements with no matching triple
  - RestrictedChoicePlaceholder values outside the allowed set
Exit code 1 if any nanopub has problems.

NOT for template nanopubs: the template meta-template uses grouped, role-restricted
statement patterns that this flat matcher does not model, so it reports false
positives on them. Use scripts/check-template-conformance.py for those instead.
"""
import re, sys, os, urllib.request
from rdflib import Dataset, Graph, URIRef, Literal, BNode, RDF, RDFS

NT = "https://w3id.org/np/o/ntemplate/"
nt = lambda n: URIRef(NT + n)
CACHE = os.environ.get("TPL_CACHE", "/tmp/nptpl")
PH_TYPES = {'AgentPlaceholder','AutoEscapeUriPlaceholder','ExternalUriPlaceholder',
 'GuidedChoicePlaceholder','IntroducedResource','LanguageTaggedLiteralPlaceholder','LiteralPlaceholder',
 'LocalResource','LongLiteralPlaceholder','RestrictedChoicePlaceholder','RootNanopubPlaceholder',
 'SequenceElementPlaceholder','TrustyUriPlaceholder','UriPlaceholder','ValuePlaceholder','EmbeddedResource'}
LITERAL_PH = {'LiteralPlaceholder','LongLiteralPlaceholder','LanguageTaggedLiteralPlaceholder'}

def graphs_of(path_or_text, is_text=False):
    d = Dataset()
    d.parse(data=path_or_text, format='trig') if is_text else d.parse(path_or_text, format='trig')
    return d

def assertion_graph(d):
    for g in d.graphs():
        if str(g.identifier).endswith('/assertion') or str(g.identifier).endswith('#assertion'):
            return g
    return None

def pubinfo_triples(d):
    for g in d.graphs():
        if str(g.identifier).endswith('/pubinfo'):
            for t in g: yield t

def fetch_template(ref):
    # accept every published nanopub URI prefix; always resolve via w3id.org
    m = re.match(r'(?:https://w3id\.org/np/|http://purl\.org/np/|https?://(?:www\.)?nanopub\.org/np/)(RA[A-Za-z0-9_-]{43})', str(ref))
    if not m: return None, None
    npuri = 'https://w3id.org/np/' + m.group(1)
    os.makedirs(CACHE, exist_ok=True)
    fn = os.path.join(CACHE, npuri.rsplit('/', 1)[-1] + '.trig')
    if not os.path.exists(fn):
        req = urllib.request.Request(npuri, headers={'Accept': 'application/trig'})
        open(fn, 'wb').write(urllib.request.urlopen(req, timeout=60).read())
    return npuri, graphs_of(fn)

def template_node(g):
    for s, _, _ in g.triples((None, RDF.type, nt('AssertionTemplate'))):
        return s
    return None

def collect_statements(g, tmpl):
    stmts = set(g.objects(tmpl, nt('hasStatement')))
    for s in list(stmts):
        stmts |= set(g.objects(s, nt('hasStatement')))   # grouped members
    return {s for s in stmts if (s, RDF.subject, None) in g}

def collect_groups(g, tmpl):
    """group statement -> its direct members, following nt:hasStatement recursively."""
    groups, frontier, seen = {}, list(g.objects(tmpl, nt('hasStatement'))), set()
    while frontier:
        s = frontier.pop()
        if s in seen:
            continue
        seen.add(s)
        members = set(g.objects(s, nt('hasStatement')))
        if members:
            groups[s] = members
            frontier.extend(members)
    return groups

def distinctive(g, pats):
    """Patterns whose fixed predicate identifies them uniquely within the template.

    Generic members such as (?x rdf:type ?y) or (?x rdfs:label "…") match almost any
    triple, so they cannot be used to decide whether a group was filled in."""
    counts = {}
    for (st, ts, tp, to, _) in pats:
        if isinstance(tp, URIRef) and not is_placeholder(g, tp):
            counts[tp] = counts.get(tp, 0) + 1
    return {st for (st, ts, tp, to, _) in pats if counts.get(tp) == 1}

def excused_by_absent_group(g, groups, satisfied, telling):
    """Members of an optional group that was not filled in are legitimately absent.

    A group's own nt:OptionalStatement does not reach its members, so without this the
    members of an unused optional group (e.g. a view's action group) are reported as
    required-but-missing. Usage is judged only on the group's telling members; a group
    that IS partly filled in stays fully required, which is what catches half-filled
    pairs such as isVersionOf+governedBy."""
    excused = set()
    changed = True
    while changed:                       # fixpoint, so nested groups propagate
        changed = False
        for grp, members in groups.items():
            if (grp, RDF.type, nt('OptionalStatement')) not in g and grp not in excused:
                continue
            probe = (members & telling) or members     # fall back if none is telling
            if probe & satisfied:
                continue
            if not members <= excused:
                excused |= members
                changed = True
    return excused

def is_placeholder(g, term):
    return any(str(o).startswith(NT) and str(o)[len(NT):] in PH_TYPES
               for o in g.objects(term, RDF.type))

def ph_kinds(g, term):
    return {str(o)[len(NT):] for o in g.objects(term, RDF.type) if str(o).startswith(NT)}

# nt:CREATOR / nt:ASSERTION are substituted by Nanodash at publish time,
# so they behave like URI placeholders rather than fixed IRIs.
SUBSTITUTED = {nt('CREATOR'), nt('ASSERTION')}

def term_matches(g, tterm, value):
    """Does a template term (fixed IRI or placeholder) match an instance term?"""
    if tterm in SUBSTITUTED:
        return isinstance(value, (URIRef, BNode))
    if not is_placeholder(g, tterm):
        return tterm == value
    kinds = ph_kinds(g, tterm)
    allowed = set(g.objects(tterm, nt('possibleValue')))
    if 'RestrictedChoicePlaceholder' in kinds and allowed:
        return value in allowed
    if kinds & LITERAL_PH:
        return isinstance(value, Literal)
    if kinds & {'UriPlaceholder','ExternalUriPlaceholder','AgentPlaceholder','GuidedChoicePlaceholder',
                'IntroducedResource','LocalResource','TrustyUriPlaceholder','AutoEscapeUriPlaceholder',
                'EmbeddedResource','RootNanopubPlaceholder'}:
        return isinstance(value, (URIRef, BNode))
    return True   # ValuePlaceholder etc: anything

def check(path):
    d = graphs_of(path)
    ag = assertion_graph(d)
    if ag is None:
        print(f"{path}: NO ASSERTION GRAPH"); return False
    refs = [o for _, p, o in pubinfo_triples(d) if p == nt('wasCreatedFromTemplate')]
    name = os.path.basename(path)
    if not refs:
        print(f"{name}: NO nt:wasCreatedFromTemplate DECLARED"); return False
    ok = True
    for ref in refs:
        npuri, td = fetch_template(ref)
        if td is None:
            print(f"{name}: cannot resolve template {ref}"); ok = False; continue
        tg = assertion_graph(td)
        tmpl = template_node(tg)
        stmts = collect_statements(tg, tmpl)
        pats = []
        for st in stmts:
            s = next(tg.objects(st, RDF.subject), None)
            p = next(tg.objects(st, RDF.predicate), None)
            o = next(tg.objects(st, RDF.object), None)
            optional = (st, RDF.type, nt('OptionalStatement')) in tg
            pats.append((st, s, p, o, optional))
        # A triple may match several statement patterns and a pattern may be satisfied by
        # several triples, so the two checks are independent existence tests rather than an
        # assignment: matching greedily would let an optional pattern "consume" a triple and
        # make a required one look uninstantiated.
        unmatched = []
        for (s, p, o) in ag:
            if not any(term_matches(tg, ts, s) and term_matches(tg, tp, p) and term_matches(tg, to, o)
                       for (st, ts, tp, to, _) in pats):
                unmatched.append((s, p, o))
        satisfied = {st for (st, ts, tp, to, _) in pats
                     if any(term_matches(tg, ts, s) and term_matches(tg, tp, p) and term_matches(tg, to, o)
                            for (s, p, o) in ag)}
        used = satisfied
        excused = excused_by_absent_group(tg, collect_groups(tg, tmpl), satisfied,
                                          distinctive(tg, pats))
        missing = [st for (st, ts, tp, to, opt) in pats
                   if not opt and st not in used and st not in excused]
        short = lambda v: (str(v).rsplit('/', 1)[-1].rsplit('#', 1)[-1] if isinstance(v, URIRef)
                           else '"' + str(v)[:45] + '"')
        if unmatched or missing:
            ok = False
            print(f"{name}  vs {npuri.rsplit('/',1)[-1]}:  UNMATCHED={len(unmatched)} MISSING_REQUIRED={len(missing)}")
            for t in unmatched: print("   ! unmatched:", short(t[0]), short(t[1]), short(t[2]))
            for st in missing: print("   ! required statement not instantiated:", short(st))
        else:
            print(f"{name}  vs {npuri.rsplit('/',1)[-1]}:  OK ({len(list(ag))} assertion triples all matched)")
    return ok

if __name__ == '__main__':
    allok = True
    for p in sys.argv[1:]:
        if not check(p): allok = False
    sys.exit(0 if allok else 1)
