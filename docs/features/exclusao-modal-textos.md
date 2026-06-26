# Feature: Textos específicos no modal de exclusão (Produtos vs Profissionais)

## Resumo
Hoje o modal de confirmação `_modal_excluir.html` usa um aviso genérico que descreve **ambos** os comportamentos (cascade em produtos + snapshot em profissionais). Trocar por texto específico por tipo. Achado já registrado pelo security-auditor como I1 da feature [[exclusao-permanente]].

## Status
✅ DONE — 2026-05-15

## Impacto estrutural
- `app/templates/_modal_excluir.html` — passa a aceitar `tipo` no `event.detail` e renderiza texto condicional
- `app/templates/produtos/lista.html` e `app/templates/profissionais/lista.html` — incluem `tipo: 'produto'` / `tipo: 'profissional'` no `CustomEvent`

Sem mudanças em backend. Sem mudanças em outros templates.

## Decisão de UX
- Para **produto**: "Esta ação é **irreversível**. Todas as movimentações de estoque deste produto serão apagadas junto."
- Para **profissional**: "Esta ação é **irreversível**. O nome será preservado nos agendamentos passados e futuros com a marca **(excluído)**, mas o cadastro do profissional será apagado."
- Manter o mesmo card vermelho (`bg-red-50 border border-red-200 text-red-800 rounded-md p-3 text-sm`), `font-semibold` apenas nas palavras-chave em negrito.
- Default seguro: se `tipo` não vier ou for inválido, usar a mensagem genérica atual (defesa em profundidade — modal continua funcional).

## Contrato do `CustomEvent`
```js
window.dispatchEvent(new CustomEvent('open-modal-excluir', {
  detail: { nome: '...', endpoint: '/...', tipo: 'produto' | 'profissional' }
}))
```

`tipo` é nova chave, opcional do ponto de vista do partial (defensivo) mas obrigatória nos dois call sites existentes.

## Critérios de aceite
- [ ] Tentar excluir um produto → modal mostra apenas o texto de produto
- [ ] Tentar excluir um profissional → modal mostra apenas o texto de profissional
- [ ] Modal antigo sem `tipo` no detail → continua mostrando algo legível (fallback)

## Plano de delegação
Onda única — `frontend-developer`. Auditoria não necessária (mudança puramente textual em template já auditado; sem mudança de contrato de evento que afete segurança).
