# Career Copilot 開発着手プラン

`CLAUDE.local.md`（現行仕様）を正として、**新規にモノレポを構築する前提**でのタスクをフェーズ順に整理したもの。

## 前提

| 項目 | 内容 |
|---|---|
| 出発点 | ゼロから新規構築。既存の実装・雛形は参照しない。 |
| 正となる仕様 | 現行 `CLAUDE.local.md`。ATS 公開 API / JSON-LD / LLM フォールバックのハイブリッド求人取得。 |
| MVP 順序 | ① レジュメ登録 → ② 求人登録・取得 → ③ ギャップ分析・添削 → ④ 選考進捗（簡易）。面接対策は後回し可。 |
| 規模の前提 | まず開発者本人の個人利用。ホスティング・認証・暗号化の選定は「個人利用でアイドルコストを抑える」構成を既定にし、負荷や公開範囲が広がった時点の切り替え先を各フェーズに明記する。 |

---

## 技術選定（確定分と根拠）

`CLAUDE.local.md` が指定・許容する範囲で、一般的なベストプラクティスに沿って絞ったもの。迷う点は Phase 00 で ADR 化する。

| 領域 | 選定 | 根拠 / 切り替え先 |
|---|---|---|
| バックエンド | FastAPI + SQLAlchemy 2.0 (async) + asyncpg + Alembic | 仕様指定。I/O（LLM・HTTP）が支配的なので async が有利。 |
| API ホスティング | **Lambda + API Gateway**（Lambda Web Adapter か Mangum）から開始 | 個人利用ではアイドルコストがほぼゼロ。持続的トラフィックや常時接続が必要になったら ECS Fargate + ALB へ。 |
| 認証 | アプリ実装。**opaque セッショントークンを httpOnly / Secure / SameSite=Lax cookie** で発行、セッションは DynamoDB（TTL）に保存、変更系リクエストに CSRF 対策 | JS から触れるストレージに JWT を置かない。Cognito（仕様の代替案）は個人利用では過剰。 |
| キュー | SQS（+ DLQ） | 仕様指定。無料枠内。 |
| 非同期ワーカー | 短時間ジョブ（LLM 構造化・分析）＝ **Lambda**、ブラウザ/クロール（Playwright、15 分超の可能性）＝ **Fargate ワーカー** | ジョブ種別で分割。Playwright は Lambda パッケージングが苦しいので Fargate のコンテナで動かす。 |
| 定期実行 | **単一ディスパッチャ**：EventBridge Scheduler → Lambda が「取得期限が来た `job_sources`」を SQS に投入 | ソースごとに EventBridge ルールを作らない（数が増えると管理不能）。 |
| DB | RDS for PostgreSQL（`db.t4g` 小）。将来 Aurora Serverless v2 も可 | 仕様指定。マッチ度・名寄せで近い将来 `pgvector` を使う想定。 |
| フロントエンド | **Vite + React + React Router の SPA**（S3 + CloudFront 配信） | 認証済みダッシュボードで SSR/SEO 不要。Next.js App Router は RSC / Node ホストの複雑さに見合わない。SSR が必要になったら再検討（ADR）。 |
| フロント状態・取得 | TanStack Query、フォームは React Hook Form + zod、API クライアントは `openapi-typescript` + `openapi-fetch` で型生成 | 標準的で軽量。 |
| IaC | Terraform | 仕様指定（CDK も可）。 |
| シークレット | **SSM Parameter Store（SecureString）** から開始 | 個人利用では無料。ローテーションや複数環境が要るようになったら Secrets Manager へ。 |
| ローカル開発 | `docker-compose`（Postgres + LocalStack で SQS/S3）。ワーカーは本番と同じハンドラ関数をプロセスで回す。テストは `moto` | ローカルで実 Lambda を再現しない（個人開発には過剰）。 |
| Python ツール | `uv` / Ruff（lint + format）/ mypy strict / pytest | 現行の標準。 |

---

## 進め方（原則）

タスクの実体は各フェーズのチェックリストにある。ここでは進め方の原則だけを示す。

