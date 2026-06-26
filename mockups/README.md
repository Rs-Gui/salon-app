# Mockups — SalãoApp

Pasta de trabalho do **redesign visual** do app. Aqui ficam as telas desenhadas
como protótipos HTML estáticos **antes** de virarem código real nos templates
(`app/templates/`). Serve como bancada de design e histórico visual do projeto.

---

## 1. Identidade visual escolhida: **Bruma**

Cinza neutro muito claro, minimalista e atemporal, com a estrutura editorial
herdada da proposta original "Aurora" (fonte serifada + layout), mas sem o tom
quente — apenas um **acento taupe** discreto.

### Paleta (tokens CSS)

| Token            | Hex       | Uso                                                |
|------------------|-----------|----------------------------------------------------|
| `--bg`           | `#F4F4F3` | Fundo geral — cinza neutro bem fraco               |
| `--surface`      | `#FFFFFF` | Cartões, áreas de conteúdo                         |
| `--surface-2`    | `#ECECEB` | Cabeçalhos, superfícies secundárias, blocos        |
| `--ink`          | `#28282A` | Texto principal (grafite quase-preto)              |
| `--ink-soft`     | `#6E6E72` | Texto secundário / legendas                        |
| `--line`         | `#E5E5E3` | Bordas e divisores                                 |
| `--line-soft`    | `#EFEFED` | Divisores fracos (linhas de meia-hora na agenda)   |
| `--accent`       | `#A89A93` | **Acento taupe** — detalhes, avatar, status        |
| `--accent-deep`  | `#8A7C75` | Acento em texto/hover                              |
| `--accent-soft`  | `#EAE5E2` | Fundo de destaque suave                            |
| `--graphite`     | `#38383B` | Item de menu ativo, botão primário, borda de bloco |

### Tipografia
- **Display / títulos:** `Fraunces` (serifa editorial, usa itálicos) — via Google Fonts
- **Corpo / interface:** `Hanken Grotesk` — via Google Fonts

> Regra de ouro: o cinza domina; o taupe aparece **só em detalhes** (avatar,
> status "aguardando", ícones, barra de pico). Nunca como cor de grande área.

---

## 2. Estrutura da pasta

```
mockups/
├── README.md       ← este arquivo
├── index.html      ← galeria/índice de todos os mockups
├── home.html               ← Home: painel de abertura
├── agenda.html             ← Agenda (grade do dia)
├── agenda-mobile.html      ← Agenda no celular (login + timeline por profissional)
├── agenda-novo.html        ← Modal: novo agendamento
├── agenda-detalhe.html     ← Modal: detalhe / edição rápida
├── clientes.html           ← Clientes (lista/roster)
├── clientes-form.html      ← Cadastro / edição de cliente
├── profissionais.html      ← Profissionais (lista)
├── profissionais-form.html ← Cadastro / edição de profissional
├── servicos.html           ← Serviços (lista)
├── servicos-form.html      ← Cadastro / edição de serviço
├── produtos.html           ← Produtos (lista/estoque)
├── produtos-form.html      ← Cadastro / edição de produto
├── produtos-historico.html ← Histórico de movimentação
├── produtos-movimentacao.html ← Modal: movimentar estoque
├── login.html              ← Acesso: login
├── setup.html              ← Acesso: configuração inicial
└── usuarios.html           ← Admin: usuários
```

> **Nota:** `home.html` é o antigo mockup "Bruma". Como ele sempre foi, na
> prática, a **tela inicial**, foi renomeado para `Home` — evitando confusão
> com a *paleta* Bruma (que continua sendo o nome do tema visual). Bruma = cor;
> Home = tela.

### Inventário e status

