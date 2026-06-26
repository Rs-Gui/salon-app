---
name: feedback-click-away-irmao
description: `@click.away` num dropdown irmão do input dispara quando o usuário clica no input — o input não é descendente do dropdown, então clicks nele contam como "fora"
metadata:
  type: feedback
---

Padrão clássico de input-de-busca + dropdown em Alpine:
```html
<div class="relative">
  <input @focus="aberto=true">
  <div x-show="aberto" @click.away="aberto=false" class="absolute ...">
```
**Bug:** o input é IRMÃO do dropdown, não descendente. Click no input bubble pelo DOM; Alpine vê target fora do dropdown → `@click.away` dispara → fecha imediatamente.

**Correção:** mover `@click.away` para o container `.relative` que envolve input + dropdown:
```html
<div class="relative" @click.away="aberto=false">
  <input @focus="aberto=true">
  <div x-show="aberto" class="absolute ...">
```
Agora click no input ou no dropdown fica DENTRO de `.relative` → não dispara. Só clicks fora disparam.

**Why:** Bug real em agendamentos/_form_modal.html e form_edit.html (todos os 3 multiselects de cada). Diagnóstico veio depois de 2 ondas de "correções" anteriores não pegarem (mousedown.prevent só corrigia o clique no item DO dropdown, não o problema do input fechar antes).

**How to apply:**
- Sempre que houver input + dropdown irmãos em `<div class="relative">`, `@click.away` vai no `.relative`
- Sintoma do bug: usuário foca o input, o dropdown "pisca" e some, ou nem aparece
- Bug encadeia: sem seleção via dropdown, hidden inputs não geram, submit chega vazio, validações backend disparam — pode parecer "submit não faz nada" porque o re-render do modal com banner de erro fica visualmente igual
- Antes de delegar correção, sempre verificar se `@click.away` está no `.relative` container e não num filho

Relacionado: [[alpine-bindings-precisam-xdata]] (outro bug Alpine silencioso).
