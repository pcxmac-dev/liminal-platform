"""What a plugin needs of this machine, and the platform's state of it (0.40.0; Monday list item 19, part two,
release 1: liminal-libs 1.103.0's needs.py and facts.py; the needs plan's revision 2, 3.7 and 3.12, with the user's
answers of 2026-11-25). The facts are recorded machines' (needs_machines, through facts.use): nothing of this machine is
read, nothing is started or reached, no plugin of this PC is asked."""
from __future__ import annotations

import copy
import threading

import pytest

from conftest import Box, api_answer
from test_app import Bot

from liminal_libs import facts, needs_machines
from liminal_libs.apps import EnvironmentLogin

import liminal_platform.app as app_module
from liminal_platform.app import INTERNET_PAIR, PlatformApp

pytestmark = pytest.mark.usefixtures("no_outside")  # nothing started, served or reached (tests/conftest.py)


class Row:
    """A stand-in row of the ledger (lifecycle.Row): its process's id and when it started."""

    def __init__(self, pid: int, started: int | None):
        self.pid, self.started = pid, started


class Counted(Box):
    """A stand-in machine plugin that counts what it is asked."""

    name, title, order = "counted", "Counted", 930

    def __init__(self):
        super().__init__()
        self.asked: list[str] = []
        self.elsewhere = ""

    def status(self):
        self.asked.append("status")
        return super().status()

    def present(self):
        self.asked.append("present")
        return True

    def not_for_here(self) -> str:
        self.asked.append("not_for_here")
        return self.elsewhere

    def check(self):
        self.asked.append("check")
        return {"ready": True}


class LinuxOnly(Counted):
    name, title = "linux-only", "Linux only"
    NEEDS = (("kernel", "linux", "required", "its Linux programs"),)


class ContainersOnly(Counted):
    name, title = "containers-only", "Containers only"
    NEEDS = (("kernel", "windows"), ("windows.feature", "Containers|Containers-DisposableClientVM", "required",
                                     "an edition whose Windows Features list either"))


class Online(Counted):
    name, title = "online", "Online"
    NEEDS = (("internet", "yes", "required", "reached over the internet"),)


class Windowsy(Counted):
    name, title = "windowsy", "Windowsy"
    NEEDS = (("kernel", "windows"), ("windows.build", ">= 26300", "required", "a Windows of 2026"))


class Elsewhere(Counted):
    """Not for this machine in its own words, with tables of elsewhere (as the Admin and Firewall bases answer)."""

    name, title = "elsewhere", "Elsewhere"

    def __init__(self):
        super().__init__()
        self.elsewhere = "Linux's firewall: this is Windows"

    def status(self):
        self.asked.append("status")
        return {"present": False, "applies": False, "why": self.elsewhere, "tables": [{"title": "elsewhere"}]}


class SaysNoApply(Counted):
    """No not_for_here(), but its status says it is not for this machine (applies: False)."""

    name, title = "says-no", "Says no"

    def status(self):
        self.asked.append("status")
        return {"present": False, "applies": False, "why": "only on a Mac"}


class Cloudbot(Bot):
    name, title = "cloudbot", "A cloud bot"
    NEEDS = (("internet", "yes", "required", "an AI service that answers over the internet"),)

    def __init__(self):
        super().__init__()
        self.key = True


def app_of(*plugins, assistants=None, login=None, settings=lambda: object()):
    return PlatformApp(log=lambda m: None, login=login, machines={p.name: p for p in plugins},
                       assistants=assistants or {}, settings=settings)


def machine(name: str, **changes) -> facts.StandIn:
    """A recorded machine's facts in place as this process's reader, changed where a test says so."""
    f = copy.deepcopy(needs_machines.facts_of(name))
    for key, value in changes.items():
        f[key] = value
    r = facts.StandIn(f)
    facts.use(r)
    return r


def offline_facts(apart: float = 30.0) -> dict:
    """this-pc's internet, two readings `apart` seconds apart saying no."""
    f = copy.deepcopy(needs_machines.facts_of("this-pc"))
    f["internet"].update({"state": "no", "readings": [[1000.0, "no"], [1000.0 + apart, "no"]]})
    return f