| Arquivo                     | Tela                       | Status                             |
|-----------------------------|----------------------------|------------------------------------|
| `home.html`                 | Home (v1 enxuta)           | 🟢 Aplicado no app                 |
| `agenda.html`               | Agenda                     | 🟢 Aplicado no app                 |
| `agenda-mobile.html`        | Agenda no celular          | 🟢 Aplicado no app                 |
| `agenda-novo.html`          | Novo agendamento (modal)   | 🟢 Aplicado no app                 |
| `agenda-detalhe.html`       | Detalhe agendamento (modal)| 🟢 Aplicado no app                 |
| `clientes.html`             | Clientes                   | 🟢 Aplicado no app                 |
| `clientes-form.html`        | Cliente (form)             | 🟢 Aplicado no app                 |
| `profissionais.html`        | Profissionais              | 🟢 Aplicado no app                 |
| `profissionais-form.html`   | Profissional (form)        | 🟢 Aplicado no app                 |
| `servicos.html`             | Serviços                   | 🟢 Aplicado no app                 |
| `servicos-form.html`        | Serviço (form)             | 🟢 Aplicado no app                 |
| `produtos.html`             | Produtos / estoque         | 🟢 Aplicado no app                 |
| `produtos-form.html`        | Produto (form)             | 🟢 Aplicado no app                 |
| `produtos-historico.html`   | Histórico de movimentação  | 🟢 Aplicado no app                 |
| `produtos-movimentacao.html`| Movimentar estoque (modal) | 🟢 Aplicado no app                 |
| `login.html`                | Login                      | 🟢 Aplicado no app                 |
| `setup.html`                | Configuração inicial       | 🟢 Aplicado no app                 |
| `usuarios.html`             | Usuários (admin)           | 🟢 Aplicado no app                 |
| `financeiro.html`           | Financeiro (lançamentos)   | 🟢 Aplicado no app                 |
| `financeiro-form.html`      | Lançamento (form)          | 🟢 Aplicado no app                 |
| `financeiro-categorias.html`| Categorias financeiras     | 🟢 Aplicado no app                 |
| `financeiro-comandas.html`  | Comandas (aba)             | 🟢 Aplicado no app                 |
| `agenda-pagamento.html`     | Pagamento + desconto/item  | 🟢 Aplicado no app                 |
| `comissoes.html`            | Comissões (aba Financeiro) | 🟢 Aplicado no app                 |

**Legenda de status:**
- ⚪ **Em revisão / Rascunho** — desenhado, aguardando aprovação
- 🟡 **Aprovado** — revisado e aprovado, pronto para aplicar no app
- 🟢 **Aplicado** — já implementado nos templates reais (mockup mantido como referência)

> **Financeiro** deixou de estar fora do escopo: o módulo (lançamentos,
> categorias, pagamento na agenda com produtos + desconto por item, e a aba
> Comandas) foi desenhado e **aplicado no app**.

---

## 3. Modo de trabalho (workflow)

Cada tela segue este ciclo. **O mockup é sempre aprovado antes de tocar no app real.**

```
1. DESENHAR   → criar/editar o mockup HTML estático nesta pasta
2. PREVIEW    → servir e abrir no navegador (porta 8002)
3. REVISAR    → você avalia; ajustes voltam ao passo 1
4. APROVAR    → status vira 🟡 nesta tabela
5. APLICAR    → portar o design para os templates reais em app/templates/
                (rodando na porta 8001), de forma incremental
6. REFERÊNCIA → status vira 🟢; o mockup permanece na pasta como referência
                visual e histórico (não é apagado)
```

### Princípios
- **Fidelidade:** o mockup recria a estrutura real da tela (mesmos elementos,
  estados e comportamentos do template), só mudando a aparência.
- **Tokens consistentes:** todo mockup usa as mesmas variáveis CSS da paleta
  Bruma (seção 1), para facilitar a tradução ao app depois.
- **Incremental e seguro:** ao aplicar no app, mexemos em poucos arquivos por
  vez e validamos rodando, sem reescrever tudo de uma vez.
- **App é a fonte da verdade:** depois de aplicado, o código real manda; o
  mockup vira só registro visual.

### Convenção de nomes
`<tela>.html` — nome curto e direto da tela (ex.: `home.html`, `agenda.html`,
`clientes.html`). Como Bruma é a única paleta, não usamos sufixo de paleta. O
índice (`index.html`) lista todos com swatch da paleta e descrição.

---

## 4. Como visualizar os mockups

Servidor estático simples a partir desta pasta:

```bash
cd mockups
python3 -m http.server 8002 --bind 127.0.0.1
```

Depois abra: **http://127.0.0.1:8002** (índice com todas as telas).

> O app real roda em paralelo na porta **8001**
> (`uvicorn app.main:app --reload --port 8001`).

---

## 5. Estado atual

O **redesign Bruma está 100% aplicado no app** — todas as telas migradas e
verificadas ponta a ponta, incluindo o módulo **Financeiro** e a **Home v1**
(saudação + contador de hoje + próximos agendamentos; sem stat tiles nem
gráfico, por decisão de manter a v1 enxuta).

Os mockups permanecem nesta pasta como **referência visual e histórico** — não
são apagados. Novas telas/ajustes seguem o mesmo ciclo: desenhar aqui → aprovar
→ aplicar no app.
