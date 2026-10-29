"""Build optional coefficient accelerator; Python reference remains available."""
from pathlib import Path
import sysconfig,subprocess,shlex,os
root=Path(__file__).resolve().parent
src=root/'affine/rounding_native.c'
out=root/'affine'/('_rounding_native'+sysconfig.get_config_var('EXT_SUFFIX'))
cmd=shlex.split(os.environ.get('CC','cc'))+['-O3','-std=c11','-shared','-fPIC','-fno-fast-math','-ffp-contract=off','-I'+sysconfig.get_path('include'),str(src),'-o',str(out),'-lm']
subprocess.run(cmd,check=True)
print(out)
