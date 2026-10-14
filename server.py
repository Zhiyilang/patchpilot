#!/usr/bin/env python3
"""PatchPilot 服务入口：python server.py（读 PORT，绑 0.0.0.0）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from patchpilot.web import serve  # noqa: E402

if __name__ == "__main__":
    serve()
