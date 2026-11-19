"""The platform's own routes, as its Internal API tab lists them beside the frame's (liminal-libs 1.63.0, internal.py;
the user, 2026-11-16: "for all apps, and all plugins, there should be an external api tab, and an internal api tab";
2026-11-17: "describe the internal API like structure that the app code can work with").

One row for each route PlatformApp.api answers, in the order its chain asks them: (method, path, what it is, its class,
who asks it). `{name}` is the part that varies (a plugin's name). The class is the one the platform notes the request
under in who talks to whom (PlatformApp.classify: read, change, ask or stream); who asks it is "page" (the platform's
page, or the charts app framing it) or "client" (a program: this page never sends it to this platform, whose GET
/api/overview it asks in place of GET /api/status). The frame's own routes (/api/app, /api/tray, /api/traffic,
/api/codebase, ...) are the library's to list (internal.FRAME_ROUTES).

The table is held to the code by tests/test_routes.py: a route the chain answers and the table does not list, a row the
chain does not answer, or a class other than classify's fails it. So a route added to `api` is added here too."""
from __future__ import annotations

MACHINE = "/api/machines/{name}"  # one machine plugin's routes start here

ROUTES = (
    ("GET", "/api/status", "everything at once: this machine, Docker, every plugin's status, the instances and the "
                           "plugins attached (every plugin asked, one after another); the page asks it only of a "
                           "platform from before GET /api/overview", "read", "client"),
    ("GET", "/api/overview", "the page's first draw: the app, this machine and every plugin by its name, title and "
                             "icon, in the state it was last found in; no plugin is asked", "read", "page"),
    ("GET", "/api/assistants", "the AI assistants, each enabled or not, valid or not and why", "read", "page"),
    ("GET", "/api/docker", "the docker command on this machine and whether an engine answers it", "read", "page"),
    ("GET", "/api/machines", "every machine plugin's status, as GET /api/machines/{name} gives each", "read", "client"),
    ("GET", "/api/instances", "the Docker instances: this machine's, its contexts', a host's and those the machine "
                              "plugins run", "read", "page"),
    ("POST", "/api/plugins/{name}/settings", "a plugin's settings kept through the login {values, forget}: its own "
                                             "keys only, a value never shown back or logged", "change", "page"),
    ("POST", "/api/plugins/{name}/enabled", "a plugin enabled or disabled {on}: disabled, it is asked nothing and "
                                            "detached", "change", "page"),
    ("POST", "/api/plugins/{name}/hidden", "a plugin's icon hidden from the dock, or shown there again {on}",
     "change", "page"),
    ("GET", MACHINE, "one machine plugin's status: what its page draws (its tabs, its hooks, its External and "
                     "Internal API)", "read", "page"),
    ("GET", MACHINE + "/setup", "its setup or job under way, or its last one, with its lines", "stream", "client"),
    ("GET", MACHINE + "/job", "its job's text after an offset (?since=), held until more comes (?wait=, 5 s at the "
                              "most)", "stream", "page"),
    ("GET", MACHINE + "/check", "its check of this machine for what it installs", "read", "page"),
    ("POST", MACHINE + "/job/cancel", "its job under way asked to stop {startedAt}: only a job whose hook its "
                                      "CANCEL_HOOKS names, which ends by itself between its steps", "change",
     "page"),
    ("POST", MACHINE + "/job", "a job started {action: install | update | hook, hook, args}: its setup, its "
                               "packages' update, or one of its JOB_HOOKS with its arguments (a hook refused as /ask "
                               "refuses it; the page its asker, in the job's own thread too)", "change", "page"),
    ("POST", MACHINE + "/terminal", "its login terminal opened, or the one open given back from its last lines",
     "stream", "page"),
    ("GET", MACHINE + "/terminal", "its terminal's output after an offset (?since=, ?wait=)", "stream", "page"),
    ("POST", MACHINE + "/terminal/input", "keys typed into its terminal {data}: the request noted in who talks to "
                                          "whom, and as keys typed, the keys themselves never noted or logged",
     "stream", "page"),
    ("POST", MACHINE + "/terminal/close", "its terminal closed", "stream", "page"),
    ("POST", MACHINE + "/setup", "its setup started {steps}: only those steps, or all of them", "change", "page"),
    ("POST", MACHINE + "/ask", "one of its hooks asked by name {hook, args}: the arguments by position, its answer "
                               "as JSON, its refusal in its own words; one only other plugins ask refused (403), one "
                               "only its page asks refused (401) when the login says you are not there", "ask",
     "page"),
    ("POST", MACHINE + "/rpc", "an agent's request, handed whole to the hook its RPC_HOOK names (MCP's JSON-RPC): "
                               "its method, the allow-listed headers, its JSON body and gone(); the hook's answer "
                               "sent as it is, with the allow-listed headers alone", "ask", "client"),
    ("GET", MACHINE + "/rpc", "the same route's GET, handed over as a POST is (MCP: the plugin answers 405, Allow: "
                              "POST, DELETE)", "ask", "client"),
    ("DELETE", MACHINE + "/rpc", "the same route's DELETE, handed over as a POST is (MCP: a legacy session ended)",
     "ask", "client"),
    ("POST", MACHINE + "/enabled", "the plugin enabled or disabled {on}, as POST /api/plugins/{name}/enabled does",
     "change", "client"),
    ("POST", MACHINE + "/run", "a command on it {command}: a client's, never the page's", "change", "client"),
)
