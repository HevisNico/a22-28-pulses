/* Conservative binary64 affine coefficient primitives.
 * IEEE round-to-nearest; no fast-math, no contraction. Each bound operation
 * advances to the next representable value separately. Overflow fails closed.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <float.h>
#include <fenv.h>

static int valid(double a){
 if(!isfinite(a)){PyErr_SetString(PyExc_ArithmeticError,"non-finite affine arithmetic");return 0;}
 return 1;
}
static double au(double a,double b){double s=a+b;if(a&&b)s=nextafter(s,INFINITY);return s;}
static double mu(double a,double b){double p=a*b;if(a&&b)p=nextafter(p,INFINITY);return p;}
static double err(double v){return fmax(fabs(nextafter(v,INFINITY)-v),fabs(v-nextafter(v,-INFINITY)));}
static int put(PyObject*d,PyObject*k,double v){
 if(!valid(v))return 0;PyObject*p=PyFloat_FromDouble(v);if(!p)return 0;
 int ok=PyDict_SetItem(d,k,p)==0;Py_DECREF(p);return ok;
}
static PyObject *scale(PyObject*a,double s,double*error){
 PyObject*d=PyDict_New(),*k,*v;if(!d||!valid(s)){Py_XDECREF(d);return NULL;}
 Py_ssize_t pos=0;*error=0;
 while(PyDict_Next(a,&pos,&k,&v)){
  double x=PyFloat_AsDouble(v);if(PyErr_Occurred()||!valid(x)){Py_DECREF(d);return NULL;}
  double p=s*x;if(!put(d,k,p)){Py_DECREF(d);return NULL;}
  if(s&&x&&fabs(s)!=1)*error=au(*error,err(p));
 }
 if(!valid(*error)){Py_DECREF(d);return NULL;}return d;
}
static PyObject *add(PyObject*a,PyObject*b,double*error){
 PyObject*d=PyDict_Copy(a),*k,*v;if(!d)return NULL;Py_ssize_t pos=0;*error=0;
 while(PyDict_Next(b,&pos,&k,&v)){
  double x=PyFloat_AsDouble(v);if(PyErr_Occurred()||!valid(x)){Py_DECREF(d);return NULL;}
  PyObject*old=PyDict_GetItemWithError(d,k);
  if(old){
   double y=PyFloat_AsDouble(old);if(PyErr_Occurred()||!valid(y)){Py_DECREF(d);return NULL;}
   double s=y+x;if(!put(d,k,s)){Py_DECREF(d);return NULL;}
   if(x&&y&&y!=-x)*error=au(*error,err(s));
  } else if(PyErr_Occurred()||PyDict_SetItem(d,k,v)<0){Py_DECREF(d);return NULL;}
 }
 if(!valid(*error)){Py_DECREF(d);return NULL;}return d;
}
static PyObject *wrap_add(PyObject*self,PyObject*args){
 PyObject*a,*b;if(!PyArg_ParseTuple(args,"O!O!",&PyDict_Type,&a,&PyDict_Type,&b))return NULL;
 double e;PyObject*d=add(a,b,&e);return d?Py_BuildValue("Nd",d,e):NULL;
}
static PyObject *wrap_scale(PyObject*self,PyObject*args){
 PyObject*a;double s;if(!PyArg_ParseTuple(args,"O!d",&PyDict_Type,&a,&s))return NULL;
 double e;PyObject*d=scale(a,s,&e);return d?Py_BuildValue("Nd",d,e):NULL;
}
static PyObject *wrap_multiply(PyObject*self,PyObject*args){
 PyObject*a,*b;double mx,my;if(!PyArg_ParseTuple(args,"O!O!dd",&PyDict_Type,&a,&PyDict_Type,&b,&mx,&my))return NULL;
 double ae,be,ce;PyObject*ad=scale(a,my,&ae);if(!ad)return NULL;
 PyObject*bd=scale(b,mx,&be);if(!bd){Py_DECREF(ad);return NULL;}
 PyObject*d=add(ad,bd,&ce);Py_DECREF(ad);Py_DECREF(bd);if(!d)return NULL;
 double e=au(au(ae,be),ce);if(!valid(e)){Py_DECREF(d);return NULL;}
 return Py_BuildValue("Nd",d,e);
}
static PyObject *wrap_sum(PyObject*self,PyObject*a){
 if(!PyDict_Check(a)){PyErr_SetString(PyExc_TypeError,"dictionary required");return NULL;}
 PyObject*k,*v;Py_ssize_t pos=0;double s=0;
 while(PyDict_Next(a,&pos,&k,&v)){
  double x=PyFloat_AsDouble(v);if(PyErr_Occurred()||!valid(x))return NULL;
  s=au(s,fabs(x));
 }
 return valid(s)?PyFloat_FromDouble(s):NULL;
}
static PyObject *bound(PyObject*args,int mult){
 double a,b;if(!PyArg_ParseTuple(args,"dd",&a,&b))return NULL;
 if(!valid(a)||!valid(b))return NULL;
 if(a<0||b<0){PyErr_SetString(PyExc_ArithmeticError,"negative error bound");return NULL;}
 double s=mult?mu(a,b):au(a,b);return valid(s)?PyFloat_FromDouble(s):NULL;
}
static PyObject *wrap_au(PyObject*s,PyObject*a){return bound(a,0);}
static PyObject *wrap_mu(PyObject*s,PyObject*a){return bound(a,1);}
/* Initialize already-validated affine values without ten Python-level
 * __setattr__ calls. Does not change arithmetic, truncate or promote noise. */
