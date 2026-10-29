"""Cover a protected return that intersects an exterior overlap group.

Uses the unchanged finite-cycle resolver and preserves every parent prefix.
The sole added scheduling rule is to route such a group to that resolver
before the legacy guard-free exterior-order flow can be attempted.
"""
import histoires_A21 as h
import validation_A15 as b
import cycle_local_A20 as cyc
import branche_retour_A19 as recovery
import groupe_protege_A22 as protected
import retour_file_A22 as queue_return
import groupe_pret_feu_A22 as ready_fire
import subdivision_recuperation_A22 as rate_cases
from garde_relative_A22 import ready_to
import ordonnanceur_A22 as causal_scheduler
from intervalles_decimaux import I,D
import metriques_A22 as measurements
LEGACY_STEP=causal_scheduler.step

def step(x,pending,suffix,cell):
 s=x.branch.state;idx=x.index
 if s['p'] in (1,2):
  # A phase-relative endpoint encloses the exterior prefix without
  # replacing the common phase by an independent absolute clock.
  anchor=s['fire'];stop=idx+1
  while True:
   U=anchor.plus(max(t.minus(anchor).hi for t,_ in pending[idx:stop]))
   included=[k+1 for k,(t,_) in enumerate(pending[stop:],start=stop) if t.box().lo<U.box().hi and t.minus(U).lo<0]
   extended=max([stop]+included)
   if extended==stop:break
   stop=extended
  group=pending[idx:stop]
  common=protected.resolve_all(x.branch,group,U,f'{cell}:A22:relative-protected:{x.count}')
  if common is not None:
   return [h.History(y,stop,x.count+len(group),x.lineage+(k,)) for k,y in enumerate(common)]
 if s['p']==2:
  stop=idx+1;upper=pending[idx][0].box().hi
  while stop<len(pending) and upper>suffix[stop]:upper=max(upper,pending[stop][0].box().hi);stop+=1
  group=pending[idx:stop]
  common=protected.resolve(x.branch,group,upper,f'{cell}:A22:protected:{x.count}')
  if common is not None:
   return [h.History(common,stop,x.count+len(group),x.lineage)]
  coarse,proof=queue_return.anticipate(s,pending,idx,f'{cell}:A22:protected:{x.count}')
  lower=min(t.box().lo for t,_ in group)
  if coarse.box().lo<=upper and coarse.box().hi>=lower:
   try:forest,nextidx,handled=queue_return.pending_window(s,pending,idx,cell,x.count)
   except b.v.Ambiguous as error:
    if str(error) not in ('One-additional-fire bound not certified for this window','Local solver requires the post-fire fast phase to cover the window'):raise
    children=rate_cases.split(x,f'{cell}:{x.count}:rate')
    if children is None:raise
    return children
   return [h.History(h.extension(x.branch,y),nextidx,x.count+len(handled)+1,x.lineage+(k,)) for k,y in enumerate(forest.branches)]
 try:return LEGACY_STEP(x,pending,suffix,cell)
 except AssertionError as error:
  if s['p']!=0 or str(error)!='internal crossing inside uncertain external cluster':raise
  return ready_fire.resolve(x,pending,suffix,cell)
 except (b.v.Ambiguous,ValueError) as error:
  if s['p']!=0:raise
  if isinstance(error,ValueError) and str(error)!='f(a) and f(b) must have different signs':raise
  earliest=min(t.box().lo for t,_ in pending[idx:])
  endpoint=min(earliest,(I(s['t'].box().hi)+I('.5')).hi)
  if endpoint>s['t'].box().hi:
   measurements.count('ready_clock_cuts')
   U=b.dep.Time(f'{cell}:{x.count}:A22:ready-slab',I(endpoint))
   cyc.no_new_fire_bound(b.dep.Time(f'{cell}:{x.count}:A22:slab-start',I(s['t'].box().lo)),endpoint)
   ys=ready_to(x.branch,U,f'{cell}:{x.count}:A22:ready-slab')
   return [h.History(y,idx,x.count+1,x.lineage+(k,)) for k,y in enumerate(ys)]
  return ready_fire.resolve(x,pending,suffix,cell)
