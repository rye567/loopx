#!/usr/bin/env python3
"""LoopX controller CLI facade.

 The implementation lives in ``loopx_controller_cli.py`` (CLI 装配)、
 ``loopx_controller_core.py`` (流程命令) and sibling modules so this
 historical entrypoint stays small while existing commands and imports
 keep working.
"""

from pathlib import Path
import sys


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    # skill 目录可能从任意 cwd 被引用（如 python loopx/tools/loopx_controller.py），
    # 必须把 tools 目录加入 sys.path 后才能做平级模块导入。
    sys.path.insert(0, str(TOOLS_DIR))

# 显式 re-export 门面符号；不再使用 `import *`，保证命名空间可追踪。
# 外部（测试/脚本）从本模块引用的符号以 tests 中实际使用面为准。
from loopx_controller_cli import (  # noqa: F401,E402
    ChineseArgumentParser,
    build_parser,
    main,
)
from loopx_controller_contracts import STAGE_SEQUENCE  # noqa: F401,E402
from loopx_controller_core import (  # noqa: F401,E402
    advance_to_stage,
    cmd_advance,
    cmd_can_write,
    cmd_confirm_stage,
    cmd_gate,
    cmd_health,
    cmd_import_artifact,
    cmd_mode,
    cmd_next,
    cmd_record_stage,
    cmd_status,
    cmd_validate,
    import_artifact_files,
    restore_imported_artifacts,
)
from loopx_controller_flow import (  # noqa: F401,E402
    build_stage_result,
    record_stage_result,
)
from loopx_controller_intake import (  # noqa: F401,E402
    auto_pass_environment_check,
    cmd_init,
    cmd_interview,
    cmd_spec,
)
from loopx_controller_state import (  # noqa: F401,E402
    build_tracking_snapshot,
    update_worklist_state,
)


if __name__ == "__main__":
    sys.exit(main())
