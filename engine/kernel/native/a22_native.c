/* A22 exact Merkle accelerator. No physical arithmetic is implemented here.
 * The Python codec remains the oracle and handles uncommon object types.
 * Runs under the GIL; all memoization belongs to one synchronous capture. */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <openssl/sha.h>
#include <stdint.h>
#include <string.h>

typedef struct {
 PyObject *builder,*memo,*active,*nodes,*hashes,*interned,*scalars;
 PyObject *interval_cls,*time_cls,*decimal_cls,*texts,*encode,*quote,*order;
 int spool;
 Py_ssize_t node_budget;
} Capture;
static void release(Capture *c) {
 Py_XDECREF(c->memo);Py_XDECREF(c->active);Py_XDECREF(c->nodes);Py_XDECREF(c->hashes);
 Py_XDECREF(c->interned);Py_XDECREF(c->scalars);Py_XDECREF(c->interval_cls);
 Py_XDECREF(c->time_cls);Py_XDECREF(c->encode);Py_XDECREF(c->quote);Py_XDECREF(c->order);
 Py_XDECREF(c->decimal_cls);Py_XDECREF(c->texts);
}
static int init(Capture *c,PyObject *builder) {
 memset(c,0,sizeof(*c));c->builder=builder;
 #define GET(field,name) if(!(c->field=PyObject_GetAttrString(builder,name)))return -1;
 GET(memo,"memo") GET(active,"active") GET(nodes,"nodes") GET(hashes,"hashes")
 GET(interned,"interned") GET(scalars,"scalar_nodes") GET(interval_cls,"interval_class")
 GET(time_cls,"time_class") GET(encode,"json_encode") GET(quote,"json_quote") GET(order,"order_key")
 GET(decimal_cls,"decimal_class") GET(texts,"decimal_texts")
 #undef GET
 PyObject *budget=PyObject_GetAttrString(builder,"node_budget");
 if(!budget)return -1;c->node_budget=PyLong_AsSsize_t(budget);Py_DECREF(budget);if(PyErr_Occurred())return -1;
 c->spool=PyObject_HasAttrString(builder,"store");return 0;
}
static void bigend(unsigned char *p,uint64_t n,int size){for(int i=size-1;i>=0;i--){p[i]=(unsigned char)n;n>>=8;}}
static PyObject *node(Capture *c,PyObject *tag,PyObject *payload,PyObject *children) {
 if(c->spool)return PyObject_CallMethod(c->builder,"node","OOO",tag,payload,children);
 PyObject *key=PyTuple_Pack(3,tag,payload,children);if(!key)return NULL;
 PyObject *old=PyDict_GetItemWithError(c->interned,key);
 if(old){Py_INCREF(old);Py_DECREF(key);return old;}
 if(PyErr_Occurred()){Py_DECREF(key);return NULL;}
 if(c->node_budget && PyList_GET_SIZE(c->nodes)>=c->node_budget){Py_DECREF(key);PyErr_SetString(PyExc_MemoryError,"Snapshot node RAM budget exceeded; use disk");return NULL;}
 Py_ssize_t ntag;const char *raw=PyUnicode_AsUTF8AndSize(tag,&ntag);
 if(!raw||!PyBytes_Check(payload)||!PyTuple_Check(children)){Py_DECREF(key);if(!PyErr_Occurred())PyErr_SetString(PyExc_TypeError,"Invalid exact Merkle node");return NULL;}
 SHA256_CTX h;unsigned char out[32],sz[8];SHA256_Init(&h);
 SHA256_Update(&h,"A22-MERKLE-2\0",13);
 bigend(sz,(uint64_t)ntag,4);SHA256_Update(&h,sz,4);SHA256_Update(&h,raw,(size_t)ntag);
 bigend(sz,(uint64_t)PyBytes_GET_SIZE(payload),8);SHA256_Update(&h,sz,8);
 SHA256_Update(&h,PyBytes_AS_STRING(payload),(size_t)PyBytes_GET_SIZE(payload));
 Py_ssize_t n=PyTuple_GET_SIZE(children);bigend(sz,(uint64_t)n,8);SHA256_Update(&h,sz,8);
 for(Py_ssize_t i=0;i<n;i++){
  Py_ssize_t k=PyLong_AsSsize_t(PyTuple_GET_ITEM(children,i));
  if(k<0||k>=PyList_GET_SIZE(c->hashes)){Py_DECREF(key);if(!PyErr_Occurred())PyErr_SetString(PyExc_ValueError,"Invalid child");return NULL;}
  PyObject *hash=PyList_GET_ITEM(c->hashes,k);SHA256_Update(&h,PyBytes_AS_STRING(hash),32);
 }
 SHA256_Final(out,&h);PyObject *digest=PyBytes_FromStringAndSize((char*)out,32);
 PyObject *number=PyLong_FromSsize_t(PyList_GET_SIZE(c->nodes));
 if(!digest||!number||PyList_Append(c->nodes,key)<0||PyList_Append(c->hashes,digest)<0||PyDict_SetItem(c->interned,key,number)<0){Py_XDECREF(number);number=NULL;}
 Py_XDECREF(digest);Py_DECREF(key);return number;
}
static PyObject *simple_node(Capture *c,const char *tag,PyObject *payload,PyObject *children){
 PyObject *t=PyUnicode_FromString(tag),*p=payload?Py_NewRef(payload):PyBytes_FromString(""),*ch=children?Py_NewRef(children):PyTuple_New(0);
 PyObject *r=(t&&p&&ch)?node(c,t,p,ch):NULL;Py_XDECREF(t);Py_XDECREF(p);Py_XDECREF(ch);return r;
}
static PyObject *jsonbytes(Capture *c,PyObject *item){
 PyObject *text=PyObject_CallOneArg(PyUnicode_CheckExact(item)?c->quote:c->encode,item);
 if(!text)return NULL;PyObject *r=PyUnicode_AsUTF8String(text);Py_DECREF(text);return r;
}
static PyObject *walk(Capture *c,PyObject *item);
static PyObject *endpoint_text(PyObject *cache,PyObject *value);
/* Exact Decimal.__str__ uses only ASCII characters with no JSON escapes.
 * Cache only immutable Decimal objects, pinned for this single capture. */
