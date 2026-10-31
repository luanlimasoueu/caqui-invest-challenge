"""Ponto de entrada serverless da API Caqui em Dia na Vercel.

A lógica continua centralizada em caqui-app/server.py para que a execução local
e o deploy usem exatamente as mesmas regras de negócio.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_SERVER_PATH = PROJECT_ROOT / "caqui-app" / "server.py"

spec = importlib.util.spec_from_file_location("caqui_local_server", LOCAL_SERVER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Não foi possível carregar a API do Caqui em Dia.")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# A Vercel instancia esta classe para cada requisição. Não iniciamos servidor
# nem fazemos bind de porta: isso permanece apenas no fluxo local.
handler = module.AppHandler
