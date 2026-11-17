import sys
from rdflib import Dataset, URIRef, Literal, RDF, RDFS
from governance_check import report as report_governance
from supersede_check import report as report_supersede
from template_links_check import report as report_template_links

NT="https://w3id.org/np/o/ntemplate/"; DCT="http://purl.org/dc/terms/"
GEN="https://w3id.org/kpxl/gen/terms/"
nt=lambda n: URIRef(NT+n)

def assertion(path):
    # found via the head graph, so old purl.org templates (graph IRIs ending in #assertion) work too
    d=Dataset(); d.parse(path, format='trig')
    has_assertion=URIRef('http://www.nanopub.org/nschema#hasAssertion')
    head=[g for g in d.graphs() if (None,has_assertion,None) in g][0]
    return d.graph(next(head.objects(None,has_assertion)))

g=assertion(sys.argv[1])

# Assertion, provenance and pubinfo templates each have their own meta-template:
# RAgeON_v… ("Defining an assertion template"), RA-yPZEY… ("Defining a provenance
# template") and RA4o9JqS… ("Defining a publication info template"). The two
# latter share their shape and differ from the first as noted where it matters.
KINDS={'AssertionTemplate':'assertion','ProvenanceTemplate':'provenance','PubinfoTemplate':'pubinfo'}
found=[(s,o) for k in KINDS for s,_,o in g.triples((None,RDF.type,nt(k)))]
if not found:
    sys.exit(f"{sys.argv[1]}: no node typed nt:AssertionTemplate, nt:ProvenanceTemplate or "
             "nt:PubinfoTemplate in the assertion; not a template")
tmpl,tmpl_type=found[0]
kind=KINDS[str(tmpl_type)[len(NT):]]
is_assertion = kind=='assertion'

# DatePlaceholder is supported by Nanodash but not yet among the meta-template's
# placeholder-type choices, so it is accepted here rather than reported.
PH_TYPES={'AgentPlaceholder','AutoEscapeUriPlaceholder','DatePlaceholder','EmbeddedResource',
 'ExternalUriPlaceholder','GuidedChoicePlaceholder','IntroducedResource',
 'LanguageTaggedLiteralPlaceholder','LiteralPlaceholder','LocalResource','LongLiteralPlaceholder',
 'NewUriPlaceholder','RestrictedChoicePlaceholder','RootNanopubPlaceholder',
 'SequenceElementPlaceholder','TrustyUriPlaceholder','UriPlaceholder','ValuePlaceholder'}
# only the assertion meta-template offers AdvancedStatement
ST_TYPES={RDF.Statement, nt('OptionalStatement'), nt('RepeatableStatement')} | \
         ({nt('AdvancedStatement')} if is_assertion else set())
# stA030: only the pubinfo meta-template offers TransientTemplate
TEMPLATE_FLAGS={nt('UnlistedTemplate')} | ({nt('TransientTemplate')} if kind=='pubinfo' else set())

# roles, as the meta-template defines them
top_stmts=set(g.objects(tmpl, nt('hasStatement')))
if is_assertion:
    groups={s for s in top_stmts if (s,RDF.type,nt('GroupedStatement')) in g}
    members=set()
    for gr in groups: members |= set(g.objects(gr, nt('hasStatement')))
    simple={s for s in top_stmts|members if (s,RDF.subject,None) in g}
    # only statements linked from the template node are "introduced"; a member reachable
    # solely via its group is NOT (stC030's object is restricted to sub:tstatement)
    all_stmts=top_stmts
else:
    # here sub:tstatement is bound by the repeatable stB010/20/30 group itself and
    # sub:group by stC020, so a statement counts whether or not the template node
    # links it, and stC010 then links the template node to either kind
    groups=set(g.subjects(RDF.type, nt('GroupedStatement')))
    members=set()
    for gr in groups: members |= set(g.objects(gr, nt('hasStatement')))
    simple=set(g.subjects(RDF.subject, None))
    all_stmts=simple|groups

# tsubj / tpred / tobj = anything appearing in those roles
tsubj={o for s in all_stmts for o in g.objects(s,RDF.subject)}
tpred={o for s in all_stmts for o in g.objects(s,RDF.predicate)}
tobj ={o for s in all_stmts for o in g.objects(s,RDF.object)}
spo=tsubj|tpred|tobj
possiblevalue={o for s in spo for o in g.objects(s, nt('possibleValue'))}
defaultvalue ={o for s in spo for o in g.objects(s, nt('hasDefaultValue'))}
# stD050: default values can carry a label only in the assertion meta-template
labeled = spo | possiblevalue | (defaultvalue if is_assertion else set())

matched=set(); reasons={}
def mark(t,why): matched.add(t); reasons[t]=why

