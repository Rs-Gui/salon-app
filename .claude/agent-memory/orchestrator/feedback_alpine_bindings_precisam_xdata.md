---
name: feedback-alpine-bindings-precisam-xdata
description: Bindings Alpine (`:attr`, `x-text`, `$store`) só funcionam dentro de uma árvore com `x-data` ancestral — sem isso ficam markup inerte
metadata:
  type: feedback
---

Diretivas Alpine como `:placeholder`, `:value`, `x-text`, `x-show`, e até referências ao store global (`$store.xxx`) só são interpretadas se o elemento estiver dentro de uma árvore com `x-data` raiz (mesmo `x-data` vazio basta).

Sem `x-data` ancestral, o `Alpine.initTree` não registra os bindings — ficam no DOM como atributos literais sem reatividade. O store pode estar populado, mas ninguém lê.

**Why:** bug real em `agendamentos/_form_modal.html` (e `form_edit.html`) onde o campo "Duração" tinha `:placeholder="$store.agServicos.sugestao + ' min'"` mas o wrapper não tinha `x-data`. O multiselect de serviços atualizava o store corretamente, mas o input não reagia. Diagnóstico do `frontend-developer` (correção: adicionar `<div x-data>` vazio no wrapper).

**How to apply:**
- Quando criar binding Alpine isolado (fora de um componente já existente), garanta `<div x-data>` (vazio é suficiente) no wrapper imediato ou ancestral
- `$store.xxx` é global no Alpine mas só é AVALIADO em escopos `x-data`
- Bug é silencioso — nenhum erro de console; binding fica como atributo cru. Inspeção do DOM mostra `:placeholder="..."` literal em vez do valor calculado
- Antes de debugar "store não atualiza" ou "binding não atualiza", primeiro verifique se há `x-data` ancestral
