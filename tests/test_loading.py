"""0.21.0 (the user, 2026-11-11: "when starting platform there is a long pause before anything is visible, there needs
instead to be a way that all plugins pop in to existance after loading, and that perhaps the main icon/page should show
loading status"): the page drawn at once from an overview that asks no plugin anything, then each plugin asked on its
own, a slow one holding no other back, the tray following each answer; the page's script and styles carry the loading
status. Stand-in plugins on a free port: nothing of this machine is asked."""
from __future__ import annotations

import threading

from conftest import Box, Wall, _port
from test_app import Bot, _call

from liminal_platform.app import PlatformApp


class Counted(Box):
    """A box that counts what it is asked, and is valid or not as the test says."""

    name = "counted"
    title = "A counted box"
    ICON = "docker"

    def __init__(self):
        super().__init__()
        self.asked: list[str] = []
        self.valid = True

    def present(self) -> bool:
        self.asked.append("present")
        return True

    def status(self) -> dict:
        self.asked.append("status")
        st = super().status()
        return st if self.valid else {**st, "valid": False, "why": "the test says it is not"}


class Slow(Box):
    """A box whose status waits until the test lets it go."""

    name = "slow"
    title = "A slow box"

    def __init__(self):
        super().__init__()
        self.began, self.go = threading.Event(), threading.Event()

    def status(self) -> dict:
        self.began.set()
        assert self.go.wait(10), "the test never let the slow box go"
        return super().status()


def test_the_overview_answers_at_once_and_asks_no_plugin():
    counted, bot = Counted(), Bot()
    app = PlatformApp(log=lambda m: None, machines={"counted": counted, "wall": Wall()}, assistants={"bot": bot}, settings=lambda: object())
    port = _port(app.start(0))
    try:
        status, ov = _call(port, "GET", "/api/overview")
        assert status == 200 and counted.asked == []  # neither its status nor whether it is present
        assert ov["app"]["app"] == "platform" and ov["app"]["icon"] == "chip" and ov["machine"]["cpus"] >= 1 and ov["disabled"] == []
        assert [(p["name"], p["kind"], p["icon"], p["enabled"], p["hidden"], p["state"]) for p in ov["plugins"]] == [
            ("counted", "machine", "docker", True, False, None), ("wall", "machine", "shield", True, False, None),
            ("bot", "assistant", "copilot", True, False, None)]  # the machines, then the assistants: the list's order
        first = ov["plugins"][0]
        assert (first["title"], first["about"]) == ("A counted box", "a stand-in machine with Docker inside") and "version" in first
        # each asked on its own: its state is in the next overview, still without asking anything
        assert _call(port, "GET", "/api/machines/counted")[1]["state"] == "active" and counted.asked == ["status"]
        assert _call(port, "GET", "/api/assistants")[1]["assistants"][0]["state"] == "invalid"  # no key
        states = {p["name"]: p["state"] for p in _call(port, "GET", "/api/overview")[1]["plugins"]}
        assert states == {"counted": "active", "wall": None, "bot": "invalid"} and counted.asked == ["status"]
        # one disabled, one hidden: said by the overview, the disabled one in its state whatever it was found in
        assert _call(port, "POST", "/api/plugins/counted/enabled", {"on": False})[0] == 200
        assert _call(port, "POST", "/api/plugins/wall/hidden", {"on": True})[0] == 200
        asked = list(counted.asked)
        ov = _call(port, "GET", "/api/overview")[1]
        by = {p["name"]: p for p in ov["plugins"]}
        assert ov["disabled"] == ["counted"] and (by["counted"]["enabled"], by["counted"]["state"]) == (False, "disabled")
        assert by["wall"]["hidden"] is True and counted.asked == asked
    finally:
        app.stop()


def test_the_parts_of_the_whole_status_are_asked_on_their_own(served):
    app, port, lines, box = served
    whole = _call(port, "GET", "/api/status")[1]
    assert _call(port, "GET", "/api/docker") == (200, whole["docker"])  # no Docker here, as the fixture says
    assert _call(port, "GET", "/api/assistants") == (200, {"assistants": []})
    assert _call(port, "GET", "/api/instances") == (200, {"instances": whole["instances"]})
    assert _call(port, "GET", "/api/machines/box")[1] == whole["machines"]["box"]
    ov = _call(port, "GET", "/api/overview")[1]
    assert (ov["app"], ov["machine"]["host"]) == (whole["app"], whole["machine"]["host"])
    assert [p["name"] for p in ov["plugins"]] == list(whole["machines"]) and all(p["state"] == "active" for p in ov["plugins"])


