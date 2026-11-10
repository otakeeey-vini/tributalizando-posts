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
`publish_now: true` = o dono clicou em **Publicar agora** no painel; o painel dispara a tarefa agendada
"Tributalizando · publicar agora" (trig_01QeinJVxUXpyxPkTYctGXWB), que leva o post à fila e publica na hora.

Sugestões do dono (`suggestions/<id>` no painel): `text, format ("" | carrossel | imagem única | reels), date ("AAAA-MM-DD" ou ""),
slot ("08:00" | "12:00" | "18:00" | ""), notes, status (new | drafting | draft | creating | used | info | skipped), post_id, reply,
created_at, draft, draft_edited, draft_approved`.
`drafting` = o dono pediu **rascunho** (botão "Ver rascunho antes", "Enviar e ver rascunho" ou "Refazer com minhas
observações"); a mesma tarefa da Rotina C escreve o rascunho e grava `status: "draft"`. Em `draft` o dono edita no painel
e, ao clicar "Aprovar e criar o post", a sugestão vai para `creating` com `draft_approved: true`.
`creating` = o dono clicou em **Criar agora**; o painel dispara a tarefa "Tributalizando · criar post da sugestão"
(trig_01VXbeVdJrkYmZXa6zjnSmeV), que segue a Rotina C.

## Rotina A · Sincronizar e publicar (de hora em hora, às :55, das 6:55 às 22:55)

O agendamento do GitHub Actions não é confiável (atrasa ou não roda). Por isso esta rotina é quem dispara
a publicação, no minuto 00 de cada hora.

1. Leia todos os documentos de `posts` no painel (ArtifactData `list`, guarde as `version`).
2. Para cada documento com `status: "approved"` e `queued` falso:
   - em `queue/<id>/post.json` grave `caption`, `scheduled_at` e `status: "approved"`;
   - depois do push, atualize no painel `queued: true` (com `if_version`).
3. Para `status: "discarded"` (ou de volta a `pending`) no painel: grave o mesmo `status` no `post.json`
   se ele ainda não foi publicado.
4. Um commit só (`git pull --rebase` antes), mensagem "Sincroniza aprovações do painel". Sem mudanças, sem commit.
5. Se existir algum `post.json` com `status: "approved"` e `scheduled_at` até o fim da hora seguinte:
   espere até o minuto 00 (use espera em segundo plano, não `sleep` em primeiro plano) e dispare o publicador:
   `gh api -X POST repos/otakeeey-vini/tributalizando-posts/actions/workflows/publicar.yml/dispatches -f ref=main -f 'inputs[modo]=publicar'`.
   Acompanhe a execução até terminar (`gh api repos/.../actions/runs`). Se nada estiver vencido, pule este passo.
6. `git pull --rebase` e traga para o painel o que o publicador gravou: `post.json` com `published`
   (copie `status`, `media_id`, `published_at`) ou `error` (copie `status` e `error`).
7. Nunca altere a legenda ou o horário que o dono editou. Nunca publique nada direto na API: só pelo workflow.

## Rotina B · Criar posts do dia seguinte (diária, à tarde)

1. Veja em `pautas.md` o que já foi publicado ou está na fila e **não repita** tema nem ângulo dos últimos 30 dias.
1.1. **Sugestões do dono vêm primeiro.** Leia `suggestions` no painel (ArtifactData `list`). Para cada uma com
   `status: "new"`, da mais antiga para a mais nova (ignore `drafting`/`draft`: estão com o dono ou com a Rotina C):
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
     (salvar, enviar, comentar), **gancho para seguir** (obrigatório, ver abaixo), "Base: ...", "Conteúdo informativo; cada caso merece análise individual.",
     5 a 8 hashtags. Máximo 2.200 caracteres.
   - **Gancho para seguir, sempre no final** (pedido do dono): toda legenda fecha o CTA com uma linha
     "👉 Siga @tributalizando ..." que dê um motivo ligado ao tema (ex.: "pra não perder o prazo da DeCripto",
     "amanhã tem a parte 2", "todo dia, imposto de cripto sem juridiquês"). A última lâmina (`cta`) e a última
     cena do Reels também levam "**Siga** @tributalizando"; os geradores acrescentam sozinhos se faltar,
     mas prefira escrever uma ação com motivo específico em `actions`.
   - Tipos de lâmina: `cover`, `point`, `big`, `checklist`, `cta` (ver docstring de `scripts/render.py`).
     Destaque com `**texto**`. Títulos de até ~6 palavras por linha; corpo de lâmina com no máximo ~45 palavras.
   - Não cite nomes de corretoras como "estrangeiras" sem confirmar; prefira "corretora sediada no exterior".
5. Renderize (`python3 scripts/render.py queue/<pasta>/spec.json`), **abra cada JPEG e confira** texto cortado,
   sobreposição e erros de português. Corrija e renderize de novo se preciso.
6. Commit + push das pastas novas (status `pending` — o publicador ignora pendentes).
7. Envie as artes ao painel (Artifact publish com `url` do painel, `asset: true`, `file_paths`) e crie os
   documentos em `posts` (ArtifactData `batch` com `set`), `status: "pending"`, `queued: false`.
8. Acrescente as 3 pautas em `pautas.md` (data, horário, título, formato) e faça commit.

## Rotina C · Rascunho ou post de sugestão agora (disparada pelo painel)

0. **Rascunhos primeiro.** Para cada sugestão com `status: "drafting"`: pesquise e confira na fonte (passo 3 da
   Rotina B), **não** renderize nem crie post. Grave em `draft` (com `if_version`) e mude para `status: "draft"`:
   ```
   draft: { format: "carrossel" | "imagem única" | "reels", tone: "técnico e direto" | "didático" | "leve e próximo" | "alerta",
            narration: "nenhuma" | "sintetica" | "paga" | "propria" (só reels), duration: 15-60 (só reels),
            title, hook (1ª linha da legenda), follow (gancho "Siga @tributalizando ..."),
            parts: [{ type: cover|point|big|checklist|cta, title, text (checklist: 1 item por linha), visual, speech (fala, se houver narração) }],
            sources: [...], claude_notes (1 a 2 frases: limitações, o que não deu para confirmar), owner_notes }
   ```
   Se já existir `draft` (dono pediu para refazer), parta dele e siga `owner_notes`; mantenha `owner_notes` no novo rascunho.
   Sem fonte confirmável ou ideia vaga: `status: "info"` com `reply`, como abaixo.
1. Liste `suggestions` com `status: "creating"`. Para cada uma, crie **um** post seguindo os passos 3 a 7 da
   Rotina B (pesquisa na fonte, spec, render, conferência das artes, push, assets e documento no painel).
2. Horário (`scheduled_at`): se a sugestão tiver `date` e `slot` futuros, use-os. Senão, o próximo horário entre
   8h, 12h e 18h (hoje ou amanhã) ainda sem post na fila; se todos de hoje e amanhã estiverem ocupados, use o
   próximo dia livre. O dono pode publicar na hora pelo botão **Publicar agora**.
3. Formato: o pedido na sugestão (`carrossel`, `imagem única` ou `reels`; para `reels` siga a seção "Reels animados");
   sem pedido, o que servir melhor ao conteúdo.
   **Com `draft` aprovado pelo dono, ele manda**: siga formato, tom, ordem e texto das lâminas/cenas, visuais, duração,
   gancho e `owner_notes`. Só mude o que estiver errado na norma ou não couber na arte (texto cortado), e diga o que
   mudou no `reply`. Narração (`narration` diferente de `nenhuma`): enquanto não estiver implementada (em teste),
   gere o Reels sem narração e avise no `reply`.
4. Na sugestão grave `status: "used"`, `post_id` e um `reply` curto; no post, `suggestion_id`. Sem fonte
   confirmável ou ideia vaga: `status: "info"` com `reply` dizendo o que falta. Sempre com `if_version`.
5. Acrescente a pauta em `pautas.md` e faça commit.

## Narração (vale para `speech` dos rascunhos e para `narration` dos Reels)

Regra do dono: a narração **explica o que está sendo mostrado, mas nunca é só a leitura do texto da tela**.
Ela vai além da arte, como um contador explicando a um cliente, no **tom** escolhido para o post.

Cada fala de cena deve trazer pelo menos um destes, que **não** está escrito na tela:
- o **porquê** da regra (o que a Receita quer controlar, de onde vem o limite);
- um **exemplo concreto em reais** ("vendeu quarenta mil, lucrou mil...");
- a **consequência prática** ou o próximo passo (DARF, prazo, o que guardar, o que acontece se esquecer);
- o **erro comum** que aquela tela evita.

Como escrever:
- Pode citar a ideia da tela em poucas palavras para ancorar, mas não repita frase nem lista da arte.
- Segunda pessoa ("você"), frases curtas, sem juridiquês. Norma citada no máximo uma vez, de forma falada
  ("a regra está na Instrução Normativa 2.291, de 2025").
- Escreva para ser **falado**: números por extenso ou como se fala ("trinta e cinco mil reais", "quinze por
  cento", "DARF código quarenta e seis zero zero"); nada de siglas soltas sem explicar na primeira vez.
- Ritmo de 2,5 palavras por segundo: cada fala cabe na duração da cena (cena de 6 s ≈ 15 palavras). Abertura
  com gancho nos 3 primeiros segundos; fechamento com um convite em uma frase.
- Tom: "técnico e direto" = preciso, sem floreio; "didático" = mais exemplo e passo a passo; "leve e próximo" =
  conversa, pode ter uma pitada de humor; "alerta" = foco no risco e no prazo, sem alarmismo.
- Os Reels guardam a narração em `narration: [{shows: "resumo do que está na tela", text: "fala"}]`, uma por
  cena, no `post.json` e no documento do painel. O dono edita no painel; na Rotina A, se a narração mudou num
  Reels aprovado, gere a voz e o vídeo de novo antes de publicar.

Exemplo (tela: "R$ 35 mil · é o limite de vendas no mês, não de lucro"):
- Ruim (leitura): "Trinta e cinco mil reais é o limite de vendas no mês. Não é limite de lucro."
- Bom: "Muita gente acha que pode lucrar até trinta e cinco mil por mês sem imposto. Não é assim: a Receita
  olha quanto você vendeu, somando todas as moedas. Vendeu quarenta mil e lucrou só mil? Passou do limite,
  e esse lucro de mil reais paga imposto, com DARF até o fim do mês seguinte."

## Identidade visual

Verde-floresta `#0E3B2E`, verde-profundo `#082A20`, dourado `#E8B931`, creme `#F6F1E6`, tinta `#13221C`.
Tipos: Inter Display (títulos, 800–900), Inter (texto), Lora itálico (citação no CTA). Logo: `brand/logo.svg`
(quadrado arredondado com "T" dourado e moeda). Wordmark "tributa**lizando**" com "lizando" em dourado.
Artes 1080×1350 (4:5), JPEG. Não use fotos de pessoas reais nem logos de corretoras.

## Reels animados (ativo quando pedido; ainda NÃO entra sozinho no lote da Rotina B)

Gere Reels quando o dono pedir, inclusive por sugestão com `format: "reels"` (Rotinas B e C).
Por conta própria, não, até que esta seção diga que Reels entram na variação de formatos da Rotina B.
- Gerador: `python3 scripts/render_video.py queue/<pasta>/spec.json` → `video.mp4` (1080×1920, 30 fps,
  H.264 + AAC, trilha sintetizada própria), `cover.jpg` e `post.json` com `format: "reels"`, `video`, `cover`.
- Spec: campos de sempre + `scenes` (tipos `hook`, `point`, `big`, `checklist`, `cta`; ver docstring do script).
  Ideal 15 a 30 s, 4 a 6 cenas. Área segura: o script já deixa margem para a interface do Instagram.
- Painel: envie `video.mp4` e `cover.jpg` como assets; no documento grave `video: "/_blob/<id>"`,
  `images: ["/_blob/<id da capa>"]`, `format: "reels"`. O painel mostra o player.
- Publicação: `scripts/publish.py` publica como REELS (`share_to_feed`, `cover_url`) quando `post.json` tem `video`.
