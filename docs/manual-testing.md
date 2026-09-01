# 手動での動作確認

自動テスト（`docs/local-testing.md`）とは別に、動いているアプリを手で叩いて確かめる手順。

- **API（curl / Swagger）**: health / 認証（email OTP）/ `/me`（Phase 02）→ 章 1〜5
- **SPA（ブラウザ）**: ログイン画面 → 保護画面 → サインアウト（Phase 03）→ 章 6

章 7（内部状態）・章 10（リセット）は両方で共通。

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

起動時ログに DynamoDB テーブル / SQS キュー / S3 バケットの作成が出る
（ローカルのみ。dev/prod は Terraform）。

## SPA を起動（章 6・9 のブラウザ操作で使う）

```bash
make web        # → http://localhost:3000  （さらに別ターミナル。API も起動しておく）
```

Vite dev サーバ。`/api/*` は `vite.config.ts` の proxy で `:8000` の API へ同一オリジンで転送される
（本番は CloudFront が同じ振り分けをする）。フロントの `.env` は不要（Sentry は DSN 未設定で no-op）。

## ワーカーを起動（章 8・9 で使う）

```bash
make worker     # SQS をポーリング。起動時にローカルのキュー / DLQ / テーブルを作成
```

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

## 6. SPA（ブラウザ）で通しで確認

前提: `make up` / `make migrate` / `make api` / `make web` が起動済み。ブラウザの devtools を開いておく。

### ハッピーパス

1. <http://localhost:3000/> を開く → 未認証なので `/login` にリダイレクト（`ProtectedRoute` が
   `state.from` に元パスを載せる）。URL が `/login` に変わる。
2. **Email** に `me@example.com` を入れて **Send code**。
   - Network タブで `POST /api/v1/auth/otp/request` が `202`、`Set-Cookie: cc_otp_challenge=...`。
   - 見出しが「We sent a code to me@example.com」に変わり、6 桁入力欄が出る。
3. コードを取得（章 3 と同じ）: `make api` のターミナルの `Your sign-in code is 123456` 行、
   または `APP_EMAIL_BACKEND=smtp` なら <http://localhost:8025>。
4. **6-digit code** に貼って **Verify**。
   - `POST /api/v1/auth/otp/verify` が `200`、`cc_session`（httpOnly）と `cc_csrf`（JS 可読）が付く。
   - `/` にリダイレクト。ヘッダに自分のメールと **Sign out**、本文に「Welcome back」。
5. **リロード** しても入ったまま（`useMe` が cookie で `/api/v1/me` を引き直す）。
6. **Sign out** → `POST /api/v1/auth/logout`（`x-csrf-token` は CSRF ミドルウェアが自動付与）→
   `/login` に戻る。以降 `/` を開くと再びログインへ。

### 失敗系・エッジ

| やること | 期待 |
|---|---|
| Email 欄に `foo`（不正形式）で Send code | 送信されず「Enter a valid email address」（zod、クライアント側） |
| 6 桁欄に `12345` など桁不足で Verify | 送信されず「Enter the 6-digit code」 |
| 誤ったコードで Verify | `401`、フォーム上部に赤い alert（Problem Details の `detail`）。画面は 6 桁入力のまま |
| コード入力画面で「Use a different email」 | メール入力画面に戻り、エラー表示もクリア |
| ログイン済みで <http://localhost:3000/login> を直接開く | すぐ `/` に戻る（`LoginPage` が `useMe` を見てリダイレクト） |
| 存在しないパス <http://localhost:3000/nope> | `/` に戻る（未ログインなら続けて `/login`） |
| `make api` を止めて画面操作 | `/api/v1/me` が失敗、`ProtectedRoute` は未認証扱いで `/login`。操作系は alert |
| devtools > Application で cookie 確認 | `cc_session` は HttpOnly ✓、`cc_csrf` は HttpOnly なし（JS から読めて当然） |

### 本番ビルドの確認（任意）

```bash
cd frontend && pnpm build && pnpm preview   # → http://localhost:4173
```

`pnpm preview` は `/api` を proxy しない。API 疎通まで見たいときは `make web`（dev）を使う。

---

## 7. 内部状態をのぞく

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

## 8. 非同期ワーカー（Phase 04）

`make up`（LocalStack の SQS / DynamoDB）が前提。

