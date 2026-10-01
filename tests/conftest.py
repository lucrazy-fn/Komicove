"""Keep the test suite isolated from the user's real Komicove data."""

import os
import shutil
import tempfile


_TEST_APPDATA = tempfile.mkdtemp(prefix="komicove-tests-")
os.environ.setdefault("KOMICOVE_APPDATA_DIR", _TEST_APPDATA)


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_APPDATA, ignore_errors=True)
