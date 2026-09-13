from __future__ import annotations
import asyncio,os
from .shttps_bridge import serve

def main():
    asyncio.run(serve(os.getenv("SYNERGYNET_SHTTPS_BIND_HOST","127.0.0.1"),int(os.getenv("SYNERGYNET_SHTTPS_BIND_PORT","9443")),os.getenv("SYNERGYNET_SHTTPS_TARGET_HOST","127.0.0.1"),int(os.getenv("SYNERGYNET_SHTTPS_TARGET_PORT","8120"))))
if __name__=="__main__": main()