### ワーカーを起動

```bash
make worker
```

起動ログ：`worker.start queue=...career-copilot-local-tasks`。
初回は `default` / `browser` の 2 キュー + 各 DLQ、`-processed-tasks` テーブルを自動作成する。

### タスクを投入して処理を見る（別ターミナル）

```bash
cd backend

# 成功するタスク
uv run python -m scripts.enqueue ping '{"echo": "hello"}'
#   → ワーカー側ログ: task.start → task.ping (echo=hello) → task.done

# 失敗するタスク
uv run python -m scripts.enqueue ping '{"fail": true}'
#   → task.failed + traceback。メッセージは削除されず in-flight のまま
```

`--browser` を付けると `browser` キューへ（ワーカーは `default` を見ているので処理はされない）。

### 失敗 → 再配信 → DLQ

失敗タスクは `VisibilityTimeout`（120 秒）が切れると再配信される。3 回受信されると DLQ 送り。
待たずに確認したい場合はキュー属性を見る：

```bash
export AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local AWS_REGION=ap-northeast-1
alias sqs='aws --endpoint-url=http://localhost:4566 sqs'

Q=$(sqs get-queue-url --queue-name career-copilot-local-tasks --query QueueUrl --output text)
sqs get-queue-attributes --queue-url "$Q" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible

DLQ=$(sqs get-queue-url --queue-name career-copilot-local-tasks-dlq --query QueueUrl --output text)
sqs receive-message --queue-url "$DLQ"      # 3 回失敗した後にここへ来る
```

### 冪等性

同じメッセージが 2 回配信されても 2 回目はスキップされる（成功後にキーを記録）。
`scripts.enqueue` は毎回新しいキーを振るので、SQS の重複配信でしか再現しないが、
処理済みキーは DynamoDB で確認できる：

```bash
alias ddb='aws --endpoint-url=http://localhost:4566 dynamodb'
ddb scan --table-name career-copilot-local-processed-tasks
#   → 処理成功した idempotency_key と expires_at（TTL 24h）
```

### Lambda ハンドラの単体確認（キュー不要）

```bash
cd backend && uv run python -c "
import asyncio, json
from app.workers.lambda_handler import _process
from app.queue.base import TaskMessage
ev = [
  {'messageId': 'ok',  'body': TaskMessage(task='ping', payload={'echo':'a'}).to_body()},
  {'messageId': 'bad', 'body': TaskMessage(task='ping', payload={'fail':True}).to_body()},
]
print(asyncio.run(_process(ev)))
"
#   → {'batchItemFailures': [{'itemIdentifier': 'bad'}]}
```

### LLM クライアント

実際の Claude 呼び出しには `APP_ANTHROPIC_API_KEY` が要る（未設定なら `structured()` は
`ServiceUnavailableError`）。キーを入れれば：

```bash
cd backend && APP_ANTHROPIC_API_KEY=sk-ant-... uv run python -c "
import asyncio
from app.llm import get_llm_client
schema = {'type':'object','properties':{'title':{'type':'string'}},'required':['title']}
r = asyncio.run(get_llm_client().structured(
    prompt='Extract the job title from: Senior Backend Engineer, Tokyo', schema=schema))
print(r.data, r.input_tokens, r.output_tokens, r.cost_usd)
"
```

---

## 9. レジュメ登録・希望条件（Phase 05）

前提（開けておくターミナル）:

| 確認方法 | 必要なプロセス |
|---|---|
| ブラウザで通し（下記「レジュメ（ブラウザ）」） | `make up` + `make api` + **`make web`** + `make worker` |
| curl だけ（「API だけで確認」以降） | `make up` + `make api` + `make worker` |
| enqueue だけ見たい（処理はされない） | `make up` + `make api` |

`make up` は `-d` なので、実際に開くのは api / web / worker の最大 3 枚。
ブラウザは <http://localhost:3000>（`make web`）にサインイン後、ヘッダの
**Résumés** / **Preferences**。

### レジュメ（ブラウザ）

1. **Résumés** → 「Paste your résumé」に職務経歴を貼って **Create from text**、
   または PDF/DOCX を選択（ブラウザが presigned URL で S3 へ直接 PUT）