static PyObject *interval_bytes(Capture *c,PyObject *lo,PyObject *hi){
 PyObject *a=endpoint_text(c->texts,lo),*b=NULL,*raw=NULL;
 if(!a)return NULL;b=endpoint_text(c->texts,hi);if(!b)goto done;
 Py_ssize_t na,nb;const char *sa=PyUnicode_AsUTF8AndSize(a,&na),*sb=PyUnicode_AsUTF8AndSize(b,&nb);
 if(!sa||!sb)goto done;
 if(na>PY_SSIZE_T_MAX-7-nb){PyErr_NoMemory();goto done;}
 raw=PyBytes_FromStringAndSize(NULL,na+nb+7);if(!raw)goto done;
 char *out=PyBytes_AS_STRING(raw);memcpy(out,"[\"",2);memcpy(out+2,sa,na);
 memcpy(out+2+na,"\",\"",3);memcpy(out+5+na,sb,nb);memcpy(out+5+na+nb,"\"]",2);
 done:Py_DECREF(a);Py_XDECREF(b);return raw;
}
static PyObject *walk_sequence(Capture *c,PyObject *item,const char *tag){
 Py_ssize_t n=PySequence_Size(item);if(n<0)return NULL;PyObject *children=PyTuple_New(n);if(!children)return NULL;
 for(Py_ssize_t i=0;i<n;i++){
  PyObject *v=PyList_CheckExact(item)?PyList_GET_ITEM(item,i):PyTuple_GET_ITEM(item,i);
  PyObject *child=walk(c,v);if(!child){Py_DECREF(children);return NULL;}PyTuple_SET_ITEM(children,i,child);
 }
 PyObject *p=PyBytes_FromString(tag),*r=p?simple_node(c,"sequence",p,children):NULL;Py_XDECREF(p);Py_DECREF(children);return r;
}
static PyObject *walk_mapping(Capture *c,PyObject *item){
 PyObject *keys=PyDict_Keys(item),*args=NULL,*kwargs=NULL,*sorted=NULL,*children=NULL,*r=NULL;
 if(!keys)goto done;args=PyTuple_Pack(1,keys);kwargs=Py_BuildValue("{s:O}","key",c->order);
 PyObject *sortfn=PyDict_GetItemString(PyEval_GetBuiltins(),"sorted");if(!args||!kwargs||!sortfn)goto done;
 sorted=PyObject_Call(sortfn,args,kwargs);if(!sorted)goto done;
 Py_ssize_t n=PyList_GET_SIZE(sorted);children=PyTuple_New(2*n);if(!children)goto done;
 for(Py_ssize_t i=0;i<n;i++){
  PyObject *key=PyList_GET_ITEM(sorted,i),*value=PyDict_GetItemWithError(item,key);
  if(!value){if(!PyErr_Occurred())PyErr_SetString(PyExc_RuntimeError,"Mapping mutated in snapshot");goto done;}
  PyObject *a=walk(c,key);if(!a)goto done;PyTuple_SET_ITEM(children,2*i,a);
  PyObject *b=walk(c,value);if(!b)goto done;PyTuple_SET_ITEM(children,2*i+1,b);
 }
 r=simple_node(c,"mapping",NULL,children);
 done:Py_XDECREF(keys);Py_XDECREF(args);Py_XDECREF(kwargs);Py_XDECREF(sorted);Py_XDECREF(children);return r;
}
static PyObject *walk_inner(Capture *c,PyObject *item){
 int primitive=item==Py_None||PyUnicode_CheckExact(item)||PyBool_Check(item)||PyLong_CheckExact(item)||PyFloat_CheckExact(item);
 if(primitive){
  PyObject *guard=PyFloat_CheckExact(item)?PyObject_CallMethod(item,"hex",NULL):Py_NewRef(item);
  if(!guard)return NULL;PyObject *key=PyTuple_Pack(2,(PyObject*)Py_TYPE(item),guard);Py_DECREF(guard);if(!key)return NULL;
  PyObject *old=PyDict_GetItemWithError(c->scalars,key);if(old){Py_INCREF(old);Py_DECREF(key);return old;}
  if(PyErr_Occurred()){Py_DECREF(key);return NULL;}
  PyObject *raw=jsonbytes(c,item),*r=raw?simple_node(c,"json",raw,NULL):NULL;Py_XDECREF(raw);
  if(r&&PyDict_SetItem(c->scalars,key,r)<0){Py_DECREF(r);r=NULL;}Py_DECREF(key);return r;
 }
 int interval=(PyObject*)Py_TYPE(item)==c->interval_cls,time=(PyObject*)Py_TYPE(item)==c->time_cls;
 int decimal=(PyObject*)Py_TYPE(item)==c->decimal_cls;
 if(!(interval||time||decimal||PyTuple_CheckExact(item)||PyList_CheckExact(item)||PyDict_CheckExact(item)))return PyObject_CallMethod(c->builder,"_walk_python","(O)",item);
 PyObject *identity=PyLong_FromVoidPtr(item);if(!identity)return NULL;
 int active=PySet_Contains(c->active,identity);if(active<0){Py_DECREF(identity);return NULL;}
 if(active){Py_DECREF(identity);return PyObject_CallMethod(c->builder,"_walk_python","(O)",item);}
 PyObject *old=PyDict_GetItemWithError(c->memo,identity);
 if(old){PyObject *r=Py_NewRef(PyTuple_GET_ITEM(old,1));Py_DECREF(identity);return r;}
 if(PyErr_Occurred()||PySet_Add(c->active,identity)<0){Py_DECREF(identity);return NULL;}
 PyObject *r=NULL;
 if(time){
  const char *names[]={"key","base","offset","terms"};
  PyObject *children=PyTuple_New(4);
  if(children){
   int ok=1;
   for(int i=0;i<4;i++){
    PyObject *field=PyObject_GetAttrString(item,names[i]);
    PyObject *child=field?walk(c,field):NULL;Py_XDECREF(field);
    if(!child){ok=0;break;}PyTuple_SET_ITEM(children,i,child);
   }
   if(ok)r=simple_node(c,"native-time-dag-v1",NULL,children);
   Py_DECREF(children);
  }
 }else if(interval){
  PyObject *lo=PyObject_GetAttrString(item,"lo"),*hi=lo?PyObject_GetAttrString(item,"hi"):NULL;
  if(lo&&hi&&(PyObject*)Py_TYPE(lo)==c->decimal_cls&&(PyObject*)Py_TYPE(hi)==c->decimal_cls){
   PyObject *raw=interval_bytes(c,lo,hi);if(raw)r=simple_node(c,"native-interval-v1",raw,NULL);Py_XDECREF(raw);
  }else if(lo&&hi){
   Py_DECREF(lo);Py_DECREF(hi);PySet_Discard(c->active,identity);Py_DECREF(identity);
   return PyObject_CallMethod(c->builder,"_walk_python","(O)",item);
  }
  Py_XDECREF(lo);Py_XDECREF(hi);
 }else if(decimal){
  PyObject *s=endpoint_text(c->texts,item),*raw=s?PyUnicode_AsUTF8String(s):NULL;
  if(raw)r=simple_node(c,"decimal",raw,NULL);Py_XDECREF(s);Py_XDECREF(raw);
 }else if(PyDict_CheckExact(item))r=walk_mapping(c,item);
 else r=walk_sequence(c,item,PyTuple_CheckExact(item)?"tuple":"list");
 if(r){PyObject *entry=PyTuple_Pack(2,item,r);if(!entry||PyDict_SetItem(c->memo,identity,entry)<0){Py_DECREF(r);r=NULL;}Py_XDECREF(entry);}
 PySet_Discard(c->active,identity);Py_DECREF(identity);return r;
}
static PyObject *walk(Capture *c,PyObject *item){
 if(Py_EnterRecursiveCall(" in A22 canonical graph"))return NULL;
 PyObject *r=walk_inner(c,item);Py_LeaveRecursiveCall();return r;
}
static PyObject *pywalk(PyObject *module,PyObject *args){
 PyObject *builder,*item;if(!PyArg_ParseTuple(args,"OO",&builder,&item))return NULL;
 Capture c;if(init(&c,builder)<0){release(&c);return NULL;}PyObject *r=walk(&c,item);release(&c);return r;
}
static PyObject *pynode(PyObject *module,PyObject *args){
 PyObject *builder,*tag,*payload,*iter;if(!PyArg_ParseTuple(args,"OOOO",&builder,&tag,&payload,&iter))return NULL;
 PyObject *children=PySequence_Tuple(iter);if(!children)return NULL;
 Capture c;if(init(&c,builder)<0){release(&c);Py_DECREF(children);return NULL;}
 PyObject *r=node(&c,tag,payload,children);release(&c);Py_DECREF(children);return r;
}
static PyObject *atom_signature(PyObject *module,PyObject *record){
 if(!PyDict_CheckExact(record)||PyDict_Size(record)!=5)goto invalid;
 Py_ssize_t pos=0;PyObject *k,*v;
 while(PyDict_Next(record,&pos,&k,&v))if(!PyUnicode_CheckExact(k))goto invalid;
 PyObject *owner=PyDict_GetItemString(record,"owner"),*serial=PyDict_GetItemString(record,"serial");
 PyObject *bounds=PyDict_GetItemString(record,"bounds"),*label=PyDict_GetItemString(record,"label"),*kind=PyDict_GetItemString(record,"kind");
 if(!owner||!serial||!bounds||!label||!kind)goto invalid;
 if(!PyUnicode_CheckExact(owner)||!PyLong_CheckExact(serial)||!PyUnicode_CheckExact(label)||!PyUnicode_CheckExact(kind)||!PyList_CheckExact(bounds)||PyList_GET_SIZE(bounds)!=2)goto invalid;
 PyObject *lo=PyList_GET_ITEM(bounds,0),*hi=PyList_GET_ITEM(bounds,1);
 if(!PyUnicode_CheckExact(lo)||!PyUnicode_CheckExact(hi))goto invalid;
 return PyTuple_Pack(6,owner,serial,lo,hi,label,kind);
 invalid:PyErr_SetString(PyExc_ValueError,"Malformed or changed atom-definition fields");return NULL;
}
/* Same exhaustive guard as the Python loop: no registry mutation/version
 * shortcut and no trust in a previously validated mutable record. */
