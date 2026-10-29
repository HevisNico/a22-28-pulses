"""Passive counters; never used to choose physical or verifier transitions."""
from collections import Counter
COUNTS=Counter()
def reset():COUNTS.clear()
def count(name):COUNTS[name]+=1
def snapshot():
    names=('guard_cover_bisections','recovery_rate_partitions','ready_clock_cuts')
    result={name:COUNTS[name] for name in names}
    result['subdivisions_total']=sum(result.values())
    result['scope']='This execution segment only. Excludes scalar root polishing and event-order branches.'
    return result
