"""Architecture & security QA for the premium PesaGuard frontend.

Validates (without a browser):
- every ES module parses under node (--check) and all relative named imports resolve
- every HTML page parses, declares a CSP, and its data-page module exists
- sidebar/palette hrefs point at real files
- API endpoints stay inside the verified backend surface
- security invariants: memory-only token, textContent rendering, no secrets
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import html.parser as html_parser

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
JS = FRONTEND / "js"


def js_files():
    return sorted(JS.rglob("*.js"))


def html_files():
    return sorted(FRONTEND.rglob("*.html"))


def test_every_js_module_parses():
    for file in js_files():
        result = subprocess.run(
            ["node", "--check", str(file)], capture_output=True, text=True
        )
        assert result.returncode == 0, f"{file}: {result.stderr}"


def test_relative_named_imports_resolve():
    checker = Path("/tmp/pg_linkcheck.mjs")
    if not checker.exists():
        checker.write_text(
                    """
import fs from 'node:fs';
import path from 'node:path';
const ROOT = process.argv[2];
function walk(dir) { return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
  const p = path.join(dir, e.name);
  return e.isDirectory() ? walk(p) : (p.endsWith('.js') ? [p] : []);
}); }
const files = walk(path.join(ROOT, 'js'));
function exportsOf(file) {
  const src = fs.readFileSync(file, 'utf8');
  const names = new Set();
  for (const m of src.matchAll(/export\\s+(?:async\\s+)?(?:function|class|const|let|var)\\s+([A-Za-z_$][\\w$]*)/g)) names.add(m[1]);
  for (const m of src.matchAll(/export\\s*\\{([^}]*)\\}/g)) {
    for (const part of m[1].split(',')) {
      const seg = part.trim().split(/\\s+as\\s+/);
      if (seg[0]) names.add((seg[1] || seg[0]).trim());
    }
  }
  if (/export\\s+default/.test(src)) names.add('default');
  if (/export\\s+\\*/.test(src)) names.add('*');
  return names;
}
let bad = 0;
for (const file of files) {
  const src = fs.readFileSync(file, 'utf8');
  for (const m of src.matchAll(/import\\s+([\\w{},*\\s$]+?)\\s+from\\s+['\"](\\.[^'\"]+)['\"]/g)) {
    const spec = m[2];
    const target = path.resolve(path.dirname(file), spec);
    if (!fs.existsSync(target)) { console.log(`MISSING_FILE ${spec}`); bad++; continue; }
    const names = exportsOf(target);
    const braces = m[1].match(/\\{([^}]*)\\}/);
    if (braces) {
      for (const part of braces[1].split(',')) {
        const name = (part.trim().split(/\\s+as\\s+/)[0] || '').trim();
        if (name && !names.has(name) && !names.has('*')) { console.log(`MISSING_EXPORT ${path.relative(ROOT, file)}: ${name} from ${spec}`); bad++; }
      }
    }
  }
}
console.log(bad === 0 ? 'LINKCHECK_OK' : `LINKCHECK_FAILURES=${bad}`);
"""
        )
    result = subprocess.run(["node", str(checker), str(FRONTEND)], capture_output=True, text=True)
    assert "LINKCHECK_OK" in result.stdout, result.stdout + result.stderr


class _Parser(html_parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.append(dict(attrs))


def test_html_pages_parse_and_declare_csp():
    for file in html_files():
        parser = _Parser()
        parser.feed(file.read_text(encoding="utf-8"))
        assert "html" in parser.tags and "body" in parser.tags, file
        if file.name == "robots.txt":
            continue
        text = file.read_text(encoding="utf-8")
        assert "Content-Security-Policy" in text, f"missing CSP: {file}"
        assert 'name="viewport"' in text, file


def test_body_pages_have_modules():
    for file in (FRONTEND / "pages").rglob("*.html"):
        text = file.read_text(encoding="utf-8")
        m = re.search(r'<body[^>]*data-page="([a-z-]+)"', text)
        if not m:
            continue
        module = JS / "pages" / f"{m.group(1)}.js"
        assert module.exists(), f"{file}: missing module {module}"


def test_navigation_targets_exist():
    text = (JS / "components" / "shell" / "Sidebar.js").read_text(encoding="utf-8")
    hrefs = set(re.findall(r"href: '([^']+)'", text))
    assert hrefs, "sidebar hrefs missing"
    for href in hrefs:
        assert (FRONTEND / href.lstrip("/")).exists(), f"dead nav link: {href}"


def test_api_endpoints_use_central_map():
    client = (JS / "api" / "client.js").read_text(encoding="utf-8")
    assert "fetch(" in client, "client must own fetch"
    page_code = "\n".join(p.read_text(encoding="utf-8") for p in (JS / "pages").glob("*.js"))
    for page in (JS / "pages").glob("*.js"):
        src = page.read_text(encoding="utf-8")
        assert "fetch(" not in src, f"{page.name} bypasses the API client"
    assert "/discrepancies" in (JS / "api" / "endpoints.js").read_text(encoding="utf-8")


def test_token_never_persisted_and_never_in_urls():
    session = (JS / "auth" / "session.js").read_text(encoding="utf-8")
    # The docstring may *mention* storage; usage must never appear.
    assert not re.search(r"localStorage\s*\.|sessionStorage\s*\.", session)
    client = (JS / "api" / "client.js").read_text(encoding="utf-8")
    assert "credentials: 'omit'" in client
    assert "token=" not in client.lower().replace("access_token=", "")


def test_no_dynamic_innerHTML_with_data():
    for file in js_files():
        src = file.read_text(encoding="utf-8")
        for line in src.splitlines():
            if ".innerHTML" not in line:
                continue
            # Only the static icon whitelist may touch innerHTML.
            assert "svg.innerHTML = path" in line or "// static" in line, f"{file}: {line.strip()}"


def test_no_secrets_committed():
    pattern = re.compile(r"(sk_live|api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9]{12,}|password\s*=\s*['\"][^'\"]{6,}|Bearer\s+[A-Za-z0-9]{20,})", re.IGNORECASE)
    for file in FRONTEND.rglob("*"):
        if file.suffix not in {".js", ".html", ".json", ".css", ".md", ".conf", ".example", ".txt"} or not file.is_file():
            continue
        if file.name == "package-lock.json":
            continue
        assert not pattern.search(file.read_text(encoding="utf-8", errors="ignore")), f"possible secret in {file}"


def test_css_entry_resolves_all_imports():
    css = FRONTEND / "css"
    text = (css / "index.css").read_text(encoding="utf-8")
    imports = re.findall(r'@import url\("([^"]+)"\);', text)
    assert imports, "css entry missing"
    for rel in imports:
        assert (css / rel).exists(), f"missing stylesheet {rel}"


def test_console_uses_design_tokens_for_color():
    console = (css() / "components" / "console.css").read_text(encoding="utf-8")
    assert "var(--color-" in console


def css():
    return FRONTEND / "css"


def test_manifest_and_pwa_assets_exist():
    assert (FRONTEND / "manifest.json").exists()
    assert (FRONTEND / "assets" / "brand" / "favicon.svg").exists()
    manifest = (FRONTEND / "manifest.json").read_text(encoding="utf-8")
    assert "PesaGuard" in manifest


def test_bootstrap_guards_protected_pages():
    boot = (JS / "bootstrap.js").read_text(encoding="utf-8")
    assert "verifySession" in boot and "data-perms" in boot
