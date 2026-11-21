"""Quality gate: counts only distinct, fully passed gate IDs; any failure fails it."""

import subprocess
import sys

import pytest

from qe.config import PROJECT_ROOT
from qe.gate import evaluate_junit

pytestmark = pytest.mark.unit


def case(name, gate_id=None, outcome="passed"):
    props = f'<properties><property name="gate_id" value="{gate_id}"/></properties>' if gate_id else ""
    body = {
        "passed": "",
        "failed": '<failure message="boom">trace</failure>',
        "error": '<error message="boom">trace</error>',
        "skipped": '<skipped type="pytest.skip" message="no backend"/>',
        "xfail": '<skipped type="pytest.xfail" message="known"/>',
    }[outcome]
    return f'<testcase classname="tests.api" name="{name}">{props}{body}</testcase>'


def report(*cases):
    return f'<testsuites><testsuite name="pytest">{"".join(cases)}</testsuite></testsuites>'


def eight_passing():
    return [case(f"t{i}", f"API-{i:02d}") for i in range(1, 9)]


def test_eight_distinct_passed_ids_pass_the_gate():
    r = evaluate_junit(report(*eight_passing()))
    assert r.ok and len(r.passed_ids) == 8


def test_seven_passed_ids_fail_the_gate():
    r = evaluate_junit(report(*eight_passing()[:7]))
    assert not r.ok and len(r.passed_ids) == 7


def test_parametrized_expansions_count_once():
    cases = [case(f"t[{i}]", "API-08") for i in range(5)] + eight_passing()[:7]
    r = evaluate_junit(report(*cases))
    assert len(r.passed_ids) == 8 and r.ok


def test_one_failing_expansion_disqualifies_the_id_and_fails_the_gate():
    cases = eight_passing() + [case("t8[b]", "API-08", "failed")]
    r = evaluate_junit(report(*cases))
    assert "API-08" in r.failed_ids and "API-08" not in r.passed_ids
    assert not r.ok


@pytest.mark.parametrize("outcome", ["skipped", "xfail"])
def test_skipped_and_xfailed_ids_never_count(outcome):
    cases = eight_passing()[:7] + [case("t8", "API-08", outcome)]
    r = evaluate_junit(report(*cases))
    assert r.skipped_ids == {"API-08"} and not r.ok


@pytest.mark.parametrize("outcome", ["failed", "error"])
def test_failure_in_a_non_gate_test_still_fails_the_gate(outcome):
    r = evaluate_junit(report(*eight_passing(), case("t_other", None, outcome)))
    assert len(r.passed_ids) == 8 and not r.ok
    assert r.failures == ["tests.api::t_other"]


# --- end to end: real pytest run → JUnit XML → gate -----------------------------------

INNER_TESTS = """
import pytest

{gate_tests}

@pytest.mark.gate("UI-99")
def test_skipped_gate():
    pytest.skip("frontend not running")
"""


def run_inner(pytester, source):
    pytester.makepyfile(test_inner=source)
    junit = pytester.path / "junit.xml"
    # The inner run shares this process; pytest-playwright keeps global soft-assertion
    # state and can't be loaded twice, so disable it for the inner session only.
    result = pytester.runpytest(
        "-p", "no:playwright", "-p", "qe.pytest_plugin", "-o", "junit_family=xunit1", f"--junitxml={junit}"
    )
    return result, junit


def test_plugin_records_gate_ids_that_the_gate_then_counts(pytester):
    gate_tests = "\n".join(
        f'@pytest.mark.gate("API-{i:02d}")\ndef test_g{i}():\n    assert {i} == {i}\n' for i in range(1, 9)
    )
    result, junit = run_inner(pytester, INNER_TESTS.format(gate_tests=gate_tests))
    result.assert_outcomes(passed=8, skipped=1)
    r = evaluate_junit(junit.read_text())
    assert r.ok
    assert r.passed_ids == {f"API-{i:02d}" for i in range(1, 9)}
    assert r.skipped_ids == {"UI-99"}


@pytest.mark.parametrize("marker", ['@pytest.mark.gate()', '@pytest.mark.gate("api-1")', '@pytest.mark.gate("A-01", "B-02")'])
def test_plugin_rejects_malformed_gate_markers(pytester, marker):
    result, _ = run_inner(pytester, f"import pytest\n{marker}\ndef test_x():\n    pass\n")
    assert result.ret == pytest.ExitCode.USAGE_ERROR


def test_cli_exit_codes(tmp_path):
    script = PROJECT_ROOT / "scripts" / "check_gate.py"
    good, bad = tmp_path / "good.xml", tmp_path / "bad.xml"
    good.write_text(report(*eight_passing()))
    bad.write_text(report(*eight_passing()[:3]))

    def run(*args):
        return subprocess.run(
            [sys.executable, str(script), *map(str, args)], capture_output=True, text=True, timeout=30, check=False
        )

    ok = run(good)
    assert ok.returncode == 0 and "gate: PASS" in ok.stdout
    assert run(bad).returncode == 1
    assert run(bad, "--min", "3").returncode == 0
    missing = run(tmp_path / "nope.xml")
    assert missing.returncode == 1 and "report not found" in missing.stdout
