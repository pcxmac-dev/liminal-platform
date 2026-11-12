"""0.23.0 (the user, 2026-11-11: "for the #connections, lets treat the plugins like a peripheral interface, and have them on
the outer periphery, which is a sphere, objects insantiated using the plugin, orbit the plugin on the peripheral, the
login/platform object is at the center, logic and intermediary interfaces (abstractions) are on the middle periphery,
which talk to the plugins and the primary application"): the platform's answer names each plugin's interface and gives
the quiet plugins too; the page draws the sphere. Stand-in plugins: nothing of this machine is asked."""
from __future__ import annotations

from conftest import Box, Wall
from test_app import Bot, _call

from liminal_platform.app import interface_of


def test_a_plugins_interface_is_the_librarys_class_it_is_built_on():
    box, wall, bot = interface_of(Box()), interface_of(Wall()), interface_of(Bot())
    assert (box["id"], box["title"], box["module"]) == ("interface:MachinePlugin", "MachinePlugin", "liminal_libs.machines.plugin")
    assert (wall["id"], wall["title"]) == ("interface:Firewall", "Firewall") and wall["sub"].startswith("The base of the firewall plugins")
    assert bot["id"] == "interface:PlatformPlugin"  # the stand-in assistant is built on the platform plugins' own base
    assert interface_of(object())["id"] == "interface:Plugin"  # nothing of the library's in its line


def test_the_traffic_names_the_interfaces_and_gives_the_quiet_plugins(served):
    app, port, lines, box = served
    t = _call(port, "GET", "/api/traffic?last=50")[1]
    # nothing asked of them yet: left out of the picture's parts, named hidden, and given whole as quiet
    assert t["hidden"] == ["box", "wall"] and [n["id"] for n in t["quiet"]] == ["box", "wall"]
    assert [(n["interface"], n["role"], n["state"]) for n in t["quiet"]] == [("interface:MachinePlugin", "plugin", "unknown"),
                                                                           ("interface:Firewall", "plugin", "unknown")]
    assert sorted(f["id"] for f in t["interfaces"]) == ["interface:Firewall", "interface:MachinePlugin"]
    assert all(f["title"] and f["sub"] for f in t["interfaces"])
    # asked: among the parts, each with its interface; none quiet
    assert _call(port, "GET", "/api/status")[0] == 200
    t = _call(port, "GET", "/api/traffic?last=50")[1]
    plugins = {n["id"]: n for n in t["nodes"] if n["role"] == "plugin"}
    assert {k: v["interface"] for k, v in plugins.items()} == {"box": "interface:MachinePlugin", "wall": "interface:Firewall"}
    assert t["quiet"] == [] and t["hidden"] == [] and len(t["interfaces"]) == 2


def test_the_sphere_comes_nearer_and_goes_farther(served):
    """0.24.0 (the user, 2026-11-11: "i need to be able to zoom in and out the connections")."""
    app, port, lines, box = served
    js, css = _call(port, "GET", "/platform.js")[1], _call(port, "GET", "/platform.css")[1]
    assert b"const ZOOM = [0.5, 6];" in js and b"const R = SPH.R * sphere.zoom, mx = SPH.cx + sphere.ox, my = SPH.cy + sphere.oy" in js
    # the wheel about the pointer, the page's own scroll left alone anywhere else
    assert b"data.addEventListener('wheel', (e) => {" in js and b"}, { passive: false });" in js
    wheel = js[js.index(b"data.addEventListener('wheel'"):js.index(b"}, { passive: false });")]
    assert b"if (!e.target.closest || !e.target.closest('#conn-svg.sphere')) return;" in wheel and wheel.index(b"return;") < wheel.index(b"e.preventDefault();")
    assert b"sphere.ox = now <= 1 ? 0 : px - SPH.cx - k * (px - SPH.cx - sphere.ox);" in js  # what is under the pointer stays there
    # a pinch, the head's buttons, the keys
    assert b"if (sphere.fingers.size === 2) {" in js and b"sphere.pinch = { gap: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, zoom: sphere.zoom };" in js
    for part in (b'class="conn-zoom" data-zoom="out"', b'class="conn-zoom level" data-zoom="whole" id="conn-zoom-level"', b'class="conn-zoom" data-zoom="in"',
                 b"if (zb.dataset.zoom === 'whole') sphereWhole(); else sphereZoom(zb.dataset.zoom === 'in' ? 1.3 : 1 / 1.3);",
                 b"const nearer = { '+': 1.3, '=': 1.3, '-': 1 / 1.3, _: 1 / 1.3 }[e.key];", b"if (nearer) sphereZoom(nearer); else sphereWhole();"):
        assert part in js, part
    assert b"const zoom = connView !== 'sphere' ? ''" in js  # the columns have none
    # nearer: Shift and a drag moves the picture, never wholly out of sight; a part picked comes back to the middle
    assert b"if (d.pan) {" in js and b"pan: e.shiftKey" in js and b"function keepInSight()" in js
    assert b"sphere.ox -= sphere.ox * k; sphere.oy -= sphere.oy * k;" in js
    assert b".conn-picture svg.sphere { overflow: hidden;" in css  # what is outside the picture is cut off


