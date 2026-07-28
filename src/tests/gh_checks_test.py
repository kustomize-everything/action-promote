import os
import subprocess
import unittest

# gh-checks.sh lives one directory up from this test (src/gh-checks.sh).
SCRIPT = os.path.join(os.path.dirname(__file__), "..", "gh-checks.sh")


def classify(output: str) -> str:
    """Source gh-checks.sh and run pr_checks_state on the given output."""
    result = subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}"; pr_checks_state "$1"', "_", output],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class TestPrChecksState(unittest.TestCase):
    def test_no_checks_reported_proceeds(self):
        # gh prints this when a PR has no status checks. It must NOT be treated
        # as pending -- that is the bug that hung auto-merge and failed
        # promotions on repos whose promotion branch has no checks.
        out = "no checks reported on the 'promotion-foo-bar' branch"
        self.assertEqual(classify(out), "proceed")

    def test_pending_waits(self):
        out = "build\tpending\t0\thttps://example.test/checks"
        self.assertEqual(classify(out), "pending")

    def test_in_progress_waits(self):
        out = "e2e\tin progress\t0\thttps://example.test/checks"
        self.assertEqual(classify(out), "pending")

    def test_all_passed_proceeds(self):
        out = "build\tpass\t12s\thttps://example.test/checks"
        self.assertEqual(classify(out), "proceed")

    def test_empty_proceeds(self):
        self.assertEqual(classify(""), "proceed")


if __name__ == "__main__":
    unittest.main()
