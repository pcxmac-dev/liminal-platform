"""0.31.0 (the user, 2026-11-16: "i need 3 plugins for inference serving local models on the platform, :: lama.cpp,
ollama and vLLM, i also need 3 harness plugins for the platform :: OpenCode, Aider, and Continue"; "they will be
classified as AI plugins"; "the other plugins are strictly proprietary service plugins"): the page's list draws one AI
plugins heading with its groups under it, Proprietary services (the assistants), Inference and Harnesses (the machine
plugins whose section is "ai", each in the group it names), and from 0.34.0 Protocols (2026-11-18: "basically a
protocol plugin that mediates MCP connections to resources by local AI agents"), and the tray keeps that order; a job
the platform says can be cancelled (a model's download runs for a long time) has a Cancel button in its panel's head,
which asks the platform to stop it. The page's script and styles are the files the platform serves, tested by their
text; the platform is asked directly where the two must agree. Nothing is started and no port is opened (conftest's
no_outside fails a test that does). A platform before 0.31.0 sends neither `group` nor `cancels`: the page draws it as
before."""
from __future__ import annotations

import re

import pytest

from liminal_libs.apps import Refused

from conftest import Box
from conftest import page_script as _script
from conftest import script_part as _part
from liminal_platform import app as platform_app
from liminal_platform.app import PlatformApp

pytestmark = pytest.mark.usefixtures("no_outside")


def _styles() -> str:
    """The page's rules as they read, however their lines are broken."""
    return " ".join((PlatformApp.STATIC / "platform.css").read_text(encoding="utf-8").split())


def test_the_list_draws_the_ai_plugins_under_one_heading_in_four_groups():
    js = _script()
    assert "const AI_GROUPS = [['inference', 'Inference'], ['harness', 'Harnesses'], ['protocol', 'Protocols']];" in js
    # under AI only with the section and a group the page draws: one or the other alone is a machine plugin
    assert "const isAi = (m) => m.section === 'ai' && AI_GROUPS.some(([g]) => g === m.group);" in js
    assert ("const sectionOf = (m) => (isAi(m) ? 'ai' : SECTIONS.some(([s]) => s === m.section) ? m.section "
            ": 'machine');") in js
    # the four sections stay the machine plugins' own: this machine's page lists no AI plugin, as it lists no assistant
    assert ("const SECTIONS = [['machine', 'Machine plugins'], ['virtualization', 'Virtualization plugins'], "
            "['os', 'OS plugins'], ['cloud', 'Cloud plugins'], ['ci', 'Continuous Integration plugins']];") in js
    draw = _part(js, "function drawList()", "function instancesTable()")
    assert "const assistants = st.assistants || [], ai = all.filter(isAi);" in draw
    # the heading when there is an assistant or an AI machine plugin; a group's name only over plugins of its own
    assert "(assistants.length || ai.length ? '<h4>AI plugins</h4>'" in draw
    assert ("(assistants.length ? '<h5 class=\"group\">Proprietary services</h5>' + assistants.map(assistant).join('')"
            " : '')") in draw
    assert "const mine = ai.filter((m) => m.group === g);" in draw
    assert "return mine.length ? `<h5 class=\"group\">${title}</h5>` + mine.map(drawn).join('') : '';" in draw
    # in the list's order: the machine plugins' sections, then AI plugins: the assistants, then AI_GROUPS' groups
    order = [draw.index(part) for part in ("SECTIONS.map(", "<h4>AI plugins</h4>",
                                           '<h5 class="group">Proprietary services</h5>', "AI_GROUPS.map(")]
    assert order == sorted(order)
    # an assistant's line as it was: its vendor (or what it is about) once it is active, its state until then
    assert "pending(a) || off(a) ? stateLine(a) : (a.vendor || a.about), cls(a), more(a));" in draw
    # with no machine plugin but AI ones (Ollama alone), the line that none is installed is still drawn above them, as
    # this machine's page says it: the four sections are drawn when a plugin is not an AI plugin
    assert "+ (all.some((m) => !isAi(m)) ? SECTIONS.map(([s, title]) => {" in draw
    assert "(all.length ? SECTIONS.map(" not in draw
    assert "AI assistants</h4>" not in js  # the heading it replaces is gone
    assert (".app-list h5.group { margin: 8px 0 2px 8px; font-size: 10px; font-weight: 600; color: var(--muted); "
            "letter-spacing: .04em; }") in _styles()