static PyObject *check_atom_state(PyObject *module,PyObject *args){
 PyObject *records,*definitions,*signatures,*absent,*decode;
 if(!PyArg_ParseTuple(args,"OOOOO",&records,&definitions,&signatures,&absent,&decode))return NULL;
 if(!PyDict_CheckExact(records)||!PyDict_CheckExact(definitions)||!PyDict_CheckExact(signatures)){
  PyErr_SetString(PyExc_ValueError,"Changed registry representation");return NULL;
 }
 Py_ssize_t pos=0;PyObject *key,*expected;
 while(PyDict_Next(definitions,&pos,&key,&expected)){
  PyObject *previous=PyDict_GetItemWithError(signatures,key),*signature=NULL;
  if(!previous){
   if(PyErr_Occurred())return NULL;
   PyObject *decoded=PyObject_CallOneArg(decode,expected);if(!decoded)return NULL;
   signature=atom_signature(module,decoded);Py_DECREF(decoded);if(!signature)return NULL;
   PyObject *entry=PyTuple_Pack(2,expected,signature);
   if(!entry||PyDict_SetItem(signatures,key,entry)<0){Py_XDECREF(entry);Py_DECREF(signature);return NULL;}
   Py_DECREF(entry);
  }else{
   if(!PyTuple_CheckExact(previous)||PyTuple_GET_SIZE(previous)!=2){PyErr_SetString(PyExc_ValueError,"Malformed pinned atom signature");return NULL;}
   int eq=PyObject_RichCompareBool(PyTuple_GET_ITEM(previous,0),expected,Py_EQ);
   if(eq<0)return NULL;
   if(!eq){PyErr_SetString(PyExc_ValueError,"Pinned atom expectation changed");return NULL;}
   signature=Py_NewRef(PyTuple_GET_ITEM(previous,1));
  }
  PyObject *record=PyDict_GetItemWithError(records,key);
  if(!record){Py_DECREF(signature);if(!PyErr_Occurred())PyErr_SetString(PyExc_ValueError,"Scoped ancestor atom definition removed");return NULL;}
  PyObject *current=atom_signature(module,record);
  if(!current){Py_DECREF(signature);return NULL;}
  int eq=PyObject_RichCompareBool(current,signature,Py_EQ);Py_DECREF(current);Py_DECREF(signature);
  if(eq<0)return NULL;
  if(!eq){PyErr_SetString(PyExc_ValueError,"Scoped ancestor atom definition changed");return NULL;}
 }
 PyObject *iterator=PyObject_GetIter(absent),*identity;
 if(!iterator)return NULL;
 while((identity=PyIter_Next(iterator))){
  int found=PyDict_Contains(records,identity);Py_DECREF(identity);
  if(found){Py_DECREF(iterator);if(found>0)PyErr_SetString(PyExc_ValueError,"Scoped constant identity became a registered atom");return NULL;}
 }
 Py_DECREF(iterator);if(PyErr_Occurred())return NULL;Py_RETURN_NONE;
}
static PyObject *metadata(PyObject *value,int *remaining);
static PyObject *metadata_inner(PyObject *value,int *remaining){
 if(--*remaining<0){PyErr_SetString(PyExc_ValueError,"Metadata guard budget exceeded");return NULL;}
 if(value==Py_None)return Py_BuildValue("(s)","none");
 if(PyUnicode_CheckExact(value)||PyBool_Check(value)||PyLong_CheckExact(value))return Py_BuildValue("(sO)",Py_TYPE(value)->tp_name,value);
 if(PyFloat_CheckExact(value)){PyObject *hex=PyObject_CallMethod(value,"hex",NULL);if(!hex)return NULL;PyObject *r=Py_BuildValue("(sO)","float",hex);Py_DECREF(hex);return r;}
 PyObject *items=NULL,*result=NULL,*keys=NULL;
 if(PyTuple_CheckExact(value)||PyList_CheckExact(value)){
  Py_ssize_t n=PySequence_Size(value);items=PyTuple_New(n);if(!items)return NULL;
  for(Py_ssize_t i=0;i<n;i++){
   PyObject *v=PyTuple_CheckExact(value)?PyTuple_GET_ITEM(value,i):PyList_GET_ITEM(value,i);
   PyObject *part=metadata(v,remaining);if(!part)goto done;PyTuple_SET_ITEM(items,i,part);
  }
  result=Py_BuildValue("(sO)",Py_TYPE(value)->tp_name,items);
 }else if(PyDict_CheckExact(value)){
  keys=PyDict_Keys(value);if(!keys)goto done;
  Py_ssize_t n=PyList_GET_SIZE(keys);
  for(Py_ssize_t i=0;i<n;i++)if(!PyUnicode_CheckExact(PyList_GET_ITEM(keys,i)))goto invalid;
  if(PyList_Sort(keys)<0)goto done;
  items=PyTuple_New(n);if(!items)goto done;
  for(Py_ssize_t i=0;i<n;i++){
   PyObject *key=PyList_GET_ITEM(keys,i),*v=PyDict_GetItemWithError(value,key);
   if(!v)goto done;PyObject *part=metadata(v,remaining);if(!part)goto done;
   PyObject *pair=PyTuple_Pack(2,key,part);Py_DECREF(part);if(!pair)goto done;PyTuple_SET_ITEM(items,i,pair);
  }
  result=Py_BuildValue("(sO)","dict",items);
 }else goto invalid;
 goto done;
 invalid:PyErr_SetString(PyExc_ValueError,"Non-JSON metadata needs ordinary encoding");
 done:Py_XDECREF(keys);Py_XDECREF(items);return result;
}
static PyObject *metadata(PyObject *value,int *remaining){
 if(Py_EnterRecursiveCall(" in A22 metadata"))return NULL;
 PyObject *result=metadata_inner(value,remaining);Py_LeaveRecursiveCall();return result;
}
static PyObject *metadata_key(PyObject *module,PyObject *value){int remaining=16384;return metadata(value,&remaining);}