for s,p,o in g:
    t=(s,p,o)
    if s==tmpl:
        if p==RDF.type and o==tmpl_type: mark(t,'stA010')
        elif p==RDFS.label and isinstance(o,Literal): mark(t,'stA020')
        elif p==URIRef(DCT+'isVersionOf'): mark(t,'stA021a')
        elif p==URIRef(GEN+'governedBy'): mark(t,'stA021b')
        elif p==URIRef(DCT+'description'): mark(t,'stA022')
        elif p==RDF.type and o in TEMPLATE_FLAGS: mark(t,'stA030')
        elif not is_assertion:
            if p==nt('hasStatement') and o in all_stmts: mark(t,'stC010')
        elif p==nt('hasTag'): mark(t,'stA025')
        elif p==nt('hasDefaultProvenance'): mark(t,'stA040')
        elif p==nt('hasRequiredPubinfoElement'): mark(t,'stA050')
        elif p==nt('hasTargetNamespace'): mark(t,'stA060')
        elif p==nt('hasTargetNanopubType'): mark(t,'stA065')
        elif p==nt('hasNanopubLabelPattern'): mark(t,'stA070')
        elif p==nt('hasStatement') and o in groups: mark(t,'stC021')
        elif p==nt('hasStatement'): mark(t,'stB001')
    elif s in groups and p==nt('hasStatement') and o in (top_stmts if is_assertion else simple): mark(t,'stC030')
    elif s in groups and p==RDF.type and o==nt('GroupedStatement'): mark(t,'stC022' if is_assertion else 'stC020')
    elif s in all_stmts and p in (RDF.subject,RDF.predicate,RDF.object): mark(t,'stB010/20/30')
    elif s in all_stmts and p==RDF.type and o in ST_TYPES: mark(t,'stC040')
    elif s in all_stmts and p==nt('statementOrder'): mark(t,'stC050')
    elif s in spo and p==RDF.type and str(o).startswith(NT) and str(o)[len(NT):] in PH_TYPES: mark(t,'stD010')
    elif is_assertion and s in tpred and p==RDF.type and o in (URIRef(GEN+'InverseRoleProperty'),URIRef(GEN+'RegularRoleProperty')): mark(t,'stD015')
    elif s in spo and p==nt('possibleValue'): mark(t,'stD020')
    elif s in spo and p==nt('possibleValuesFrom'): mark(t,'stD030')
    elif s in spo and p==nt('possibleValuesFromApi'): mark(t,'stD040')
    elif s in spo and p==nt('hasDefaultValue'): mark(t,'stD045')
    elif s in tobj and p==nt('hasDatatype'): mark(t,'stD046')
    elif s in tobj and p==nt('hasLanguageTag'): mark(t,'stD047')
    elif s in tobj and p==nt('possibleLanguageTag'): mark(t,'stD048')
    elif s in labeled and p==RDFS.label and isinstance(o,Literal): mark(t,'stD050')
    elif s in spo and p==nt('hasPrefix'): mark(t,'stD061')
    elif s in spo and p==nt('hasPrefixLabel'): mark(t,'stD062')
    elif s in spo and p==nt('hasRegex'): mark(t,'stD070')

un=[t for t in g if t not in matched]
print(f"triples: {len(list(g))}   matched: {len(matched)}   UNMATCHED: {len(un)}"
      + ("" if is_assertion else f"   ({kind} template)"))
for s,p,o in sorted(un, key=lambda t:(str(t[0]),str(t[1]))):
    sh=lambda v: str(v).rsplit('/',1)[-1] if isinstance(v,URIRef) else '"'+str(v)[:40]+'"'
    print("   !", sh(s), sh(p), sh(o))

# grouped statements that require a partner
def pair_check(name,a,b):
    ha=any((tmpl,a,None) in g for _ in [0]); hb=any((tmpl,b,None) in g for _ in [0])
    if ha!=hb: print(f"   ! group {name}: only one half present -> would not match")
pair_check('stA021 (isVersionOf+governedBy)', URIRef(DCT+'isVersionOf'), URIRef(GEN+'governedBy'))
for ph in spo:
    hp=(ph,nt('hasPrefix'),None) in g; hl=(ph,nt('hasPrefixLabel'),None) in g
    if hp!=hl: print(f"   ! group stD060 on {ph}: hasPrefix/hasPrefixLabel not paired")
for st in simple:
    for r,n in ((RDF.subject,'subject'),(RDF.predicate,'predicate'),(RDF.object,'object')):
        if (st,r,None) not in g: print(f"   ! stB000 on {st}: missing rdf:{n}")
    if is_assertion:
        if st not in top_stmts: print(f"   ! {st} not linked from the template node (stB001)")
    elif st not in top_stmts|members:
        # matches the meta-template, but Nanodash reads statements only through these links
        print(f"   ! {st} linked neither from the template node nor from a group, so Nanodash never reads it")

# a governed template: is its kind registered with the space it names? (a note, never a failure)
report_governance(sys.argv[1])
# a new version: does it keep the IRIs the version it supersedes introduces?
report_supersede(sys.argv[1])
# do its provenance and pubinfo template links name templates of those kinds?
report_template_links(sys.argv[1])
