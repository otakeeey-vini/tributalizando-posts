# Tributalizando · manual de operação

Perfil: **@tributalizando** (Instagram). Conteúdo: tributação de criptoativos para pessoa física no Brasil
(IR, ganho de capital, DeCripto, declaração anual, exterior). Objetivo: mostrar que o autor é técnico,
falando em linguagem simples. 3 posts por dia: **8h, 12h e 18h** (horário de Brasília, `-03:00`).

## Peças do sistema

| Peça | Onde | Função |
|---|---|---|
| Painel de revisão | https://claude.ai/artifact/XDKqYAk2VHZqcnwZcmCY76 | O dono revisa, edita e aprova. Banco: coleção `posts` |
| Fila | `queue/<AAAA-MM-DD-HHMM-slug>/` neste repositório | `spec.json` (conteúdo), `post.json` (estado), `NN.jpg` (artes) |
| Publicador | `.github/workflows/publicar.yml` + `scripts/publish.py` | A cada 15 min publica `status: approved` com horário vencido |
| Gerador de artes | `scripts/render.py` | `python3 scripts/render.py queue/<pasta>/spec.json` |

Documento no painel (`posts/<pasta>`): `title, format, scheduled_at, caption, sources[], images[] ("/_blob/<id>"),
asset_ids[], status (pending|approved|discarded|published|error), queued (bool), error, media_id, created_at, updated_at`.
O id do documento é igual ao nome da pasta na fila. Post feito a partir de sugestão leva também `suggestion_id`.

Sugestões do dono (`suggestions/<id>` no painel): `text, format ("" | carrossel | imagem única), date ("AAAA-MM-DD" ou ""),
slot ("08:00" | "12:00" | "18:00" | ""), notes, status (new | used | info | skipped), post_id, reply, created_at`.

## Rotina A · Sincronizar (07:40, 11:40, 17:40, 21:40)

1. Leia todos os documentos de `posts` no painel (ArtifactData `list`, guarde as `version`).
2. Para cada documento com `status: "approved"` e `queued` falso:
   - em `queue/<id>/post.json` grave `caption`, `scheduled_at` e `status: "approved"`;
   - depois do push, atualize no painel `queued: true` (com `if_version`).
3. Para `status: "discarded"` (ou de volta a `pending`) no painel: grave o mesmo `status` no `post.json`
   se ele ainda não foi publicado.
4. Traga para o painel o que o publicador gravou no repositório: `post.json` com `published` (copie `status`,
   `media_id`, `published_at`) ou `error` (copie `status` e `error`).
5. Um commit só (`git pull --rebase` antes), mensagem "Sincroniza aprovações do painel".
6. Nunca altere a legenda ou o horário que o dono editou. Nunca publique nada direto na API.

## Rotina B · Criar posts do dia seguinte (diária, à tarde)

1. Veja em `pautas.md` o que já foi publicado ou está na fila e **não repita** tema nem ângulo dos últimos 30 dias.
1.1. **Sugestões do dono vêm primeiro.** Leia `suggestions` no painel (ArtifactData `list`). Para cada uma com
   `status: "new"`, da mais antiga para a mais nova:
   - com `date` igual ao dia que você vai preencher (ou vazia): use nos slots desse dia, respeitando `slot` e
     `format` quando informados (se `slot` já estiver ocupado por outra sugestão, use o próximo livre);
   - com `date` futura e diferente: deixe para o lote daquele dia;
   - com `date` já passada: trate como sem data.
   Siga as `notes` do dono. Se a ideia não der para confirmar na fonte ou estiver vaga demais, não invente:
   grave `status: "info"` e explique em `reply` (1 frase) o que falta. Se for fora do tema do perfil, `status:
   "skipped"` com `reply` explicando. Complete os slots que sobrarem com pautas suas.
   Depois de criar o post: na sugestão grave `status: "used"`, `post_id` (nome da pasta) e um `reply` curto;
   no documento do post grave `suggestion_id`. Sempre com `if_version`.
2. Escolha 3 pautas para o **próximo dia sem posts na fila** (comece por amanhã; se já houver pastas
   `queue/<data>-*` para amanhã, use o dia seguinte livre), nos horários 8h, 12h e 18h, variando formato: pelo menos um carrossel (4 a 7 lâminas)
   e uma imagem única. Priorize o que é atual: prazos do mês (DeCripto vence no último dia útil do mês seguinte),
   mudanças de regra, dúvidas comuns, exemplos com números.
3. **Pesquise antes de afirmar**: use busca na web e confira norma, artigo, alíquota, prazo e valor na fonte
   (de preferência Receita Federal, legislação, Planalto). Se não confirmar, não use o dado.
   Lembretes já conferidos (nov/2026): DeCripto = IN RFB 2.291/2025 (obrigação da PF desde 01/07/2026, art. 19;
   PF que opera em exchange no exterior, DEX ou sem intermediário acima de R$ 35 mil/mês, art. 5º, II e § 3º;
   prazo último dia útil do mês seguinte, art. 12; multas art. 13). Isenção de vendas até R$ 35 mil/mês:
   Lei 9.250/1995, art. 22 (vale o total vendido, não o lucro). Ganho de capital: Lei 8.981/1995, art. 21,
   DARF 4600. A MP 1.303/2025 perdeu a validade: não trate como regra vigente.
4. Escreva cada `spec.json` (veja exemplos em `queue/`): campos `title, format, scheduled_at, sources, caption, slides`.
   - Linguagem simples, frases curtas, sem juridiquês; a norma vai no campo `note` das lâminas ("Base:").
   - Legenda: gancho na 1ª linha, explicação curta, 2 a 4 linhas com emoji de marcador (📌📅⚠️), CTA
     (salvar, enviar, comentar), "Base: ...", "Conteúdo informativo; cada caso merece análise individual.",
     5 a 8 hashtags. Máximo 2.200 caracteres.
   - Tipos de lâmina: `cover`, `point`, `big`, `checklist`, `cta` (ver docstring de `scripts/render.py`).
     Destaque com `**texto**`. Títulos de até ~6 palavras por linha; corpo de lâmina com no máximo ~45 palavras.
   - Não cite nomes de corretoras como "estrangeiras" sem confirmar; prefira "corretora sediada no exterior".
5. Renderize (`python3 scripts/render.py queue/<pasta>/spec.json`), **abra cada JPEG e confira** texto cortado,
   sobreposição e erros de português. Corrija e renderize de novo se preciso.
6. Commit + push das pastas novas (status `pending` — o publicador ignora pendentes).
7. Envie as artes ao painel (Artifact publish com `url` do painel, `asset: true`, `file_paths`) e crie os
   documentos em `posts` (ArtifactData `batch` com `set`), `status: "pending"`, `queued: false`.
8. Acrescente as 3 pautas em `pautas.md` (data, horário, título, formato) e faça commit.

## Identidade visual

Verde-floresta `#0E3B2E`, verde-profundo `#082A20`, dourado `#E8B931`, creme `#F6F1E6`, tinta `#13221C`.
Tipos: Inter Display (títulos, 800–900), Inter (texto), Lora itálico (citação no CTA). Logo: `brand/logo.svg`
(quadrado arredondado com "T" dourado e moeda). Wordmark "tributa**lizando**" com "lizando" em dourado.
Artes 1080×1350 (4:5), JPEG. Não use fotos de pessoas reais nem logos de corretoras.
