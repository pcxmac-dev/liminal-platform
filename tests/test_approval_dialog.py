"""0.37.0: the approval dialog and plugin_state (liminal-libs 1.93.0's one "run a service" interface;
service-containers-design §3.10). A container plugin's approve_plan is a hook only its page asks: the platform refuses
it to a plugin (403) and asks it from the page. A service plugin's answer holding `approve` and `then` makes the page
ask each plan's plan_words, draw it in that plugin's words, ask each accept in turn, send approve_plan as the page in
the order plan_words gives, then start `then` as a job; the script is tested by its text, as the platform's other
tests do. plugin_state says the platform's last word on a plugin, asking it nothing. Stand-ins alone: the library's
FakeDocker, its stand-in firewall and service plugin; nothing is served, nothing runs."""
from __future__ import annotations

import pytest

from liminal_libs.machines import MachinePlugin, standins
from liminal_libs.machines.standins import FakeDocker, ServiceOwner, StandInHost, StandInNetworkHost, target

from conftest import api_answer as _api
from conftest import page_script as _script
from conftest import script_part as _part

from liminal_platform.app import PlatformApp

pytestmark = pytest.mark.usefixtures("no_outside")

DIG = "sha256:" + "a" * 64
SPEC = {"owner": "jenkins", "name": "ci", "title": "Jenkins", "system": "linux", "parts": [{
    "name": "controller", "image": {"ref": "docker.io/jenkins/jenkins:2.528.2-lts-jdk21", "digest": DIG},
    "ports": [{"name": "web", "container": 8080, "host": 8080, "lan": False}],
    "volumes": [{"name": "home", "path": "/var/jenkins_home", "holds": "its jobs"}], "memory": 1 << 30}]}


def _world(tmp_path):
    out = standins.Outside(sleep=lambda s: None, health=lambda h, p, path: True, platform="windows::TEST",
                           folder=tmp_path)
    host = StandInHost({"wsl-ubuntu": (target(wsl=""), FakeDocker())}, outside=out)
    firewall, jenkins = StandInNetworkHost(), ServiceOwner("jenkins")
    app = PlatformApp(log=lambda m: None, machines={p.name: p for p in (host, firewall, jenkins)}, assistants={},
                      state=tmp_path / "state")
    for p in (host, firewall, jenkins):
        app.attach(p)
    return app, host, firewall, jenkins


def _page(app, plugin, hook, *args):
    return _api(app, "POST", f"/api/machines/{plugin}/ask", {"hook": hook, "args": list(args)})


def test_a_plan_is_approved_from_the_page_and_never_by_a_plugin(tmp_path):
    app, host, firewall, jenkins = _world(tmp_path)
    assert _page(app, "standin-host", "grant_service", "jenkins", "wsl-ubuntu")[0] == 200
    assert _page(app, "standin-firewall", "grant_network", "standin-host")[0] == 200
    plan = jenkins.call("service_plan", "install", "jenkins/ci", SPEC, "wsl-ubuntu", {})
    assert [a["plugin"] for a in plan["approve"]] == ["standin-host", "standin-firewall"]
    status, words = _page(app, "standin-host", "plan_words", plan["plan"])
    assert status == 200 and words["answer"]["approve_args"][0] == "accept_lan"
    with pytest.raises(Exception) as e:  # a plugin's ask of a page-only hook: refused by the platform (403)
        jenkins.call("approve_plan", plan["plan"])
    assert getattr(e.value, "status", None) == 403
    assert _page(app, "standin-host", "approve_plan", plan["plan"])[0] == 200
    for a in plan["approve"][1:]:
        assert _page(app, a["plugin"], "approve_plan", a["plan"])[0] == 200
    work = jenkins.call("apply_plan", plan["plan"])["work"]
    host._svc.works.get(work).thread.join(10)
    assert jenkins.call("service_work", work, 0)["ok"] is True


def test_plugin_state_says_the_platforms_last_word_asking_nothing(tmp_path):
    class Gone(MachinePlugin):
        name, title, about, api, order = "gone", "Gone", "a stand-in that is not valid", "2.2", 997

        def __init__(self):
            self.asked = 0

        def status(self):
            self.asked += 1
            return {"present": True, "valid": False, "why": "no engine answers", "summary": ""}
    gone = Gone()
    app = PlatformApp(log=lambda m: None, machines={"gone": gone}, assistants={}, state=tmp_path)
    assert app.plugin_state("gone")["state"] == "unknown" and gone.asked == 0
    app.machine_status(gone)
    asked = gone.asked
    assert app.plugin_state("gone") == {"name": "gone", "state": "invalid", "why": "no engine answers", "page": "#gone"}
    assert gone.asked == asked  # asked nothing
    assert app.plugin_state("nobody")["state"] == "not installed"


def test_the_dialog_asks_each_plan_in_its_own_plugins_words_then_starts_the_job():
    js = _script()
    send = _part(js, "async function send() {")
    assert "if (!err && approvable(out && out.answer)) {" in send
    approvable = _part(js, "const approvable = (a) =>", ";\n")
    assert "includes('approve_plan')" in approvable  # only a plugin whose page asks approve_plan
    words = _part(js, "async function planWords(d) {")
    assert "{ hook: 'plan_words', args: [item.plan] }" in words and "approve_args" in words
    drawn = _part(js, "function approvalHtml(head, btn) {")
    assert "asks you to confirm" in drawn and "x.words" in drawn
    yes = _part(js, "async function planYes(d) {")
    # each accept asked in turn, then approve_plan as the page, its accepts in approve_args' order
    assert "a.accepted.push(accepts[a.k].name)" in yes
    assert "[item.plan, ...arrayOf(w.approve_args).map((n) => a.accepted.includes(n))]" in yes
    assert "{ hook: 'approve_plan', args }" in yes
    then = _part(js, "async function planThen(d) {")
    assert "{ action: 'hook', hook: then.hook, args: arrayOf(then.args) }" in then and "follow(d.name, 'hook'" in then
    decline = _part(js, "async function planDecline(d) {")
    assert "a.items.slice(a.i)" in decline and "hook: 'decline_plan'" in decline
    assert "else if (what === 'plan-yes') planYes(dlg);" in js and "else if (what === 'plan-decline') planDecline(dlg);" in js
