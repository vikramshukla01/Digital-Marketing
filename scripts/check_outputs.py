import pandas as pd
from pathlib import Path

hill = Path("Outputs/EDA/hillstrom_treatment_distribution.csv")
df_h = pd.read_csv(hill)
vals = df_h["treatment_raw"].astype(str).unique().tolist()
print("Unique treatment_raw values:", vals)
print("Lengths:", [len(v) for v in vals])

cri = Path("Outputs/EDA/criteo_treatment_distribution.csv")
df_c = pd.read_csv(cri)
print("Criteo treatment unique:", df_c["treatment"].unique())
print("Criteo dtypes:\n", df_c.dtypes)
