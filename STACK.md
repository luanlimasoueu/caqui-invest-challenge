# Stack recomendada — Caqui Invest

## Visão geral

Para o aplicativo do desafio, a recomendação é usar TypeScript no front-end e Python no back-end. Essa combinação permite criar uma interface web clara para o cliente e para o atendente, mantendo no servidor o controle das regras de negócio, dos dados sintéticos e da integração com IA.

```text
React + TypeScript
        ↓
API REST em FastAPI
        ↓
SQLite no MVP / PostgreSQL em produção
        ↓
CSV, JSON e Markdown do desafio
```

## Front-end

- **Linguagem:** TypeScript, com HTML e CSS.
- **Tecnologia sugerida:** React ou Next.js.
- **Responsabilidades:**
  - tela do cliente;
  - timeline de aplicações e resgates;
  - painel do atendente;
  - alertas de risco;
  - encaminhamento para atendimento humano;
  - exibição das fontes usadas em cada resposta.

O TypeScript adiciona tipagem ao JavaScript e ajuda a detectar erros antes da execução, o que é útil para representar estados, prazos e transições das operações.

## Back-end

- **Linguagem:** Python.
- **Framework sugerido:** FastAPI.
- **Responsabilidades:**
  - consultar clientes e operações;
  - calcular liquidação usando calendário e horário de corte;
  - mascarar CPF;
  - detectar golpe, vulnerabilidade e prompt injection;
  - gerar protocolos;
  - controlar a fila humana;
  - buscar artigos da base de conhecimento;
  - integrar a IA com segurança.

O FastAPI permite expor uma API REST em Python e gerar documentação interativa da API.

## Banco de dados

- **MVP:** SQLite.
- **Evolução:** PostgreSQL.
- **Dados iniciais:** `clientes.json`, `operacoes.csv`, `posicoes.csv`, `conversas.csv`, `calendario.json`, `taxas.json` e os artigos da base de conhecimento.

## Motor de regras

As decisões críticas devem permanecer em código determinístico, e não depender apenas da IA. O motor deve validar:

- dias úteis, feriados e horário de corte;
- regras de liquidação;
- horário de atendimento humano;
- sinais de golpe e cliente vulnerável;
- limite de cinco passos e prevenção de doom loop;
- CPF mascarado e isolamento dos dados do cliente;
- ausência de recomendação de investimento.

A IA pode classificar a intenção, extrair informações, localizar artigos, sugerir a redação e resumir o caso para o atendente. A resposta final deve passar pelo motor de regras antes de ser exibida.

## Stack mínima para o Hands On

```text
React + TypeScript
FastAPI + Python
SQLite
API REST com JSON
```

Para um protótipo de um dia, SQLite é suficiente. Depois, o banco pode ser migrado para PostgreSQL sem alterar a divisão principal da aplicação.

## Alternativa de protótipo rápido

Se a prioridade for velocidade absoluta, o protótipo pode ser feito somente em Python com Streamlit e SQLite. Para uma experiência mais próxima de um produto real, a recomendação continua sendo React/TypeScript no front-end e Python/FastAPI no back-end.
