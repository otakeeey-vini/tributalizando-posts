# Tributalizando · publicação automática

Publica no Instagram do @tributalizando os posts aprovados no painel de revisão.

- `queue/<post>/post.json` + imagens JPEG: um post por pasta.
- `.github/workflows/publicar.yml`: roda a cada 15 minutos e publica o que estiver
  com `"status": "approved"` e horário já vencido. Depois grava `published` ou `error`.
- `scripts/publish.py`: chama a API oficial do Instagram (gratuita).

Segredos necessários (Settings → Secrets and variables → Actions):
- `IG_ACCESS_TOKEN`: token gerado no app da Meta
- `IG_USER_ID`: 17841472741202861

Teste manual: Actions → Publicar no Instagram → Run workflow → modo **testar**.
