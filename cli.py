#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""واجهة سطر أوامر IntelliFile

استخدام:
    python cli.py classify /path/to/folder
    python cli.py search "تقارير المبيعات" /path
    python cli.py duplicates /path/to/folder
    python cli.py organize /path/to/folder
    python cli.py chat
    python cli.py voice
    python cli.py rag "ما هي مبيعات الربع الأول"
    python cli.py stats /path/to/folder

أو عبر entry point:
    intellifile classify /path/to/folder
"""

import sys
import logging


def main():
    """نقطة دخخول CLI"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if len(sys.argv) < 2:
        from src.core.agent_cli import AgentCLI
        AgentCLI().parser.print_help()
        sys.exit(0)

    from src.core.agent_cli import AgentCLI
    cli = AgentCLI()
    result = cli.execute_command(sys.argv[1], sys.argv[2:])

    if not result.get("success"):
        print(f"\nخطأ: {result.get('error', 'غير معروف')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
