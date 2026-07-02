"""Regression guards for the Clients workspace UI (static/js/clients.js).

The panel is browser-coupled and not importable in pytest, so these are static
checks (repo convention — see test_document_editor_scroll.py): every registration
point the SPA needs must stay wired, or the surface silently disappears.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INDEX = (ROOT / "static/index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "static/app.js").read_text(encoding="utf-8")
APP_PY = (ROOT / "app.py").read_text(encoding="utf-8")
CLIENTS_JS = (ROOT / "static/js/clients.js").read_text(encoding="utf-8")
CHAT_JS = (ROOT / "static/js/chat.js").read_text(encoding="utf-8")
STYLE = (ROOT / "static/style.css").read_text(encoding="utf-8")
SLASH = (ROOT / "static/js/slashCommands.js").read_text(encoding="utf-8")


def test_sidebar_and_rail_buttons_exist():
    assert 'id="tool-clients-btn"' in INDEX
    assert 'id="rail-clients"' in INDEX
    # Customize-UI visibility row wired with the matching key
    assert 'data-ui-key="tool-clients"' in INDEX


def test_app_js_wiring():
    assert "import clientsModule from './js/clients.js';" in APP_JS
    assert "el('tool-clients-btn')" in APP_JS
    assert "clientsModule.togglePanel()" in APP_JS
    assert "'rail-clients':   'tool-clients-btn'" in APP_JS
    assert "'tool-clients':        '#tool-clients-btn'" in APP_JS
    # Deep-link opener registered
    assert "'/clients':" in APP_JS


def test_deep_link_route_served():
    assert '@app.get("/clients")' in APP_PY
    # And it must NOT be auth-exempt (page path relies on the login redirect)
    assert '"/clients"' not in APP_PY.split("AUTH_EXEMPT_EXACT")[1].split("}")[0]


def test_module_contract():
    # Exposure convention: default export + window global with the toggle API
    assert "window.clientsModule = clientsModule" in CLIENTS_JS
    for fn in ("openPanel", "closePanel", "togglePanel", "isPanelOpen"):
        assert fn in CLIENTS_JS
    # Live-refresh consumer + agent producer pair
    assert "addEventListener('clients-refresh'" in CLIENTS_JS
    assert "json.tool === 'manage_clients'" in CHAT_JS
    assert "new CustomEvent('clients-refresh')" in CHAT_JS
    # Naive-UTC timestamps must be parsed as UTC (renders 'in 5h' otherwise)
    assert "s += 'Z'" in CLIENTS_JS


def test_css_section_and_frosted_optin():
    assert ".clients-pane {" in STYLE
    # Stage chips exist for every canonical stage
    for stage in ("stuck", "moving", "landing", "landed", "unknown"):
        assert f".clients-stage-{stage}" in STYLE
    # Frosted-glass theme is an explicit allowlist — the pane must be in it
    assert "body.theme-frosted .clients-pane" in STYLE
    # Mobile bottom-sheet takeover
    assert "body.clients-view .clients-pane" in STYLE


def test_slash_open_target():
    assert "clients: ['tool-clients-btn', 'rail-clients']" in SLASH


def test_no_unicode_emoji_in_clients_js():
    # Repo PR rule: no Unicode emoji in UI code — icons are inline SVG.
    for ch in CLIENTS_JS:
        assert ord(ch) < 0x1F000, f"emoji-range character found: {ch!r}"
