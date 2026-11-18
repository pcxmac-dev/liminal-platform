"""A password typed in a plugin's form (a field of type password: sudo's, for the Linux plugins' Root access and their
changes; the user, 2026-11-17: handed to sudo for that one action, "never kept, logged, written, shown", DECISIONS
addendum 9) is never shown by the page: it is "(given)" where the dialog lists what is sent and in its words, also
while what was sent is answered; it is not listed in the second confirmation, where it is typed again, since the first
ask let go of it; it is never written back into its field when the dialog is drawn again (Back, Change it); and the
dialog's values no longer hold it once it is asked or the dialog closes. It is sent as typed: its spaces are its own
(sudo -S is given the line as it is), spaces alone are none, and a key typed in one is trimmed where it is kept (the
settings' route here; the library's keys). The page's script is tested by its text, as the platform's other tests do
(a headless browser ran the dialog itself over the Linux firewall's real forms when this was built and when it was
fixed); the settings' route is asked of the app directly. Nothing is served and nothing runs (conftest's no_outside
fails a test that starts a process or reaches for the network)."""
from __future__ import annotations

import pytest

from liminal_libs.apps import EnvironmentLogin
from liminal_libs.machines import MachinePlugin
from liminal_libs.sources.keys import KeyVar

from conftest import page_script as _script
from conftest import script_part as _part

from liminal_platform.app import PlatformApp

pytestmark = pytest.mark.usefixtures("no_outside")


def test_a_password_is_said_given_wherever_the_dialog_says_what_is_sent():
    js = _script()
    assert "const GIVEN = '(given)';" in js
    shown = _part(js, "function shownValue(x, v) {")
    # before its value is read, as a choice's title or as it is: a password's words are "(given)", nothing else
    assert shown.index("if (x.type === 'password') return GIVEN;") < shown.index("const c = choiceOf(x, v);")
    # the confirmations' list of what is sent, and their words (`{name}`), both say a value through shownValue
    assert "${esc(shownValue(x, values[x.name]))}" in _part(js, "function valuesList(")
    assert "by[x.name] = shownValue(x, values[x.name]);" in _part(js, "function filled(")


def test_a_password_sent_is_still_said_given_while_it_is_answered():
    """The dialog is drawn again while what was sent is answered, its values let go of the password by then: the list
    and the words say it was given, from the names of the fields that held one (never a value), not "–"."""
    js = _script()
    forget = _part(js, "function forgetSecrets(d) {")
    assert "if (given(d.values[x.name])) gone.push(x.name);" in forget and "return gone;" in forget
    send = _part(js, "async function send() {")
    assert send.index("d.sent = forgetSecrets(d);") < send.index("drawDialog();") < send.index("out = await asked;")
    assert send.index("d.busy = false;\n    d.sent = [];") > send.index("out = await asked;")  # its answer in: gone
    draw = _part(js, "function drawDialog() {")
    # every step draws the values as the dialog says them: the dialog's own, or while asked these with the password
    assert "const { form: f, step } = dlg, c = f.confirm || {};" in draw
    assert ("const values = dlg.busy && (dlg.sent || []).length\n"
            "      ? { ...dlg.values, ...Object.fromEntries(dlg.sent.map((n) => [n, GIVEN])) } : dlg.values;") in draw
    assert draw.count("dlg.values") == 2  # (those two)
    confirm = draw[draw.index("} else if (step === 'confirm') {"):draw.index("} else if (step === 'accept') {")]
    assert "filled(c.title || f.title || f.hook, f, values)" in confirm and "valuesList(f, values)" in confirm
    # the second confirmation while its ask is answered: the password said given in the list, no empty field for it
    accept = draw[draw.index("} else if (step === 'accept') {"):draw.index("} else if (step === 'done') {")]
    assert ("(dlg.busy ? valuesList(f, values) : valuesList(f, values, true) + secretFields(f, values))"
            in accept)


def test_a_password_field_is_drawn_empty_whatever_was_typed():
    field = _part(_script(), "function fieldHtml(x, i, values) {")
    [line] = [x for x in field.splitlines() if 'type="password"' in x]
    assert line.strip() == '? `<input type="password" ${keys} ${attrs}${hint}>`'
    assert "value=" not in line  # Back and Change it draw the form again: a password is typed again, never put back


