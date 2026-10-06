"""Keep the test suite isolated from the user's real Komicove data."""

import os
import shutil
import tempfile


_TEST_APPDATA = tempfile.mkdtemp(prefix="komicove-tests-")
os.environ.setdefault("KOMICOVE_APPDATA_DIR", _TEST_APPDATA)
os.environ.setdefault("KOMICOVE_DATABASE_URL", "sqlite:///" + os.path.join(_TEST_APPDATA, "test-api.db").replace("\\", "/"))
os.environ.setdefault("KOMICOVE_GUIDED_AI", "0")  # Local models must not change deterministic fixtures.


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_APPDATA, ignore_errors=True)