- **縦に薄く通す**：各機能で `API → キュー → ワーカー → DB → フロント` を 1 本つなぎ、動く状態を保ちながら広げる。
- **小さな PR とレビューのループ**：短命ブランチ、Conventional Commits、`main` は常にデプロイ可能。詳細は Phase 00。
- **品質ゲートを最初に立てて常時グリーン**：lint / 型 / テスト / terraform validate を Phase 00 で CI に載せる。
- **チケット分割**：フェーズを 0.5〜2 日で終わる単位に割り、`docs/` に実装計画を書く（`fullstack-dev-skills` のワークフローはソロなら任意）。
- **縦の動線を早期に確認**：Phase 04 を終えたら Phase 07 のギャップ分析を薄く 1 本通し、キュー経由 LLM → DB 保存の経路を先に固める。

---

## Phase 00 — 基盤とワークフロー整備

**Goal**: 誰でも `clone → up → test` でき、CI が守る土台を作る。

- [x] モノレポ構成を確定：`backend/`（API + workers 同一パッケージ）`frontend/` `infra/terraform/` `infra/localstack/` `docs/` `scripts/`（ADR-0002）
- [x] Python ツールチェーン：`uv` + `pyproject.toml`（extras を `worker` / `browser` に分割、`package = false`）、Ruff、mypy strict
- [x] Node ツールチェーン：pnpm、TypeScript strict、ESLint（flat config）、Prettier、Vite（React SPA）
- [x] フロント構成の方針決め：状態管理・データ取得（TanStack Query）・フォーム（RHF + zod）・API クライアント（openapi-typescript）を ADR-0008 で確定。UI コンポーネント方針は Phase 03（実画面が出てから）
- [x] pre-commit：generic hooks + detect-secrets（`.secrets.baseline`）+ ruff / mypy / eslint / prettier / terraform fmt の local hook
- [x] ローカル環境：`docker-compose` に Postgres（ホスト **5433**、`_test` DB を init SQL で作成）+ LocalStack（SQS / S3）。`.env.example`、`.editorconfig`、`.gitignore`
- [x] Makefile：`up/down` `install` `api` `web` `migrate` `worker` `lint` `fmt` `test`（+ `make help`）
- [x] CI（GitHub Actions）：backend / frontend / infra の 3 ワークフロー、path フィルタ、依存キャッシュ、`main` と PR で実行
- [x] 依存脆弱性スキャン：`.github/dependabot.yml`（uv / npm / actions / terraform、週次・グループ化）、CI に `pip-audit`（backend）/ `pnpm audit`（frontend）
- [x] ブランチ / コミット規約：trunk ベース（`phase-00-foundation` で作業）、PR テンプレート。Conventional Commits は運用ルール、CODEOWNERS は未設定（任意）
- [x] 初期 ADR：ADR-0001〜0008（ADR 運用 / モノレポ / API Lambda 開始 / cookie セッション認証 / ワーカー Lambda・Fargate 分割 / 求人取得ハイブリッド / 機微データ保護 / フロント SPA）
- [x] README：セットアップ手順、アーキテクチャ図、レイアウト表、private 明記
- [x] シークレット方針：ローカルは `backend/.env`、クラウドは SSM Parameter Store（SecureString）。`.gitignore` で `.env` 除外、detect-secrets で防御

**Done**: `make lint && make test` グリーン、`docker compose up` で API と DB が起動（確認済み）。CI は GitHub 上で `main` push 時に検証。

---

## Phase 01 — ドメインモデルと DB スキーマ

**Goal**: 複数ソースの求人を名寄せでき、機微データを守れるスキーマを固める。

