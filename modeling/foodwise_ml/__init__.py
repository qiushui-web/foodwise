"""食刻有数 · 建模侧共享代码（产物契约、区间校准、决策、归因）。

当前模块：
  * manifest.py  —— 产物清单 v2 的构建、校验、哈希绑定
  * intervals.py —— CQR 偏移、分层收缩、ACI 状态更新、区间指标、校准产物校验

后续模块：
  * decision.py  —— 临界分位 + 约束投影 + regret
  * attribute.py —— BSTS/ITS + 置换检验
"""

from .intervals import (  # noqa: F401
    ACIController,
    CALIBRATION_METHOD,
    CALIBRATION_SCHEMA_VERSION,
    apply_offset,
    build_calibration_artifact,
    conformal_quantile,
    conformity_scores,
    interval_report,
    picp,
    pinaw,
    shrink_offset,
    validate_calibration_artifact,
    winkler_score,
)
from .manifest import (  # noqa: F401
    CALIBRATION_STATUS,
    MODEL_KINDS,
    SCHEMA_VERSION,
    ManifestError,
    assert_valid,
    build_manifest,
    load_manifest,
    sha256_file,
    validate_manifest,
    verify_artifact_hashes,
    write_manifest,
)

__all__ = [
    "ACIController",
    "CALIBRATION_METHOD",
    "CALIBRATION_SCHEMA_VERSION",
    "CALIBRATION_STATUS",
    "MODEL_KINDS",
    "SCHEMA_VERSION",
    "ManifestError",
    "apply_offset",
    "assert_valid",
    "build_calibration_artifact",
    "build_manifest",
    "conformal_quantile",
    "conformity_scores",
    "interval_report",
    "load_manifest",
    "picp",
    "pinaw",
    "sha256_file",
    "shrink_offset",
    "validate_calibration_artifact",
    "validate_manifest",
    "verify_artifact_hashes",
    "winkler_score",
    "write_manifest",
]