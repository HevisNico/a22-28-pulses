"""Explicit fresh launch from layer1. This file does nothing until executed."""
from pathlib import Path
import argparse, datetime, os, sys

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,help='Must not already exist')
    parser.add_argument('--workers',type=int,choices=range(1,13),default=8)
    parser.add_argument('--memory-mib',type=int,default=1536)
    parser.add_argument('--cpu-seconds',type=int,default=14400)
    parser.add_argument('--epsilon',default='1e-4',help='relative physical-parameter half-width')
    args=parser.parse_args()
    if args.memory_mib<0 or args.cpu_seconds<0:parser.error('Budgets must be nonnegative')
    root=Path(__file__).resolve().parent
    output=(args.out if args.out is not None else root/'results'/(
        'A22_fresh_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))).resolve()
    if output.exists():parser.error('Fresh output directory already exists; choose a new path')
    native=list((root/'affine').glob('_rounding_native*.so'))+list((root/'affine').glob('_rounding_native*.pyd'))
    if not native:parser.error('Build extensions first: python build_all_native.py')
    print('Starting a NEW research campaign: layers1 through18.',flush=True)
    print('Output:',output,flush=True)
    command=[sys.executable,'-B',str(root/'run.py'),'--out',str(output),'--through','18',
        '--workers',str(args.workers),'--memory-mib',str(args.memory_mib),
        '--cpu-seconds',str(args.cpu_seconds),'--epsilon',args.epsilon]
    os.execv(sys.executable,command)

if __name__=='__main__':main()