@pytest.fixture
def this_pc():
    return machine("this-pc")


# -- not for this machine: never attached, never asked ------------------------------------------------------------------
def test_a_plugin_not_for_this_machine_is_unmet_never_asked_and_never_attached(this_pc):
    p = LinuxOnly()
    app = app_of(p)
    assert app.attach_plugins([p]) == [] and app.plugin(p.name) is None  # item 38: never started
    answer = app.machine_status(p)
    assert answer["state"] == "unmet" and answer["valid"] is False and answer["enabled"] is True
    assert answer["needs"]["met"] is False and answer["needs"]["sort"] == "machine"
    assert answer["status"]["applies"] is False and answer["status"]["present"] is None  # an older page: notHere
    assert answer["status"]["summary"].startswith("not for this machine: ") and "Linux" in answer["why"]
    assert answer["asks"] == [] and answer["apiFacts"] == {}
    assert p.asked == ["not_for_here"] * p.asked.count("not_for_here")  # nothing but its words, which ask nothing
    assert app.plugin(p.name) is None and "linux-only" not in app.active(fresh=True)
    assert app.plugin_state(p.name)["state"] == "unmet"


def test_the_overview_judges_the_needs_and_asks_no_status(this_pc):
    p, w = LinuxOnly(), Windowsy()
    app = app_of(p, w)
    rows = {r["name"]: r for r in app.overview()["plugins"]}
    assert rows["linux-only"]["state"] == "unmet" and rows["linux-only"]["needs"]["met"] is False
    assert rows["windowsy"]["state"] is None and rows["windowsy"]["needs"]["met"] is True
    assert "status" not in p.asked and "status" not in w.asked and "present" not in p.asked  # the needs plan's M20


def test_its_own_words_ask_its_status_for_the_tables_of_elsewhere(this_pc):
    p = Elsewhere()
    app = app_of(p)
    answer = app.machine_status(p)
    assert answer["state"] == "unmet" and answer["needs"]["sort"] == "machine"
    assert "status" in p.asked and answer["status"]["tables"] == [{"title": "elsewhere"}]
    assert answer["needs"]["rows"][0]["said"] == p.elsewhere


def test_a_status_that_says_it_does_not_apply_is_one_need_of_the_machine(this_pc):
    p = SaysNoApply()
    app = app_of(p)
    answer = app.machine_status(p)
    assert answer["state"] == "unmet" and answer["needs"]["sort"] == "machine" and "only on a Mac" in answer["why"]
    assert answer["status"]["applies"] is False
    with pytest.raises(app_module.Refused) as e:
        app.check(p.name)
    assert e.value.status == 409 and "not for this machine" in e.value.reason


def test_a_status_that_says_it_does_not_apply_stays_unmet_read_after_read(this_pc):
    p = SaysNoApply()
    app = app_of(p)
    for _ in range(3):  # each read the same: never 'invalid' between (the review of 0.40.0)
        answer = app.machine_status(p)
        assert answer["state"] == "unmet" and answer["needs"]["sort"] == "machine" and "only on a Mac" in answer["why"]
        assert answer["status"]["applies"] is False
    assert p.name in app._unmet and p.name not in app._invalid


def test_a_status_that_no_longer_says_it_does_not_apply_comes_back(this_pc):
    p = SaysNoApply()
    app = app_of(p)
    assert app.machine_status(p)["state"] == "unmet"
    p.status = lambda: {"present": True}
    answer = app.machine_status(p)
    assert answer["state"] == "active" and answer["needs"]["met"] is not False


def test_a_need_of_the_moment_asks_nothing_and_says_how(this_pc):
    p = ContainersOnly()  # this PC's Containers and Windows Sandbox are off (map-facts, 2026-11-17)
    app = app_of(p)
    answer = app.machine_status(p)
    assert answer["state"] == "unmet" and answer["needs"]["sort"] == "moment"
    assert answer["status"] == {"present": None, "summary": f"not met now: {answer['needs']['why']}"}
    assert "status" not in p.asked and "applies" not in answer["status"]
    unmet = [r for r in answer["needs"]["rows"] if r["state"] == "unmet"]
    assert unmet and "Windows Features" in unmet[0]["how"]


