"""0.31.0 (the user, 2026-11-16: "i need 3 plugins for inference serving local models on the platform, :: lama.cpp,
ollama and vLLM, i also need 3 harness plugins for the platform :: OpenCode, Aider, and Continue"; "they will be
classified as AI plugins"; "the other plugins are strictly proprietary service plugins"): a machine plugin whose SECTION
is "ai" says its group beside it (liminal-libs 1.62.0's AiPlugin.GROUP: "inference" for a model server's, "harness" for
a coding harness's). The overview's row and the status carry both, so the page's list draws one AI heading: the
assistants (the proprietary services), then a group for each. The tray puts their icons after the assistants', the
model servers before the harnesses. "ai" with a group the platform does not draw, or with none, is a machine plugin, as
any section it does not know is.

Stand-in plugins asked of the app itself: nothing is served, no port is opened, no process is started (conftest's
no_outside fails a test that does), and this machine's facts are a stand-in's."""
from __future__ import annotations

import pytest

from conftest import Box
from conftest import api_answer as _ask
from test_app import Bot

import liminal_platform.app as app_module
from liminal_platform.app import AI_GROUPS, AI_SECTION, SECTIONS, PlatformApp, group_of, section_of

pytestmark = pytest.mark.usefixtures("no_outside")


@pytest.fixture(autouse=True)
def facts_of_a_stand_in(monkeypatch):
    """This machine's facts are a stand-in's: on Linux Python reads the processor's name by running `uname -p`."""
    monkeypatch.setattr(app_module, "facts", lambda: {"system": "Stand-in", "cpus": 1, "host": "a stand-in"})


class Server(Box):
    """A stand-in model server's plugin."""

    name = "server"
    title = "A model server"
    ICON = "ollama"
    SECTION = "ai"
    GROUP = "inference"


class Second(Server):
    """Another model server's: within a group the registry's order is kept."""

    name = "second"
    title = "Another model server"
    ICON = "vllm"


class Coder(Box):
    """A stand-in coding harness's plugin."""

    name = "coder"
    title = "A coding harness"
    ICON = "opencode"
    SECTION = "ai"
    GROUP = "harness"


class Stray(Box):
    """A plugin of the AI section naming a group the platform does not draw."""

    name = "stray"
    title = "A stray box"
    SECTION = "ai"
    GROUP = "elsewhere"


class Bare(Box):
    """A plugin of the AI section naming no group at all."""

    name = "bare"
    title = "A bare box"
    SECTION = "ai"


class Grouped(Box):
    """A plugin naming one of the AI section's groups from outside it."""

    name = "grouped"
    title = "A grouped box"
    SECTION = "cloud"
    GROUP = "inference"


def _tray(app) -> list[tuple[str, str]]:
    return [(i["id"], i["icon"]) for i in _ask(app, "GET", "/api/tray")[1]["items"]]


def test_an_ai_plugin_says_its_group_and_ai_without_one_is_a_machine_plugin():
    assert AI_SECTION == "ai" and AI_GROUPS == ("inference", "harness")
    assert SECTIONS == ("machine", "virtualization", "os", "cloud")  # the four stay: AI is no fifth among them
    said = [(section_of(p), group_of(p)) for p in (Server(), Second(), Coder(), Stray(), Bare(), Grouped(), Box())]
    assert said == [("ai", "inference"), ("ai", "inference"), ("ai", "harness"), ("machine", ""), ("machine", ""),
                    ("cloud", ""), ("machine", "")]
    assert group_of(Bot()) == "" and group_of(object()) == ""  # an assistant; an older library's plugin, with no GROUP

    class Odd(Box):
        SECTION = "ai"
        GROUP = ("inference",)  # not a word

    assert (section_of(Odd()), group_of(Odd())) == ("machine", "")


