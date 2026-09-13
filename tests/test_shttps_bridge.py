from synergynet_transport.shttps_bridge import OpaqueSHTTPSRelay,RelayTarget

def test_relay_configuration_has_no_crypto_keys_or_application_authority():
    r=OpaqueSHTTPSRelay(RelayTarget("127.0.0.1",8120)); assert r.target.port==8120; assert not hasattr(r,"identity"); assert not hasattr(r,"private_key")