def test_unmet_needs_refuse_every_new_ask_at_once(this_pc):
    p = ContainersOnly()
    app = app_of(p)
    for call in (lambda: app.ask(p.name, "status", []), lambda: app.check(p.name),
                 lambda: app.start_setup(p.name), lambda: app.start_hook_job(p.name, "pull", []),
                 lambda: app.open_terminal(p.name)):
        with pytest.raises(app_module.Refused) as e:
            call()
        assert e.value.status == 409 and "not met now" in e.value.reason
    assert "check" not in p.asked and p.setups == []


def test_a_plugin_whose_needs_are_met_is_as_before(this_pc):
    p = Windowsy()
    app = app_of(p)
    assert app.attach_plugins([p]) == ["windowsy"]
    answer = app.machine_status(p)
    assert answer["state"] == "active" and answer["needs"]["met"] is True and "status" in p.asked


def test_one_that_says_nothing_is_judged_by_its_status_as_before(this_pc):
    p = Counted()  # no NEEDS, no words
    app = app_of(p)
    answer = app.machine_status(p)
    assert answer["state"] == "active" and answer["needs"]["met"] is None and answer["needs"]["declared"] is False
    assert answer["needs"]["why"] == "It has not said what it needs yet"


def test_switched_off_it_is_disabled_and_its_needs_still_said(this_pc):
    p = LinuxOnly()
    app = app_of(p)
    app.set_enabled(p.name, False)
    answer = app.machine_status(p)
    assert answer["state"] == "disabled" and answer["needs"]["met"] is False  # the user's answer 6: out either way


# -- the features' read waits at the attach ----------------------------------------------------------------------------
def test_the_attach_reads_the_features_first_and_waits_for_them(this_pc):
    p, w = ContainersOnly(), Windowsy()
    app = app_of(p, w)
    order: list[str] = []
    this_pc.features_ready = lambda timeout=2.0: order.append(f"ready {timeout}") or True
    real = app._judged

    def judged(plugin, *a, **k):
        order.append(plugin.name)
        return real(plugin, *a, **k)

    app._judged = judged
    assert app.attach_plugins([p, w]) == ["windowsy"]  # Containers off: not attached
    assert this_pc.features_begun == ["Containers", "Containers-DisposableClientVM"]
    assert order == ["windowsy", f"ready {facts.FEATURES_WAIT_S}", "containers-only"]


# -- unmet once attached: nothing cut, let go once nothing of it runs (S13, M15) -----------------------------------------
def test_unmet_once_attached_is_let_go_only_after_its_job_and_its_processes(monkeypatch, this_pc):
    p = Windowsy()
    app = app_of(p)
    app.attach_plugins([p])
    gate, ran = threading.Event(), threading.Event()

    def setup(log=print, steps=None):
        ran.set()
        gate.wait(5)
        return [{"step": "slow", "ok": True}]

    p.setup = setup
    job = app.start_setup(p.name, ["slow"])
    assert ran.wait(5)
    mine = {"windowsy": [Row(4242, 77)]}
    monkeypatch.setattr(app_module.lifecycle, "mine", lambda owner=None: list(mine.get(owner, [])))
    monkeypatch.setattr(app_module.proc_mod, "pid_alive", lambda pid: pid == 4242)
    monkeypatch.setattr(app_module.proc_mod, "started", lambda pid: 77 if pid == 4242 else None)
    older = copy.deepcopy(needs_machines.facts_of("this-pc"))
    older["windows"]["build"] = 26100  # its build need is unmet now (of the moment: Windows Update)
    facts.use(facts.StandIn(older))
    with pytest.raises(app_module.Refused) as e:
        app.check(p.name)
    assert e.value.status == 409
    assert app.machine_status(p)["state"] == "unmet" and app.plugin(p.name) is p  # the job runs: not let go
    gate.set()
    job.thread.join(5)
    assert not job.running
    assert app.machine_status(p)["state"] == "unmet" and app.plugin(p.name) is p  # its process is in the ledger
    mine.clear()
    assert app.machine_status(p)["state"] == "unmet" and app.plugin(p.name) is None  # let go at the first read after


