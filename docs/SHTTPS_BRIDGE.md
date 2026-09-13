# SynergyNet -> SHTTPS bridge v1

SynergyNet transports SHTTPS end-to-end as opaque bytes. It does not terminate the ML-KEM/ML-DSA handshake, does not hold SHTTPS traffic keys and does not parse application envelopes.

```text
Auto-Company SHTTPS client
  -> SynergyNet opaque relay / future route
  -> Autopilot or NEXUS SHTTPS server
```

The first bridge is a bounded TCP relay that preserves this trust boundary. Future peer discovery, multipath, cache and store-and-forward implementations can replace the direct target selector without changing the SHTTPS wire/session protocol.

`SHTTPS` owns authenticated session/framing/compression negotiation. `SynergyNet` owns route selection and byte movement. Neither transport layer grants payment, accounting, trading, validator or agent-execution authority.
