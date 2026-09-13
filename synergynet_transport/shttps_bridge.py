from __future__ import annotations
import asyncio
from dataclasses import dataclass

@dataclass(frozen=True)
class RelayTarget:
    host:str
    port:int

class OpaqueSHTTPSRelay:
    """Byte-transparent relay for end-to-end protected SHTTPS streams.

    The relay never terminates PQ identity/session security and therefore never sees
    application plaintext or SHTTPS traffic keys. It owns routing only.
    """
    def __init__(self,target:RelayTarget,*,max_buffer:int=1024*1024,connect_timeout:float=10.0):
        self.target=target; self.max_buffer=max(4096,int(max_buffer)); self.connect_timeout=float(connect_timeout)
    async def handle(self,reader:asyncio.StreamReader,writer:asyncio.StreamWriter)->None:
        upstream_r=upstream_w=None
        try:
            upstream_r,upstream_w=await asyncio.wait_for(asyncio.open_connection(self.target.host,self.target.port),timeout=self.connect_timeout)
            async def pipe(src,dst):
                while True:
                    chunk=await src.read(min(65536,self.max_buffer))
                    if not chunk: break
                    dst.write(chunk); await dst.drain()
                try: dst.write_eof()
                except (AttributeError,OSError): pass
            await asyncio.gather(pipe(reader,upstream_w),pipe(upstream_r,writer))
        finally:
            writer.close()
            if upstream_w is not None: upstream_w.close()
            try: await writer.wait_closed()
            except Exception: pass
            if upstream_w is not None:
                try: await upstream_w.wait_closed()
                except Exception: pass

async def serve(bind_host:str,bind_port:int,target_host:str,target_port:int)->None:
    relay=OpaqueSHTTPSRelay(RelayTarget(target_host,target_port)); server=await asyncio.start_server(relay.handle,bind_host,int(bind_port))
    async with server: await server.serve_forever()
