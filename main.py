import io
import sys
import asyncio
import argparse

# Windows 控制台统一重配为 UTF-8
if isinstance(sys.stdout, io.TextIOWrapper): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if isinstance(sys.stderr, io.TextIOWrapper): sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from core.StandardFlow import run
from tools.Files import get_yaml_content

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LabelNetwork API 测试执行器")
    parser.add_argument(
        "--path",
        type=str,
        required=True,
        help="测试用例 YAML 文件路径",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=True,
        help="遇失败 step 立即停止（默认开启）",
    )
    parser.add_argument(
        "--no-fail-fast",
        action="store_false",
        dest="fail_fast",
        help="遇失败 step 继续执行后续步骤",
    )
    return parser.parse_args()

async def main() -> None:
    args = _parse_args()

    # 解析前校验 YAML 合法性
    raw: dict = get_yaml_content(args.path)
    if not raw:
        print(f"❌ YAML 解析失败或文件为空: {args.path}", file=sys.stderr)
        sys.exit(1)

    print(f"✅ YAML 解析成功，开始执行测试...")
    result = await run(args.path, fail_fast=args.fail_fast)
    print(result.info_str)

    if not result.is_passed: sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
