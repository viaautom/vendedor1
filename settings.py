"""
Configurações de negócio (keywords, filtros de preço/desconto, intervalo
de busca) — editáveis pelo painel em tempo real, persistidas no SQLite.
Diferente de config.py, que guarda credenciais/infra (só via .env).
"""
import config
import storage

_CHAVES_LISTA = {"keywords"}
_CHAVES_BOOL = {"min_price_aplica"}
_CHAVES_INT = {"min_discount_percent", "check_interval_hours"}
_CHAVES_FLOAT = {"min_price", "max_price"}


def _defaults() -> dict:
    return {
        "keywords": list(config.KEYWORDS),
        "min_discount_percent": config.MIN_DISCOUNT_PERCENT,
        "min_price": config.MIN_PRICE,
        "min_price_aplica": True,
        "max_price": config.MAX_PRICE,
        "check_interval_hours": config.CHECK_INTERVAL_HOURS,
    }


def carregar_configuracoes() -> dict:
    cfg = _defaults()
    salvos = storage.obter_config_kv()

    if "keywords" in salvos:
        linhas = [linha.strip() for linha in salvos["keywords"].split("\n")]
        cfg["keywords"] = [linha for linha in linhas if linha]
    for chave in _CHAVES_BOOL:
        if chave in salvos:
            cfg[chave] = salvos[chave] == "1"
    for chave in _CHAVES_INT:
        if chave in salvos:
            cfg[chave] = int(salvos[chave])
    for chave in _CHAVES_FLOAT:
        if chave in salvos:
            cfg[chave] = float(salvos[chave])

    return cfg


def salvar_configuracoes(cfg: dict):
    valores = {
        "keywords": "\n".join(cfg["keywords"]),
        "min_discount_percent": str(int(cfg["min_discount_percent"])),
        "min_price": str(float(cfg["min_price"])),
        "min_price_aplica": "1" if cfg["min_price_aplica"] else "0",
        "max_price": str(float(cfg["max_price"])),
        "check_interval_hours": str(int(cfg["check_interval_hours"])),
    }
    storage.definir_config_kv(valores)


def filtrar_por_preco(ofertas: list[dict], cfg: dict) -> list[dict]:
    resultado = []
    for oferta in ofertas:
        preco = float(oferta.get("preco") or 0)
        if cfg["min_price_aplica"] and preco < cfg["min_price"]:
            continue
        if preco > cfg["max_price"]:
            continue
        resultado.append(oferta)
    return resultado