def test_the_pages_groups_are_the_platforms_in_its_order(monkeypatch):
    """The page's script is not run here: what it names must be what the platform sends."""
    # this machine's facts stood in: on Linux the real ones run `uname -p` for the processor's name
    monkeypatch.setattr(platform_app, "facts", lambda: {"host": "a stand-in", "cpus": 1})
    groups = re.search(r"const AI_GROUPS = (.*);", _script()).group(1)
    assert tuple(re.findall(r"'([a-z]+)', '[A-Za-z ]+'", groups)) == platform_app.AI_GROUPS == (
        "inference", "harness", "protocol")
    assert platform_app.AI_SECTION == "ai" and "m.section === 'ai'" in _script()

    class Served(Box):
        """A stand-in model server's plugin."""

        name = "served"
        SECTION = "ai"
        GROUP = "inference"

    class Gateway(Box):
        """A stand-in protocol plugin's (0.34.0: MCP's group)."""

        name = "gateway"
        SECTION = "ai"
        GROUP = "protocol"

    app = PlatformApp(log=lambda m: None, machines={"box": Box(), "served": Served(), "gateway": Gateway()},
                      assistants={})
    try:
        rows = {p["name"]: (p["section"], p["group"]) for p in app.overview()["plugins"]}
        assert rows == {"box": ("machine", ""), "served": ("ai", "inference"),  # what `held` keeps: section and group
                        "gateway": ("ai", "protocol")}
        assert app.api(None, "GET", "/api/machines/served", {}, None)[1]["group"] == "inference"
        assert app.api(None, "GET", "/api/machines/gateway", {}, None)[1]["group"] == "protocol"
    finally:
        app.stop()


def test_a_plugin_not_answered_yet_keeps_its_group_and_the_tray_its_order():
    js = _script()
    held = _part(js, "function held(ov)", "const unanswered")
    assert "section: p.section, group: p.group," in held  # from the overview: under AI plugins at once, dimmed
    # the tray until the platform says its own: machines, the assistants, then the AI machine plugins group by group
    tray = _part(js, "function trayFollows(name, present)", "// -- the list:")
    assert "const names = Object.keys(st.machines), ofAi = (n) => isAi(st.machines[n]);" in tray
    assert ("const order = [...names.filter((n) => !ofAi(n)), ...(st.assistants || []).map((a) => a.name),\n"
            "      ...AI_GROUPS.flatMap(([g]) => names.filter((n) => ofAi(n) && st.machines[n].group === g))];") in tray
    assert "plugins.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));" in tray


def test_a_job_that_can_be_cancelled_has_a_cancel_button_in_its_panels_head():
    js = _script()
    # shown only while a job runs that the platform says can be cancelled, disabled once it is asked to stop
    assert ("const cancelButton = (m, j) => `<button type=\"button\" class=\"job-cancel\" "
            "data-machine=\"${esc(m.name)}\"`\n"
            "    + `${j.cancels && j.running ? '' : ' hidden'}${j.cancelling ? ' disabled' : ''}>Cancel</button>`;"
            ) in js
    panel = _part(js, "function setupLog(m)", "function installHtml(m)")
    places = [panel.index(part) for part in ('class="muted small state"', "${cancelButton(m, j)}", 'class="term-hide"')]
    assert places == sorted(places)  # in the head: after the state's words, before the x that only hides the panel
    state = _part(js, "function jobState(j)", "const cancelButton")
    assert "if (j.running) return j.cancelling ? 'cancelling…' : 'running…';" in state
    assert "if (j.cancelled && !j.ok) return 'cancelled';" in state  # one that ended well all the same is done
    assert "return j.ok ? 'done' : j.ok === false ? 'ended with a failure' : '';" in state  # as before
    # what the platform says with the job's lines is kept (a platform before 0.31.0 says none of it: no button, as
    # before), and the head is set in place: the panel is not drawn again for it
    poll = _part(js, "async function pollJob(name)", "async function cancelJob(name)")
    for part in ("j.cancels = !!got.cancels;", "j.cancelling = !!got.cancelling || !!j.asked;",
                 "j.cancelled = !!got.cancelled;", "syncJob(name);"):
        assert part in poll, part
    sync = _part(js, "function syncJob(name)", "function jobTitle(m, j)")
    for part in ("if (state) state.textContent = jobState(j);", "b.hidden = !(j.cancels && j.running);",
                 "b.disabled = !!j.cancelling;"):
        assert part in sync, part
    styles = _styles()
    assert ".term-head button.job-cancel { font-size: 12px; }" in styles
    assert ".term-head button.job-cancel:disabled { opacity: .4; cursor: default; background: transparent; }" in styles
    # hidden by its attribute alone: no rule gives the button a display of its own
    assert not re.search(r"job-cancel[^{}]*\{[^}]*display", styles)