- [ ] エンティティ設計：`users` `job_preferences` `resumes` `resume_versions` `job_sources` `jobs` `job_postings`（名寄せ）`applications` `application_events` `analysis_results` `llm_usage`
- [ ] 共通求人スキーマ：`source_type`(`ats`/`json_ld`/`llm`)、`ats_vendor`、`raw_text_hash`、`match_score`、`needs_review`、構造化フィールド（職種 / 必須・歓迎スキル / 年収 / 勤務地 / リモート可否 / 雇用形態）
- [ ] 名寄せ設計：正規化した会社名 + 職種 + 勤務地（+ ATS の external id）でクラスタリング。`jobs` = 取得単位、`job_postings` = 論理求人
- [ ] `job_sources`：登録 URL、robots 判定結果、スケジュール、最終取得時刻、ソース判定結果（ats_vendor / json_ld / fallback）
- [ ] 機微データ保護（既定）：RDS 保管時暗号化（KMS）、S3 は SSE-KMS、全経路 TLS、IAM / セキュリティグループを最小化、ログ・LLM プロンプトに PII を出さない、保持期間を短く。**アプリ層のカラム暗号化は既定にしない**（検索・索引・鍵運用のコストが高く、レジュメは常時 LLM で復号処理するため効果が薄い）。特定フィールドに必要と判断したら ADR 化
- [ ] `pgvector` 検討：マッチ度スコアリングと名寄せで埋め込み検索が要るか。要るなら拡張を初期マイグレーションに含める
- [ ] Alembic 初期マイグレーション：モデルと一致（`alembic check`）、ロールバック確認
- [ ] ER 図と seed：`docs/data-model.md` に ER 図、開発用 seed スクリプト

**Done**: マイグレーション適用でスキーマ再現・ロールバック可、seed で最小データ投入ができる。

---

## Phase 02 — バックエンド API 基盤

**Goal**: 認証・設定・テスト・可観測性を備えた FastAPI の土台。

- [ ] レイヤー構成：`api → services → repositories → models`。`pydantic-settings` で設定管理
- [ ] 非同期 DB：SQLAlchemy 2.0 + asyncpg、セッション / Unit of Work、Alembic 連携
- [ ] 認証：opaque セッショントークンを httpOnly / Secure / SameSite=Lax cookie で発行、セッションは DynamoDB（TTL）保存、パスワードは argon2、メール登録 + 検証、変更系に CSRF 対策。OAuth（Google / LinkedIn）は後続
- [ ] 認可：ユーザーは自分のリソースのみ（行レベルのアクセス制御を共通化）
- [ ] API 規約：`/api/v1` バージョニング、一覧はページネーション規約を統一、エラーレスポンスは Problem Details（RFC 9457）、セキュリティヘッダ
- [ ] 入力バリデーション：Pydantic で全入力を検証。レート制限（API Gateway スロットリング。アプリ内で足す場合は共有ストア前提。プロセス内 limiter は複数インスタンスで効かない点に注意）
- [ ] 構造化ログ：JSON（structlog 等）、`request_id`、PII はマスク / ハッシュ
- [ ] ヘルスチェック：liveness / readiness（DB 疎通）
- [ ] OpenAPI：自動ドキュメント、フロント向けに `openapi-typescript` で型出力
- [ ] テスト基盤：pytest、トランザクション分離、factory / fixtures、`httpx.AsyncClient`、カバレッジ閾値

**Done**: 登録 → ログイン → 保護リソース取得の E2E テストが通り、OpenAPI が出力される。

---

## Phase 03 — フロントエンド土台

**Goal**: 認証済みで画面遷移でき、API と型付きでつながる SPA の骨格。

- [ ] ルーティング：React Router の構成、認証ガード、共通レイアウト
- [ ] API クライアント：`openapi-fetch` + 生成型、Cookie 認証（credentials: include）、同一オリジン配信（CloudFront が `/api/*` を API Gateway、それ以外を S3 SPA へ）、エラーハンドリング共通化
- [ ] 認証フロー：ログイン / サインアップ / セッション更新 / 保護ルート
- [ ] UI 基盤：Phase 00 で決めたコンポーネント方針・状態管理・データ取得（TanStack Query）・フォーム（RHF + zod）の実装
- [ ] テスト：vitest + Testing Library、Playwright で主要フローの E2E
- [ ] エラー可観測性：フロント・バックエンドのアプリエラー追跡（Sentry 等）