def test_the_overview_and_each_status_carry_the_section_and_the_group():
    machines = {"box": Box(), "coder": Coder(), "grouped": Grouped(), "second": Second(), "server": Server(),
                "stray": Stray()}
    app = PlatformApp(log=lambda m: None, machines=machines, assistants={"bot": Bot()}, settings=lambda: object())
    try:
        status, ov = _ask(app, "GET", "/api/overview")
        assert status == 200 and [(p["name"], p["kind"], p["section"], p["group"]) for p in ov["plugins"]] == [
            ("box", "machine", "machine", ""), ("coder", "machine", "ai", "harness"),
            ("grouped", "machine", "cloud", ""),  # a group named from outside the AI section: none
            ("second", "machine", "ai", "inference"), ("server", "machine", "ai", "inference"),
            ("stray", "machine", "machine", ""),  # "ai" with a group the platform does not draw: Machine plugins
            ("bot", "assistant", "assistant", "")]  # an assistant's section is its kind, and it names no group
        for name, section, group in (("server", "ai", "inference"), ("coder", "ai", "harness"),
                                     ("stray", "machine", ""), ("grouped", "cloud", ""), ("box", "machine", "")):
            m = _ask(app, "GET", f"/api/machines/{name}")[1]
            assert (m["section"], m["group"], m["state"]) == (section, group, "active"), name
        whole = _ask(app, "GET", "/api/status")[1]["machines"]
        assert {n: (m["section"], m["group"]) for n, m in whole.items()} == {
            "box": ("machine", ""), "coder": ("ai", "harness"), "grouped": ("cloud", ""), "second": ("ai", "inference"),
            "server": ("ai", "inference"), "stray": ("machine", "")}
        off = _ask(app, "POST", "/api/plugins/server/enabled", {"on": False})[1]  # disabled: said all the same
        assert (off["state"], off["section"], off["group"]) == ("disabled", "ai", "inference")
        bots = _ask(app, "GET", "/api/assistants")[1]["assistants"]
        assert "group" not in bots[0]  # an assistant's own status says none: its kind is its place, as it was
    finally:
        app.stop()


def test_the_tray_puts_the_ai_plugins_after_the_assistants_the_model_servers_before_the_harnesses():
    bot = Bot()
    bot.key = True  # a key and a plan with API access: active
    machines = {"coder": Coder(), "box": Box(), "second": Second(), "stray": Stray(), "server": Server()}
    app = PlatformApp(log=lambda m: None, machines=machines, assistants={"bot": bot}, settings=lambda: object())
    try:
        # the machine plugins not of the AI section, the assistants, then the model servers and the harnesses, each
        # group in the registry's order (the order the machines are given in)
        assert _tray(app) == [("platform", "chip"), ("box", "chip"), ("stray", "chip"), ("bot", "copilot"),
                              ("second", "vllm"), ("server", "ollama"), ("coder", "opencode")]
        assert [(i.id, i.kind, i.app) for i in app.items()][-1] == ("coder", "plugin", "platform")
        assert app.active() == ["coder", "box", "second", "stray", "server"]  # which are active: one order, as before
        # hidden, disabled or not valid, one of them leaves the tray as any plugin does; the rest keep their places
        assert _ask(app, "POST", "/api/plugins/server/hidden", {"on": True})[0] == 200
        assert _tray(app)[4:] == [("second", "vllm"), ("coder", "opencode")]
        assert _ask(app, "POST", "/api/plugins/server/hidden", {"on": False})[0] == 200
        assert _ask(app, "POST", "/api/plugins/second/enabled", {"on": False})[0] == 200
        assert _tray(app)[4:] == [("server", "ollama"), ("coder", "opencode")]
        machines["coder"].status = lambda: {"present": False, "valid": False, "why": "nothing is installed yet"}
        assert _ask(app, "GET", "/api/machines/coder")[1]["state"] == "invalid"
        assert _tray(app) == [("platform", "chip"), ("box", "chip"), ("stray", "chip"), ("bot", "copilot"),
                              ("server", "ollama")]
        bot.key = False  # no assistant active: the AI machine plugins still come last
        assert _ask(app, "GET", "/api/assistants")[1]["assistants"][0]["state"] == "invalid"
        assert _tray(app) == [("platform", "chip"), ("box", "chip"), ("stray", "chip"), ("server", "ollama")]
    finally:
        app.stop()


def test_without_an_ai_plugin_the_tray_is_as_it_was():
    bot = Bot()
    bot.key = True
    app = PlatformApp(log=lambda m: None, machines={"box": Box(), "stray": Stray()}, assistants={"bot": bot},
                      settings=lambda: object())
    try:
        assert _tray(app) == [("platform", "chip"), ("box", "chip"), ("stray", "chip"), ("bot", "copilot")]
    finally:
        app.stop()