def test_a_process_that_ended_by_itself_holds_nothing_back(monkeypatch, this_pc):
    p = Windowsy()
    app = app_of(p)
    app.attach_plugins([p])
    rows = [Row(4242, 77), Row(4343, 88)]  # still in the ledger: only end_owned takes rows out
    monkeypatch.setattr(app_module.lifecycle, "mine", lambda owner=None: list(rows) if owner == p.name else [])
    monkeypatch.setattr(app_module.proc_mod, "pid_alive", lambda pid: pid == 4343)  # 4242 ended
    monkeypatch.setattr(app_module.proc_mod, "started", lambda pid: 99 if pid == 4343 else None)  # 4343 reused
    ended = []  # the detach ends what is left of it: told, nothing signalled here
    monkeypatch.setattr(app_module.lifecycle, "end_owned", lambda owner, *a, **k: ended.append(owner) or [])
    older = copy.deepcopy(needs_machines.facts_of("this-pc"))
    older["windows"]["build"] = 26100
    facts.use(facts.StandIn(older))
    assert app.machine_status(p)["state"] == "unmet" and app.plugin(p.name) is None  # nothing of it runs: let go
    assert ended == [p.name]


def test_the_switch_lets_go_at_once_as_before(this_pc):
    p = Windowsy()
    app = app_of(p)
    app.attach_plugins([p])
    app._busy = lambda name: True  # a job or a process of it, as the platform would find them
    app.set_enabled(p.name, False)
    assert app.plugin(p.name) is None


def test_the_internet_gone_holds_the_plugin_and_it_comes_back(this_pc):
    p = Online()
    app = app_of(p)
    assert app.attach_plugins([p]) == ["online"]
    assert app.machine_status(p)["state"] == "active"
    facts.use(facts.StandIn(offline_facts()))
    answer = app.machine_status(p)
    assert answer["state"] == "unmet" and answer["needs"]["held"] is True
    assert app.plugin(p.name) is p  # held: still attached, its own background work goes on (the user's answer 19)
    assert "online" not in app.active(fresh=True) and not any(i.id == "online" for i in app.items())
    with pytest.raises(app_module.Refused):
        app.ask(p.name, "status", [])
    facts.use(facts.StandIn(needs_machines.facts_of("this-pc")))
    assert app.machine_status(p)["state"] == "active" and app.plugin(p.name) is p


def test_one_no_reading_does_not_take_the_internet_away(this_pc):
    p = Online()
    app = app_of(p)
    facts.use(facts.StandIn(offline_facts(apart=5.0)))  # two readings, but not 15 s apart: unknown, never hidden
    assert app.machine_status(p)["state"] == "active"


def test_offline_settings_take_the_internet_away_whatever_the_switch(this_pc):
    class Settings:
        offline, read_only = True, False

    p = Online()
    app = app_of(p, settings=lambda: Settings())
    app.set_internet("there")
    answer = app.machine_status(p)
    assert answer["state"] == "unmet" and "LIMINAL_OFFLINE" in answer["why"]
    assert app.offline() == "LIMINAL_OFFLINE"


# -- the tray's assistants (M22) ----------------------------------------------------------------------------------------
def test_an_assistant_not_asked_yet_is_judged_for_its_needs_first(this_pc):
    bot = Cloudbot()
    asked = []
    app = app_of(assistants={"cloudbot": bot})
    app.assistant_validity = lambda p: asked.append(p.name) or (True, "")
    assert any(i.id == "cloudbot" for i in app.items())
    facts.use(facts.StandIn(offline_facts()))
    app2 = app_of(assistants={"cloudbot": bot})
    app2.assistant_validity = lambda p: asked.append("again") or (True, "")
    assert not any(i.id == "cloudbot" for i in app2.items()) and "again" not in asked
    answer = app2.assistant_status(bot)
    assert answer["state"] == "unmet" and answer["valid"] is False and answer["needs"]["met"] is False


# -- this machine's facts from the one reading (B4) ---------------------------------------------------------------------
def test_this_machines_facts_come_from_the_reader(this_pc):
    f = app_module.facts()
    assert f["machine"] == "x86-64" and f["memoryInstalledMb"] == 65536 and f["memoryMb"] == 68137205760 // 2**20