**Done**: ログイン → 保護画面表示 → API 取得 → ログアウト がブラウザで通り、E2E がある。

---

## Phase 04 — 非同期ワーカー基盤

**Goal**: キュー抽象・ワーカー・LLM クライアントをローカルで固める。

- [ ] TaskQueue 抽象：SQS 実装 + キュー未設定時のログフォールバック
- [ ] ワーカーのハンドラ設計：SQS メッセージ 1 件を処理する純粋関数。Lambda は部分バッチ応答（`batchItemFailures`）でラップ、Fargate は受信ループでラップ。冪等性、DLQ
- [ ] ジョブ種別の割り当て：LLM 構造化・分析 → Lambda、ブラウザクロール（Playwright）→ Fargate ワーカーサービス
- [ ] ローカル実行：`docker-compose` の LocalStack（SQS / S3）に対し、ワーカーを本番と同じハンドラ関数を呼ぶプロセスで回す（`make worker`）。テストは `moto` + ハンドラ関数の直接呼び出し
- [ ] LLM クライアント：Claude、forced tool use で JSON Schema 構造化、トークン / 概算コストを `llm_usage` に記録、リトライ / バックオフ / タイムアウト、SDK エラー → `ServiceUnavailable` 写像、モデルは `settings.llm_model`

**Done**: enqueue → ワーカー処理 → 成功削除 / 失敗 redrive がローカルで自動テストできる。

---

## Phase 05 — MVP① 初期レジュメ登録

**Goal**: PDF / Word または フォームから、構造化された職務経歴と希望条件を登録できる。

- [ ] アップロード：PDF / Word → S3（presigned PUT）、サイズ・形式バリデーション
- [ ] テキスト抽出：PDF（pypdf / pdfminer）、docx（python-docx）。抽出失敗時はフォーム入力にフォールバック
- [ ] LLM 構造化：SQS 経由で 会社 / 期間 / 役割 / 実績 を JSON Schema 抽出
- [ ] スキル・経験タグ：レジュメからの自動抽出 と 自己申告 の突き合わせ
- [ ] 実績の定量化サポート：数値化されていない実績への指摘
- [ ] CRUD + バージョン：`resumes` / `resume_versions`、構造化結果の確認・編集 API
- [ ] 希望条件の登録：職種、年収レンジ、勤務地、リモート可否、転職時期（`job_preferences`）
- [ ] フロント：アップロード画面、処理中の状態表示、構造化結果の編集フォーム、タグ確認 UI

**Done**: PDF アップロード → 構造化 → 編集 → 保存 の一連が E2E で通る。

---

## Phase 06 — MVP② 求人登録・取得パイプライン

**Goal**: `CLAUDE.local.md §4.2` の 9 手順を、ATS → JSON-LD → LLM の優先順で実装する。

> 着手前に「未決定事項」#2〜#4（ATS ベンダ優先順位・国産 ATS 調査・robots/規約の方針）を潰しておく。

