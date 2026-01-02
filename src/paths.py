from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def data_processed_dir() -> Path:
    d = project_root() / "Data" / "Processed"
    d.mkdir(parents=True, exist_ok=True)
    return d


def outputs_eda_dir() -> Path:
    d = project_root() / "Outputs" / "EDA"
    d.mkdir(parents=True, exist_ok=True)
    return d


def outputs_models_dir() -> Path:
    """Returns Outputs/Models and creates it if missing."""
    d = project_root() / "Outputs" / "Models"
    d.mkdir(parents=True, exist_ok=True)
    return d
