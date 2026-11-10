package org.foodwise.decision;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * LightGBM 官方文本模型（v3/v4）的纯 Java 推理器。
 *
 * 与 {@link org.foodwise.service.LgbmCampusModel} 的区别：本类不做 log 空间还原，
 * 直接把叶值求和作为输出，因此适用于分位数回归模型（目标即原始销量）。
 * 数值契约由 Python 侧 quantile_parity_fixture.json 的逐值对齐测试保证。
 */
public final class LightGbmTextModel {

    private final String name;
    private final List<Tree> trees = new ArrayList<>();
    private int featureCount;

    private LightGbmTextModel(String name) {
        this.name = name;
    }

    public static LightGbmTextModel load(InputStream input, String name) throws IOException {
        LightGbmTextModel model = new LightGbmTextModel(name);
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            Map<String, String> block = null;
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.startsWith("feature_names=")) {
                    model.featureCount = line.substring("feature_names=".length()).trim().split("\\s+").length;
                    continue;
                }
                if (line.startsWith("Tree=")) {
                    if (block != null) model.trees.add(build(block));
                    block = new LinkedHashMap<>();
                    continue;
                }
                if (block != null && "end of trees".equals(line)) {
                    model.trees.add(build(block));
                    block = null;
                    continue;
                }
                if (block != null && !line.isEmpty()) {
                    int eq = line.indexOf('=');
                    if (eq > 0) block.put(line.substring(0, eq).trim(), line.substring(eq + 1).trim());
                }
            }
            if (block != null) model.trees.add(build(block));
        }
        if (model.trees.isEmpty() || model.featureCount <= 0) {
            throw new IOException("LGBM_MODEL_EMPTY:" + name);
        }
        return model;
    }

    private static Tree build(Map<String, String> block) {
        Tree tree = new Tree();
        tree.splitFeature = parseInts(block.get("split_feature"));
        tree.threshold = parseDoubles(block.get("threshold"));
        tree.leftChild = parseInts(block.get("left_child"));
        tree.rightChild = parseInts(block.get("right_child"));
        tree.leafValue = parseDoubles(block.get("leaf_value"));
        return tree;
    }

    /** 叶值和：分位数模型输出即预测分位，不需要 expm1。 */
    public double predict(double[] features) {
        if (features == null || features.length != featureCount) {
            throw new IllegalArgumentException("FEATURE_LENGTH_MISMATCH: expected " + featureCount);
        }
        double sum = 0;
        for (Tree tree : trees) sum += leafValue(tree, features);
        return sum;
    }

    private static double leafValue(Tree tree, double[] x) {
        int node = 0;
        while (true) {
            double value = x[tree.splitFeature[node]];
            // LightGBM 数值分裂：v <= threshold 走左子树；NaN 按右子树
            boolean goLeft = !Double.isNaN(value) && value <= tree.threshold[node];
            int child = goLeft ? tree.leftChild[node] : tree.rightChild[node];
            if (child < 0) return tree.leafValue[-child - 1];
            node = child;
        }
    }

    public int treeCount() {
        return trees.size();
    }

    public int featureCount() {
        return featureCount;
    }

    public String name() {
        return name;
    }

    private static int[] parseInts(String value) {
        if (value == null || value.isBlank()) return new int[0];
        String[] tokens = value.trim().split("\\s+");
        int[] out = new int[tokens.length];
        for (int i = 0; i < tokens.length; i++) out[i] = Integer.parseInt(tokens[i]);
        return out;
    }

    private static double[] parseDoubles(String value) {
        if (value == null || value.isBlank()) return new double[0];
        String[] tokens = value.trim().split("\\s+");
        double[] out = new double[tokens.length];
        for (int i = 0; i < tokens.length; i++) out[i] = Double.parseDouble(tokens[i]);
        return out;
    }

    private static final class Tree {
        int[] splitFeature = new int[0];
        double[] threshold = new double[0];
        int[] leftChild = new int[0];
        int[] rightChild = new int[0];
        double[] leafValue = new double[0];
    }
}