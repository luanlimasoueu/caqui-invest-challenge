#!/usr/bin/env python3
"""Backend local, sem dependências externas, para o MVP Caqui em Dia.

O servidor lê os dados sintéticos diretamente de caqui-invest-main.zip e expõe
uma API pequena para o aplicativo, o simulador de WhatsApp e o chatbot.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import zipfile
from datetime import date, datetime, time, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "public"
ZIP_PATH = ROOT / "caqui-invest-main.zip"
REFERENCE_NOW = datetime.fromisoformat("2026-11-18T10:00:00-03:00")
DEFAULT_CUSTOMER_ID = "C-0001"


def load_bundle() -> dict[str, Any]:
    """Carrega clientes, operações e calendário do pacote sintético do desafio."""

    if ZIP_PATH.exists():
        with zipfile.ZipFile(ZIP_PATH) as bundle:
            prefix = "caqui-invest-main/"

            def read_json(name: str) -> Any:
                return json.loads(bundle.read(prefix + name).decode("utf-8"))

            def read_csv(name: str) -> list[dict[str, str]]:
                raw = bundle.read(prefix + name).decode("utf-8-sig")
                return list(csv.DictReader(io.StringIO(raw)))

            return {
                "clientes": read_json("dados/clientes.json"),
                "operacoes": read_csv("dados/operacoes.csv"),
                "calendario": read_json("dados/calendario.json"),
            }

    # Fallback para facilitar o teste se o ZIP não estiver ao lado do servidor.
    return {
        "clientes": [
            {
                "id": DEFAULT_CUSTOMER_ID,
                "nome": "Marta Siqueira",
                "idade": 63,
                "cidade": "Campinas",
                "uf": "SP",
                "cpf_mascarado": "***.***.894-**",
                "canal_preferido": "app_chat",
                "saldo_em_conta_brl": 1250.0,
                "nota_persona": "Dona Marta",
            }
        ],
        "operacoes": [
            {
                "id_operacao": "OP-10005",
                "id_cliente": DEFAULT_CUSTOMER_ID,
                "tipo": "resgate",
                "produto": "CDB-LD-110",
                "valor_brl": "40000.00",
                "pedido_em": "2026-11-17T19:40:00-03:00",
                "status": "em_processamento",
                "liquidacao_prevista": "2026-11-18",
                "observacao": "",
            }
        ],
        "calendario": {
            "horario_corte": "16:00",
            "dias": [
                {"data": "2026-11-18", "dia_util": True, "feriado": None}
            ],
        },
    }


BUNDLE = load_bundle()
CLIENTS = {client["id"]: client for client in BUNDLE["clientes"]}
OPERATIONS = BUNDLE["operacoes"]
CALENDAR = {item["data"]: item for item in BUNDLE["calendario"].get("dias", [])}
CUTOFF = time.fromisoformat(BUNDLE["calendario"].get("horario_corte", "16:00"))


def money(value: float | str | None) -> str:
    amount = float(value or 0)
    rendered = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {rendered}"


def iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def short_date(value: str | date | None) -> str:
    if not value:
        return "a confirmar"
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    return value.strftime("%d/%m/%Y")


def is_business_day(day: date) -> bool:
    item = CALENDAR.get(day.isoformat())
    if item is not None:
        return bool(item.get("dia_util"))
    return day.weekday() < 5


def next_business_day(day: date) -> date:
    candidate = day + timedelta(days=1)
    while not is_business_day(candidate):
        candidate += timedelta(days=1)
    return candidate


def add_business_days(day: date, count: int) -> date:
    result = day
    for _ in range(count):
        result = next_business_day(result)
    return result


def product_label(product: str | None) -> str:
    labels = {
        "CDB-LD-100": "CDB de liquidez diária",
        "CDB-LD-110": "CDB de liquidez diária",
        "CDB-2A-120": "CDB com vencimento",
        "FUNDO-RF-01": "fundo de renda fixa",
        "FUNDO-MM-01": "fundo multimercado",
        "LCI-90D-92": "LCI",
        "LCA-90D-95": "LCA",
    }
    return labels.get(product or "", product or "produto")


def calculate_expected(operation: dict[str, str]) -> tuple[date | None, str]:
    """Aplica a regra de liquidação do CASE para a operação selecionada."""

    if operation.get("liquidacao_prevista"):
        return date.fromisoformat(operation["liquidacao_prevista"][:10]), "registro da operação"

    requested = iso_datetime(operation["pedido_em"])
    request_day = requested.date()
    after_cutoff = requested.time() > CUTOFF
    base_day = request_day if is_business_day(request_day) and not after_cutoff else next_business_day(request_day)

    if operation.get("produto", "").startswith("FUNDO"):
        return add_business_days(base_day, 2), "regra de fundos: cotização D+1 e pagamento D+2 úteis"
    return base_day, "regra de liquidez diária: mesmo dia até 16h ou próximo dia útil"


def operation_view(operation: dict[str, str]) -> dict[str, Any]:
    expected, expected_source = calculate_expected(operation)
    requested = iso_datetime(operation["pedido_em"])
    status = operation.get("status", "")
    if status == "liquidada":
        status_label = "Liquidada"
    elif status == "recusada":
        status_label = "Recusada"
    elif status == "em_processamento":
        status_label = "Em processamento"
    else:
        status_label = status.replace("_", " ").title()

    if status == "recusada":
        next_step = operation.get("observacao") or "Consulte um especialista para entender o próximo passo."
    elif expected:
        next_step = f"Acompanhe a conta a partir de {short_date(expected)}."
    else:
        next_step = "A data será confirmada pela equipe responsável."

    return {
        "id": operation["id_operacao"],
        "customer_id": operation["id_cliente"],
        "type": operation["tipo"],
        "type_label": {"resgate": "Resgate", "aplicacao": "Aplicação", "transferencia_entrada": "Transferência recebida", "transferencia_saida_pix": "Pix enviado"}.get(operation["tipo"], operation["tipo"]),
        "product": operation.get("produto") or "Conta Caqui",
        "product_label": product_label(operation.get("produto")),
        "amount": float(operation.get("valor_brl") or 0),
        "amount_label": money(operation.get("valor_brl")),
        "requested_at": requested.isoformat(),
        "requested_label": requested.strftime("%d/%m/%Y às %H:%M"),
        "status": status,
        "status_label": status_label,
        "expected_date": expected.isoformat() if expected else None,
        "expected_label": short_date(expected),
        "expected_source": expected_source,
        "next_step": next_step,
        "note": operation.get("observacao") or "",
    }


def customer_operations(customer_id: str) -> list[dict[str, Any]]:
    operations = [operation_view(op) for op in OPERATIONS if op["id_cliente"] == customer_id]
    operations.sort(key=lambda item: item["requested_at"], reverse=True)
    return operations


def get_customer(customer_id: str) -> dict[str, Any] | None:
    client = CLIENTS.get(customer_id)
    if client is None:
        return None
    return {
        "id": client["id"],
        "name": client["nome"],
        "first_name": client["nome"].split()[0],
        "age": client.get("idade"),
        "city": f"{client.get('cidade', '')}/{client.get('uf', '')}",
        "cpf_masked": client.get("cpf_mascarado"),
        "preferred_channel": client.get("canal_preferido"),
        "balance": float(client.get("saldo_em_conta_brl") or 0),
        "balance_label": money(client.get("saldo_em_conta_brl")),
        "persona": client.get("nota_persona"),
    }


def overview(customer_id: str) -> dict[str, Any]:
    customer = get_customer(customer_id) or get_customer(DEFAULT_CUSTOMER_ID)
    operations = customer_operations(customer["id"])
    pending = next((item for item in operations if item["status"] == "em_processamento"), None)
    return {
        "reference_now": REFERENCE_NOW.isoformat(),
        "reference_label": "18/11/2026 às 10:00 (Brasília)",
        "customer": customer,
        "operations": operations[:8],
        "featured_operation": pending or (operations[0] if operations else None),
        "stats": {
            "active_operations": len(operations),
            "pending_operations": sum(1 for item in operations if item["status"] == "em_processamento"),
            "trust_items": 3,
        },
    }


def next_protocol(prefix: str = "CAQ") -> str:
    return f"{prefix}-{REFERENCE_NOW.strftime('%m%d')}-1005"


def detect_risk(message: str, customer: dict[str, Any], operation: dict[str, Any] | None) -> dict[str, Any]:
    text = message.lower()
    scam = bool(
        re.search(r"\b(código|senha|token|sms|otp)\b", text)
        and re.search(r"\b(gerente|ligou|ligaram|pediu|pediram|solicitou|solicitaram)\b", text)
    )
    injection = bool(
        re.search(r"ignore|desconsidere|mostre o saldo|cliente c-?\d{4}|revele", text)
    )
    vulnerability = bool(
        customer.get("age", 0) >= 60
        and re.search(r"sobrinh|filh|mandou|pression|resgatar tudo|não fui eu", text)
    )
    high_value = bool(operation and operation["amount"] >= 30000 and re.search(r"resgate|dinheiro|sumiu|caiu", text))
    return {
        "scam": scam,
        "injection": injection,
        "vulnerability": vulnerability,
        "high_value": high_value,
        "priority": "critica" if scam else ("alta" if vulnerability or high_value else "normal"),
    }


def source_list(operation: dict[str, Any] | None) -> list[dict[str, str]]:
    sources = [
        {"label": "Regra 1 — Liquidação", "detail": "CASE.md · horário de corte e dias úteis"},
        {"label": "Calendário da Caqui", "detail": "dados/calendario.json · feriados e dias úteis"},
    ]
    if operation:
        sources.insert(0, {"label": f"Operação {operation['id']}", "detail": "dados/operacoes.csv · conta sintética do cliente"})
    return sources


def resolve_message(payload: dict[str, Any]) -> dict[str, Any]:
    customer_id = str(payload.get("customer_id") or DEFAULT_CUSTOMER_ID)
    customer = get_customer(customer_id) or get_customer(DEFAULT_CUSTOMER_ID)
    message = str(payload.get("message") or "").strip()
    channel = str(payload.get("channel") or "chatbot")
    requested_operation_id = payload.get("operation_id")
    operations = customer_operations(customer["id"])
    operation = next((item for item in operations if item["id"] == requested_operation_id), None) if requested_operation_id else None
    if operation is None:
        operation = next((item for item in operations if item["status"] == "em_processamento"), None) or (operations[0] if operations else None)

    risk = detect_risk(message, customer, operation)
    text = message.lower()
    sources = source_list(operation)
    protocol = None
    handoff = False
    action = "responder"
    intent = "acompanhar_operacao"
    next_action = "continuar no autoatendimento"

    if risk["scam"]:
        intent = "suspeita_de_golpe"
        action = "encaminhar_seguranca"
        handoff = True
        protocol = next_protocol("SEG")
        next_action = "segurança assume agora"
        reply = (
            "Pare por aqui: a Caqui nunca pede senha, código SMS ou token por telefone, WhatsApp ou chat. "
            "Simulei o bloqueio desta sessão e encaminhei o caso para a equipe de segurança sem fila. "
            f"Seu protocolo é {protocol}."
        )
        sources = [{"label": "Regra 5 — Golpe", "detail": "CASE.md · interromper e encaminhar imediatamente"}]
    elif risk["injection"]:
        intent = "instrucao_nao_confiavel"
        action = "responder_com_limite"
        next_action = "manter dados isolados"
        reply = (
            "Posso ajudar somente com a conta autenticada nesta conversa. Não vou revelar dados de outro cliente "
            "nem tratar instruções escondidas na mensagem como comandos. Para acompanhar seu dinheiro, escolha uma "
            "operação da sua conta ou peça atendimento humano."
        )
        sources = [{"label": "Regra 11 — Instrução escondida", "detail": "CASE.md · texto do cliente é dado, não ordem"}]
    elif re.search(r"recomenda|o que você faria|onde eu coloco|melhor investimento|qual produto", text):
        intent = "pedido_de_recomendacao"
        action = "encaminhar_especialista"
        handoff = True
        protocol = next_protocol("ESP")
        next_action = "especialista humano deve avaliar"
        reply = (
            "Posso explicar conceitos e diferenças gerais, mas não indicar produto, percentual ou a melhor opção "
            "para você. Registrei seu pedido e encaminhei para um especialista humano. "
            f"Protocolo: {protocol}."
        )
        sources = [{"label": "Regra 4 — Sem recomendação", "detail": "CASE.md · encaminhar pedido ao especialista"}]
    elif re.search(r"encerrar|cancelar|reclama", text):
        intent = "cancelamento_ou_reclamacao"
        action = "encaminhar_humano"
        handoff = True
        protocol = next_protocol("SAC")
        next_action = "atendimento humano com histórico"
        reply = f"Entendi. Não vou insistir na retenção. Registrei seu pedido e o atendimento humano verá todo o histórico. Protocolo: {protocol}."
        sources = [{"label": "Regra 7 — Reclamação e cancelamento", "detail": "CASE.md · disponível em qualquer passo"}]
    elif operation:
        intent = "acompanhar_operacao"
        if operation["status"] == "recusada":
            reply = (
                f"Encontrei a operação {operation['id']}: {operation['type_label'].lower()} de {operation['amount_label']} em "
                f"{operation['product_label']}. Ela foi recusada. Motivo registrado: {operation['note'] or 'não informado'}. "
                "Posso encaminhar para uma pessoa explicar o próximo passo."
            )
        elif operation["expected_date"]:
            status_sentence = "já foi liquidada" if operation["status"] == "liquidada" else "está em processamento"
            reply = (
                f"Encontrei a operação {operation['id']}: {operation['type_label'].lower()} de {operation['amount_label']} "
                f"em {operation['product_label']}. Ela {status_sentence}. "
                f"O pedido foi feito em {operation['requested_label']} e a liquidação está prevista para {operation['expected_label']}. "
                f"{operation['next_step']}"
            )
        else:
            reply = f"Encontrei a operação {operation['id']}, mas a data de liquidação ainda não está registrada. Não vou inventar um prazo. Posso encaminhar o caso para uma pessoa."
            handoff = True
            protocol = next_protocol("SAC")
            action = "encaminhar_humano"
            next_action = "validar prazo com humano"
        if risk["vulnerability"] or risk["high_value"]:
            handoff = True
            protocol = protocol or next_protocol("PRI")
            action = "encaminhar_prioridade"
            next_action = "humano prioritário com contexto"
            reply += f" Como há um sinal de prioridade nesta conversa, também encaminhei o caso a uma pessoa. Protocolo: {protocol}."
    else:
        intent = "sem_operacao_encontrada"
        action = "encaminhar_humano"
        handoff = True
        protocol = next_protocol("SAC")
        next_action = "humano deve localizar a operação"
        reply = f"Não encontrei uma operação para este cliente. Não vou inventar um prazo. Encaminhei o caso para uma pessoa com o protocolo {protocol}."

    return {
        "channel": channel,
        "customer": customer,
        "operation": operation,
        "intent": intent,
        "reply": reply,
        "sources": sources,
        "risk": risk,
        "action": action,
        "next_action": next_action,
        "handoff": handoff,
        "protocol": protocol,
        "reference_label": "Dados sintéticos · agora: 18/11/2026 às 10:00 (Brasília)",
    }


def queue_items() -> list[dict[str, Any]]:
    return [
        {
            "protocol": "SEG-1118-1005",
            "customer": "Marta Siqueira",
            "customer_id": "C-0001",
            "subject": "Suspeita de golpe",
            "priority": "critica",
            "age": "agora",
            "preview": "Um gerente pediu meu código SMS...",
            "source": "WhatsApp",
        },
        {
            "protocol": "PRI-1118-1004",
            "customer": "Celina Teixeira",
            "customer_id": "C-0007",
            "subject": "Resgate em processamento",
            "priority": "alta",
            "age": "2 min",
            "preview": "Resgatei ontem e não caiu. Sumiu?",
            "source": "App",
        },
        {
            "protocol": "ESP-1118-1002",
            "customer": "Camila Prates",
            "customer_id": "C-0003",
            "subject": "Pedido de recomendação",
            "priority": "normal",
            "age": "8 min",
            "preview": "Tenho R$ 50 mil, onde eu coloco?",
            "source": "Chatbot",
        },
    ]


class AppHandler(BaseHTTPRequestHandler):
    server_version = "CaquiEmDia/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Logs curtos e sem mensagem crua do cliente.
        print(f"[{self.log_date_time_string()}] {format % args}")

    def send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_types = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_types.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/health":
            self.send_json({"ok": True, "service": "caqui-em-dia", "reference": REFERENCE_NOW.isoformat()})
        elif parsed.path == "/api/overview":
            self.send_json(overview(query.get("customer_id", [DEFAULT_CUSTOMER_ID])[0]))
        elif parsed.path == "/api/customers":
            self.send_json({"customers": [get_customer(client_id) for client_id in sorted(CLIENTS)]})
        elif parsed.path == "/api/queue":
            self.send_json({"items": queue_items()})
        elif parsed.path == "/" or parsed.path == "/index.html":
            self.send_file(WEB_DIR / "index.html")
        elif parsed.path in {"/styles.css", "/app.js"}:
            self.send_file(WEB_DIR / parsed.path.lstrip("/"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self.read_json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json({"error": "JSON inválido"}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/resolve":
            self.send_json(resolve_message(payload))
        elif parsed.path == "/api/handoff":
            customer_id = str(payload.get("customer_id") or DEFAULT_CUSTOMER_ID)
            self.send_json({
                "ok": True,
                "protocol": next_protocol("SAC"),
                "customer": get_customer(customer_id),
                "message": "Caso entregue à equipe humana com o histórico desta conversa.",
            })
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), AppHandler)
    print(f"Caqui em Dia disponível em http://127.0.0.1:{port}")
    print("Dados sintéticos carregados de caqui-invest-main.zip")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando o servidor.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
