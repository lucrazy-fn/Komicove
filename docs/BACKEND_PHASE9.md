# Backend database and failures / Banco e falhas do backend

## Português

O backend usa `KOMICOVE_DATABASE_URL` (ou o legado `PANEL_DATABASE_URL`). Sem URL, usa SQLite local e preserva `panel.db` quando ele já existe. Os ajustes abaixo se aplicam somente ao PostgreSQL; todos aceitam também o prefixo legado `PANEL_`:

| Variável | Padrão | Uso |
| --- | ---: | --- |
| `KOMICOVE_DB_POOL_PRE_PING` | `true` | Verifica conexões antes do uso. |
| `KOMICOVE_DB_POOL_SIZE` | `5` | Conexões persistentes por processo. |
| `KOMICOVE_DB_MAX_OVERFLOW` | `10` | Conexões extras temporárias por processo. |
| `KOMICOVE_DB_POOL_TIMEOUT` | `30` | Segundos de espera por conexão livre. |
| `KOMICOVE_DB_POOL_RECYCLE` | `1800` | Segundos para reciclar conexões; `-1` desativa. Ajuste abaixo do limite de inatividade do servidor/proxy quando necessário. |

Considere o número de processos ao dimensionar o total máximo de conexões: `(POOL_SIZE + MAX_OVERFLOW) x processos`.

`init_db()` executa a migração incremental na inicialização. A Fase 9 adiciona índices idempotentes em `publications(status, published_at)`, `publications(user_id, created_at)`, `notifications(user_id, created_at)` e `session_tokens(user_id, created_at)`. Eles correspondem, respectivamente, à descoberta, às publicações do usuário, às notificações e à lista de sessões. `LibraryState` e aliases já têm restrições únicas iniciadas por `user_id`, usadas na sincronização; os tokens de ação/moderação são consultados por hash único antes de verificar `expires_at`, e seus índices de expiração existentes são preservados. Não há migração destrutiva. Faça backup antes de atualizar um banco de produção.

Falhas temporárias de banco/storage retornam 503, timeouts retornam 504 e erros internos retornam 500. Cada resposta inclui `X-Request-ID`; envie esse valor ao investigar logs. Os logs de requisição registram ID, método, status, classe da exceção e posições da pilha, sem mensagens de exceção, parâmetros SQL ou credenciais.

## English

The backend uses `KOMICOVE_DATABASE_URL` (or legacy `PANEL_DATABASE_URL`). Without a URL it uses local SQLite and keeps an existing `panel.db`. The settings above apply only to PostgreSQL and also accept the legacy `PANEL_` prefix. Pool size and overflow are per process; keep their combined total within the database connection limit. Set recycle below a server or proxy idle limit when needed; `-1` disables it.

`init_db()` runs the incremental migration on startup. Phase 9 adds the four idempotent indexes listed above for discovery, user publications, notifications, and sessions. `LibraryState` and its aliases already have user-first unique keys; action and moderator tokens are looked up by unique hash before `expires_at` is checked, so their existing expiry indexes remain. Back up production data before updating.

Temporary database/storage failures return 503, timeouts return 504, and internal errors return 500. Every response includes `X-Request-ID` for log correlation. Request logs omit exception messages, SQL parameters, and credentials.
