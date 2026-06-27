"""Geocodificação leve via Nominatim (OpenStreetMap). Sem chave de API.

Converte um texto ("Centro, Matias Barbosa, MG, Brasil") em coordenadas
(lat, lon). Respeita a política de uso do Nominatim:
  - User-Agent identificável;
  - no máximo ~1 requisição/segundo (espaçamento automático);
  - resultados cacheáveis para evitar chamadas repetidas.

Degrada graciosamente: se `requests` não estiver disponível ou a rede
falhar, `geocode()` devolve None em vez de levantar exceção.
"""
from __future__ import annotations

import time

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ALIME/0.3 (simulador de mobilidade - IME; contato@vistopred.com.br)"

# Espaçamento mínimo entre requisições (política do Nominatim: <= 1/seg).
_MIN_INTERVAL_S = 1.1
_last_call = [0.0]


def _respect_rate_limit() -> None:
    now = time.time()
    wait = _MIN_INTERVAL_S - (now - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()


def geocode(query: str, country_codes: str = "br") -> tuple[float, float, str] | None:
    """Devolve (lat, lon, nome_resolvido) para `query`, ou None se não achar.

    `country_codes` restringe a busca (ex.: "br"). Passe "" para global.
    """
    query = (query or "").strip()
    if not query:
        return None
    try:
        import requests
    except Exception:
        return None
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "addressdetails": 0,
    }
    if country_codes:
        params["countrycodes"] = country_codes
    try:
        _respect_rate_limit()
        resp = requests.get(
            NOMINATIM_URL,
            params=params,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR"},
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    if not data:
        return None
    item = data[0]
    try:
        return (float(item["lat"]), float(item["lon"]),
                item.get("display_name", query))
    except Exception:
        return None


def build_query(zone_name: str, city: str = "", uf: str = "",
                country: str = "Brasil") -> str:
    """Monta o texto de busca a partir do nome da zona + contexto do estudo."""
    parts = [
        (zone_name or "").strip(),
        (city or "").strip(),
        (uf or "").strip(),
        (country or "").strip(),
    ]
    return ", ".join(p for p in parts if p)
