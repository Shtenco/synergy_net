from __future__ import annotations
import argparse, hashlib, json, os, signal, socket, socketserver, tempfile, threading, zlib
from pathlib import Path
from typing import Any, BinaryIO

MAX_HEADER=16*1024; MAX_PAYLOAD=32*1024*1024; MAX_PEERS=256
class SynergyNetError(ValueError): pass

def canonical(v:Any)->bytes:
 def chk(x):
  if x is None or isinstance(x,(str,bool)): return
  if isinstance(x,int) and not isinstance(x,bool):
   if abs(x)>2**53-1: raise SynergyNetError('unsafe integer')
   return
  if isinstance(x,float): raise SynergyNetError('floats forbidden')
  if isinstance(x,list):
   for y in x: chk(y)
   return
  if isinstance(x,dict):
   if any(not isinstance(k,str) for k in x): raise SynergyNetError('bad key')
   for y in x.values(): chk(y)
   return
  raise SynergyNetError('unsupported')
 chk(v); return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()

def jline(v): return canonical(v)+b'\n'
def readj(r:BinaryIO):
 line=r.readline(MAX_HEADER+1)
 if not line or len(line)>MAX_HEADER or not line.endswith(b'\n'): raise SynergyNetError('frame')
 try:v=json.loads(line.decode())
 except Exception as e: raise SynergyNetError('json') from e
 if not isinstance(v,dict): raise SynergyNetError('object')
 canonical(v); return v

def exact(v,fields):
 if set(v)!=set(fields): raise SynergyNetError('shape')
def digest(v):
 if not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v): raise SynergyNetError('digest')
 return v

def bounded(v,name,lo,hi):
 if isinstance(v,bool) or not isinstance(v,int) or not lo<=v<=hi: raise SynergyNetError(name)
 return v

