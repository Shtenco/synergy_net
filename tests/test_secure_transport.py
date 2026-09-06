from __future__ import annotations

from dataclasses import replace

import pytest

from synergynet_fabric import SynergyNetTransport


T0 = "2026-09-06T10:00:00Z"
PAYLOAD = b'{"signed":"opaque-event-bytes"}'


def test_transport_has_no_domain_authority():
    assert SynergyNetTransport.authority == "p2p_transport"
    assert SynergyNetTransport.execution_authority == "NONE"
    assert SynergyNetTransport.accounting_authority == "NONE"
    assert SynergyNetTransport.payment_authority == "NONE"
    assert SynergyNetTransport.validator_authority == "NONE"


def test_store_forward_survives_restart_and_acks(tmp_path):
    db = tmp_path / "synergynet.db"
    transport = SynergyNetTransport(db)
    packet = transport.enqueue(
        event_id="event-1",
        topic="synergy.contract.synergy-pay-system.trading-execution-intent.v1",
        source_repo="Shtenco/midas_ai",
        destination_repo="Shtenco/synergy_pay_system",
        payload=PAYLOAD,
        now=T0,
    )
    assert transport.state("event-1") == "PENDING"
    transport.close()

    transport = SynergyNetTransport(db)
    claimed = transport.claim(T0, lease_seconds=10)
    assert len(claimed) == 1
    assert claimed[0].packet.payload == PAYLOAD
    assert claimed[0].packet.payload_hash == packet.payload_hash
    transport.ack(packet.network_message_id, T0)
    assert transport.state("event-1") == "ACKED"
    transport.close()


def test_stale_transport_lease_is_recovered(tmp_path):
    transport = SynergyNetTransport(tmp_path / "lease.db")
    transport.enqueue(
        event_id="event-lease",
        topic="topic",
        source_repo="A",
        destination_repo="B",
        payload=PAYLOAD,
        now=T0,
    )
    assert len(transport.claim(T0, lease_seconds=1)) == 1
    assert transport.state("event-lease") == "INFLIGHT"
    assert transport.recover_stale("2026-09-06T10:00:01Z") == 1
    assert transport.state("event-lease") == "RETRY"
    second = transport.claim("2026-09-06T10:00:01Z", lease_seconds=1)
    assert second[0].attempts == 2
    transport.close()


def test_same_event_id_with_different_wire_bytes_is_rejected(tmp_path):
    transport = SynergyNetTransport(tmp_path / "conflict.db")
    transport.enqueue(
        event_id="event-conflict",
        topic="topic",
        source_repo="A",
        destination_repo="B",
        payload=PAYLOAD,
        now=T0,
    )
    with pytest.raises(ValueError, match="different wire payload"):
        transport.enqueue(
            event_id="event-conflict",
            topic="topic",
            source_repo="A",
            destination_repo="B",
            payload=b"tampered",
            now=T0,
        )
    transport.close()


def test_transport_retry_exhaustion_moves_packet_to_dead_letter(tmp_path):
    transport = SynergyNetTransport(tmp_path / "dead.db")
    packet = transport.enqueue(
        event_id="event-dead",
        topic="topic",
        source_repo="A",
        destination_repo="B",
        payload=PAYLOAD,
        now=T0,
    )
    first = transport.claim(T0, lease_seconds=1)[0]
    assert first.attempts == 1
    assert transport.fail(packet.network_message_id, "peer offline", T0, "2026-09-06T10:00:01Z", max_attempts=2) == "RETRY"
    second = transport.claim("2026-09-06T10:00:01Z", lease_seconds=1)[0]
    assert second.attempts == 2
    assert transport.fail(packet.network_message_id, "peer offline", "2026-09-06T10:00:01Z", "2026-09-06T10:00:03Z", max_attempts=2) == "DEAD"
    assert transport.state("event-dead") == "DEAD"
    assert transport.count_dead() == 1
    transport.close()
