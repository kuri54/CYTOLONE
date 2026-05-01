import shutil
from pathlib import Path

from huggingface_hub import snapshot_download

from CYTOLONE.model import get_model_id, get_llm_id

from CYTOLONE.util import load_config

def download_and_flatten(model_id: str, base_output_dir: Path):
    snapshot_path = Path(snapshot_download(
        repo_id=model_id,
        local_files_only=False,
        # resume_download=True
    ))

    dest_dir = base_output_dir / model_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    for item in snapshot_path.iterdir():
        if item.is_file():
            shutil.copy2(item, dest_dir / item.name)

    print(f"Flattened model '{model_id}' to '{dest_dir}'")

def model_is_installed(model_id: str, base_output_dir: Path):
    dest_dir = base_output_dir / model_id
    return dest_dir.exists() and any(item.is_file() for item in dest_dir.iterdir())

def get_download_targets(config=None):
    if config is None:
        config = load_config()

    targets = [get_model_id(config["MODEL"])]
    if config["LLM_GEN"]:
        targets.append(get_llm_id(config["LLM_MODEL"]))

    return targets

def download_models(config=None, output_root=Path("mlx_models"), force=False):
    targets = get_download_targets(config)
    downloaded = []

    for model_id in targets:
        if not force and model_is_installed(model_id, output_root):
            continue
        download_and_flatten(model_id, output_root)
        downloaded.append(model_id)

    return downloaded

def download_models_with_status(force=False):
    config = load_config()
    targets = get_download_targets(config)
    output_root = Path("mlx_models")

    yield (
        "Checking models...\n"
        f"Targets:\n" + "\n".join(f"- {target}" for target in targets)
    )

    downloaded = []
    skipped = []
    try:
        for model_id in targets:
            if not force and model_is_installed(model_id, output_root):
                skipped.append(model_id)
                yield f"Already installed: {model_id}"
                continue

            yield f"Downloading {model_id}..."
            download_and_flatten(model_id, output_root)
            downloaded.append(model_id)
    except Exception as exc:  # noqa: BLE001
        yield (
            "Model download failed.\n"
            f"Error: {exc}\n\n"
            "Downloaded before failure:\n"
            + ("\n".join(f"- {model_id}" for model_id in downloaded) or "- None")
            + "\n\nSkipped before failure:\n"
            + ("\n".join(f"- {model_id}" for model_id in skipped) or "- None")
        )
        return

    yield (
        "Model check completed.\n"
        "Downloaded models:\n"
        + ("\n".join(f"- {model_id}" for model_id in downloaded) or "- None")
        + "\n\nAlready installed:\n"
        + ("\n".join(f"- {model_id}" for model_id in skipped) or "- None")
    )

def main():
    download_models()

if __name__ == "__main__":
    main()
