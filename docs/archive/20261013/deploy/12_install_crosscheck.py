# -*- coding: utf-8 -*-
"""安装大模型混测后端：拷贝3个service文件 + 给ApiController加接口"""
import shutil, re, sys
from pathlib import Path

SRC = r"c:\Users\lenovo\Desktop\商业精英挑战赛\deploy\java_pure"
ROOT = Path(__file__).resolve().parents[1]
DST = str(ROOT / "src" / "main" / "java" / "org" / "foodwise" / "service")
CTL = str(ROOT / "src" / "main" / "java" / "org" / "foodwise" / "api" / "v1" / "ApiV1Controller.java")

files = ["LgbmCampusModel.java", "ZhipuAiService.java", "ModelCrossCheckService.java"]
for f in files:
    shutil.copyfile(rf"{SRC}\{f}", rf"{DST}\{f}")
    print("copied:", f)

src = open(CTL, encoding="utf-8").read()

# 1. import
if "import org.foodwise.service.ModelCrossCheckService;" not in src:
    src = src.replace(
        "import org.foodwise.service.DualPredictionService;",
        "import org.foodwise.service.DualPredictionService;\nimport org.foodwise.service.ModelCrossCheckService;")

# 2. field
if "private final ModelCrossCheckService" not in src:
    src = src.replace(
        "    private final DualPredictionService dualPredictionService;\n",
        "    private final DualPredictionService dualPredictionService;\n    private final ModelCrossCheckService modelCrossCheckService;\n")

# 3. constructor param + assignment
if "ModelCrossCheckService modelCrossCheckService" not in src:
    src = src.replace(
        "                         DualPredictionService dualPredictionService) {",
        "                         DualPredictionService dualPredictionService,\n                         ModelCrossCheckService modelCrossCheckService) {")
    src = src.replace(
        "        this.dualPredictionService = dualPredictionService;\n    }",
        "        this.dualPredictionService = dualPredictionService;\n        this.modelCrossCheckService = modelCrossCheckService;\n    }")

# 4. endpoint after /predictions/dual
if "/model/cross-check" not in src:
    anchor = """    @GetMapping("/model/campus-series")"""
    endpoint = """    @PostMapping("/model/cross-check")
    public Map<String, Object> crossCheck(@RequestBody @Validated PredictionRequest request) {
        return modelCrossCheckService.crossCheck(
                request.dishId(), request.weather(), request.examWeek(), request.campusEvent());
    }

"""
    src = src.replace(anchor, endpoint + anchor)

open(CTL, "w", encoding="utf-8").write(src)
print("ApiController patched OK")

