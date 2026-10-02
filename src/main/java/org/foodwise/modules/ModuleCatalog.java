package org.foodwise.modules;

import java.util.List;

public final class ModuleCatalog {
    private ModuleCatalog() {
    }

    public static List<ModuleDefinition> definitions() {
        return List.of(
                new ModuleDefinition("operations", "经营台账、反馈、数量守恒和数据来源", "org.foodwise.modules.operations"),
                new ModuleDefinition("prediction", "需求预测、备餐区间和模型版本", "org.foodwise.modules.prediction"),
                new ModuleDefinition("waste", "剩余分析、预警和限时优惠", "org.foodwise.modules.waste"),
                new ModuleDefinition("orders", "订单和取餐核销", "org.foodwise.modules.orders"),
                new ModuleDefinition("analytics", "趋势、回测、财务和减损报告", "org.foodwise.modules.analytics"),
                new ModuleDefinition("intelligence", "AI 经营摘要和建议反馈", "org.foodwise.modules.intelligence"),
                new ModuleDefinition("identity", "登录、角色和操作员上下文", "org.foodwise.modules.identity")
        );
    }

    public record ModuleDefinition(String name, String responsibility, String packageName) {
    }
}

