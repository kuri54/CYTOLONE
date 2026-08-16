from dataclasses import dataclass


@dataclass(frozen=True)
class LLMGenerationDefaults:
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.8
    top_k: int = 20
    seed: int = 42
    enable_thinking: bool = False


LLM_GENERATION_DEFAULTS = LLMGenerationDefaults()


@dataclass(frozen=True)
class LLMModelSpec:
    """Product metadata for one manually selected local LLM."""

    key: str
    repo_id: str
    runtime: str
    display_name: str
    tier: str
    download_size: str
    memory_recommendation: str
    status: str = "supported"
    legacy: bool = False
    generation_defaults: LLMGenerationDefaults = LLM_GENERATION_DEFAULTS

    @property
    def model_id(self):
        """Compatibility alias for the pre-registry model dictionary."""
        return self.repo_id


@dataclass(frozen=True)
class RegisteredModelSpec:
    """Common model-management metadata for application models and LLMs."""

    role: str
    key: str
    repo_id: str
    display_name: str
    download_size: str
    memory_recommendation: str
    status: str = "supported"
    runtime: str = ""
    legacy: bool = False


LLM_MODEL_REGISTRY = {
    "qwen3.5-9b-4bit": LLMModelSpec(
        key="qwen3.5-9b-4bit",
        repo_id="mlx-community/Qwen3.5-9B-4bit",
        runtime="mlx-vlm",
        display_name="Qwen3.5 9B (4-bit)",
        tier="Lightweight / default",
        download_size="5.95 GB",
        memory_recommendation="16 GB or more",
    ),
    "qwen3.5-9b-8bit": LLMModelSpec(
        key="qwen3.5-9b-8bit",
        repo_id="mlx-community/Qwen3.5-9B-8bit",
        runtime="mlx-vlm",
        display_name="Qwen3.5 9B (8-bit)",
        tier="Lightweight quality",
        download_size="10.4 GB",
        memory_recommendation="24 GB or more",
    ),
    "qwen3.5-27b-5bit": LLMModelSpec(
        key="qwen3.5-27b-5bit",
        repo_id="mlx-community/Qwen3.5-27B-5bit",
        runtime="mlx-vlm",
        display_name="Qwen3.5 27B (5-bit)",
        tier="Recommended quality",
        download_size="19.4 GB",
        memory_recommendation="32 GB or more",
    ),
    "qwen3.5-27b-8bit": LLMModelSpec(
        key="qwen3.5-27b-8bit",
        repo_id="mlx-community/Qwen3.5-27B-8bit",
        runtime="mlx-vlm",
        display_name="Qwen3.5 27B (8-bit)",
        tier="High quality",
        download_size="29.5 GB",
        memory_recommendation="48 GB or more",
    ),
    "qwen3.8-27b-4bit": LLMModelSpec(
        key="qwen3.8-27b-4bit",
        repo_id="mlx-community/Qwen3.8-27B-4bit",
        runtime="mlx-vlm",
        display_name="Qwen3.8 27B (4-bit)",
        tier="Validation candidate",
        download_size="about 16.1 GB",
        memory_recommendation="Preliminary; validate locally",
    ),
    "qwen3.8-27b-8bit": LLMModelSpec(
        key="qwen3.8-27b-8bit",
        repo_id="mlx-community/Qwen3.8-27B-8bit",
        runtime="mlx-vlm",
        display_name="Qwen3.8 27B (8-bit)",
        tier="Validation candidate",
        download_size="about 29.5 GB",
        memory_recommendation="Preliminary; validate locally",
    ),
    "gpt-oss-120b": LLMModelSpec(
        key="gpt-oss-120b",
        repo_id="mlx-community/gpt-oss-120b-MXFP4-Q4",
        runtime="mlx-lm",
        display_name="GPT-OSS 120B (Legacy)",
        tier="Legacy",
        download_size="about 63 GB",
        memory_recommendation="128 GB or more",
        status="legacy",
        legacy=True,
    ),
    "gpt-oss-20b": LLMModelSpec(
        key="gpt-oss-20b",
        repo_id="mlx-community/gpt-oss-20b-MXFP4-Q8",
        runtime="mlx-lm",
        display_name="GPT-OSS 20B (Legacy compatibility)",
        tier="Legacy compatibility",
        download_size="existing repository",
        memory_recommendation="Preliminary; validate locally",
        status="legacy",
        legacy=True,
    ),
    "deepseek-r1": LLMModelSpec(
        key="deepseek-r1",
        repo_id="mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit",
        runtime="mlx-lm",
        display_name="DeepSeek-R1 (Legacy compatibility)",
        tier="Legacy compatibility",
        download_size="existing repository",
        memory_recommendation="Preliminary; validate locally",
        status="legacy",
        legacy=True,
    ),
}

