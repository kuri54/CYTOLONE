import argparse
import shutil
import tempfile
import uuid
from pathlib import Path

from huggingface_hub import snapshot_download

from CYTOLONE.app_paths import models_path
from CYTOLONE.model import (
    get_llm_id,
    get_model_id,
    get_registered_model,
    iter_registered_models,
)
from CYTOLONE.model_storage import model_directory_is_complete
from CYTOLONE.util import load_config


class ModelDeletionConfirmationRequired(ValueError):
    pass


def _remove_path(path):
    path = Path(path)
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _safe_target(repo_id, base_output_dir):
    root_path = Path(base_output_dir).expanduser()
    if root_path.is_symlink():
        raise ValueError("The CYTOLONE models directory must not be a symlink")
    root = root_path.resolve(strict=False)
    relative = Path(repo_id)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Model target must be a relative repository path")
    target = root / relative
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Model target must remain below the CYTOLONE models directory") from exc
    if target == root:
        raise ValueError("The CYTOLONE models directory itself is not a model target")
    return root, target


def _target_has_symlink(root, target):
    current = root
    for part in target.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _assert_safe_target(root, target):
    if _target_has_symlink(root, target):
        raise ValueError("Refusing to manage a model through a symlinked path")


def _registered_target(role, key, base_output_dir=None, require_managed_root=False):
    spec = get_registered_model(role, key)
    managed_path = models_path().expanduser()
    managed_root = managed_path.resolve(strict=False)
    if require_managed_root and managed_path.is_symlink():
        raise ValueError("The CYTOLONE models directory must not be a symlink")
    root, target = _safe_target(
        spec.repo_id,
        managed_path if base_output_dir is None else base_output_dir,
    )
    if require_managed_root and root != managed_root:
        raise ValueError("Model deletion is restricted to models_path()")
    return spec, root, target


def _model_state(target, root=None):
    if root is not None and _target_has_symlink(root, target):
        return "unsafe link"
    if target.is_symlink():
        return "unsafe link"
    if not target.exists():
        return "not installed"
    return "installed" if model_directory_is_complete(target) else "incomplete"


def _directory_size(target, root=None):
    if root is not None and _target_has_symlink(root, target):
        return 0
    if not target.is_dir() or target.is_symlink():
        return 0
    total = 0
    for item in target.rglob("*"):
        if item.is_file() and not item.is_symlink():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def _format_size(size):
    if size <= 0:
        return "—"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024


def _promote_staging(staging_dir, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = None

    if destination.exists():
        backup = destination.parent / f".{destination.name}.backup-{uuid.uuid4().hex}"
        destination.rename(backup)

    try:
        staging_dir.rename(destination)
    except Exception:
        if destination.exists():
            _remove_path(destination)
        if backup is not None and backup.exists():
            backup.rename(destination)
        raise

    if backup is not None:
        _remove_path(backup)


def download_and_flatten(model_id: str, base_output_dir: Path, force=False):
    """Download one snapshot directly into a validated staging directory."""

    base_output_dir = Path(base_output_dir)
    root, destination = _safe_target(model_id, base_output_dir)
    _assert_safe_target(root, destination)
    if not force and model_directory_is_complete(destination):
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-",
            dir=destination.parent,
        )
    )

    try:
        snapshot_download(
            repo_id=model_id,
            local_dir=staging_dir,
            local_files_only=False,
        )
        if not model_directory_is_complete(staging_dir):
            raise RuntimeError(
                f"Downloaded model {model_id} is incomplete: "
                "config.json, tokenizer/processor files, and weights are required."
            )
        _assert_safe_target(root, destination)
        _promote_staging(staging_dir, destination)
    except Exception:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    print(f"Downloaded model '{model_id}' to '{destination}'")
    return destination


def model_is_installed(model_id: str, base_output_dir: Path):
    root, target = _safe_target(model_id, base_output_dir)
    return not _target_has_symlink(root, target) and model_directory_is_complete(target)


def download_registered_model(role, key, base_output_dir=None, force=False):
    spec, root, target = _registered_target(role, key, base_output_dir)
    _assert_safe_target(root, target)
    download_and_flatten(spec.repo_id, root, force=force)
    return target


def delete_registered_model(
    role,
    key,
    base_output_dir=None,
    confirmation=False,
    release_callback=None,
):
    """Delete one registry model below the CYTOLONE-owned models root."""

    if confirmation is not True:
        raise ModelDeletionConfirmationRequired(
            "Confirm deletion of the selected model before continuing."
        )

    spec, root, target = _registered_target(
        role,
        key,
        base_output_dir,
        require_managed_root=True,
    )
    _assert_safe_target(root, target)
    if not target.exists() and not target.is_symlink():
        return False

    if release_callback is not None:
        release_callback(spec)

    _remove_path(target)
    return True


def get_download_targets(config=None):
    if config is None:
        config = load_config()

    # The model page is user initiated, so it may prepare the selected LLM even
    # while generation is disabled. No download happens at import or startup.
    targets = [get_model_id(config["MODEL"]), get_llm_id(config["LLM_MODEL"])]
    return list(dict.fromkeys(targets))


