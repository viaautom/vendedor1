import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("instagram_autorresponder.py")

assert MODULE_PATH.exists(), "O módulo de Instagram ainda não existe"

spec = importlib.util.spec_from_file_location("instagram_autorresponder", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

assert mod.extrair_ids_de_texto("#id1-id2 #id3") == ["id1", "id2", "id3"]
assert mod.extrair_ids_de_texto("#PWHEYC72414 #PCAMISETAF8E49B") == [
    "PWHEYC72414",
    "PCAMISETAF8E49B",
]

msg = mod.montar_mensagem([
    {"nome": "Produto A", "link_afiliado": "https://exemplo.com/a"},
    {"nome": "Produto B", "link_afiliado": "https://exemplo.com/b"},
])
assert "Produto A" in msg and "https://exemplo.com/a" in msg
assert "Oi! 💖" in msg
print("ok")
