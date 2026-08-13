import gc
import importlib
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from transformers import AutoTokenizer

from CYTOLONE.model import LLM_GENERATION_DEFAULTS, get_llm_spec
from CYTOLONE.model_storage import model_directory_is_complete


class LLMRuntimeError(RuntimeError):
    pass


class MissingLLMModelError(LLMRuntimeError):
    pass


_MLX_VLM_GENERATION_LOCK = threading.Lock()


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


def _set_mlx_vlm_thread_local_stream():
    """Work around mlx-vlm 0.4.4's thread-bound generation stream."""

    try:
        generation_module = importlib.import_module("mlx_vlm.generate")
        mlx_core = importlib.import_module("mlx.core")
        new_thread_local_stream = getattr(mlx_core, "new_thread_local_stream", None)
        if new_thread_local_stream is None:
            return
        stream = new_thread_local_stream(
            mlx_core.default_device()
        )
        generation_module.generation_stream = stream
        return stream
    except (ImportError, AttributeError):
        return


def _load_text_only_vlm(model_path):
    """Load an mlx-vlm model without its unused image processor."""
    utils = importlib.import_module("mlx_vlm.utils")
    tokenizer_utils = importlib.import_module("mlx_vlm.tokenizer_utils")
    model_path = Path(model_path)
    model = utils.load_model(model_path, lazy=True)
    detokenizer_class = tokenizer_utils.load_tokenizer(
        model_path, return_tokenizer=False
    )
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    tokenizer.detokenizer = detokenizer_class(tokenizer)
    tokenizer.stopping_criteria = utils.StoppingCriteria(
        getattr(model.config, "eos_token_id", None), tokenizer
    )
    return model, tokenizer


def _exception_summary(exc, limit=300):
    detail = " ".join(str(exc).split()) or "no detail provided"
    if len(detail) > limit:
        detail = f"{detail[: limit - 3]}..."
    return f"{type(exc).__name__}: {detail}"


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
            load_model = (
                _load_text_only_vlm if spec.runtime == "mlx-vlm" else module.load
            )
            return load_model, module.generate
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
                f"Load failed ({_exception_summary(exc)}). The model may be "
                "incomplete, "
                "incompatible, or exceed available memory. Open Model Management to "
                "re-download it if the files are incomplete."
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
            with _MLX_VLM_GENERATION_LOCK:
                _set_mlx_vlm_thread_local_stream()
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
