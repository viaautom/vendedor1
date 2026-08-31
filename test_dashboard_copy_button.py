import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("dashboard.py")

spec = importlib.util.spec_from_file_location("dashboard", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

assert hasattr(mod, "copiar_link_html"), "Função de cópia do link não encontrada"
html = mod.copiar_link_html("https://exemplo.com/produto/123")
assert "navigator.clipboard" in html.lower() or "execcommand" in html.lower()
assert "data-copy" in html.lower()
assert "href=\"https://exemplo.com/produto/123\"" in html
assert "link/" in html.lower()
assert "copiar" in html.lower()
assert "abrir" in html.lower()
assert "https://exemplo.com/produto/123" not in html.split("<span", 1)[1].split("</span>", 1)[0].lower()
print("ok")
