import gc
import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

from CYTOLONE.model import LLM_GENERATION_DEFAULTS, get_llm_spec
from CYTOLONE.model_storage import model_directory_is_complete


class LLMRuntimeError(RuntimeError):
    pass


class MissingLLMModelError(LLMRuntimeError):
    pass


@dataclass(frozen=True)
class GenerationSettings:
    max_tokens: int = LLM_GENERATION_DEFAULTS.max_tokens
    temperature: float = LLM_GENERATION_DEFAULTS.temperature
    top_p: float = LLM_GENERATION_DEFAULTS.top_p
    top_k: int = LLM_GENERATION_DEFAULTS.top_k
    seed: int = LLM_GENERATION_DEFAULTS.seed

    @classmethod
    def from_mapping(cls, values=None):
        values = values or {}
        defaults = cls()
        settings = cls(
            max_tokens=int(values.get("LLM_MAX_TOKENS", defaults.max_tokens)),
            temperature=float(values.get("LLM_TEMPERATURE", defaults.temperature)),
            top_p=float(values.get("LLM_TOP_P", defaults.top_p)),
            top_k=int(values.get("LLM_TOP_K", defaults.top_k)),
            seed=int(values.get("LLM_SEED", defaults.seed)),
        )
        if settings.max_tokens < 1:
            raise ValueError("LLM_MAX_TOKENS must be at least 1")
        if not 0.0 <= settings.temperature <= 2.0:
            raise ValueError("LLM_TEMPERATURE must be between 0.0 and 2.0")
        if not 0.0 <= settings.top_p <= 1.0:
            raise ValueError("LLM_TOP_P must be between 0.0 and 1.0")
        if not 0 <= settings.top_k <= 10000:
            raise ValueError("LLM_TOP_K must be between 0 and 10000")
        if not 0 <= settings.seed <= 2**32 - 1:
            raise ValueError("LLM_SEED must be between 0 and 4294967295")
        return settings


def _format_chat_prompt(processor, messages):
    template_owner = getattr(processor, "tokenizer", processor)
    apply_chat_template = getattr(template_owner, "apply_chat_template", None)
    if apply_chat_template is None:
        return "\n\n".join(
            f"[{message['role'].upper()}]\n{message['content']}" for message in messages
        )

    try:
        return apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    except TypeError:
        return apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )


def _clear_mlx_cache():
    # Do not import MLX from cleanup paths. This keeps mock-only tests and
    # app startup free of native runtime initialization; real backends load it
    # before this helper is reached.
    mlx_core = sys.modules.get("mlx.core")
    clear_cache = getattr(mlx_core, "clear_cache", None)
    if clear_cache is not None:
        clear_cache()


def _seed_mlx(seed):
    # See _clear_mlx_cache: importing mlx.core solely to seed a mock or an
    # otherwise unloaded runtime can register native bindings more than once.
    mlx_core = sys.modules.get("mlx.core")
    random_module = getattr(mlx_core, "random", None)
    seed_fn = getattr(random_module, "seed", None)
    if seed_fn is not None:
        try:
            seed_fn(seed)
        except RuntimeError:
            pass


def _legacy_sampler(settings):
    sample_utils = sys.modules.get("mlx_lm.sample_utils")
    if sample_utils is None:
        backend_module = sys.modules.get("mlx_lm")
        if backend_module is None or not hasattr(backend_module, "__path__"):
            return None
    try:
        if sample_utils is None:
            sample_utils = importlib.import_module("mlx_lm.sample_utils")
        return sample_utils.make_sampler(
            temp=settings.temperature,
            top_p=settings.top_p,
            top_k=settings.top_k,
        )
    except (ImportError, AttributeError):
        return None


class LocalLLMRuntime:
    """Lazy, single-active-model runtime for Qwen VLM and legacy MLX-LM."""

    def __init__(self):
        self._active_model_key = None
        self._model = None
        self._processor = None
        self._generate = None

    @property
    def active_model_key(self):
        return self._active_model_key

    def release_model(self, model_key):
        if self._active_model_key == model_key:
            self.clear()

    def clear(self):
        self._model = None
        self._processor = None
        self._active_model_key = None
        self._generate = None
        gc.collect()
        _clear_mlx_cache()

    @staticmethod
    def _backend(spec):
        module_name = "mlx_vlm" if spec.runtime == "mlx-vlm" else "mlx_lm"
        try:
            module = importlib.import_module(module_name)
            return module.load, module.generate
        except (ImportError, AttributeError) as exc:
            raise LLMRuntimeError(
                f"The {spec.runtime} runtime for {spec.display_name} is unavailable. "
                "Reinstall CYTOLONE's dependencies before enabling LLM findings."
            ) from exc

    def _load_if_needed(self, model_key, model_path):
        spec = get_llm_spec(model_key)
        model_path = Path(model_path)
        if not model_directory_is_complete(model_path):
            raise MissingLLMModelError(
                f"{spec.display_name} is not installed or is incomplete at "
                f"{model_path}. Open Model Management and download the selected LLM "
                "before enabling findings generation."
            )

        if self._active_model_key == model_key and self._model is not None:
            return spec

        if self._model is not None:
            self.clear()

        load_model, generate_text = self._backend(spec)
        try:
            self._model, self._processor = load_model(str(model_path))
        except Exception as exc:  # noqa: BLE001
            raise LLMRuntimeError(
                f"Could not load {spec.display_name} from {model_path}. "
                "Open Model Management and try a force re-download."
            ) from exc
        self._active_model_key = model_key
        self._generate = generate_text
        return spec

    def generate(self, model_key, model_path, messages, settings=None):
        settings = GenerationSettings.from_mapping(settings)
        spec = self._load_if_needed(model_key, model_path)
        prompt = _format_chat_prompt(self._processor, messages)
        _seed_mlx(settings.seed)
        generation_kwargs = {
            "max_tokens": settings.max_tokens,
            "verbose": False,
        }

        if spec.runtime == "mlx-vlm":
            # The chat template disables thinking. No image argument is passed:
            # Qwen is a text-only explanation layer.
            generation_kwargs.update(
                {
                    "temperature": settings.temperature,
                    "top_p": settings.top_p,
                    "top_k": settings.top_k,
                }
            )
            result = self._generate(
                self._model,
                self._processor,
                prompt,
                **generation_kwargs,
            )
        else:
            sampler = _legacy_sampler(settings)
            if sampler is not None:
                generation_kwargs["sampler"] = sampler
            result = self._generate(
                self._model,
                self._processor,
                prompt,
                **generation_kwargs,
            )

        return getattr(result, "text", result).__str__().strip()
