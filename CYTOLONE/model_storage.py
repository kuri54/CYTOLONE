import json
import re
from pathlib import Path


WEIGHT_SUFFIXES = (".safetensors", ".bin", ".gguf")
WEIGHT_INDEX_SUFFIXES = (".safetensors.index.json", ".bin.index.json")
SHARDED_WEIGHT_PATTERN = re.compile(
    r"^(?P<prefix>.+)-\d+-of-\d+(?P<suffix>\.safetensors|\.bin)$"
)
TOKENIZER_FILES = {
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
}
PROCESSOR_FILES = {
    "processor_config.json",
    "preprocessor_config.json",
    "chat_template.json",
}


def _has_file_named(directory: Path, names):
    return any((directory / name).is_file() for name in names)


def _weight_index_files(directory):
    return sorted(
        item
        for item in directory.iterdir()
        if item.is_file()
        and not item.is_symlink()
        and item.name.endswith(WEIGHT_INDEX_SUFFIXES)
    )


def _required_shard_index_files(directory):
    required = set()
    for item in directory.iterdir():
        if not item.is_file():
            continue
        match = SHARDED_WEIGHT_PATTERN.match(item.name)
        if match:
            required.add(
                f"{match.group('prefix')}{match.group('suffix')}.index.json"
            )
    return required


def _indexed_weights_are_complete(directory):
    """Validate every shard referenced by each root-level weight index."""

    index_files = _weight_index_files(directory)
    if not index_files:
        return None

    for index_file in index_files:
        try:
            with index_file.open(encoding="utf-8") as file:
                index = json.load(file)
        except (OSError, ValueError):
            return False

        weight_map = index.get("weight_map") if isinstance(index, dict) else None
        if not isinstance(weight_map, dict) or not weight_map:
            return False

        shard_names = []
        for shard_name in weight_map.values():
            if not isinstance(shard_name, str) or not shard_name:
                return False
            shard_names.append(shard_name)

        for shard_name in set(shard_names):
            shard_path = Path(shard_name)
            if shard_path.is_absolute() or ".." in shard_path.parts:
                return False
            shard_path = directory / shard_path
            if shard_path.is_symlink() or not shard_path.is_file():
                return False

    return True


def model_directory_is_complete(directory):
    """Return whether a local model has the files needed before promotion."""

    directory = Path(directory)
    config_file = directory / "config.json"
    if not directory.is_dir() or not config_file.is_file():
        return False

    try:
        with config_file.open(encoding="utf-8") as file:
            if not isinstance(json.load(file), dict):
                return False
    except (OSError, ValueError):
        return False

    try:
        has_tokenizer = _has_file_named(directory, TOKENIZER_FILES)
        has_processor = _has_file_named(directory, PROCESSOR_FILES)
        required_index_files = _required_shard_index_files(directory)
        if any(not (directory / name).is_file() for name in required_index_files):
            return False
        indexed_weights = _indexed_weights_are_complete(directory)
        has_weights = any(
            item.is_file() and item.suffix in WEIGHT_SUFFIXES
            for item in directory.iterdir()
        )
    except OSError:
        return False
    if indexed_weights is False:
        return False
    if indexed_weights is True:
        has_weights = True
    return (has_tokenizer or has_processor) and has_weights