LLM_MODEL_CHOICES = list(LLM_MODEL_REGISTRY)
LLM_MODEL_DISPLAY_CHOICES = [
    (spec.display_name, spec.key) for spec in LLM_MODEL_REGISTRY.values()
]

APP_MODEL_REGISTRY = {
    "v1.0": RegisteredModelSpec(
        role="application",
        key="v1.0",
        repo_id="kuri54/mlx-CYTOLONE-v1",
        display_name="CYTOLONE application v1.0",
        download_size="not specified",
        memory_recommendation="not applicable",
    ),
    "v1.1": RegisteredModelSpec(
        role="application",
        key="v1.1",
        repo_id="kuri54/mlx-CYTOLONE-v1.1",
        display_name="CYTOLONE application v1.1",
        download_size="not specified",
        memory_recommendation="not applicable",
    ),
}
APP_MODEL_CHOICES = list(APP_MODEL_REGISTRY)
APP_MODEL_DISPLAY_CHOICES = [
    (spec.display_name, spec.key) for spec in APP_MODEL_REGISTRY.values()
]

# Keep the old application dictionary available for callers outside the app.
APP_MODELS = {
    key: {"model_id": spec.repo_id}
    for key, spec in APP_MODEL_REGISTRY.items()
}

# Keep the old combined dictionary available for callers outside the app.
models = {**APP_MODELS}
models.update(
    {
        key: {"model_id": spec.repo_id, "runtime": spec.runtime}
        for key, spec in LLM_MODEL_REGISTRY.items()
    }
)


def get_model_id(version):
    return APP_MODEL_REGISTRY[version].repo_id


def get_llm_spec(llm_model):
    try:
        return LLM_MODEL_REGISTRY[llm_model]
    except KeyError as exc:
        raise ValueError(f"Unknown LLM model: {llm_model}") from exc


def get_llm_id(llm_model):
    return get_llm_spec(llm_model).repo_id


def get_registered_model(role, key):
    if role == "application":
        try:
            return APP_MODEL_REGISTRY[key]
        except KeyError as exc:
            raise ValueError(f"Unknown application model: {key}") from exc
    if role == "llm":
        spec = get_llm_spec(key)
        return RegisteredModelSpec(
            role="llm",
            key=spec.key,
            repo_id=spec.repo_id,
            display_name=spec.display_name,
            download_size=spec.download_size,
            memory_recommendation=spec.memory_recommendation,
            status=spec.status,
            runtime=spec.runtime,
            legacy=spec.legacy,
        )
    raise ValueError(f"Unknown model role: {role}")


def iter_registered_models():
    for spec in APP_MODEL_REGISTRY.values():
        yield spec
    for key in LLM_MODEL_REGISTRY:
        yield get_registered_model("llm", key)


def format_llm_model_table():
    lines = [
        "| Model | Tier | Repository | Download size | Preliminary unified memory | Status |",
        "|---|---|---|---:|---:|---|",
    ]
    for spec in LLM_MODEL_REGISTRY.values():
        lines.append(
            f"| {spec.display_name} (`{spec.key}`) | {spec.tier} | "
            f"`{spec.repo_id}` | {spec.download_size} | "
            f"{spec.memory_recommendation} | {spec.status} |"
        )
    return "\n".join(lines)
