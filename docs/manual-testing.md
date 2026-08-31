# 手動での動作確認

自動テスト（`docs/local-testing.md`）とは別に、動いているアプリを手で叩いて確かめる手順。
Phase 02 時点で叩けるのは health / 認証（email OTP）/ `/me` まで。

---

## 準備（初回）

```bash
make install
cp backend/.env.example backend/.env          # APP_EMAIL_BACKEND=console のまま
make up                                        # Postgres:5433 / LocalStack:4566 / MailHog:8025
make migrate                                   # スキーマ適用
```

## API を起動

```bash
make api        # → http://localhost:8000  （別ターミナル）
```

起動時ログに `career-copilot-local-{sessions,otp,ratelimit}` の DynamoDB テーブル作成が出る
（ローカルのみ。dev/prod は Terraform）。

---

## 1. ヘルスチェック

```bash
curl -s localhost:8000/healthz            # {"status":"ok"}
curl -s localhost:8000/readyz             # {"status":"ready","checks":{"database":"ok"}}
```

`make down` で DB を止めてから `/readyz` を叩くと `503` / `"database":"error"` になる。

## 2. Swagger UI（対話的に叩く）

<http://localhost:8000/docs> — `/api/v1/auth/*` と `/me` が並ぶ。
`openapi.json` は <http://localhost:8000/openapi.json>。

---

## 3. 認証（email OTP）— ハッピーパス

Cookie を保持する必要があるので `-c/-b` でクッキージャーを使う。

```bash
JAR=/tmp/cc.jar; rm -f $JAR

# (1) コード発行 — 常に 202（アカウントの有無を漏らさない）
curl -s -c $JAR -b $JAR -X POST localhost:8000/api/v1/auth/otp/request \
  -H 'content-type: application/json' -d '{"email":"me@example.com"}'
# → {"status":"accepted"}   + Set-Cookie: cc_otp_challenge=...

# (2) コードを取得
#   console バックエンド(既定): `make api` を動かしているターミナルの
#     `email.console ... body=...Your sign-in code is 123456...` から読む
#   smtp バックエンド        : http://localhost:8025 (MailHog) で見る
CODE=123456   # ↑ から手で貼る

# (3) 検証 — 成功で cc_session（httpOnly）と cc_csrf（JS 可読）を発行
curl -s -c $JAR -b $JAR -X POST localhost:8000/api/v1/auth/otp/verify \
  -H 'content-type: application/json' -d "{\"email\":\"me@example.com\",\"code\":\"$CODE\"}"
# → {"id":"...","email":"me@example.com","email_verified":true,...}

# (4) 保護リソース
curl -s -c $JAR -b $JAR localhost:8000/api/v1/me

# (5) セッション一覧
curl -s -c $JAR -b $JAR localhost:8000/api/v1/auth/sessions

# (6) ログアウト — 変更系は CSRF ヘッダ必須
CSRF=$(awk '/cc_csrf/{print $NF}' $JAR)
curl -s -c $JAR -b $JAR -o /dev/null -w '%{http_code}\n' \
  -X POST localhost:8000/api/v1/auth/logout -H "x-csrf-token: $CSRF"     # 204

curl -s -c $JAR -b $JAR -o /dev/null -w '%{http_code}\n' localhost:8000/api/v1/me   # 401
```

## 4. 認証 — 失敗系（すべて `application/problem+json`）

| やること | 期待 |
|---|---|
| `/otp/verify` を `/otp/request` 前に叩く（challenge cookie なし） | `422` `code: validation-error` |
| 誤ったコードで検証 | `401` `code: authentication-required` |
| 同じコードで 5 回失敗 | 5 回目で `429` `code: rate-limited`、以降そのコードは無効（新規発行が必要） |
| `/otp/request` を同じメールに 6 回以上 | いずれも `202` だが 6 回目以降はメールが飛ばない |
| `/logout` を CSRF ヘッダなしで | `403` `code: csrf-check-failed` |
| Cookie なしで `/me` | `401` |

```bash
# 例: 誤コード
curl -s -c $JAR -b $JAR -X POST localhost:8000/api/v1/auth/otp/request \
  -H 'content-type: application/json' -d '{"email":"x@example.com"}' >/dev/null
curl -s -c $JAR -b $JAR -X POST localhost:8000/api/v1/auth/otp/verify \
  -H 'content-type: application/json' -d '{"email":"x@example.com","code":"000000"}'
```

## 5. レスポンスヘッダの確認

```bash
curl -s -D - -o /dev/null localhost:8000/healthz | grep -iE \
  'x-request-id|x-content-type-options|x-frame-options|content-security-policy|referrer-policy'
```

`X-Request-ID` はリクエストごとに変わる。`X-Request-ID: <任意>` を送ると echo される。

---

## 6. 内部状態をのぞく

### MailHog（`APP_EMAIL_BACKEND=smtp` のとき）

`backend/.env` で `APP_EMAIL_BACKEND=smtp` にして `make api` を再起動 → <http://localhost:8025>。

### DynamoDB（LocalStack）

```bash
export AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local AWS_REGION=ap-northeast-1
alias ddb='aws --endpoint-url=http://localhost:4566 dynamodb'

ddb list-tables
ddb scan --table-name career-copilot-local-sessions
ddb scan --table-name career-copilot-local-otp        # code_hash のみ（平文コードは無い）
ddb scan --table-name career-copilot-local-ratelimit
```

セッション / OTP はハッシュだけが保存されていることを確認できる。

### Postgres

```bash
docker compose exec db psql -U career -d career_copilot \
  -c "select email, email_verified_at is not null as verified, created_at from users;"
```

---

## 7. リセット

```bash
# DynamoDB / MailHog の中身だけ捨てる
docker compose restart localstack mailhog

# DB も含めて全部
make down && docker compose down -v && make up && make migrate
```