def test_a_reader_that_fails_leaves_the_facts_as_before(monkeypatch):
    class Broken(facts.StandIn):
        def read(self, *a, **k):
            raise OSError("no")

    facts.use(Broken({}))
    f = app_module.facts()
    assert f["machine"] == app_module.py_platform.machine() and "memoryInstalledMb" not in f


# -- GET /api/needs, the platform's --------------------------------------------------------------------------------------
def test_the_report_holds_and_takes_the_switch(this_pc):
    app = app_of(LinuxOnly(), Windowsy(), assistants={"cloudbot": Cloudbot()})
    status, report = api_answer(app, "GET", "/api/needs")
    assert status == 200 and report["held"] is True and report["switch"] is True
    rows = {r["name"]: r for r in report["plugins"]}
    assert rows["linux-only"]["state"] == "unmet" and rows["linux-only"]["needs"]["sort"] == "machine"
    assert rows["windowsy"]["needs"]["met"] is True and rows["cloudbot"]["kind"] == "assistant"
    assert report["internet"]["rule"] == "system" and report["internet"]["kept"] is False
    assert report["facts"]["system"] == "windows"
    status, one = api_answer(app, "GET", "/api/needs", query={"plugin": "windowsy"})
    assert status == 200 and [r["name"] for r in one["plugins"]] == ["windowsy"]
    assert api_answer(app, "GET", "/api/needs", query={"plugin": "nobody"})[0] == 404


def test_the_switch_takes_two_words(this_pc):
    app = app_of(Online())
    assert api_answer(app, "POST", "/api/needs/internet", {"rule": "maybe"})[0] == 400
    status, said = api_answer(app, "POST", "/api/needs/internet", {"rule": "there"})
    assert status == 200 and said == {"rule": "there", "kept": False}  # the platform's own login keeps nothing
    assert app.internet_rule() == "there"


class KeepingLogin(EnvironmentLogin):
    """A login that keeps the signed-in person's settings (as the login app's session does), counting its reads."""

    keeps_settings = True

    def __init__(self, store: dict):
        super().__init__(env={})
        self.store, self.reads = store, 0

    @property
    def signed_in(self) -> bool:
        return True

    def setting(self, name):
        self.reads += 1
        return self.store.get(name)

    def keep_setting(self, name, value, kind="preference", label=""):
        self.store[name] = value
        return {"name": name}


def test_the_switch_is_kept_in_your_login_and_brought_back_once(this_pc):
    store: dict = {}
    login = KeepingLogin(store)
    p = Online()
    app = app_of(p, login=login)
    status, said = api_answer(app, "POST", "/api/needs/internet", {"rule": "there"})
    assert said["kept"] is True and store[INTERNET_PAIR] == "there"
    facts.use(facts.StandIn(offline_facts()))
    later = app_of(Online(), login=KeepingLogin(store))  # the platform started again
    assert later.internet_rule() == "system"
    reads = later.login.reads
    api_answer(later, "GET", "/api/needs")
    assert later.internet_rule() == "there" and later.login.reads > reads
    reads = later.login.reads
    api_answer(later, "GET", "/api/needs")
    assert later.machine_status(later.machines()["online"])["state"] == "active"  # taken as there
    # brought back once; never read from the store at a judgement (the plugins' switches are read once besides)
    assert later.login.reads == reads


def test_with_a_login_that_keeps_nothing_it_holds_in_memory(this_pc):
    app = app_of(Online(), login=EnvironmentLogin(env={}))
    api_answer(app, "POST", "/api/needs/internet", {"rule": "there"})
    status, report = api_answer(app, "GET", "/api/needs")
    assert report["internet"] == {**report["internet"], "rule": "there", "kept": False}


# -- Connections ----------------------------------------------------------------------------------------------------------
def test_connections_give_a_quiet_node_its_needs_sort(this_pc):
    p = LinuxOnly()
    app = app_of(p)
    app.machine_status(p)
    quiet = {n["id"]: n for n in app.connections()["quiet"]}
    assert quiet["linux-only"]["state"] == "unmet" and quiet["linux-only"]["sort"] == "machine"