def test_cancel_asks_the_platform_by_one_click_and_says_a_refusal():
    js = _script()
    assert "const jc = e.target.closest('button.job-cancel[data-machine]');" in js
    assert "if (jc) { cancelJob(jc.dataset.machine); return; }" in js
    cancel = _part(js, "async function cancelJob(name)", "async function loadCheck(name, fresh)")
    # only a job that runs and can be cancelled, asked once: a platform without the route never says `cancels`
    assert "if (!j || !j.running || !j.cancels || j.asked) return;" in cancel
    # the job meant, by its startedAt as the platform said it (none said: the one under way, as the route takes it)
    assert "const meant = typeof j.startedAt === 'number' ? { startedAt: j.startedAt } : {};" in cancel
    assert "try { await api('POST', `api/machines/${enc(name)}/job/cancel`, meant); }" in cancel
    assert js.count("/job/cancel`") == 1  # asked from nowhere else
    assert "if (jobs[name] === j) { syncJob(name); say(name, e.message); }" in cancel  # refused: the platform's words
    assert "openForm(" not in cancel and "Dialog" not in cancel  # one click, no dialog


def test_a_panel_knows_its_job_by_when_it_began_and_follows_no_other():
    """A Cancel clicked before the page is told that its job has ended names that job, so the platform refuses it
    (409) and never stops the next one; and an answer with another job in its place (this one ended, then another
    began: from another page, a quick second form) is followed in a panel of its own, none of its lines in this
    one's. Every platform's job says its startedAt; a job's answer to the form that began it says it first."""
    js = _script()
    follow = _part(js, "function follow(name, action, steps, what, startedAt) {", "\n  }")
    assert "what: what || '', startedAt: typeof startedAt === 'number' ? startedAt : null };" in follow
    assert "follow(d.name, 'hook', [], what, out.job.startedAt);" in _part(js, "async function send() {", "\n  }")
    poll = _part(js, "async function pollJob(name)", "async function cancelJob(name)")
    other = ("        if (typeof got.startedAt === 'number' && typeof j.startedAt === 'number' && got.startedAt !== "
             "j.startedAt) {\n"
             "          follow(name, got.action || j.action, got.steps, '', got.startedAt);\n"
             "          break;\n"
             "        }\n"
             "        if (typeof got.startedAt === 'number') j.startedAt = got.startedAt;\n"
             "        const [text, offset] = fresh(j.offset, got);\n")
    assert other in poll  # told apart before a line of it is written in this panel
    assert poll.index("const got = await api('GET', `api/machines/${enc(name)}/job?since=${j.offset}&wait=2`);") \
        < poll.index(other)


def test_what_a_plugin_answers_or_refuses_with_is_drawn_as_text_every_space_and_line_kept():
    """0.34.0 (the MCP plugin's page; the plan's critique: "Add a test that untrusted strings are drawn as text"): a
    call waiting for your answer is opened whole (its waiting_call: the agent's arguments, every character shown as
    the library writes it), and an ask-twice call's second confirmation repeats its exact arguments in the plugin's
    refusal. What a plugin says is put on the page as text, never as markup (esc: & < > " ' written as entities), and
    the dialog keeps its spaces and its lines, so "rm  -rf" is not shown as "rm -rf"."""
    js, styles = _script(), _styles()
    assert "const esc = window.LiminalIcons.esc;" in js  # the library's: every character of markup escaped
    answer = _part(js, "function answerHtml(a)")
    assert "${esc(cap(String(a.said)))}</p>" in answer and "`<li>${esc(l)}</li>`" in answer  # its said, each line
    assert "<p class=\"said\">${esc(a)}</p>" in answer and "facts(a)" in answer  # words alone; facts escape their own
    draw = _part(js, "function drawDialog()")
    assert '<blockquote class="words">${esc(dlg.words)}</blockquote>' in draw  # a refusal: the plugin's own words
    assert "(x.words ? `<p class=\"words\">${esc(filled(x.words, f, values))}</p>` : '')" in draw
    cell = js[js.index("const cellHtml = "):js.index("const longWord = ")]
    assert "`${esc(c.text)}${c.sub ? `<div class=\"sub\">${esc(c.sub)}</div>` : ''}`) : esc(c));" in cell
    assert ".form-dialog ul.lines li, .form-dialog blockquote.words { white-space: pre-wrap; }" in styles
    assert ".form-dialog ul.lines { margin: 6px 0; padding-left: 18px; font-size: 12px; overflow-wrap: anywhere; }" \
        in styles  # a long word still breaks, so a long argument never widens the dialog
    assert ".form-dialog .note, .form-dialog .words { overflow-wrap: anywhere; }" in styles


def test_the_route_the_button_asks_is_one_the_platform_answers():
    """Asked of the app directly, as the page's script words it: nothing is served."""
    app = PlatformApp(log=lambda m: None, machines={"box": Box()}, assistants={})
    try:
        with pytest.raises(Refused) as refused:
            app.api(None, "POST", "/api/machines/box/job/cancel", {}, {})
        assert refused.value.status == 409  # no job runs: refused as such, not as an unknown route (404)
        assert app.api(None, "GET", "/api/machines/box/job", {"since": "0"}, None)[1]["running"] is False
    finally:
        app.stop()
