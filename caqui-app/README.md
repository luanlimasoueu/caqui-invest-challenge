# Caqui em Dia

MVP navegável para o case **“Cadê meu dinheiro?”**. O mesmo back-end alimenta três superfícies:

- aplicativo do cliente;
- simulador de WhatsApp;
- chatbot com fontes e encaminhamento humano;
- painel humano com fila priorizada.

## Como executar

Requisito: Python 3.10 ou mais recente.

Na raiz do repositório:

```bash
python3 caqui-app/server.py
```

Depois, abra <http://127.0.0.1:8000>.

O servidor não precisa de dependências externas para esta demonstração. Ele lê os dados sintéticos diretamente do arquivo `caqui-invest-main.zip`.

## Publicação na Vercel

O projeto está pronto para ser importado diretamente na Vercel, mantendo a
raiz do repositório como **Root Directory**.

- `public/` contém o HTML, CSS e JavaScript publicados no CDN;
- `api/index.py` expõe a API Python serverless;
- `vercel.json` encaminha `/api/*` para a função e inclui os dados
  sintéticos no bundle.

Não configure comando de build nem *Output Directory*. Após um novo deploy,
abra a URL de produção e confirme que `/api/health` retorna JSON.

## Endpoints principais

```text
GET  /api/health
GET  /api/customers
GET  /api/overview?customer_id=C-0001
GET  /api/queue
POST /api/resolve
POST /api/handoff
```

Exemplo de resolução:

```json
{
  "customer_id": "C-0001",
  "channel": "chatbot",
  "message": "Resgatei ontem e não caiu. Sumiu?"
}
```

## Cenários demonstráveis

1. Acompanhar o resgate `OP-10005` da Dona Marta.
2. Ver o prazo calculado a partir do horário de corte e do calendário.
3. Repetir a pergunta no chatbot ou no WhatsApp simulado.
4. Informar que alguém pediu um código SMS e interromper o fluxo para segurança.
5. Pedir recomendação e receber explicação sem indicação de produto.
6. Abrir o caso no painel humano com protocolo e contexto.

## Decisões de segurança

- dados somente sintéticos;
- CPF exibido apenas de forma mascarada;
- cálculo de prazo no back-end;
- fonte da resposta exibida ao usuário;
- tentativa de golpe encaminhada sem fila;
- mensagens de cliente não são tratadas como instrução de sistema;
- recomendação de investimento nunca é produzida pelo bot.

## Próximas melhorias

- trocar o servidor local por FastAPI;
- separar o front-end em React + TypeScript;
- persistir protocolos e conversas em PostgreSQL;
- conectar uma fila real de atendimento;
- adicionar testes automatizados para as 12 regras do case;
- incluir autenticação e observabilidade antes de qualquer uso real.
