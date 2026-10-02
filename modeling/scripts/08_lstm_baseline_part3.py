
def train_mlp(X_train: pd.DataFrame, y_train: pd.Series) -> Any:
    """
    训练 MLPRegressor 作为 LSTM-Attention 的替代。

    参考论文架构（LSTM 2x64 -> MultiheadAttention 4head -> FC 1）：
      - 隐藏层1: 64 神经元 (对应 LSTM 64维)
      - 隐藏层2: 32 神经元 (对应 Attention 输出)
      - 输出层: 1 神经元
    """
    from sklearn.neural_network import MLPRegressor

    # 小样本时禁用 early_stopping（验证集太少会报错）
    use_early_stop = len(X_train) >= 20
    model = MLPRegressor(
        hidden_layer_sizes=(64, 32),
        activation="relu",
        solver="adam",
        max_iter=500,
        random_state=42,
        early_stopping=use_early_stop,
        validation_fraction=0.1 if use_early_stop else None,
        n_iter_no_change=20,
        verbose=False,
    )
    model.fit(X_train, y_train)
    return model
