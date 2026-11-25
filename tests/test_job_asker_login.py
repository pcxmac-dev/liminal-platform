"""A job's thread runs as the person who asked for it (item 21: the asking login is each thread's own)."""
from __future__ import annotations

import threading

import pytest

apps = pytest.importorskip("liminal_libs.apps")
if not hasattr(apps, "as_user"):
    pytest.skip("a library before 1.88.0", allow_module_level=True)

from liminal_platform import app as app_module  # noqa: E402


def test_a_job_started_by_a_person_runs_as_them_in_its_own_thread():
    person, seen = object(), []
    with apps.as_user(person):
        run = app_module._handed(lambda: seen.append(apps.asking_login()))
    t = threading.Thread(target=run)
    t.start()
    t.join(5)
    assert seen == [person]  # not the thread's own (none) nor the platform's


def test_with_no_one_asking_the_job_runs_as_before():
    seen = []
    run = app_module._handed(lambda: seen.append(apps.asking_login()))
    t = threading.Thread(target=run)
    t.start()
    t.join(5)
    assert seen == [None]