static PyObject *form_names[10];
static PyObject *wrap_new_form(PyObject*self,PyObject*args){
 PyObject *cls,*lo,*hi,*coeff,*error;
 if(!PyArg_ParseTuple(args,"OOOO!O",&cls,&lo,&hi,&PyDict_Type,&coeff,&error))return NULL;
 if(!PyType_Check(cls)){PyErr_SetString(PyExc_TypeError,"type required");return NULL;}
 PyObject *obj=((PyTypeObject*)cls)->tp_alloc((PyTypeObject*)cls,0);
 if(!obj)return NULL;
 PyObject *d=PyDict_Copy(coeff);
 if(!d){Py_DECREF(obj);return NULL;}
 PyObject *values[]={lo,hi,d,error,Py_None,Py_None,Py_None,Py_None,Py_None,Py_None};
 for(int i=0;i<10;i++){
  if(PyObject_GenericSetAttr(obj,form_names[i],values[i])<0){Py_DECREF(d);Py_DECREF(obj);return NULL;}
 }
 Py_DECREF(d);return obj;
}

/* Keep the kmax largest |coefficients| (ties: first in dict order), return
   (kept dict, upward-rounded sum of the dropped |coefficients|).
   Same rule and same left-to-right outward summation as rounding.truncate_coeff. */
static PyObject *wrap_truncate(PyObject*self,PyObject*args){
 PyObject*a,*k,*v;Py_ssize_t kmax,pos=0,n,i=0;
 if(!PyArg_ParseTuple(args,"O!n",&PyDict_Type,&a,&kmax))return NULL;
 if(kmax<1){PyErr_SetString(PyExc_ValueError,"kmax must be positive");return NULL;}
 n=PyDict_Size(a);
 if(n<=kmax){PyObject*c=PyDict_Copy(a);return c?Py_BuildValue("Nd",c,0.0):NULL;}
 double*m=PyMem_Malloc((size_t)n*sizeof(double));if(!m)return PyErr_NoMemory();
 while(PyDict_Next(a,&pos,&k,&v)){
  double x=PyFloat_AsDouble(v);if(PyErr_Occurred()||!valid(x)){PyMem_Free(m);return NULL;}
  m[i++]=fabs(x);
 }
 /* quickselect: value of rank kmax-1 in descending order (exact, no float ops) */
 Py_ssize_t lo=0,hi=n-1,want=kmax-1;
 while(lo<hi){
  double piv=m[lo+(hi-lo)/2];Py_ssize_t i2=lo,j2=hi;
  while(i2<=j2){while(m[i2]>piv)i2++;while(m[j2]<piv)j2--;if(i2<=j2){double t=m[i2];m[i2]=m[j2];m[j2]=t;i2++;j2--;}}
  if(want<=j2)hi=j2;else if(want>=i2)lo=i2;else break;
 }
 double thr=m[want];Py_ssize_t above=0;for(Py_ssize_t r=0;r<n;r++)if(m[r]>thr)above++;
 Py_ssize_t ties=kmax-above;PyMem_Free(m);
 PyObject*d=PyDict_New();if(!d)return NULL;double extra=0;pos=0;
 while(PyDict_Next(a,&pos,&k,&v)){
  double x=PyFloat_AsDouble(v),ax=fabs(x);
  if(ax>thr||(ax==thr&&ties>0)){
   if(ax==thr)ties--;
   if(PyDict_SetItem(d,k,v)<0){Py_DECREF(d);return NULL;}
  } else extra=au(extra,ax);
 }
 if(!valid(extra)){Py_DECREF(d);return NULL;}
 return Py_BuildValue("Nd",d,extra);
}
static PyMethodDef methods[]={
 {"sum_abs",wrap_sum,METH_O,NULL},{"add_coeff",wrap_add,METH_VARARGS,NULL},
 {"scale_coeff",wrap_scale,METH_VARARGS,NULL},{"multiply_coeff",wrap_multiply,METH_VARARGS,NULL},
 {"add_up",wrap_au,METH_VARARGS,NULL},{"mul_up",wrap_mu,METH_VARARGS,NULL},
 {"new_form",wrap_new_form,METH_VARARGS,NULL},{"truncate_coeff",wrap_truncate,METH_VARARGS,NULL},{NULL,NULL,0,NULL}};
static struct PyModuleDef mod={PyModuleDef_HEAD_INIT,"_rounding_native",NULL,-1,methods};
PyMODINIT_FUNC PyInit__rounding_native(void){
 if(FLT_RADIX!=2||DBL_MANT_DIG!=53||DBL_MAX_EXP!=1024||fegetround()!=FE_TONEAREST){
  PyErr_SetString(PyExc_ImportError,"IEEE binary64 round-to-nearest required");return NULL;
 }
 const char *names[]={"clo","chi","_d","e","_r","_lo","_hi","_dr","_mc","_key"};
 for(int i=0;i<10;i++){form_names[i]=PyUnicode_InternFromString(names[i]);if(!form_names[i])return NULL;}
 return PyModule_Create(&mod);
}