def test_the_page_draws_connections_as_a_sphere(served):
    app, port, lines, box = served
    js, css = _call(port, "GET", "/platform.js")[1], _call(port, "GET", "/platform.css")[1]
    # the sphere by default, the columns kept beside it; the choice kept in this browser
    assert b"localStorage.getItem(VIEW_KEY) === 'columns' ? 'columns' : 'sphere'" in js and b"const VIEW_KEY = 'liminal:platform:conn-view';" in js
    assert b'class="conn-view" data-view="${v}" aria-pressed="${connView === v}"' in js and b"function connectionsSvg" in js
    assert b"const m = sph ? sphereModel(t) : connectionsModel(t), shape = `${connView}/${shapeOf(m)}`;" in js
    # three shells: the centre and who is close to it, the interfaces on the middle periphery, the plugins on the sphere
    assert b"const SPH = { W: 800, H: 590, cx: 400, cy: 296, R: 226, D: 3.4, MID: 0.52, CORE: 0.2, OUT: 1.07, ORBIT: 8 };" in js
    assert b"if (app) app.p = [0, 0, 0];" in js and b"g.p = vMul(g.dir, SPH.MID);" in js and b"n.p = vMul(fib(i, Math.max(3, close.length)), SPH.CORE);" in js
    assert b"[...(t.nodes || []), ...(t.quiet || []).map((n) => ({ ...n, quiet: true }))]" in js  # the quiet plugins too
    assert b"p.interface = p.interface || `interface:${p.kind === 'assistant' ? 'AssistantPlugin' : 'MachinePlugin'}`;" in js  # an older platform
    # what the platform or the login and a plugin say goes through the plugin's interface
    assert b"if (plugin) return { via: m.byId.get(plugin.interface) || null };" in js and b"d = `M${at(A)}L${at(e.via.q)}L${at(B)}`;" in js
    # what was made or reached with a plugin orbits it; the Docker instances it gives among them
    assert b"n.p = owner && owner.role === 'plugin' ? vMul(around(owner.p, 0.115 + 0.055 * n.tier, turn), SPH.OUT)" in js
    assert b"const id = `instance:${i.name}`;" in js and b"(out[1].role === 'plugin' ? 1e6 : 0)" in js
    # it turns by itself, by a drag and by the arrow keys; it rests under the pointer, while a part is picked, and for no motion
    assert b"} else if (!calm && !sphere.drag && !sphere.hover && !focusNode) { sphere.yaw += dt * 0.075; moved = true; }" in js
    assert b"const calm = still();" in js and b"sphere.yaw = d.yaw + dx * 0.0085;" in js
    assert b"{ ArrowLeft: [-0.14, 0], ArrowRight: [0.14, 0], ArrowUp: [0, -0.14], ArrowDown: [0, 0.14] }[e.key]" in js
    assert b"if (focusNode && connView === 'sphere') sphereAim(focusNode);" in js
    assert b"if (sphere.dragged && e.target.closest('#conn-svg')) { sphere.dragged = false; return; }" in js  # a drag's end picks nothing
    # an interface picked holds its plugins and what goes through it
    assert b"(!!members && (members.has(l.from) || members.has(l.to)) && sphereVia(l) === focusNode)" in js
    for part in (b".conn-picture svg.sphere { touch-action: pan-y;", b".conn-picture svg.sphere .node { opacity: var(--depth, 1);",
                 b".conn-picture .node.far .label { display: none; }", b".conn-picture .node.role-interface rect:not(.hit)",
                 b"html.touch .conn-picture .node circle.hit { pointer-events: all; }", b".conn-view[aria-pressed=\"true\"]"):
        assert part in css, part
