from research.legacy_distillation_v1.verification_network_v2 import VerificationNetworkV2

ASSESSMENTS = [99, 100, 101, 100.5, 99.5, 100.2, 99.8]


def test_honest_small_noise_is_accepted():
    verifier = VerificationNetworkV2()
    decision = verifier.verify("honest", 102, ASSESSMENTS, posted_bond=40)
    assert not decision.caught


def test_repeated_ten_percent_overclaim_is_caught_by_cumulative_drift():
    verifier = VerificationNetworkV2()
    caught_at = None
    for i in range(1, 12):
        decision = verifier.verify("slow-drift", 110, ASSESSMENTS, posted_bond=50)
        if decision.caught:
            caught_at = i
            break
    assert caught_at is not None
    assert caught_at <= 6
    assert decision.reason == "cumulative_drift"


def test_gross_overclaim_is_caught_immediately():
    verifier = VerificationNetworkV2()
    decision = verifier.verify("gross", 160, ASSESSMENTS, posted_bond=100)
    assert decision.caught
    assert decision.reason == "instant_deviation"