- [ ] URL 登録 API：採用トップ / 求人一覧ページを登録。`job_sources` に保存
- [ ] robots.txt / アクセス制御：取得前に robots を機械チェック（`protego` 等）、Disallow は取らない。アクセス間隔制御、User-Agent 明示
- [ ] ソース判定 A（ATS）：URL パターン（`boards.greenhouse.io` / `jobs.lever.co` / `*.ashbyhq.com` 等）+ ページ内スクリプト / iframe / リンクホストで判定、board 識別子を抽出
- [ ] ATS アダプタ：Greenhouse / Lever / Ashby（+ 国内実績で HERP）から着手 → **共通スキーマへの正規化レイヤー**（ページネーション・日付形式のベンダ差を吸収）。未対応は経路 C へフォールバック
- [ ] ソース判定 B（JSON-LD）：`<script type="application/ld+json">` をパースして `JobPosting` を抽出（stdlib `json` + `selectolax`/`lxml`、または `extruct`）。`@graph` 形式・複数 JobPosting・HTML エンティティ対応。欠損フィールドは `needs_review`
- [ ] ソース判定 C（フォールバック）：クロール（httpx 静的 / Playwright JS 必須は Fargate ワーカー）→ 一覧→詳細リンク発見（キーワード候補抽出 → LLM で「求人詳細か」判定の二段）→ `trafilatura` で本文抽出
- [ ] 差分検知（手順 5）：正規化テキストのハッシュを前回と比較。**必ず LLM 呼び出しの前に置く**。A/B は構造化データを固定フィールド順で文字列化、C は抽出本文
- [ ] 一次フィルタ（手順 6）：ルールベースで「明らかな不一致」のみ除外（職種カテゴリ違い、勤務地 NG かつリモート不可、雇用形態対象外）。ここで LLM を呼ばない。除外分は DB に残さない
- [ ] LLM 構造化（手順 7、C のみ）：差分あり かつ 一次通過のみ。JSON Schema で出力強制、必須欠如は `needs_review`。**取得本文はプロンプトインジェクション前提で扱う**（横断リスク参照）
- [ ] マッチ & 二次フィルタ（手順 8–9）：経歴 × 求人票でマッチ度スコア算出 → 閾値未満は保存せず破棄
- [ ] 保存：閾値超のみ。構造化結果 + `source_type` + `ats_vendor` + `raw_text_hash` + `match_score`
- [ ] スケジューリング：単一ディスパッチャ（EventBridge Scheduler → Lambda）が取得期限の来た `job_sources` を SQS に投入。取得失敗はサイレントリトライせずユーザーに明示し手動登録へ誘導
- [ ] フロント：求人一覧（スコア順）、ソース一覧とステータス、取得失敗表示、手動登録フォーム、ブックマーク / ステータス管理

**Done**: 実 ATS ボード 1 件・JSON-LD ページ 1 件・フォールバック 1 件 で 取得 → スコア → 保存 が通る。

---

## Phase 07 — MVP③ ギャップ分析・レジュメ添削

**Goal**: 求人ごとに不足を可視化し、カスタム版レジュメを Before/After で提示する。

- [ ] 分析 1 本通し：分析トリガー API → SQS → handler → `LlmClient` → `analysis_results` 保存。**Phase 04 直後に薄く先行実装**して縦の動線を固める
- [ ] ギャップ分析：不足スキル・経験、レジュメで言及すべき点、学習 / 資格の推奨
- [ ] レジュメの求人適応：求人ごとのカスタム版を `resume_versions` に生成、元版と比較
- [ ] プロンプト設計：求人票の該当箇所を**根拠として必須出力**、捏造禁止の制約、確信度、`needs_review`。説明可能性（§3.8）。求人本文由来の「指示」を無視する構成
- [ ] Before/After UI：差分表示、採用 / 却下、手動編集
- [ ] エクスポート：Word / PDF、企業ごとのフォーマット対応

**Done**: 求人 1 件に対し ギャップ分析 + カスタム版生成 + 差分表示 + エクスポート ができる。

---

## Phase 08 — MVP④ 選考進捗管理（簡易版）

**Goal**: 応募のステータスと履歴を管理し、停滞をリマインドする。

- [ ] 応募 CRUD：ステータス（書類選考中 / 一次面接 / 最終面接 / 内定 / 辞退）
- [ ] 履歴とメモ：`application_events` で遷移履歴、企業ごとのメモ・面接フィードバック
- [ ] カンバン UI：ドラッグでステータス変更
- [ ] リマインダー：選考スケジュール、ステータス停滞。メール / アプリ内通知
- [ ] ダッシュボード：応募数、通過率、平均選考期間

**Done**: 応募作成 → ステータス遷移 → 履歴閲覧 → ダッシュボード集計 が通る。

---

## Phase 09 — 非機能・横断的関心事

**Goal**: セキュリティ・コスト・可観測性を運用に耐える水準にする。各フェーズと並行で進める。

