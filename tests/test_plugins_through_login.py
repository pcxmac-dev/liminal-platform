"""The plugins switched off and hidden, a preference of the platform's signed-in user (0.34.4; Monday list item 21; the
user, 2026-11-19: "preferences, keys, licenses all get stored in the individual's login db"): kept as the pair
`platform-plugins` of a login that keeps them (a stand-in here), never written to plugins.json then; an EnvironmentLogin
keeps none, so plugins.json as before; the file's switches copied into the user's store once, the file left as it was.
Nothing started."""
from __future__ import annotations

import json

from conftest import Box, Wall
from liminal_libs.apps import EnvironmentLogin, Login, Unauthorized

from liminal_platform.app import PLUGINS_FILE, PLUGINS_PAIR, PlatformApp


class StoreLogin(Login):
    """A stand-in for the login app's session: one user's pairs in a dict."""

    keeps_settings = True

    def __init__(self, name: str = "ada"):
        self.name, self.pairs = name, {}

    def user(self) -> dict:
        return {"name": self.name}

    def vector(self, name: str) -> str:
        raise Unauthorized("no such pair", 404)

    def setting(self, name: str):
        return json.loads(self.pairs[name][1]) if name in self.pairs else None

    def keep_setting(self, name, value, kind="preference", label=""):
        self.pairs[name] = (kind, json.dumps(value))
        return {"name": name, "kind": kind}


def _app(tmp_path, login):
    return PlatformApp(log=lambda m: None, login=login, machines={"box": Box(), "wall": Wall()}, assistants={},
                       state=tmp_path)


def test_the_switches_are_kept_in_the_signed_in_users_store(tmp_path):
    ada = StoreLogin()
    app = _app(tmp_path, ada)
    app.set_enabled("wall", False)
    app.set_hidden("box", True)
    assert ada.pairs[PLUGINS_PAIR] == ("preference", json.dumps({"disabled": ["wall"], "hidden": ["box"]}))
    assert not (tmp_path / PLUGINS_FILE).exists()  # never the file then
    again = _app(tmp_path, ada)  # a restart, the same user signed in
    assert again.disabled() == {"wall"} and again.hidden() == {"box"}
    assert _app(tmp_path, StoreLogin("bob")).disabled() == set()  # another user's own (none)


def test_an_environment_login_keeps_none_so_plugins_json_as_before(tmp_path):
    app = _app(tmp_path, EnvironmentLogin(env={}))
    app.set_enabled("wall", False)
    assert json.loads((tmp_path / PLUGINS_FILE).read_text(encoding="utf-8")) == {"disabled": ["wall"], "hidden": []}
    assert _app(tmp_path, EnvironmentLogin(env={})).disabled() == {"wall"}


def test_the_files_switches_move_into_the_users_store_once(tmp_path):
    (tmp_path / PLUGINS_FILE).write_text(json.dumps({"disabled": ["box"], "hidden": ["wall"]}), encoding="utf-8")
    ada = StoreLogin()
    app = _app(tmp_path, ada)
    assert app.disabled() == {"box"} and app.hidden() == {"wall"}
    assert json.loads(ada.pairs[PLUGINS_PAIR][1]) == {"disabled": ["box"], "hidden": ["wall"]}
    app.set_enabled("box", True)
    assert json.loads(ada.pairs[PLUGINS_PAIR][1]) == {"disabled": [], "hidden": ["wall"]}
    assert json.loads((tmp_path / PLUGINS_FILE).read_text(encoding="utf-8")) == {"disabled": ["box"], "hidden": ["wall"]}
    assert _app(tmp_path, ada).disabled() == set()  # hers from then on, not the file's


def test_a_store_that_refuses_falls_back_to_the_file(tmp_path):
    class Down(StoreLogin):
        def setting(self, name):
            raise Unauthorized("no login app answers", 503)

        def keep_setting(self, name, value, kind="preference", label=""):
            raise Unauthorized("no login app answers", 503)

    app = _app(tmp_path, Down())
    app.set_enabled("wall", False)
    assert json.loads((tmp_path / PLUGINS_FILE).read_text(encoding="utf-8"))["disabled"] == ["wall"]
