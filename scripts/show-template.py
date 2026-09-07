#!/usr/bin/env python3
"""Print an assertion template's statements in author-friendly form."""
import sys, os, re, urllib.request
from rdflib import Dataset, URIRef, Literal, RDF, RDFS
NT="https://w3id.org/np/o/ntemplate/"; nt=lambda n: URIRef(NT+n)
CACHE=os.environ.get("TPL_CACHE","/tmp/nptpl")
def load(code):
    os.makedirs(CACHE,exist_ok=True); fn=os.path.join(CACHE,code+'.trig')
    if not os.path.exists(fn):
        req=urllib.request.Request('https://w3id.org/np/'+code,headers={'Accept':'application/trig'})
        open(fn,'wb').write(urllib.request.urlopen(req,timeout=60).read())
    d=Dataset(); d.parse(fn,format='trig'); return d
def ag(d):
    for g in d.graphs():
        if str(g.identifier).endswith('/assertion'): return g
code=sys.argv[1]; g=ag(load(code))
tmpl=next(g.subjects(RDF.type, nt('AssertionTemplate')))
print("TEMPLATE:", next(g.objects(tmpl, RDFS.label), '?'))
print("identity :", "legacy (reference by NANOPUB uri)" if str(tmpl).endswith('/assertion') else f"embedded -> reference {tmpl}")
sh=lambda v: (str(v).rsplit('/',1)[-1].rsplit('#',1)[-1] if isinstance(v,URIRef) else '"'+str(v)[:40]+'"')
stmts=set(g.objects(tmpl, nt('hasStatement')))
for s in list(stmts): stmts |= set(g.objects(s, nt('hasStatement')))
def desc(t):
    kinds=[str(o)[len(NT):] for o in g.objects(t,RDF.type) if str(o).startswith(NT)]
    if not kinds: return sh(t)
    lbl=next(g.objects(t,RDFS.label),'')
    pv=[sh(v) for v in g.objects(t, nt('possibleValue'))]
    dv=[sh(v) for v in g.objects(t, nt('hasDefaultValue'))]
    api='API' if (t,nt('possibleValuesFromApi'),None) in g else ''
    extra=(' choices='+','.join(sorted(pv)) if pv else '')+(' default='+','.join(dv) if dv else '')+(' '+api if api else '')
    return f"?{sh(t)}[{'/'.join(kinds)}{extra}] «{lbl}»"
for st in sorted(stmts, key=str):
    if (st,RDF.subject,None) not in g: continue
    flags=[]
    if (st,RDF.type,nt('OptionalStatement')) in g: flags.append('OPT')
    if (st,RDF.type,nt('RepeatableStatement')) in g: flags.append('REP')
    s=next(g.objects(st,RDF.subject)); p=next(g.objects(st,RDF.predicate)); o=next(g.objects(st,RDF.object))
    print(f"  {sh(st):8} {','.join(flags):8} {desc(s)}  --{sh(p)}->  {desc(o)}")