def test_the_dialog_lets_go_of_a_password_once_it_is_asked_or_closed():
    js = _script()
    forget = _part(js, "function forgetSecrets(d) {")
    assert "if (!x || x.type !== 'password' || typeof x.name !== 'string') return;" in forget
    assert "d.values[x.name] = null;" in forget
    send = _part(js, "async function send() {")
    # the request made from the values typed, then they are let go of, then the dialog is drawn again (its password
    # fields empty), and only then is the answer awaited: the dialog never holds a password while it is answered
    made = send.index("{ hook: d.form.hook, args: argsOf(d.form, d.values, d.accepted) });")
    assert made < send.index("forgetSecrets(d);") < send.index("drawDialog();") < send.index("out = await asked;")
    assert "await api(" not in send
    # a dialog cancelled, or a form opened over another: what was typed is let go of with it
    assert "forgetSecrets(d);" in _part(js, "function closed() {")
    assert "forgetSecrets(dlg);" in _part(js, "function openForm(")


def test_the_second_confirmation_has_the_password_typed_again():
    js = _script()
    draw = _part(js, "function drawDialog() {")
    accept = draw[draw.index("} else if (step === 'accept') {"):draw.index("} else if (step === 'done') {")]
    # what is sent, the password not among it (let go of when the first ask was sent), then its field again, empty
    assert "valuesList(f, values, true)" in accept and "secretFields(f, values)" in accept
    assert "&& !(again && x.type === 'password')" in _part(js, "function valuesList(f, values, again) {")
    assert ("const secretFields = (f, values) => f.fields.map((x, i) => (x && x.type === 'password' "
            "&& whenMet(values, x)\n    ? fieldHtml(x, i, values) : '')).join('');") in js
    # its Go on anyway sends nothing until the password is typed again, then sends it with the acceptance
    assert "else if (what === 'accept') { if (typedAgain()) { dlg.accepted.push(dlg.accept); send(); } }" in js
    again = _part(js, "function typedAgain() {")  # each password field checked as a fill's field is ("is needed")
    assert "if (checkField(x, i, c, String((c && c.value) || ''), null)) { ok = false; first = first || c; }" in again
    assert "return ok;" in again


def test_a_password_is_sent_as_typed_and_spaces_alone_are_none():
    """sudo -S is handed the line as it is: a password's leading or trailing spaces are its own. The fill's check and
    the second confirmation's are one check (checkField), which decides by its trimmed words whether one was typed and
    keeps what was typed: the fill's reads what its form holds, the second confirmation's its password fields."""
    js = _script()
    check = _part(js, "function checkField(x, i, c, typed, empty) {")
    assert "const v = typed.trim(), bad = $(`fd-${i}-bad`);" in check
    assert "else if (!v) why = x.required ? `${x.label || x.name} is needed` : '';" in check  # spaces alone: none
    assert "dlg.values[x.name] = !v ? empty : x.type === 'password' ? typed : v;" in check  # every other kind trimmed
    assert check.count(".trim()") == 1  # trimmed only to tell whether one was typed
    assert js.count("is needed`") == 1  # (no second copy of the check)
    # nothing typed: kept as '' by the fill's check, as none by the second confirmation's
    assert "checkField(x, i, c, String(dlg.values[x.name] ?? ''), '')" in _part(js, "function review() {")
    assert "checkField(x, i, c, String((c && c.value) || ''), null)" in _part(js, "function typedAgain() {")


def test_a_key_typed_in_a_password_field_is_trimmed_where_it_is_kept():
    """A plugin's secret setting is a password field on the page, sent as typed since 0.31.0: the settings' route keeps
    it trimmed, as it keeps every setting (and the library's keys.clean trims a model server's key)."""

    class Keyed(MachinePlugin):
        name, title, about, api, order = "keyed", "Keyed", "a stand-in with a secret setting", "2.1", 905
        keys = (KeyVar("KEYED_API_KEY", label="API key"),)

        def present(self):
            return True

        def status(self):
            return {"present": True, "valid": True, "summary": "", "why": ""}

    kept, said = {}, []
    app = PlatformApp(log=said.append, login=EnvironmentLogin(env=kept), machines={"keyed": Keyed()}, assistants={})
    try:
        out = app.save_settings("keyed", {"values": {"KEYED_API_KEY": "  s3cret-value \t"}})
        assert out["kept"] == ["KEYED_API_KEY"] and kept == {"KEYED_API_KEY": "s3cret-value"}
        assert not any("s3cret" in line for line in said)
    finally:
        app.stop()