2. 詳細画面に遷移し「Reading and structuring…」（2 秒間隔でポーリング）
3. 実 LLM 呼び出しには `APP_ANTHROPIC_API_KEY` が必要（`backend/.env`、章 準備参照）。
   未設定だと worker が `resume.process` で失敗し、version は `structuring` のまま
   → `make worker` のログに traceback、SQS で redrive → DLQ
4. キーがあれば `ready` になり編集フォーム表示：summary / skills（カンマ区切り）/
   会社・実績。数値の無い実績には 💡 の定量化ヒント。**Save** で `PATCH`

### API だけで確認（キー不要な範囲）

```bash
J=/tmp/j; # 章 3 でログイン済みのクッキージャー
CSRF=$(awk '/cc_csrf/{print $NF}' $J)

# テキストから作成 → status=structuring、resume.process が enqueue される
curl -s -c $J -b $J -X POST localhost:8000/api/v1/resumes \
  -H 'content-type: application/json' -H "x-csrf-token: $CSRF" \
  -d '{"raw_text":"Jane Doe. Backend engineer six years. Python FastAPI PostgreSQL AWS."}'

curl -s -c $J -b $J localhost:8000/api/v1/resumes           # 一覧
```

### アップロード用 S3 の中身

```bash
alias s3='aws --endpoint-url=http://localhost:4566 s3'
s3 ls s3://career-copilot-local-resumes/resumes/ --recursive
```

### 希望条件

```bash
curl -s -c $J -b $J -X PUT localhost:8000/api/v1/preferences \
  -H 'content-type: application/json' -H "x-csrf-token: $CSRF" \
  -d '{"desired_roles":["Backend Engineer"],"locations":["Tokyo","Remote"],"salary_min":8000000,"remote_required":true}'
curl -s -c $J -b $J localhost:8000/api/v1/preferences
```

---

## 9b. 求人ソース登録・取得（Phase 06 part 1）

前提：`make up` + `make api`（+ ブラウザ通しなら `make web`、取得を実際に走らせるなら `make worker`）。

### ブラウザ

1. ヘッダ **Jobs** → 「Manage career-page sources」→ Careers URL に採用ページ URL
   （例 `https://boards.greenhouse.io/anthropic`）を入れて **Add source**
2. 一覧にカードが出て「Waiting for first fetch…」。数秒で worker が拾い
   `robots: ok/blocked/unknown` と最終取得時刻 or エラーに変わる
3. **Fetch now** で即再取得、**Pause/Resume**、**Delete**
4. **Jobs** に戻り **Add a job manually** で会社・タイトルを入れると一覧に追加
   （★で bookmark）。スコアが付くのは part 2

> part 1 の `job_source.fetch` は robots チェックと到達性確認まで。求人の
> 分類・抽出・スコアリングは part 2。

### API だけ

```bash
J=/tmp/j; CSRF=$(awk '/cc_csrf/{print $NF}' $J)

# ソース登録 → job_source.fetch が enqueue される
curl -s -c $J -b $J -X POST localhost:8000/api/v1/job-sources \
  -H 'content-type: application/json' -H "x-csrf-token: $CSRF" \
  -d '{"url":"https://boards.greenhouse.io/anthropic"}'

curl -s -c $J -b $J localhost:8000/api/v1/job-sources    # robots_state / last_* を確認

# 期限の来たソースをまとめて enqueue（EventBridge ディスパッチャの代役）
uv run --project backend python -m scripts.schedule_fetches

# 手動求人
curl -s -c $J -b $J -X POST localhost:8000/api/v1/jobs \
  -H 'content-type: application/json' -H "x-csrf-token: $CSRF" \
  -d '{"company_name":"Acme","title":"Backend Engineer","location":"Tokyo"}'
curl -s -c $J -b $J localhost:8000/api/v1/jobs
```

SSRF ガードの確認：`{"url":"http://169.254.169.254/"}` や `http://localhost:8000/`
を登録して `make worker` のログで `job_source.fetch` が `last_error` を残すのを見る
（`APP_FETCH_ALLOW_PRIVATE_HOSTS` は既定 false）。

---

## 10. リセット

```bash
# DynamoDB / SQS / MailHog の中身だけ捨てる
docker compose restart localstack mailhog

# 特定のキューだけ空にする
sqs purge-queue --queue-url "$Q"

# DB も含めて全部
make down && docker compose down -v && make up && make migrate
```
