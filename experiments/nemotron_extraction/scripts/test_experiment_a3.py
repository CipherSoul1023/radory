"""Offline checks for A3's frozen real-evidence configuration and gate."""

from __future__ import annotations

from run_experiment_a import response_format as a1_response_format
from run_experiment_a3 import (
    ARM,
    load_configuration,
    response_format,
    without_patterns,
)


def test_a3_uses_exact_experiment_a_cases_and_4096_budget():
    config, parent = load_configuration()
    assert len(parent["cases"]) == config["max_live_calls"] == 16
    assert config["arm"] == ARM
    assert config["max_tokens"] == 4096
    assert config["retries"] == 0


def test_a3_schema_differs_from_a1_only_by_pattern_keywords():
    current = a1_response_format()
    changed = response_format()
    assert current != changed
    assert without_patterns(current) == changed
    assert "pattern" in str(current)
    assert "pattern" not in str(changed)


def test_a3_acceptance_gate_is_not_weaker_than_experiment_a():
    config, parent = load_configuration()
    acceptance = config["acceptance"]
    prior = parent["acceptance_per_arm"]
    assert acceptance["typed_schema"] == prior["typed_schema_min"] == 16
    assert acceptance["backend_valid_min"] == prior["backend_valid_min"] == 15
    assert acceptance["truncations_max"] == prior["truncations_max"] == 0
    assert acceptance["backend_valid_controls"] == prior["valid_controls_min"] == 6
    assert acceptance["character_collapse_cases_max"] == 0
    assert acceptance["character_collapse_occurrences_max"] == 0