- [ ] **SSRF 対策**（URL 登録機能の最重要事項）：プライベート / リンクローカル IP・クラウドメタデータ（`169.254.169.254`）・`localhost` をブロック、DNS リバインディング対策、リダイレクト追跡制限、スキームは http/https のみ、タイムアウト・レスポンスサイズ上限。Phase 06 と同時に実装
- [ ] 個人情報保護：Phase 01 の既定（保管時暗号化・TLS・IAM 最小化・ログの PII 除去・保持期間）を実装で確認、退会時のデータ削除
- [ ] LLM コスト管理：ユーザー / 日次のレート制限、使用量・コストのダッシュボード、上限アラート
- [ ] データソース遵守管理：robots.txt・利用規約の遵守状況を `job_sources` で管理。公開 API でも各社規約を確認
- [ ] 監視：CloudWatch Logs / Metrics / Alarms。SQS 滞留・DLQ・Lambda エラー率・Fargate タスク健全性のアラート
- [ ] バックアップ：RDS 自動バックアップ、復元手順のドキュメントと訓練
- [ ] セキュリティレビュー：認証・認可・入力バリデーション・出力エンコーディング・パラメータ化クエリ・プロンプトインジェクションの通しレビュー

**Done**: セキュリティチェックリスト完了、SSRF テストが CI にある、コストダッシュボードが稼働。

---

## Phase 10 — インフラとデプロイ

**Goal**: まず dev 単一環境を Terraform で再現可能にし、CI/CD で自動デプロイする。prod 分離は一般公開時。

- [ ] Terraform モジュール：`network`(VPC) / `database`(RDS PostgreSQL) / `queue`(SQS + DLQ) / `api`(Lambda + API Gateway) / `workers`(Lambda + Fargate サービス + イベントソースマッピング) / `storage`(S3) / `frontend`(S3 + CloudFront、`/api/*` を API Gateway へ) / `scheduler`(EventBridge Scheduler → ディスパッチャ Lambda) / `sessions`(DynamoDB)
- [ ] 環境：当面 dev のみ。state は S3 backend（`backend.hcl`）、`tfvars.example`
- [ ] シークレット：SSM Parameter Store（SecureString）に LLM API キー、DB 認証情報、セッション署名鍵
- [ ] CI/CD：test → build（backend / worker イメージ、frontend）→ ECR push → マイグレーション（ワンショットタスク）→ デプロイ → スモークテスト
- [ ] ネットワーク境界：IAM 最小権限、S3 パブリックアクセスブロック、RDS は非公開サブネット、CloudFront に ACM 証明書
- [ ] 初回デプロイ：dev への自動デプロイ、スモークテスト、ロールバック手順の確認
- [ ] 一般公開時に追加：prod 環境分離、API を Fargate + ALB へ、WAF（レート制限・マネージドルール）、RDS PITR / マルチ AZ、Secrets Manager へ移行、独立ドメイン

**Done**: dev 環境へ自動デプロイされ、ヘルスチェック通過、`terraform plan` がクリーン。

---

## Phase 11 — 運用開始後の拡張

**Goal**: 本人の転職活動で実際に使い、精度とカバレッジを広げる。

- [ ] 実利用フィードバック：開発者本人の転職活動で使い、フィルタ閾値・プロンプトを調整
- [ ] ATS ベンダ拡充：Workable / SmartRecruiters / Recruitee / Workday。国産 ATS（HERP / HRMOS / Talentio）の対応追加
- [ ] アグリゲーター API 対応：Adzuna / Jooble / Talent.com 等（国内提供状況の調査結果しだい）
- [ ] 面接対策（§3.6）：想定質問の自動生成、模擬面接（LLM 対話）、企業研究サマリー。独立性が高く後回し可
- [ ] OAuth 連携：Google / LinkedIn ログインの追加
- [ ] 複数内定の比較検討サポート（§3.5）

**Done**: 継続タスク（明確な完了なし）。コスト・精度をモニタリングしながら優先度順に着手する。

---

## 常に意識する横断リスク

### 設計に組み込むべき前提

