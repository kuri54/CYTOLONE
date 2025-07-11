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

def main():
    config = load_config()

    model_version = config["MODEL"]
    llm_gen = config["LLM_GEN"]

    output_root = Path("mlx_models")

    model_id = get_model_id(model_version)
    download_and_flatten(model_id, output_root)

    if llm_gen:
        llm_id = get_llm_id()
        download_and_flatten(llm_id, output_root)

if __name__ == "__main__":
    main()