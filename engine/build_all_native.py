"""Build the native extensions for this Python interpreter; starts no campaign."""
from pathlib import Path
import os, shlex, subprocess, sys, sysconfig

def main():
    root=Path(__file__).resolve().parent
    subprocess.run([sys.executable,str(root/'build_native.py')],check=True)
    source=root/'kernel/native/a22_native.c'
    target=source.parent/('_a22_native'+sysconfig.get_config_var('EXT_SUFFIX'))
    command=shlex.split(os.environ.get('CC','cc'))+[
        '-O3','-std=c11','-shared','-fPIC','-fno-fast-math','-ffp-contract=off',
        '-I'+sysconfig.get_path('include'),str(source),'-o',str(target),'-lm','-lcrypto']
    subprocess.run(command,check=True)
    print(target)

if __name__=='__main__':main()