- **差分検知とフィルタは LLM 呼び出しの前に必ず置く。** 順序を崩すとコストが暴走する。
- **ユーザー入力の URL をサーバがフェッチする** ＝ SSRF の主経路。対策詳細は Phase 09、実装は Phase 06 と同時に。
- **取得した求人ページ本文＝信頼できない入力。** LLM に渡す際はプロンプトインジェクション対策（指示とデータを明示デリミタで分離、出力は常に JSON Schema 検証、本文由来の「指示」を無視）。レジュメ添削でも同様。
- **職務経歴・個人情報は機微データ。** 保管時暗号化・TLS・アクセス制御・ログの PII 除去を後付けにしない。
- **LLM 出力は JSON Schema で強制、** 必須欠如は破棄せず「要確認」フラグ。捏造対策の根拠出力を必須にする。

### 個別の課題と対策

| 課題 | 対策 |
|---|---|
| ATS 判定の精度 | URL パターン + ページ内スクリプト / iframe / リンクホストで判定。iframe 埋め込み型は親ページから board 識別子を抽出。外れたら経路 C。 |
| ATS API のベンダ差 | レスポンス形状・ページネーション・日付形式が各社バラバラ。ベンダ別アダプタ → 共通スキーマの正規化レイヤーで吸収。 |
| JS レンダリングサイト | 経路 C のみ Playwright、Fargate ワーカーで実行。ATS 公開 API・JSON-LD は静的取得で足りることが多い。 |
| 取得失敗時の挙動 | サイレントリトライを繰り返さない。ユーザーに失敗を明示し手動登録へ誘導。 |
| フィルタの誤除外 | 一次フィルタは「明らかな不一致」のみ。閾値は緩めで運用開始し、取りこぼしを見て調整。 |
| LLM コスト | trafilatura で本文抽出しノイズ除去してから渡す。ハッシュ比較で不要な再解析を回避。 |
| スクレイピング本文のプロンプトインジェクション | データ部を明示デリミタで隔離、システム指示を上書きさせない、出力スキーマ検証で逸脱を弾く。本文は添削・分析の「指示」として扱わない。 |
| Lambda コールドスタート | 個人利用では許容。体感が問題になったらプロビジョンドコンカレンシー、または API を Fargate へ。 |

---

## 未決定事項（着手前に潰す順）

`CLAUDE.local.md §5` より。

1. **DB スキーマの名寄せ構造**（`ats`/`json_ld`/`llm` を横断）→ **Phase 01** で ADR 化。
2. **対応 ATS ベンダの優先順位**（Greenhouse / Lever / HERP から着手するか）→ **Phase 06 着手前**。
3. **国産 ATS（HERP / HRMOS / Talentio）の公開 API の有無調査** → **Phase 06 着手前**（実際の対応追加は Phase 11）。
4. **ATS 公開 API・JSON-LD 取得時の利用規約 / robots の扱い** → **Phase 06 着手前**に方針文書。
5. **ギャップ分析・添削のプロンプト設計**（ハルシネーション対策、Before/After 差分 UI）→ **Phase 07**。
6. **Adzuna 等アグリゲーター API の日本国内提供状況** → **Phase 11**（MVP 後）。

---

## 着手順序（土台フェーズ）

おおむね最初の 2 週間前後。土台を一周させてから MVP に入る。

1. **Phase 00**（基盤・ワークフロー）
2. **Phase 01**（ドメイン / DB スキーマ、機微データ保護と `pgvector` の ADR）
3. **Phase 02**（バックエンド API 基盤：cookie セッション認証 + health + テスト基盤）
4. **Phase 03**（フロントエンド土台：認証フロー + API クライアント）
5. **Phase 04**（非同期ワーカー基盤：TaskQueue + ローカルワーカー + `LlmClient`）
6. **Phase 07 を薄く先取り**：分析トリガー API → SQS → handler → LLM → DB 保存 を 1 本通す
7. その後 **MVP ① → ② → ③ → ④**（Phase 05 → 06 → 07 → 08）。Phase 09 は全期間で並行、Phase 10 は MVP がひととおり動いてから。

---

出典：`CLAUDE.local.md`（現行仕様）。ローカル DB の起こし方はメモリ `local-db-for-tests.md` 参照。
