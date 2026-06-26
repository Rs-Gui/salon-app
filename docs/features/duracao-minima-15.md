# Feature: Duração mínima de 15 minutos (Serviço + Agendamento)

## Resumo
Subir o piso da duração de **1 min → 15 min** tanto no cadastro de Serviço quanto na duração efetiva do Agendamento (override ou calculada).

## Status
✅ DONE — 2026-05-15

### Aplicado
- `servicos.py` (criar + atualizar): mensagem `"Duração mínima é de 15 minutos."`
- `agendamentos.py` (`_validar_agendamento`): mensagem `"A duração mínima é de 15 minutos."`
- 3 templates com `min="15"` (servicos/form, agendamentos/_form_modal, agendamentos/form_edit)
- Texto auxiliar de `servicos/form.html` atualizado de "Entre 1 e 300 minutos." para "Entre 15 e 300 minutos."

## Impacto estrutural
- `app/routers/servicos.py` — validação no `criar`/`atualizar`
- `app/routers/agendamentos.py` — `_validar_agendamento` valida duração efetiva ≥ 15
- `app/templates/servicos/form.html` — `<input min="1">` → `<input min="15">`
- `app/templates/agendamentos/_form_modal.html` e `form_edit.html` — `<input min="1">` → `<input min="15">` no campo `duracao_override`

## Validações

### Serviço
Hoje tem: `_parse_duracao` retorna None pra valores ≤0, `duracao > 300` dispara erro. Adicionar:
- `duracao < 15` → `"Duração mínima é de 15 minutos."`

Ordem das validações: nome → duração obrigatória → **mínimo 15** → máximo 300 → unicidade

### Agendamento
Hoje `_validar_agendamento` valida `duracao > 300`. Adicionar:
- Duração efetiva (override ou max dos serviços) `< 15` → `"A duração mínima é de 15 minutos."`

Aplicar logo após o cálculo da duração efetiva, antes do check de máximo.

## Decisão sobre dados existentes
Serviços com duração `< 15` já cadastrados continuam funcionando (não migrar via SQL). A validação só dispara em **novas edições** desses serviços ou em **novos agendamentos** que os usem. Quando o usuário tentar salvar um agendamento com serviço de 10 min, vai ver o erro literal. Ele decide se reatualiza o serviço.

## Templates (HTML5 client-side)
- Agendamento `duracao_override`: `min="15"`. Placeholder e texto auxiliar continuam mostrando a sugestão dinâmica via Alpine — sem mudança.
- Serviço `duracao_minutos`: `min="15"`. Placeholder text "30" pode ficar (sugere um valor padrão razoável).

## Plano de delegação
Onda única paralela:
- `backend-architect`: 2 routers
- `frontend-developer`: 3 templates

Sem auditoria — mudança trivial de constraint.

## Critérios de aceite
- [ ] Cadastrar serviço com duração 10 → erro "Duração mínima é de 15 minutos."
- [ ] Cadastrar serviço com duração 15 → OK
- [ ] Criar agendamento com override `5` → erro "A duração mínima é de 15 minutos."
- [ ] Criar agendamento com serviço de 10min (legado) e sem override → erro "A duração mínima é de 15 minutos."
- [ ] Criar agendamento com serviço de 30min e sem override → OK
- [ ] Inputs HTML5 com `min="15"` bloqueiam submit no browser antes do round-trip
