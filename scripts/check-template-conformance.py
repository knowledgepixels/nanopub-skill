import sys
from rdflib import Dataset, URIRef, Literal, RDF, RDFS

NT="https://w3id.org/np/o/ntemplate/"; DCT="http://purl.org/dc/terms/"
GEN="https://w3id.org/kpxl/gen/terms/"
nt=lambda n: URIRef(NT+n)

def assertion(path):
    d=Dataset(); d.parse(path, format='trig')
    return [g for g in d.graphs() if str(g.identifier).endswith('/assertion')][0]

g=assertion(sys.argv[1])
tmpl=[s for s,_,_ in g.triples((None,RDF.type,nt('AssertionTemplate')))][0]

PH_TYPES={'AgentPlaceholder','AutoEscapeUriPlaceholder','EmbeddedResource','ExternalUriPlaceholder',
 'GuidedChoicePlaceholder','IntroducedResource','LanguageTaggedLiteralPlaceholder','LiteralPlaceholder',
 'LocalResource','LongLiteralPlaceholder','RestrictedChoicePlaceholder','RootNanopubPlaceholder',
 'SequenceElementPlaceholder','TrustyUriPlaceholder','UriPlaceholder','ValuePlaceholder'}
ST_TYPES={RDF.Statement, nt('AdvancedStatement'), nt('OptionalStatement'), nt('RepeatableStatement')}

# roles, as the meta-template defines them
top_stmts=set(g.objects(tmpl, nt('hasStatement')))
groups={s for s in top_stmts if (s,RDF.type,nt('GroupedStatement')) in g}
members=set()
for gr in groups: members |= set(g.objects(gr, nt('hasStatement')))
simple={s for s in top_stmts|members if (s,RDF.subject,None) in g}
# only statements linked from the template node are "introduced"; a member reachable
# solely via its group is NOT (stC030's object is restricted to sub:tstatement)
all_stmts=top_stmts

# tsubj / tpred / tobj = anything appearing in those roles
tsubj={o for s in all_stmts for o in g.objects(s,RDF.subject)}
tpred={o for s in all_stmts for o in g.objects(s,RDF.predicate)}
tobj ={o for s in all_stmts for o in g.objects(s,RDF.object)}
spo=tsubj|tpred|tobj
possiblevalue={o for s in spo for o in g.objects(s, nt('possibleValue'))}
defaultvalue ={o for s in spo for o in g.objects(s, nt('hasDefaultValue'))}
labeled = spo | possiblevalue | defaultvalue

matched=set(); reasons={}
def mark(t,why): matched.add(t); reasons[t]=why

for s,p,o in g:
    t=(s,p,o)
    if s==tmpl:
        if p==RDF.type and o==nt('AssertionTemplate'): mark(t,'stA010')
        elif p==RDFS.label and isinstance(o,Literal): mark(t,'stA020')
        elif p==URIRef(DCT+'isVersionOf'): mark(t,'stA021a')
        elif p==URIRef(GEN+'governedBy'): mark(t,'stA021b')
        elif p==URIRef(DCT+'description'): mark(t,'stA022')
        elif p==nt('hasTag'): mark(t,'stA025')
        elif p==RDF.type and o==nt('UnlistedTemplate'): mark(t,'stA030')
        elif p==nt('hasDefaultProvenance'): mark(t,'stA040')
        elif p==nt('hasRequiredPubinfoElement'): mark(t,'stA050')
        elif p==nt('hasTargetNamespace'): mark(t,'stA060')
        elif p==nt('hasTargetNanopubType'): mark(t,'stA065')
        elif p==nt('hasNanopubLabelPattern'): mark(t,'stA070')
        elif p==nt('hasStatement') and o in groups: mark(t,'stC021')
        elif p==nt('hasStatement'): mark(t,'stB001')
    elif s in groups and p==nt('hasStatement') and o in top_stmts: mark(t,'stC030')
    elif s in groups and p==RDF.type and o==nt('GroupedStatement'): mark(t,'stC022')
    elif s in all_stmts and p in (RDF.subject,RDF.predicate,RDF.object): mark(t,'stB010/20/30')
    elif s in all_stmts and p==RDF.type and o in ST_TYPES: mark(t,'stC040')
    elif s in all_stmts and p==nt('statementOrder'): mark(t,'stC050')
    elif s in spo and p==RDF.type and str(o).startswith(NT) and str(o)[len(NT):] in PH_TYPES: mark(t,'stD010')
    elif s in tpred and p==RDF.type and o in (URIRef(GEN+'InverseRoleProperty'),URIRef(GEN+'RegularRoleProperty')): mark(t,'stD015')
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
print(f"triples: {len(list(g))}   matched: {len(matched)}   UNMATCHED: {len(un)}")
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
    if st not in top_stmts: print(f"   ! {st} not linked from the template node (stB001)")
