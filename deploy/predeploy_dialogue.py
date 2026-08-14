"""Ephemeral-staging gate for the production dialogue regression.

This intentionally creates a fictional escalation case. Run it only against a
disposable staging database and pass ``--allow-state-mutation`` explicitly.
"""

from __future__ import annotations

import argparse
import uuid

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--allow-state-mutation", action="store_true")
    args = parser.parse_args()
    if not args.allow_state_mutation:
        raise SystemExit("refusing to create a staging case without --allow-state-mutation")

    base = args.base_url.rstrip("/")
    health = httpx.get(f"{base}/api/v1/health", timeout=10)
    health.raise_for_status()
    if health.json()["data"]["status"] != "ready":
        raise RuntimeError(f"staging dependencies are not ready: {health.json()['data']}")

    run = str(uuid.uuid4())
    conversation = httpx.post(
        f"{base}/api/v1/hires/emp-alyssa/conversations",
        headers={"Idempotency-Key": f"predeploy-conversation-{run}"},
        json={"simulated_date": "2026-08-10"},
        timeout=10,
    ).json()["data"]
    prompts = [
        "Whats my payroll", "Well then how do i do the onboard",
        "How to i put my payroll details", "I need help in this",
        "route it please", "how does payroll work",
    ]
    expected = [
        "grounded_answer", "escalation_offer", "escalation_offer",
        "escalation_offer", "escalation_confirmation", "grounded_answer",
    ]
    for index, (prompt, outcome) in enumerate(zip(prompts, expected, strict=True)):
        response = httpx.post(
            f"{base}/api/v1/hires/emp-alyssa/conversations/{conversation['id']}/messages",
            headers={"Idempotency-Key": f"predeploy-turn-{run}-{index}"},
            json={"message": prompt},
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()["data"]
        if result["type"] != outcome:
            raise RuntimeError(f"turn {index + 1} returned {result['type']}, expected {outcome}")
        if any(not item["policy_id"].startswith("PAY-") for item in result.get("citations", [])):
            raise RuntimeError(f"turn {index + 1} returned a wrong-topic citation")
    print("PREDEPLOY_DIALOGUE=PASS")


if __name__ == "__main__":
    main()
