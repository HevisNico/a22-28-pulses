"""Exact witnesses, rounding oracle, identities and artifact rejection tests."""
from pathlib import Path
import unittest,sys,os,tempfile,math,random,json,importlib.util
from fractions import Fraction as F
from decimal import Decimal as D,localcontext
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'affine'))
os.environ.setdefault('A22_ARTIFACT_DIR',str(ROOT/'test_diagnostics'))
import engine,affine_iv as af,temporal,artifacts as ar,rounding
I=af.I

class ArithmeticTests(unittest.TestCase):
 def setUp(self):af.FRESH=None;temporal.begin_producer('test')
 def test_radius_witness(self):
  d={'big':1.0,**{str(i):2**-54 for i in range(95)}};x=I.make(D(0),D(0),d,0.)
  self.assertGreaterEqual(F(x.hi),sum(map(F.from_float,d.values()),F(0)))
 def test_truncation_witness(self):
  d={str(i):2**(-i%70) for i in range(250)};x=I.make(D(0),D(0),d,0.)
  self.assertGreaterEqual(F(x.hi),sum(map(F.from_float,d.values()),F(0)))
 def test_hull_correlations(self):
  x=I.symbol('x',1);h=af.hull([x,-x]);z=h-x
  self.assertLessEqual(F(z.lo),-2*F.from_float(x.d['x']))
  self.assertIsNot(h,x)
 def test_min_endpoint_no_owner(self):
  x=I.symbol('x',1);y=-x+I('.1');z=I(min(x.lo,y.lo),min(x.hi,y.hi))-x
  self.assertLessEqual(F(z.lo),F(1,10)-2*F.from_float(x.d['x']))
 def test_immutable(self):
  x=I.symbol('x',1)
  with self.assertRaises(AttributeError):x.clo=D(1)
  with self.assertRaises(TypeError):x.d['x']=4.
 def test_fresh_independent_times_same_label(self):
  bound=I(-1,1);a=temporal.Time('same',bound);b=temporal.Time('same',bound)
  self.assertNotEqual(a.token(),b.token());self.assertLessEqual(a.minus(b).lo,-2);self.assertGreaterEqual(a.minus(b).hi,2)
 def test_copy_preserves_identity(self):
  a=temporal.Time('same',I(-1,1));b=a.copy()
  self.assertEqual(a.token(),b.token());self.assertEqual(a.minus(b).pair(),['0','0'])
  self.assertEqual(a.plus('0.1234567890123456789012345678901').minus(a).lo,D('0.1234567890123456789012345678901'))
 def test_constant_clock_collision(self):
  a=temporal.Time('a',I(1));b=temporal.Time('b',I('1.000000000000000000000000000001'))
  self.assertNotEqual(a.token(),b.token())
 def test_atom_definition_conflict(self):
  a=temporal.Time('a',I(-1,1));b=temporal.Time('b',I(-2,2),terms=((a.terms[0][0],1,I(-2,2)),))
  with self.assertRaises(ValueError):a.minus(b)
 def test_equal_boxes_distinct_histories(self):
  a=engine.b.ac.History(I.symbol('a',1));b=engine.b.ac.History(I.symbol('b',1))
  self.assertEqual(len(engine.unique_histories([a,b])),2)
  self.assertEqual(len(engine.unique_histories([a,a])),1)
 def test_generated_pointwise_add_multiply(self):
  rng=random.Random(1931)
  for case in range(180):
   c1=D(rng.randrange(-20,21))/10;c2=D(rng.randrange(-20,21))/10
   da={str(i):rng.randrange(-10,11)*2.**-12 for i in range(6)};db={str(i):rng.randrange(-10,11)*2.**-12 for i in range(6)}
   a=I.make(c1,c1,da,2.**-20);b=I.make(c2,c2,db,2.**-20)
   for x,op in ((a+b,lambda p,q:p+q),(a*b,lambda p,q:p*q)):
    for sign in (-1,1):
     eps={str(i):rng.choice((-1,0,1)) for i in range(6)}
     va=F(c1)+sum((F(v)*eps[k] for k,v in da.items()),F(0))+sign*F(a.e)
     vb=F(c2)+sum((F(v)*eps[k] for k,v in db.items()),F(0))-sign*F(b.e)
     v=op(va,vb);linear=sum((F(v)*eps[k] for k,v in x.d.items()),F(0))
     self.assertLessEqual(F(x.clo)+linear-F(x.e),v);self.assertGreaterEqual(F(x.chi)+linear+F(x.e),v)
 def test_unary_pointwise(self):
  for center in ('0.5','1','2','5'):
   x=I(center)+I.symbol('x','.01')
   for name in ('exp','ln','reciprocal'):
    y=getattr(x,name)()
    for eps in (-1,0,1):
     with localcontext() as c:
      c.prec=400
      v=D(center)+D(x.d['x'])*eps
      truth=v.exp() if name=='exp' else v.ln() if name=='ln' else 1/v
     linear=F(y.d.get('x',0.))*eps
     self.assertLessEqual(F(y.clo)+linear-F(y.e),F(truth));self.assertGreaterEqual(F(y.chi)+linear+F(y.e),F(truth))
 def test_ambient_precision_independence(self):
  x=I('1.123456789012345678901234567890123')+I.symbol('x','.001')
  with localcontext() as c:c.prec=7;a=(x*x).fingerprint()
  with localcontext() as c:c.prec=60;b=(x*x).fingerprint()
  self.assertEqual(a,b)
 def test_primitive_upward_exact_oracle(self):
  rng=random.Random(17)
  values=[0.,5e-324,2**-1022,1.,2**-54,2.**500]
  values += [math.ldexp(rng.random(),rng.randrange(-1000,500)) for _ in range(100)]
  for a in values:
   for b in values:
    for fn,exact in ((rounding.add_up,F(a)+F(b)),(rounding.mul_up,F(a)*F(b))):
     try:r=fn(a,b)
     except ArithmeticError:continue
     self.assertGreaterEqual(F(r),exact)
 def test_native_python_differential(self):
  try:import _rounding_native as native
  except ImportError:self.skipTest('native accelerator unavailable')
  source=(ROOT/'affine/rounding.py').read_text().split('# Override only')[0]
  ref={};exec(compile(source,'rounding_reference','exec'),ref)
  rng=random.Random(448)
  for _ in range(250):
   a={str(i):math.ldexp(rng.uniform(-1,1),rng.randrange(-500,500)) for i in range(rng.randrange(1,100))}
   b={str(i):math.ldexp(rng.uniform(-1,1),rng.randrange(-500,500)) for i in range(rng.randrange(1,100))}
   for name,args in [('sum_abs',(a,)),('add_coeff',(a,b)),('scale_coeff',(a,.731)),('multiply_coeff',(a,b,-.39,2.73))]:
    self.assertEqual(getattr(native,name)(*args),ref[name](*args))
 def test_codec_round_trip_and_mutation(self):
  x=I.symbol('x',1);t=temporal.Time('t',x);h=engine.b.ac.History(x,fire=t)
  data={'state':h,'outputs':(t,t.copy()),'two_histories':(h,engine.b.ac.History(-x)),'bool':True,'int':1}
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'x.json';sha,check=ar.write_checked(p,data);self.assertTrue(check['full_content_equal'])
   old=p.read_text();p.write_text(old+' ')
   with self.assertRaises(ValueError):ar.read(p,sha)
 def test_unknown_artifact_rejected(self):
  with self.assertRaises(ValueError):ar.decode({'schema':'legacy','nodes':[],'root':0})
 def test_settings_guards_and_per_port_delay(self):
  engine.settings_cell('test-cell')
  a,b,c=engine.b.D1_PORTS
  self.assertNotEqual(a.d,b.d);self.assertNotEqual(b.d,c.d)
  self.assertLess((a-b).lo,0);self.assertGreater((a-b).hi,0)
if __name__=='__main__':unittest.main(verbosity=2)
