"""pytest フィクスチャ (DB / HTTP クライアント)。

## 前提となる概念と関係

- Engine: DB 接続の「工場」と設定。内部にコネクションプールを持つ。DB とは直接
  喋らず Connection を出すだけ。生成が重いのでアプリ (テストならセッション) 全体で 1 個。
- Connection: 実際の通信路 1 本。SQL はすべてこの上を流れ、状態 (トランザクション中か
  どうか等) を持つ。
- Transaction: Connection 上の「ひとまとまり」。commit で恒久確定、rollback で全破棄。
  1 本の Connection にトップレベルは同時に 1 つだけ。
- SAVEPOINT: 進行中トランザクションの中に置く「しおり」。部分巻き戻し可、ネスト可。
  RELEASE で確定扱い (本当の確定は外側の commit 次第)。
- Session: ORM オブジェクトの作業台。add で追跡し flush で SQL 化。中で Connection を
  1 本使う。commit は flush とトランザクション commit をまとめて行う。
- bind: Session にどの通信路を使わせるか。bind=engine なら自分で接続を取る (本番)。
  bind=conn なら渡した既存接続を使う (下記テスト方式)。

## このファイルのテスト分離方式

1. engine フィクスチャ (session スコープ): engine を 1 個だけ作り、モデル定義
   (Base.metadata) から drop_all -> create_all でテーブルを用意する。Alembic ではなく
   モデル駆動。マイグレーション往復の検証は alembic check が別途担当。
2. db フィクスチャ (関数スコープ): 接続を 1 本借り、その上に「外側トランザクション」を
   張り、その接続に Session を bind する。テスト終了時に外側を rollback するので、
   テストが何を書いても DB は毎回まっさらに戻る (テーブル再作成不要・順序非依存)。
3. join_transaction_mode="create_savepoint": 外側トランザクションが進行中の接続に
   bind された Session は、外側に直接触らず SAVEPOINT を切ってそこで作業する。これで
   テスト対象コードの session.commit() は RELEASE SAVEPOINT に化けるだけで外側は開いた
   ままとなり、フィクスチャの trans.rollback() が必ず効く。SQLAlchemy 2.0 以前は同等の
   ことを after_transaction_end イベントで手書きしていた。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.main import app


def _test_database_url() -> str:
    """Derive the test DB URL from settings, forcing a ``*_test`` database name."""
    url = make_url(get_settings().database_url)
    name = url.database or ""
    if not name.endswith("_test"):
        url = url.set(database=f"{name}_test")
    assert "test" in (url.database or ""), "refusing to run tests against a non-test database"
    return url.render_as_string(hide_password=False)


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine]:
    eng = create_async_engine(_test_database_url(), poolclass=NullPool)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def db(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """A session in a transaction that is rolled back after each test (isolation)."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