class Store:
 def __init__(self,root): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
 def path(self,d): d=digest(d); return self.root/d[:2]/d[2:]
 def has(self,d): return self.path(d).is_file()
 def put(self,raw:bytes):
  raw=bytes(raw); d=hashlib.sha256(raw).hexdigest(); p=self.path(d); p.parent.mkdir(parents=True,exist_ok=True)
  if p.exists():
   if self.get(d)!=raw: raise SynergyNetError('collision')
   return d
  fd,tmp=tempfile.mkstemp(prefix='.chunk-',dir=p.parent)
  try:
   with os.fdopen(fd,'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
   os.replace(tmp,p)
  finally:
   try: os.unlink(tmp)
   except FileNotFoundError: pass
  return d
 def get(self,d):
  raw=self.path(d).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=d: raise SynergyNetError('corrupt')
  return raw

class ContentHandler(socketserver.StreamRequestHandler):
 def handle(self):
  st=self.server.state
  while True:
   try:req=readj(self.rfile)
   except Exception: self.wfile.write(jline({'ok':False,'error':'INVALID_FRAME','execution_authority':'NONE'})); return
   op=req.get('op')
   try:
    if op=='STATUS':
     exact(req,{'op'}); out={'ok':True,'schema':'synergynet.content-service/v3','protocol':'synergynet.content-wire/v3','service_id':'content-cache','status':'READY','max_payload_bytes':st['max_payload'],'execution_authority':'NONE'}
     self.wfile.write(jline(out)); self.wfile.flush(); continue
    if op=='HAS':
     exact(req,{'op','digest'}); out={'ok':True,'present':st['store'].has(digest(req['digest'])),'execution_authority':'NONE'}; self.wfile.write(jline(out));self.wfile.flush();continue
    if op=='PUT':
     exact(req,{'op','digest','raw_size','payload_size','codec'}); d=digest(req['digest']); rs=bounded(req['raw_size'],'raw_size',0,st['max_payload']); ps=bounded(req['payload_size'],'payload_size',0,st['max_payload']); codec=req['codec']
     if codec not in {'raw','zlib-9'}: raise SynergyNetError('codec')
     payload=self.rfile.read(ps)
     if len(payload)!=ps: raise SynergyNetError('truncated')
     raw=payload if codec=='raw' else zlib.decompress(payload)
     if len(raw)!=rs or hashlib.sha256(raw).hexdigest()!=d: raise SynergyNetError('integrity')
     if st['store'].put(raw)!=d: raise SynergyNetError('store')
     self.wfile.write(jline({'ok':True,'digest':d,'execution_authority':'NONE'}));self.wfile.flush();continue
    if op=='GET_RAW':
     exact(req,{'op','digest'}); d=digest(req['digest']); raw=st['store'].get(d)
     if len(raw)>st['max_payload']: raise SynergyNetError('oversize')
     self.wfile.write(jline({'ok':True,'digest':d,'raw_size':len(raw),'execution_authority':'NONE'}));self.wfile.write(raw);self.wfile.flush();continue
    raise SynergyNetError('op')
   except Exception:
    self.wfile.write(jline({'ok':False,'error':'INVALID_REQUEST','execution_authority':'NONE'}));self.wfile.flush();return

class Server(socketserver.ThreadingTCPServer): allow_reuse_address=True; daemon_threads=True
class ContentServer:
 def __init__(self,root,host='127.0.0.1',port=0,max_payload=MAX_PAYLOAD):
  s=Server((host,port),ContentHandler); s.state={'store':Store(root),'max_payload':bounded(max_payload,'max_payload',1,256*1024*1024)}; self.s=s; self.t=None
 @property
 def address(self): return (str(self.s.server_address[0]),int(self.s.server_address[1]))
 def start(self): self.t=threading.Thread(target=self.s.serve_forever,daemon=True);self.t.start();return self
 def close(self): self.s.shutdown();self.s.server_close();self.t and self.t.join(5)
 def __enter__(self): return self.start()
 def __exit__(self,*_): self.close()

class ContentClient:
 def __init__(self,address,timeout=5.0): self.address=address;self.timeout=timeout
 def req(self,v,body=b''):
  with socket.create_connection(self.address,timeout=self.timeout) as s:
   r=s.makefile('rb');s.sendall(jline(v)); body and s.sendall(body); out=readj(r)
   if v['op']=='GET_RAW' and out.get('ok'):
    raw=r.read(out['raw_size']); return out,raw
   return out,None
 def status(self): return self.req({'op':'STATUS'})[0]
 def has(self,d): return bool(self.req({'op':'HAS','digest':digest(d)})[0]['present'])
 def put(self,raw,codec='raw'):
  raw=bytes(raw);d=hashlib.sha256(raw).hexdigest();p=raw if codec=='raw' else zlib.compress(raw,9);out,_=self.req({'op':'PUT','digest':d,'raw_size':len(raw),'payload_size':len(p),'codec':codec},p)
  if not out.get('ok'): raise SynergyNetError('put'); return d
  return d
 def get(self,d):
  out,raw=self.req({'op':'GET_RAW','digest':digest(d)})
  if not out.get('ok') or hashlib.sha256(raw).hexdigest()!=d: raise SynergyNetError('get')
  return raw

class Directory:
 def __init__(self,payload):
  if not isinstance(payload,dict) or set(payload)!={'schema','peers'} or payload['schema']!='synergynet.static-peer-directory/v3': raise SynergyNetError('directory')
  peers=payload['peers']
  if not isinstance(peers,list) or not peers or len(peers)>MAX_PEERS: raise SynergyNetError('peers')
  self.p={}
  for x in peers:
   if not isinstance(x,dict) or set(x)!={'peer_id','host','port'}: raise SynergyNetError('peer')
   pid=x['peer_id'];host=x['host'];port=x['port']
   if not isinstance(pid,str) or not pid or len(pid.encode())>128 or not isinstance(host,str) or not host or isinstance(port,bool) or not isinstance(port,int) or not 1<=port<=65535: raise SynergyNetError('peer')
   if pid in self.p: raise SynergyNetError('duplicate')
   self.p[pid]=(host,port)
 @classmethod
 def file(cls,p): return cls(json.loads(Path(p).read_text(encoding='utf-8')))
 def get(self,pid):
  if pid not in self.p: raise SynergyNetError('not allowlisted')
  return self.p[pid]

class RelayHandler(socketserver.StreamRequestHandler):
 def handle(self):
  try:req=readj(self.rfile);st=self.server.state;op=req.get('op')
  except Exception: self.wfile.write(jline({'ok':False,'error':'INVALID_FRAME','execution_authority':'NONE'}));return
  try:
   if op=='STATUS': exact(req,{'op'}); out={'ok':True,'schema':'synergynet.relay-service/v3','protocol':'synergynet.relay-wire/v3','service_id':'synergynet','status':'READY','peer_directory_mode':'STATIC_LOCAL_ALLOWLIST','peer_count':len(st['dir'].p),'execution_authority':'NONE'}
   elif op=='RELAY_CHUNK':
    exact(req,{'op','request_id','source_peer_id','destination_peer_id','chunk_digest'});d=digest(req['chunk_digest']);src=req['source_peer_id'];dst=req['destination_peer_id']
    if src==dst: raise SynergyNetError('same')
    raw=ContentClient(st['dir'].get(src),st['timeout']).get(d);cc=ContentClient(st['dir'].get(dst),st['timeout']);stored=cc.put(raw)
    if stored!=d or not cc.has(d): raise SynergyNetError('dest')
    base={'ok':True,'schema':'synergynet.relay-service/v3','protocol':'synergynet.relay-wire/v3','operation':'RELAY_CHUNK','request_id':req['request_id'],'source_peer_id':src,'destination_peer_id':dst,'chunk_digest':d,'raw_bytes':len(raw),'relay_scope':'STATIC_LOCAL_ALLOWLIST','execution_authority':'NONE'}
    base['response_digest']=hashlib.sha256(canonical(base)).hexdigest();out=base
   else: raise SynergyNetError('op')
  except Exception: out={'ok':False,'error':'INVALID_REQUEST','execution_authority':'NONE'}
  self.wfile.write(jline(out));self.wfile.flush()

class RelayServer:
 def __init__(self,directory,host='127.0.0.1',port=0,timeout=5.0): self.s=Server((host,port),RelayHandler);self.s.state={'dir':directory,'timeout':timeout};self.t=None
 @property
 def address(self): return (str(self.s.server_address[0]),int(self.s.server_address[1]))
 def start(self): self.t=threading.Thread(target=self.s.serve_forever,daemon=True);self.t.start();return self
 def close(self): self.s.shutdown();self.s.server_close();self.t and self.t.join(5)
 def __enter__(self): return self.start()
 def __exit__(self,*_): self.close()

def selftest():
 import tempfile
 with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
  with ContentServer(a) as sa, ContentServer(b) as sb:
   raw=b'SYNERGYNET-ARTIFACT-SELFTEST';d=ContentClient(sa.address).put(raw,'zlib-9')
   directory=Directory({'schema':'synergynet.static-peer-directory/v3','peers':[{'peer_id':'A','host':sa.address[0],'port':sa.address[1]},{'peer_id':'B','host':sb.address[0],'port':sb.address[1]}]})
   relay=RelayServer(directory).start()
   try:
    with socket.create_connection(relay.address,timeout=5) as s:
     r=s.makefile('rb');s.sendall(jline({'op':'RELAY_CHUNK','request_id':'selftest','source_peer_id':'A','destination_peer_id':'B','chunk_digest':d}));out=readj(r)
    if not out.get('ok') or ContentClient(sb.address).get(d)!=raw: raise SynergyNetError('selftest failed')
   finally: relay.close()
 print(json.dumps({'status':'PASS','artifact_runtime':'synergynet-v3','execution_authority':'NONE'},sort_keys=True));return 0

def run_content(argv):
 p=argparse.ArgumentParser();p.add_argument('--store',required=True);p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=7791);a=p.parse_args(argv);stop=threading.Event()
 def h(*_):stop.set()
 signal.signal(signal.SIGINT,h);signal.signal(signal.SIGTERM,h)
 with ContentServer(a.store,a.host,a.port): stop.wait()
 return 0

def run_relay(argv):
 p=argparse.ArgumentParser();p.add_argument('--peer-directory',required=True);p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=7792);a=p.parse_args(argv);stop=threading.Event()
 def h(*_):stop.set()
 signal.signal(signal.SIGINT,h);signal.signal(signal.SIGTERM,h)
 with RelayServer(Directory.file(a.peer_directory),a.host,a.port): stop.wait()
 return 0

def main(argv=None):
 import sys
 v=list(sys.argv[1:] if argv is None else argv)
 if not v: raise SystemExit('mode required: content-cache|relay|selftest')
 mode=v.pop(0)
 if mode=='content-cache': return run_content(v)
 if mode=='relay': return run_relay(v)
 if mode=='selftest': return selftest()
 raise SystemExit('unknown mode')
if __name__=='__main__': raise SystemExit(main())
