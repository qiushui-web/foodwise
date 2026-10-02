# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path
p = Path(r"D:\IdeaProjects\Examples\modeling\data\02_processed\finetune_uwaste.parquet")
df = pd.read_parquet(p)
print("shape:", df.shape)
print("columns:", list(df.columns))
print("\ndtypes:\n", df.dtypes.to_string())
print("\nhead:\n", df.head(3).to_string())
if "sold_qty" in df.columns:
    print("\ntarget stats:\n", df["sold_qty"].describe().to_string())
for c in ["date", "stall_name", "dish_id", "dish_name", "category_id", "meal"]:
    if c in df.columns:
        try:
            print(f"\n{c}: nunique={df[c].nunique()} sample={list(df[c].dropna().unique()[:6])}")
        except Exception as e:
            print(c, "err", e)