def test_a_slow_plugin_holds_no_other_back():
    slow = Slow()
    app = PlatformApp(log=lambda m: None, machines={"slow": slow, "box": Box()}, assistants={})
    port = _port(app.start(0))
    got: dict = {}
    asking = threading.Thread(target=lambda: got.update(slow=_call(port, "GET", "/api/machines/slow")), daemon=True)
    try:
        asking.start()
        assert slow.began.wait(5)  # the slow one is being asked now
        assert _call(port, "GET", "/api/overview")[0] == 200
        assert _call(port, "GET", "/api/machines/box")[1]["state"] == "active"
        assert _call(port, "GET", "/api/tray")[0] == 200 and "slow" not in got  # all answered while it still waits
    finally:
        slow.go.set()
        asking.join(5)
        app.stop()
    assert got["slow"][0] == 200 and got["slow"][1]["state"] == "active"


def test_the_tray_follows_a_plugin_asked_on_its_own():
    """Until 0.21.0 the page asked the whole status, which set the tray's active plugins anew; asked one at a time, each
    answer moves its plugin in or out of the tray at once, not after ACTIVE_SECONDS."""
    counted = Counted()
    app = PlatformApp(log=lambda m: None, machines={"counted": counted, "wall": Wall()}, assistants={})
    port = _port(app.start(0))
    tray = lambda: [i["id"] for i in _call(port, "GET", "/api/tray")[1]["items"]]  # noqa: E731
    try:
        assert tray() == ["platform", "counted", "wall"]  # both present: asked once, kept a minute
        counted.valid = False
        assert _call(port, "GET", "/api/machines/counted")[1]["state"] == "invalid"
        assert tray() == ["platform", "wall"]
        counted.valid = True
        assert _call(port, "GET", "/api/machines/counted")[1]["state"] == "active"
        assert tray() == ["platform", "counted", "wall"]  # back in its place, before the wall
        assert counted.asked.count("present") == 1  # the tray never asked it again meanwhile
    finally:
        app.stop()


def test_the_page_draws_at_once_and_says_what_it_is_loading(served):
    app, port, lines, box = served
    js, css = _call(port, "GET", "/platform.js")[1], _call(port, "GET", "/platform.css")[1]
    # the overview first, then each part on its own; a platform started before 0.21.0 (no overview: 404) the old way
    for part in (b"api('GET', 'api/overview')", b"api('GET', `api/machines/${enc(name)}`)", b"api('GET', 'api/assistants')",
                 b"rest('api/docker'", b"rest('api/instances'", b"if (e.status === 404) return renderWhole(g);",
                 b"Promise.all([api('GET', 'api/status'), api('GET', 'api/tray')])"):
        assert part in js, part
    assert js.index(b"api('GET', 'api/overview')") < js.index(b"api('GET', `api/machines/${enc(name)}`)")
    # one not answered yet keeps its place, said loading; the chip's ring and the list's line count the answers
    for part in (b"pending: true", b"' pending'", b"class=\"chip wait\">loading<", b"id=\"loading-line\" role=\"status\"",
                 b"chip.classList.toggle('loading', !!loading)", b"chip.style.setProperty('--p'", b"Loading plugins", b"animation-delay:-"):
        assert part in js, part
    for part in (b".app-list .item.pending", b"@keyframes pop-in", b"#rail button.pop", b"#rail button.master.loading::after",
                 b"conic-gradient(var(--accent) calc(var(--p, 0) * 1%)", b".loading-line .bar > span"):
        assert part in css, part
    # nothing moves for a reader who asked for no motion
    reduced = css[css.rindex(b"@media (prefers-reduced-motion: reduce)"):]
    assert b"#rail button.pop" in reduced and b"#rail button.master.loading svg" in reduced and b"animation: none" in reduced
