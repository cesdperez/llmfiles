import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "qa-lock.sh"


class QaLockTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.lock = Path(self.home.name) / ".cache/fullsend/qa.lock"

    def tearDown(self):
        self.home.cleanup()

    def qa(self, *args, timeout=10):
        env = {**os.environ, "HOME": self.home.name, "QA_LOCK_POLL_SECONDS": "0.1"}
        return subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True,
                              text=True, timeout=timeout)

    def take(self, label):
        result = self.qa("take", label)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def age_owner(self, seconds):
        past = time.time() - seconds
        os.utime(self.lock / "owner", (past, past))

    def test_token_is_one_word_so_an_unquoted_token_survives_word_splitting(self):
        token = self.take("test/e2e wait")
        self.assertEqual(token.split(), [token])

    def test_release_frees_the_lock(self):
        token = self.take("a")
        self.assertEqual(self.qa("release", token).returncode, 0)
        self.assertFalse(self.lock.exists())

    def test_release_with_another_token_fails_loudly_and_keeps_the_lock(self):
        token = self.take("a")
        result = self.qa("release", "a:1:2")
        self.assertEqual(result.returncode, 1)
        self.assertIn(token, result.stderr)
        self.assertTrue(self.lock.exists())

    def test_release_with_a_split_token_is_a_usage_error(self):
        self.take("a")
        result = self.qa("release", "12024", "1795865249")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(self.lock.exists())

    def test_release_of_a_free_lock_succeeds_so_a_second_release_is_harmless(self):
        token = self.take("a")
        self.qa("release", token)
        self.assertEqual(self.qa("release", token).returncode, 0)

    def test_touch_with_another_token_fails_loudly(self):
        self.take("a")
        result = self.qa("touch", "a:1:2")
        self.assertEqual(result.returncode, 1)
        self.assertIn("qa-lock", result.stderr)

    def test_take_for_the_holding_label_returns_the_held_token(self):
        token = self.take("feature/x")
        self.assertEqual(self.take("feature/x"), token)

    def test_run_for_the_holding_label_runs_under_the_held_lock(self):
        token = self.take("feature/x")
        result = self.qa("run", "feature/x", "--", "sh", "-c", "exit 3")
        self.assertEqual(result.returncode, 3)
        self.assertEqual((self.lock / "owner").read_text().strip(), token)

    def test_run_releases_and_returns_the_command_code(self):
        result = self.qa("run", "a", "--", "sh", "-c", "exit 4")
        self.assertEqual(result.returncode, 4)
        self.assertFalse(self.lock.exists())

    def test_run_waits_for_another_label(self):
        self.take("a")
        with self.assertRaises(subprocess.TimeoutExpired):
            self.qa("run", "b", "--", "true", timeout=1)

    def test_a_run_whose_process_died_is_cleared_at_once(self):
        self.lock.mkdir(parents=True)
        (self.lock / "owner").write_text("a:999999:1\n")
        (self.lock / "pid").write_text("999999\n")
        self.assertEqual(self.qa("run", "b", "--", "true", timeout=5).returncode, 0)

    def test_a_span_untouched_for_over_an_hour_is_cleared(self):
        self.take("a")
        self.age_owner(3700)
        self.assertEqual(self.qa("run", "b", "--", "true", timeout=5).returncode, 0)

    def test_a_lock_without_owner_from_a_take_killed_mid_way_is_cleared(self):
        self.lock.mkdir(parents=True)
        past = time.time() - 120
        os.utime(self.lock, (past, past))
        self.assertEqual(self.qa("run", "b", "--", "true", timeout=5).returncode, 0)

    def test_status_names_the_holder(self):
        token = self.take("a")
        result = self.qa("status")
        self.assertEqual(result.returncode, 0)
        self.assertIn(token, result.stdout)

    def test_status_of_a_free_lock(self):
        self.assertIn("free", self.qa("status").stdout)

    def test_a_killed_run_leaves_no_heartbeat_that_keeps_the_lock_fresh(self):
        env = {**os.environ, "HOME": self.home.name, "QA_LOCK_BEAT_SECONDS": "0.2"}
        proc = subprocess.Popen(["bash", str(SCRIPT), "run", "a", "--", "sleep", "3"], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 5
        while not (self.lock / "owner").exists() and time.time() < deadline:
            time.sleep(0.05)
        proc.kill()
        proc.wait()
        time.sleep(0.5)
        self.age_owner(3700)
        time.sleep(0.6)
        self.assertGreater(time.time() - (self.lock / "owner").stat().st_mtime, 3000)


if __name__ == "__main__":
    unittest.main()
