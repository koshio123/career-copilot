# ローカルでのテスト方法

CI（`.github/workflows/`）が回すのと同じチェックをローカルで実行する手順。
すべてリポジトリルートから。

## TL;DR

```bash
make install     # 初回のみ: backend(uv) + frontend(pnpm) 依存インストール
make lint        # 静的解析:  ruff + ruff format + mypy(strict) / eslint + tsc
make test        # テスト:     pytest / vitest
make fmt         # 自動整形（lint で怒られたとき）
```

`make lint && make test` が緑なら、その変更は CI も通る想定。

---

## 全体（Make ターゲット）

| コマンド | 中身 |
|---|---|
| `make lint` | `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy .`<br>`cd frontend && pnpm run lint && pnpm run typecheck` |
| `make test` | `cd backend && uv run pytest`<br>`cd frontend && pnpm run test` |
| `make fmt` | `ruff check --fix` + `ruff format` / `prettier --write` |

`make help` で全ターゲット一覧。

---

## バックエンド（`backend/`）

### テスト実行

```bash
cd backend

uv run pytest                     # 全部（デフォルト: -q --strict-markers）
uv run pytest -v                   # 詳細
uv run pytest tests/test_health.py            # ファイル指定
uv run pytest tests/test_health.py::test_healthz_returns_ok   # 関数指定
uv run pytest -k health           # 名前で絞り込み
uv run pytest -x --lf             # 最初の失敗で停止 / 前回失敗分だけ
uv run pytest --cov=app --cov-report=term-missing   # カバレッジ（CI と同じ）
```

### 静的解析

```bash
cd backend
uv run ruff check .            # lint
uv run ruff format --check .   # フォーマット確認（--check を外すと整形実行）
uv run mypy .                  # 型チェック（strict）
```

### DB が必要なテストについて

- **現時点（Phase 00）**：テストは `httpx.ASGITransport` でアプリを直接叩くだけ
  なので、DB もネットワークも不要。`make up` なしで動く。
- **Phase 02 以降**：`conftest.py` がトランザクション分離のフィクスチャで
  PostgreSQL を使う。事前に以下が必要：

  ```bash
  make up      # docker compose: Postgres を host:5433 で起動
               # 初回起動時に career_copilot / career_copilot_test を作成
  ```

  接続先は `backend/.env` の `APP_DATABASE_URL`（テストは `career_copilot_test`
  を使う）。`.env` が無ければ `cp backend/.env.example backend/.env`。

- **Docker が使えない場合**のフォールバック（使い捨て Postgres クラスタを直接
  起動する手順）はメモリ `local-db-for-tests.md` にまとめてある。要点：

  ```bash
  initdb -U career --auth=trust -D <scratch>/pgdata
  pg_ctl -D <scratch>/pgdata -o "-p 54329 -k /tmp/cc-pg -c listen_addresses=127.0.0.1" -l /tmp/cc-pg/pg.log -w start
  psql -h 127.0.0.1 -p 54329 -U career -d postgres -c "create database career_copilot_test;"
  # 実行時:
  APP_DATABASE_URL=postgresql+asyncpg://career@127.0.0.1:54329/career_copilot_test uv run pytest
  ```

---

## フロントエンド（`frontend/`）

```bash
cd frontend

pnpm run test          # 一度だけ実行（vitest run）— CI と同じ
pnpm run test:watch    # 変更監視モード
pnpm exec vitest run src/App.test.tsx    # ファイル指定
pnpm exec vitest run -t "renders the app"  # テスト名で絞り込み
pnpm run coverage                        # カバレッジ（@vitest/coverage-v8）

pnpm run lint          # eslint
pnpm run typecheck     # tsc -b（プロジェクト参照）
pnpm run format:check  # prettier --check（--write は `pnpm run format`）
pnpm run build         # 本番ビルド（型エラーも検出。CI で実行）
```

テストは `jsdom` + Testing Library。共通セットアップは `src/setupTests.ts`
（`@testing-library/jest-dom` のマッチャ登録）。

---

## pre-commit（任意だが推奨）

コミット時に上記チェックの一部を自動実行する。

```bash
uvx pre-commit install          # 有効化（1回）
uvx pre-commit run --all-files   # 手動で全ファイルに対して実行
uvx pre-commit autoupdate        # フック定義の更新
```

フック：generic（trailing-whitespace 等）+ detect-secrets + ruff / mypy /
eslint / prettier / terraform fmt。

---

## CI との対応

| ローカル | CI ワークフロー |
|---|---|
| `cd backend && uv run ruff/mypy/pytest` | `.github/workflows/backend.yml` |
| `cd backend && uv export ... && uvx pip-audit` | 同上（`audit` ジョブ） |
| `cd frontend && pnpm lint/typecheck/format:check/test/build` | `.github/workflows/frontend.yml` |
| `cd frontend && pnpm audit --audit-level high` | 同上 |
| `terraform fmt -check -recursive infra/` | `.github/workflows/infra.yml` |

CI は path フィルタで、変更のあった領域のワークフローだけ走る。
