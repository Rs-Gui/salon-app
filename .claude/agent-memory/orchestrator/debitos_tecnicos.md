---
name: debitos-tecnicos
description: Catálogo central de débitos técnicos do SalaoApp registrados mas não corrigidos — cada item aponta a feature de origem
metadata:
  type: project
---

Lista viva de DTs por feature. Atualize sempre que um auditor levantar algo aceito mas não corrigido.

**Why:** débitos somem se ficarem espalhados em N arquivos de feature; este é o índice rápido.

**How to apply:** consultar antes de planejar nova feature pra ver se vale agrupar correção; ao corrigir, mover o item daqui pra histórico no rodapé.

## Ativos

### Truncamento silencioso de `observacoes` (todos os CRUDs)
- Onde: `app/routers/{clientes,profissionais,servicos,produtos}.py` — todos truncam `observacoes[:2000]` em vez de rejeitar
- Por que: padrão herdado; consistência > correção pontual. Corrigir em conjunto.
- Origem: [[produtos]] DT-1; aplica-se também a CRUDs anteriores

### PRAGMA foreign_keys=ON não emitido
- Onde: `app/database.py` — SQLite não enforce FKs por default
- Por que: hoje irrelevante (sem rota DELETE em lugar nenhum); valeria blindar contra mudança futura
- Origem: [[produtos]] DT-3

### Concorrência em campos denormalizados
- Onde: `produto.estoque_atual` é fonte da verdade duplicada das `MovimentacaoEstoque`. Race teórica em multi-aba.
- Mitigação atual: defesa em profundidade em `movimentar` (rollback se `estoque_atual < 0` após saída)
- Origem: [[produtos]] DT-4

### `_migrar_schema` precisa ser estendida para o Financeiro
- Quando o módulo Financeiro entrar, `MovimentacaoEstoque` ganhará `agendamento_id` e o whitelist de `tipo` precisará incluir `saida_venda`. Migração ALTER + atualização do whitelist no router.
- Origem: [[produtos]] DT-5

### GET de modal com `tipo` inválido cai silenciosamente em `entrada`
- Onde: `app/routers/produtos.py` GET `/produtos/{id}/movimentar`
- Por que: defesa em profundidade, mas mascara bugs no frontend
- Origem: [[produtos]] DT-2

### Helper `_calcula_profissionais` retorna `SimpleNamespace` sem TypedDict
- Onde: `app/routers/agendamentos.py`
- Por que: contrato `{id, nome, ativo, excluido}` exposto aos templates é frouxo
- Origem: [[exclusao-permanente]] DT-3

### `onclick` inline com `tojson` no nome (modal de exclusão)
- Onde: `app/templates/produtos/lista.html`, `app/templates/profissionais/lista.html` — `onclick="window.dispatchEvent(...{nome: {{ p.nome|tojson }} ...})"`
- Por que: seguro hoje, mas `data-*` + `addEventListener` seria mais robusto e CSP-friendly
- Origem: [[exclusao-permanente]] DT-2

### `_migrar_schema` engole exceções genéricas
- Onde: `app/database.py` — todos os blocos `except Exception: pass`
- Por que: pode mascarar erros reais (disco cheio, banco corrompido)
- Recomendação futura: capturar `sqlalchemy.exc.OperationalError` especificamente e logar
- Origem: [[exclusao-permanente]] DT-1

### Tooltip "(is) inativo(s)" no calendário cobre também excluídos
- Onde: `app/templates/agendamentos/lista.html`
- Por que: o conceito "(excluído)" foi tratado como variação visual de "(inativo)" em UX; tooltip não acompanhou
- Origem: [[exclusao-permanente]] DT-5

### `nome_snapshot == NULL` cai silenciosamente em "(nome perdido)"
- Onde: `app/routers/agendamentos.py` helper `_calcula_profissionais`
- Por que: defensivo é OK, mas regressão silenciosa de dados não dispara alerta
- Origem: [[exclusao-permanente]] DT-6

## Resolvidos
(vazio)