def download_models(config=None, output_root=None, force=False):
    config = load_config() if config is None else config
    output_root = models_path() if output_root is None else Path(output_root)
    downloaded = []

    for role, key in (
        ("application", config["MODEL"]),
        ("llm", config["LLM_MODEL"]),
    ):
        spec, _, target = _registered_target(role, key, output_root)
        if not force and _model_state(target, output_root.resolve(strict=False)) == "installed":
            continue
        download_registered_model(role, key, output_root, force=force)
        downloaded.append(spec.repo_id)

    return downloaded


def model_management_summary(config=None, output_root=None):
    config = load_config() if config is None else config
    output_root = models_path() if output_root is None else Path(output_root)
    rows = [
        "| Role | Model | Selected | State | Local size | Download | Unified memory guidance |",
        "|---|---|---:|---|---:|---:|---:|",
    ]
    for spec in iter_registered_models():
        selected = (
            config["MODEL"] == spec.key
            if spec.role == "application"
            else config["LLM_MODEL"] == spec.key
        )
        _, root, target = _registered_target(spec.role, spec.key, output_root)
        rows.append(
            f"| {spec.role} | {spec.display_name} (`{spec.key}`) | "
            f"{'yes' if selected else 'no'} | {_model_state(target, root)} | "
            f"{_format_size(_directory_size(target, root))} | {spec.download_size} | "
            f"{spec.memory_recommendation} |"
        )
    return "### Model Management\n\n" + "\n".join(rows)


def model_download_summary(config=None, output_root=None):
    """Compatibility alias for callers using the previous summary name."""

    return model_management_summary(config=config, output_root=output_root)


def _download_status(message, config, output_root):
    return message, model_management_summary(config=config, output_root=output_root)


def download_model_with_status(role, key, force=False):
    config = load_config()
    output_root = models_path()
    spec, _, target = _registered_target(role, key, output_root)
    yield _download_status(
        f"Preparing {spec.display_name}...",
        config,
        output_root,
    )
    if not force and _model_state(target, output_root.resolve(strict=False)) == "installed":
        yield _download_status(
            f"{spec.display_name} is already installed and complete.",
            config,
            output_root,
        )
        return
    try:
        download_registered_model(role, key, output_root, force=force)
    except Exception as exc:  # noqa: BLE001
        yield _download_status(
            f"Model download failed for {spec.display_name}.\nError: {exc}",
            config,
            output_root,
        )
        return
    yield _download_status(
        f"Model download completed for {spec.display_name}.\nStored at: {target}",
        config,
        output_root,
    )


def delete_model_with_status(role, key, confirmation, release_callback=None):
    config = load_config()
    output_root = models_path()
    spec = get_registered_model(role, key)
    try:
        _registered_target(role, key, output_root)
        deleted = delete_registered_model(
            role,
            key,
            output_root,
            confirmation=confirmation,
            release_callback=release_callback,
        )
    except Exception as exc:  # noqa: BLE001
        return (
            f"Model deletion failed for {spec.display_name}.\nError: {exc}",
            model_management_summary(config=config, output_root=output_root),
        )
    message = (
        f"Deleted {spec.display_name}."
        if deleted
        else f"{spec.display_name} is not installed."
    )
    return message, model_management_summary(config=config, output_root=output_root)


def download_models_with_status(force=False):
    config = load_config()
    targets = get_download_targets(config)
    output_root = models_path()

    yield _download_status(
        "Checking selected application and LLM models...\n"
        "Targets:\n" + "\n".join(f"- {target}" for target in targets),
        config,
        output_root,
    )

    downloaded = []
    skipped = []
    try:
        for model_id in targets:
            if not force and model_is_installed(model_id, output_root):
                skipped.append(model_id)
                yield _download_status(
                    f"Already installed and complete: {model_id}",
                    config,
                    output_root,
                )
                continue

            yield _download_status(
                f"Downloading {model_id} into a staging directory...",
                config,
                output_root,
            )
            download_and_flatten(model_id, output_root, force=force)
            downloaded.append(model_id)
    except Exception as exc:  # noqa: BLE001
        yield _download_status(
            "Model download failed.\n"
            f"Error: {exc}\n\n"
            "An existing complete model is preserved when replacement fails.\n\n"
            "Downloaded before failure:\n"
            + ("\n".join(f"- {model_id}" for model_id in downloaded) or "- None")
            + "\n\nSkipped before failure:\n"
            + ("\n".join(f"- {model_id}" for model_id in skipped) or "- None"),
            config,
            output_root,
        )
        return

    yield _download_status(
        "Model check completed.\n"
        "Downloaded models:\n"
        + ("\n".join(f"- {model_id}" for model_id in downloaded) or "- None")
        + "\n\nAlready installed:\n"
        + ("\n".join(f"- {model_id}" for model_id in skipped) or "- None"),
        config,
        output_root,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Download one configured CYTOLONE model."
    )
    parser.add_argument(
        "role",
        nargs="?",
        choices=("application", "llm"),
        default="application",
        help="Configured model role to download (default: application)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an already installed model",
    )
    args = parser.parse_args()
    config = load_config()
    key = config["MODEL"] if args.role == "application" else config["LLM_MODEL"]
    download_registered_model(args.role, key, force=args.force)


if __name__ == "__main__":
    main()
