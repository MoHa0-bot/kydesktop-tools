import os
import threading
import time
import unittest

from kylinpkg.util import CancelToken, OperationCancelled, run


@unittest.skipUnless(os.name == "posix", "需要 POSIX 进程组")
class CancelTest(unittest.TestCase):
    def test_cancel_running_command(self):
        token = CancelToken()

        def cancel_later():
            time.sleep(0.2)
            token.cancel()

        thread = threading.Thread(target=cancel_later, daemon=True)
        thread.start()
        started = time.time()
        with self.assertRaises(OperationCancelled):
            run(["sleep", "10"], timeout=20, cancel=token)
        self.assertLess(time.time() - started, 5.0)

    def test_cancel_before_start(self):
        token = CancelToken()
        token.cancel()
        with self.assertRaises(OperationCancelled):
            run(["true"], cancel=token)

    def test_normal_command_still_works(self):
        proc = run(["sh", "-c", "echo ok"], cancel=CancelToken())
        self.assertEqual(proc.stdout.strip(), "ok")
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