/* Current-term validation and exact string capture. No interval arithmetic,
 * no producer allocation and no acceptance based on a previously seen object. */
static PyObject *endpoint_text(PyObject *cache,PyObject *value){
 PyObject *key=PyLong_FromVoidPtr(value);if(!key)return NULL;
 PyObject *old=PyDict_GetItemWithError(cache,key),*result=NULL;
 if(old && PyTuple_CheckExact(old) && PyTuple_GET_SIZE(old)==2 && PyTuple_GET_ITEM(old,0)==value){
  result=Py_NewRef(PyTuple_GET_ITEM(old,1));Py_DECREF(key);return result;
 }
 if(PyErr_Occurred()){Py_DECREF(key);return NULL;}
 result=PyObject_Str(value);if(!result){Py_DECREF(key);return NULL;}
 PyObject *entry=PyTuple_Pack(2,value,result);
 if(PyDict_Size(cache)>=32768)PyDict_Clear(cache);
 if(!entry||PyDict_SetItem(cache,key,entry)<0){Py_CLEAR(result);}
 Py_XDECREF(entry);Py_DECREF(key);return result;
}
static PyObject *validated_terms(PyObject *module,PyObject *args){
 PyObject *expression,*records,*interval_cls,*decimal_cls,*parse,*refusal,*texts;
 if(!PyArg_ParseTuple(args,"OOOOOOO",&expression,&records,&interval_cls,&decimal_cls,&parse,&refusal,&texts))return NULL;
 if(!PyTuple_CheckExact(expression)||!PyDict_CheckExact(records)||!PyDict_CheckExact(texts))Py_RETURN_NOTIMPLEMENTED;
 Py_ssize_t n=PyTuple_GET_SIZE(expression);
 PyObject *output=PyTuple_New(n),*lo=NULL,*hi=NULL,*parsed=NULL,*ls=NULL,*hs=NULL,*entry=NULL;
 if(!output)return NULL;
 for(Py_ssize_t i=0;i<n;i++){
  PyObject *term=PyTuple_GET_ITEM(expression,i);
  if(!PyTuple_CheckExact(term)||PyTuple_GET_SIZE(term)!=3)goto fallback;
  PyObject *key=PyTuple_GET_ITEM(term,0),*coef=PyTuple_GET_ITEM(term,1),*value=PyTuple_GET_ITEM(term,2);
  if(!PyUnicode_CheckExact(key)||!PyLong_Check(coef)||(PyObject*)Py_TYPE(value)!=interval_cls)goto fallback;
  lo=PyObject_GetAttrString(value,"lo");hi=PyObject_GetAttrString(value,"hi");if(!lo||!hi)goto error;
  if((PyObject*)Py_TYPE(lo)!=decimal_cls||(PyObject*)Py_TYPE(hi)!=decimal_cls)goto fallback;
  PyObject *record=PyDict_GetItemWithError(records,key);
  if(PyErr_Occurred())goto error;
  if(record && record!=Py_None){
   if(!PyDict_CheckExact(record))goto fallback;
   PyObject *bounds=PyDict_GetItemString(record,"bounds");
   if(!bounds)goto fallback;
   int tuple=PyTuple_CheckExact(bounds),list=PyList_CheckExact(bounds);
   if((!tuple&&!list)||PySequence_Size(bounds)!=2)goto fallback;
   PyObject *a=tuple?PyTuple_GET_ITEM(bounds,0):PyList_GET_ITEM(bounds,0);
   PyObject *b=tuple?PyTuple_GET_ITEM(bounds,1):PyList_GET_ITEM(bounds,1);
   if(!PyUnicode_CheckExact(a)||!PyUnicode_CheckExact(b))goto fallback;
   parsed=PyObject_CallFunctionObjArgs(parse,a,b,NULL);if(!parsed)goto error;
   if(!PyTuple_CheckExact(parsed)||PyTuple_GET_SIZE(parsed)!=2){PyErr_SetString(PyExc_TypeError,"Invalid parsed atom bounds");goto error;}
   int l=PyObject_RichCompareBool(lo,PyTuple_GET_ITEM(parsed,0),Py_EQ);
   int h=PyObject_RichCompareBool(hi,PyTuple_GET_ITEM(parsed,1),Py_EQ);
   if(l<0||h<0)goto error;
   if(!l||!h){PyErr_SetString(refusal,"Time atom bounds changed");goto error;}
   Py_CLEAR(parsed);
  }else{
   const char *identity=PyUnicode_AsUTF8(key);if(!identity)goto error;
   int equal=PyObject_RichCompareBool(lo,hi,Py_EQ);if(equal<0)goto error;
   if(strncmp(identity,"A22:[",5)==0||!equal){PyErr_SetString(refusal,"Unknown time atom; checked catalogue required");goto error;}
  }
  ls=endpoint_text(texts,lo);hs=endpoint_text(texts,hi);if(!ls||!hs)goto error;
  entry=PyTuple_Pack(4,key,coef,ls,hs);if(!entry)goto error;
  PyTuple_SET_ITEM(output,i,entry);entry=NULL;
  Py_CLEAR(lo);Py_CLEAR(hi);Py_CLEAR(ls);Py_CLEAR(hs);
 }
 return output;
 fallback:
 Py_CLEAR(output);output=Py_NewRef(Py_NotImplemented);
 error:
 Py_XDECREF(lo);Py_XDECREF(hi);Py_XDECREF(parsed);Py_XDECREF(ls);Py_XDECREF(hs);Py_XDECREF(entry);
 if(PyErr_Occurred())Py_CLEAR(output);
 return output;
}

static PyMethodDef methods[]={{"check_atom_state",check_atom_state,METH_VARARGS,"Exhaustive exact atom registry guard."},{"validated_terms",validated_terms,METH_VARARGS,"Validate current atom terms and capture exact endpoints."},{"atom_signature",atom_signature,METH_O,"Exact typed atom guard."},{"metadata_key",metadata_key,METH_O,"Exact typed environment guard."},{"walk",pywalk,METH_VARARGS,"Capture exact canonical graph."},{"node",pynode,METH_VARARGS,"Intern exact canonical node."},{NULL,NULL,0,NULL}};
static struct PyModuleDef definition={PyModuleDef_HEAD_INIT,"_a22_native",NULL,-1,methods};
PyMODINIT_FUNC PyInit__a22_native(void){return PyModule_Create(&definition);}
