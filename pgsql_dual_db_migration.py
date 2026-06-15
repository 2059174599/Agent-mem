#!/usr/bin/env python3
"""
PostgreSQL 双库全量迁移脚本。

默认行为：
1. 从两个源库分别导出完整 dump（schema + data）。
2. 在目标端使用 pg_restore --create 覆盖目标数据库。
3. 两组数据库按顺序执行，任何一步失败立即退出。

为避免把口令写入仓库，密码统一从环境变量读取：

  export SRC_AICS_PRO_PASSWORD='...'
  export SRC_AICS_PRO_PLUGIN_PASSWORD='...'
  export DST_AICS_PRO_PASSWORD='...'
  export DST_AICS_PRO_PLUGIN_PASSWORD='...'

运行示例：

  python pgsql_dual_db_migration.py --yes
  python pgsql_dual_db_migration.py --only aics_pro --yes

依赖：
  - pg_dump
  - pg_restore
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class DatabaseConfig:
    name: str
    host: str
    port: int
    database: str
    username: str
    password_env: str
    maintenance_db: str = "postgres"

    @property
    def password(self) -> str:
        value = os.getenv(self.password_env)
        if not value:
            raise ValueError(
                f"缺少环境变量 {self.password_env}，无法连接数据库 {self.name}"
            )
        return value

    def display_dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.username}"
        )


@dataclass(frozen=True)
class MigrationPair:
    name: str
    source: DatabaseConfig
    target: DatabaseConfig


MIGRATION_PAIRS = (
    MigrationPair(
        name="aics_pro",
        source=DatabaseConfig(
            name="source_aics_pro",
            host="postgres2198.5434-wm.db.idc",
            port=5434,
            database="aics_pro",
            username="aics_pro",
            password_env="SRC_AICS_PRO_PASSWORD",
        ),
        target=DatabaseConfig(
            name="target_aics_pro",
            host="pre-ce-db15100.db.idc",
            port=5432,
            database="aics_pro",
            username="aics_pro",
            password_env="DST_AICS_PRO_PASSWORD",
        ),
    ),
    MigrationPair(
        name="aics_pro_plugin",
        source=DatabaseConfig(
            name="source_aics_pro_plugin",
            host="postgres2199.5433-wm.db.idc",
            port=5433,
            database="aics_pro_plugin",
            username="aics_pro_plugin",
            password_env="SRC_AICS_PRO_PLUGIN_PASSWORD",
        ),
        target=DatabaseConfig(
            name="target_aics_pro_plugin",
            host="pre-ce-db15100.db.idc",
            port=5433,
            database="aics_pro_plugin",
            username="aics_pro_plugin",
            password_env="DST_AICS_PRO_PLUGIN_PASSWORD",
        ),
    ),
)


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def ensure_binaries(commands: Iterable[str]) -> None:
    missing = [command for command in commands if shutil.which(command) is None]
    if missing:
        raise RuntimeError(
            "缺少 PostgreSQL 客户端命令: "
            + ", ".join(missing)
            + "。请先安装 PostgreSQL client 工具。"
        )


def build_env(password: str) -> dict[str, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    return env


def format_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def run_command(
    command: list[str],
    *,
    password: str,
    description: str,
) -> None:
    log(f"{description}: {format_command(command)}")
    result = subprocess.run(
        command,
        env=build_env(password),
        text=True,
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    if result.returncode != 0:
        raise RuntimeError(f"{description}失败，退出码: {result.returncode}")


def dump_database(pair: MigrationPair, dump_dir: Path) -> Path:
    dump_path = dump_dir / f"{pair.name}.dump"
    source = pair.source
    command = [
        "pg_dump",
        "--host",
        source.host,
        "--port",
        str(source.port),
        "--username",
        source.username,
        "--dbname",
        source.database,
        "--format=custom",
        "--verbose",
        "--clean",
        "--if-exists",
        "--create",
        "--no-owner",
        "--no-privileges",
        "--file",
        str(dump_path),
    ]
    run_command(
        command,
        password=source.password,
        description=f"导出源库 {source.database}",
    )
    return dump_path


def restore_database(pair: MigrationPair, dump_path: Path) -> None:
    target = pair.target
    command = [
        "pg_restore",
        "--host",
        target.host,
        "--port",
        str(target.port),
        "--username",
        target.username,
        "--dbname",
        target.maintenance_db,
        "--verbose",
        "--clean",
        "--if-exists",
        "--create",
        "--no-owner",
        "--no-privileges",
        str(dump_path),
    ]
    run_command(
        command,
        password=target.password,
        description=f"恢复到目标库 {target.database}",
    )


def migrate_pair(pair: MigrationPair, dump_dir: Path, keep_dump: bool) -> None:
    log("=" * 72)
    log(f"开始迁移: {pair.name}")
    log(f"源库: {pair.source.display_dsn()}")
    log(f"目标库: {pair.target.display_dsn()}")
    dump_path = dump_database(pair, dump_dir)
    restore_database(pair, dump_path)
    if not keep_dump and dump_path.exists():
        dump_path.unlink()
    log(f"迁移完成: {pair.name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="双 PostgreSQL 全量迁移脚本")
    parser.add_argument(
        "--only",
        choices=[pair.name for pair in MIGRATION_PAIRS],
        help="只迁移指定数据库",
    )
    parser.add_argument(
        "--dump-dir",
        default="",
        help="dump 文件目录，默认使用系统临时目录",
    )
    parser.add_argument(
        "--keep-dump",
        action="store_true",
        help="保留导出的 dump 文件，便于复查",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="跳过覆盖确认，直接执行",
    )
    return parser.parse_args()


def confirm_execution(selected_pairs: list[MigrationPair]) -> None:
    log("即将执行 PostgreSQL 全量覆盖迁移。")
    for pair in selected_pairs:
        log(
            f"- {pair.name}: {pair.source.database}@{pair.source.host}:{pair.source.port} "
            f"-> {pair.target.database}@{pair.target.host}:{pair.target.port}"
        )
    answer = input("确认继续吗？这会覆盖目标数据库现有内容 [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        raise SystemExit("已取消执行。")


def resolve_dump_dir(arg_value: str) -> Path:
    if arg_value:
        path = Path(arg_value).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path
    temp_dir = Path(tempfile.mkdtemp(prefix="pgsql_migration_"))
    return temp_dir


def main() -> int:
    args = parse_args()
    ensure_binaries(("pg_dump", "pg_restore"))

    selected_pairs = [
        pair for pair in MIGRATION_PAIRS if args.only in (None, pair.name)
    ]
    if not selected_pairs:
        raise SystemExit("没有匹配到可迁移的数据库配置。")

    if not args.yes:
        confirm_execution(selected_pairs)

    dump_dir = resolve_dump_dir(args.dump_dir)
    log(f"dump 目录: {dump_dir}")

    try:
        for pair in selected_pairs:
            migrate_pair(pair, dump_dir, args.keep_dump)
    except Exception as exc:
        log(f"迁移失败: {exc}")
        return 1

    log("全部迁移完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
