import json
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import gradio as gr

from CYTOLONE.app import (
    build_app,
    build_model_management_page,
    build_settings_page,
    delete_model_from_ui,
    download_model_from_ui,
    generate_comments,
    get_labels_for_order,
    load_application_model,
    MANUAL_GENERATION_BUTTON_LABELS,
    MANUAL_GENERATION_GUIDANCE,
    reset_analysis_outputs,
    run as run_app,
    show_manual_generation_with_current_config,
)
from CYTOLONE.default_config.config_manager import main as config_main
from CYTOLONE.default_config.config_manager import read_config, write_config
from CYTOLONE.download_models import (
    ModelDeletionConfirmationRequired,
    delete_registered_model,
    download_and_flatten,
    download_model_with_status,
    download_models,
    download_models_with_status,
    get_download_targets,
    model_management_summary,
    model_download_summary,
    model_is_installed,
)
from CYTOLONE.download_models import main as download_main
from CYTOLONE.label_caption import (
    DIAGNOSIS_CANDIDATE_LABELS,
    LLM_DIAGNOSIS_LABELS,
    classification_label,
    get_label_caption,
    get_llm_diagnosis_label,
)
from CYTOLONE.llm_prompt import build_prompt_v2
from CYTOLONE.llm_runtime import (
    LLMRuntimeError,
    LocalLLMRuntime,
    MissingLLMModelError,
    _set_mlx_vlm_thread_local_stream,
)
from CYTOLONE.model import (
    LLM_MODEL_REGISTRY,
    get_llm_spec,
)
from CYTOLONE.model_storage import model_directory_is_complete
from CYTOLONE.settings_page import apply_settings, get_settings_values, validate_settings
from CYTOLONE.theme import (
    CYTOLONE_GREEN,
    CYTOLONE_GREEN_DARK,
    CYTOLONE_GREEN_HOVER,
    CYTOLONE_PURPLE,
    CYTOLONE_PURPLE_DARK,
    CYTOLONE_THEME,
)
from CYTOLONE.util import build_config_df


def make_model_directory(directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(json.dumps({"model_type": "mock"}), encoding="utf-8")
    (directory / "tokenizer.json").write_text("{}", encoding="utf-8")
    (directory / "model.safetensors").write_bytes(b"mock weights")


def make_sharded_model_directory(directory, missing_shard=False, include_index=True):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(json.dumps({"model_type": "mock"}), encoding="utf-8")
    (directory / "tokenizer.json").write_text("{}", encoding="utf-8")
    if include_index:
        (directory / "model.safetensors.index.json").write_text(
            json.dumps(
                {
                    "metadata": {"total_size": 2},
                    "weight_map": {
                        "layer.0": "model-00001-of-00002.safetensors",
                        "layer.1": "model-00002-of-00002.safetensors",
                    },
                }
            ),
            encoding="utf-8",
        )
    (directory / "model-00001-of-00002.safetensors").write_bytes(b"shard 1")
    if not missing_shard:
        (directory / "model-00002-of-00002.safetensors").write_bytes(b"shard 2")


class LLMRegistryTests(unittest.TestCase):
    def test_qwen_registry_contains_manual_choices_and_vlm_runtime(self):
        self.assertEqual(
            list(LLM_MODEL_REGISTRY)[:4],
            [
                "qwen3.5-9b-4bit",
                "qwen3.5-9b-8bit",
                "qwen3.5-27b-5bit",
                "qwen3.5-27b-8bit",
            ],
        )
        self.assertEqual(get_llm_spec("qwen3.5-9b-4bit").runtime, "mlx-vlm")
        self.assertEqual(get_llm_spec("qwen3.5-9b-4bit").generation_defaults.max_tokens, 512)
        self.assertFalse(get_llm_spec("qwen3.5-9b-4bit").generation_defaults.enable_thinking)
        self.assertEqual(get_llm_spec("gpt-oss-120b").runtime, "mlx-lm")
        self.assertTrue(get_llm_spec("gpt-oss-120b").legacy)

    def test_download_targets_include_selected_llm_when_generation_is_disabled(self):
        targets = get_download_targets(
            {
                "MODEL": "v1.1",
                "LLM_MODEL": "qwen3.5-9b-4bit",
                "LLM_GEN": False,
            }
        )
        self.assertEqual(len(targets), 2)
        self.assertIn("mlx-community/Qwen3.5-9B-4bit", targets)


class PromptV2Tests(unittest.TestCase):
    def test_prompt_separates_system_and_user_and_hides_classifier_internals(self):
        prompt = build_prompt_v2(
            "cervix",
            "en",
            "Mild_dysplasia",
            "Adeno_carcinoma",
        )

        self.assertIn("have not inspected the cell image", prompt.system)
        self.assertIn("do not make a final diagnosis", prompt.system)
        self.assertIn("Respond only in English", prompt.system)
        self.assertIn("Mild dysplasia", prompt.user)
        self.assertIn("Adenocarcinoma", prompt.user)
        self.assertNotIn("_", prompt.user)
        self.assertNotIn("0.8", prompt.user)
        self.assertNotIn("confidence", prompt.user.lower())
        self.assertEqual(len(prompt.messages), 2)
        self.assertEqual(prompt.messages[0]["role"], "system")
        self.assertEqual(prompt.messages[1]["role"], "user")

    def test_japanese_prompt_is_profile_driven(self):
        prompt = build_prompt_v2(
            "cervix", "ja", "Moderate_dysplasia", "Severe_dysplasia"
        )
        self.assertIn("子宮頸部細胞診", prompt.user)
        self.assertIn("Moderate dysplasia", prompt.user)
        self.assertIn("Severe dysplasia", prompt.user)
        for japanese_name in ("萎縮", "軽度異形成", "中等度異形成", "高度異形成", "扁平上皮癌", "腺癌"):
            self.assertNotIn(japanese_name, prompt.user)
        self.assertIn("出力言語は日本語に限定", prompt.system)
        self.assertNotIn("_", prompt.user)

    def test_prompt_output_budget_and_safety_contract_is_symmetric(self):
        english = build_prompt_v2(
            "cervix", "en", "Mild_dysplasia", "Atrophy"
        ).system
        japanese = build_prompt_v2(
            "cervix", "ja", "Mild_dysplasia", "Atrophy"
        ).system

        self.assertIn("no more than 6 bullet points total", english)
        self.assertIn("do not repeat a conclusion or add a summary", english)
        self.assertIn("write exactly 4 bullets, one sentence each", english)
        self.assertIn("directly compare both candidates in the same sentence", english)
        self.assertIn("rather than listing candidates separately", english)
        self.assertIn("typical general patterns", english)
        self.assertIn("N/C ratio", english)
        self.assertIn("Keep Section 2 to at most 1 short, one-sentence bullet", english)
        self.assertIn("Keep Section 3 to at most 1 short, one-sentence bullet", english)
        self.assertIn("actual cytology, clinical findings, and standard management guidance", english)
        self.assertIn("do not automatically recommend invasive tests, procedures, or treatment", english)
        self.assertNotIn("serum hormone measurement", english)

        self.assertIn("箇条書きは全体で最大6個", japanese)
        self.assertIn("結論の反復や追加の要約は書かない", japanese)
        self.assertIn("第1セクションを最も詳しく", japanese)
        self.assertIn("箇条書きはちょうど4個、各1文", japanese)
        self.assertIn("2候補を同じ文で直接比較", japanese)
        self.assertIn("候補ごとに別々に列挙せず", japanese)
        self.assertIn("N/C比", japanese)
        self.assertIn("第2セクションは最大1個の短い箇条書き（1文）", japanese)
        self.assertIn("第3セクションも最大1個の短い箇条書き（1文）", japanese)
        self.assertIn("実際の細胞診・臨床所見と標準的な管理指針", japanese)
        self.assertIn("侵襲的検査、処置、治療を自動的に勧めない", japanese)
        self.assertNotIn("血清ホルモン測定", japanese)

    def test_unknown_diagnosis_label_is_actionable(self):
        with self.assertRaisesRegex(ValueError, "Unknown diagnosis label"):
            build_prompt_v2("cervix", "en", "Unknown_label", "Negative")

    def test_six_diagnoses_have_english_llm_safe_names(self):
        expected = {
            "Atrophy",
            "Mild_dysplasia",
            "Moderate_dysplasia",
            "Severe_dysplasia",
            "Squamous_cell_carcinoma",
            "Adeno_carcinoma",
        }
        self.assertEqual(set(LLM_DIAGNOSIS_LABELS["cervix"]), expected)
        self.assertNotIn("Negative", LLM_DIAGNOSIS_LABELS["cervix"])
        for diagnosis in expected:
            name = get_llm_diagnosis_label("cervix", diagnosis)
            self.assertTrue(name.isascii())
            self.assertNotIn("_", name)


class ClassificationLabelTests(unittest.TestCase):
    def test_classifier_results_remain_english_for_both_languages(self):
        _, english_labels, _ = get_label_caption("cervix", "en")
        _, japanese_labels, _ = get_label_caption("cervix", "ja")
        self.assertEqual(english_labels, classification_label["cervix"])
        self.assertEqual(japanese_labels, classification_label["cervix"])

    def test_full_candidates_are_exactly_the_seven_hierarchy_strings(self):
        expected = tuple(classification_label["cervix"])
        full = get_labels_for_order(
            "cervix", classification_label["cervix"],
            ["Full", "Anomaly", "Malignancy", "System", "Diagnosis"],
            "Full",
        )
        self.assertEqual(full, list(expected))
        self.assertIn("Normal Benign NILM Negative", full)

    def test_diagnosis_candidates_exactly_exclude_only_negative(self):
        expected = list(DIAGNOSIS_CANDIDATE_LABELS["cervix"])
        diagnosis = get_labels_for_order(
            "cervix", classification_label["cervix"],
            ["Full", "Anomaly", "Malignancy", "System", "Diagnosis"],
            "Diagnosis",
        )
        self.assertEqual(diagnosis, expected)
        self.assertNotIn("Normal Benign NILM Negative", diagnosis)
        self.assertIn("Normal Benign NILM Atrophy", diagnosis)

    def test_unknown_llm_diagnosis_label_is_actionable(self):
        with self.assertRaisesRegex(ValueError, "Unknown diagnosis label"):
            get_llm_diagnosis_label("cervix", "Negative")


class DocumentationTests(unittest.TestCase):
    def test_readmes_hide_llm_tuning_and_runtime_details(self):
        forbidden = (
            "LLM_GEN_THRESHOLD",
            "LLM_MAX_TOKENS",
            "LLM_TEMPERATURE",
            "LLM_TOP_P",
            "LLM_TOP_K",
            "LLM_SEED",
            "mlx-vlm",
            "staging",
            "thinking mode",
        )
        for path in (Path("README.md"), Path("README_JA.md")):
            content = path.read_text(encoding="utf-8")
            for term in forbidden:
                self.assertNotIn(term, content, f"{term} should not appear in {path}")
            self.assertIn("Model Management", content)


class SettingsCompatibilityTests(unittest.TestCase):
    def test_old_config_inherits_new_defaults_without_replacing_old_choices(self):
        with tempfile.TemporaryDirectory() as temporary:
            old_path = Path(temporary) / "config.ini"
            old_path.write_text(
                "[SETTINGS]\n"
                "LANGUAGE = ja\n"
                "MODEL = v1.0\n"
                "LLM_MODEL = gpt-oss-20b\n"
                "LLM_GEN = True\n"
                "LLM_GEN_THRESHOLD = 0.4\n"
                "WEBCAM_IMAGE_SIZE = 900\n"
                "DEBUG = True\n",
                encoding="utf-8",
            )
            config = read_config(old_path)
            self.assertEqual(config["SETTINGS"]["LLM_MODEL"], "gpt-oss-20b")
            self.assertEqual(config["SETTINGS"]["LLM_MAX_TOKENS"], "512")
            self.assertEqual(config["SETTINGS"]["LLM_SEED"], "42")

    def test_invalid_settings_do_not_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict("os.environ", {"CYTOLONE_DATA_ROOT": temporary}):
                config = read_config()
                write_config(config)
                before = Path(temporary, "config.ini").read_text(encoding="utf-8")
                with self.assertRaises(ValueError):
                    apply_settings(
                        "en",
                        "v1.1",
                        "qwen3.5-9b-4bit",
                        0,
                        False,
                    )
                self.assertEqual(Path(temporary, "config.ini").read_text(encoding="utf-8"), before)

    def test_valid_settings_bounds_are_explicit(self):
        values = validate_settings(
            "en",
            "v1.1",
            "qwen3.5-9b-4bit",
            1024,
            False,
        )
        self.assertEqual(values["WEBCAM_IMAGE_SIZE"], 1024)
        self.assertNotIn("LLM_TEMPERATURE", values)

    def test_normal_settings_preserve_hidden_llm_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict("os.environ", {"CYTOLONE_DATA_ROOT": temporary}):
                config = read_config()
                config["SETTINGS"]["LLM_GEN_THRESHOLD"] = "0.45"
                config["SETTINGS"]["LLM_MAX_TOKENS"] = "321"
                config["SETTINGS"]["LLM_TEMPERATURE"] = "0.25"
                config["SETTINGS"]["LLM_TOP_P"] = "0.65"
                config["SETTINGS"]["LLM_TOP_K"] = "12"
                config["SETTINGS"]["LLM_SEED"] = "9"
                config["SETTINGS"]["LLM_GEN"] = "True"
                write_config(config)

                result = apply_settings(
                    "ja", "v1.0", "qwen3.5-9b-8bit", 900, True
                )
                after = read_config()["SETTINGS"]

            self.assertEqual(len(result), 6)
            self.assertEqual(after["LLM_GEN"], "True")
            self.assertEqual(after["LLM_GEN_THRESHOLD"], "0.45")
            self.assertEqual(after["LLM_MAX_TOKENS"], "321")
            self.assertEqual(after["LLM_TEMPERATURE"], "0.25")
            self.assertEqual(after["LLM_TOP_P"], "0.65")
            self.assertEqual(after["LLM_TOP_K"], "12")
            self.assertEqual(after["LLM_SEED"], "9")

    def test_normal_settings_values_and_main_summary_are_concise(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict("os.environ", {"CYTOLONE_DATA_ROOT": temporary}):
                values = get_settings_values()
            frame = build_config_df(
                {
                    "LANGUAGE": "en",
                    "MODEL": "v1.1",
                    "LLM_MODEL": "qwen3.5-9b-4bit",
                    "LLM_GEN": False,
                    "LLM_GEN_THRESHOLD": 0.8,
                    "LLM_MAX_TOKENS": 512,
                    "LLM_TEMPERATURE": 0.7,
                    "LLM_TOP_P": 0.8,
                    "LLM_TOP_K": 20,
                    "LLM_SEED": 42,
                    "WEBCAM_IMAGE_SIZE": 1024,
                    "DEBUG": False,
                }
            )
            self.assertEqual(len(values), 5)
            self.assertEqual(len(frame), 4)
            self.assertNotIn("Generate", set(frame["Item"]))
            self.assertNotIn("Threshold", set(frame["Item"]))
            self.assertNotIn("Temperature", set(frame["Item"]))

    def test_cli_rejects_invalid_llm_range_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict("os.environ", {"CYTOLONE_DATA_ROOT": temporary}):
                config = read_config()
                write_config(config)
                config_path = Path(temporary, "config.ini")
                before = config_path.read_text(encoding="utf-8")

                with patch.object(sys, "argv", ["cytolone-config", "--LLM_TOP_P", "2"]):
                    with self.assertRaises(SystemExit) as context:
                        config_main()

                self.assertEqual(context.exception.code, 2)
                self.assertEqual(config_path.read_text(encoding="utf-8"), before)


class ManualGenerationUXTests(unittest.TestCase):
    QUESTION = "What is the diagnosis for this image?"
    QUESTION_MAP = {QUESTION: "Diagnosis"}
    ORDER = ["Full", "Anomaly", "Malignancy", "System", "Diagnosis"]

    def _config(self, language="en", llm_gen=False):
        return {
            "LANGUAGE": language,
            "MODEL": "v1.1",
            "LLM_MODEL": "qwen3.5-9b-4bit",
            "LLM_GEN": llm_gen,
            "LLM_GEN_THRESHOLD": 0.8,
            "LLM_MAX_TOKENS": 512,
            "LLM_TEMPERATURE": 0.7,
            "LLM_TOP_P": 0.8,
            "LLM_TOP_K": 20,
            "LLM_SEED": 42,
            "WEBCAM_IMAGE_SIZE": 1024,
            "DEBUG": False,
        }

    def test_reset_clears_results_and_prepares_language_specific_button(self):
        for language in ("ja", "en"):
            label, label_probs, guidance, button, comment, capture = reset_analysis_outputs(language)
            self.assertIsNone(label["value"])
            self.assertEqual(label_probs, {})
            self.assertEqual(guidance["value"], "")
            self.assertFalse(guidance["visible"])
            self.assertEqual(button["value"], MANUAL_GENERATION_BUTTON_LABELS[language])
            self.assertFalse(button["visible"])
            self.assertTrue(button["interactive"])
            self.assertEqual(comment["value"], "")
            self.assertEqual(capture["value"], "")

    def test_manual_offer_uses_diagnosis_threshold_only_even_when_llm_gen_is_false(self):
        config = self._config(language="ja", llm_gen=False)
        question = "この画像の診断は?"
        labels = {"Atrophy": 0.45, "Mild_dysplasia": 0.40}
        with patch(
            "CYTOLONE.app.get_main_context",
            return_value=(config, {question: "Diagnosis"}, [], self.ORDER),
        ):
            guidance, button = show_manual_generation_with_current_config(
                question, labels, "cervix"
            )

        self.assertTrue(guidance["visible"])
        self.assertEqual(guidance["value"], MANUAL_GENERATION_GUIDANCE["ja"])
        self.assertTrue(button["visible"])
        self.assertTrue(button["interactive"])
        self.assertEqual(button["value"], MANUAL_GENERATION_BUTTON_LABELS["ja"])

    def test_manual_offer_is_hidden_for_non_diagnosis_or_non_close_results(self):
        config = self._config()
        with patch(
            "CYTOLONE.app.get_main_context",
            return_value=(config, self.QUESTION_MAP, [], self.ORDER),
        ):
            guidance, button = show_manual_generation_with_current_config(
                self.QUESTION, {"Atrophy": 0.8, "Mild_dysplasia": 0.1}, "cervix"
            )
        self.assertFalse(guidance["visible"])
        self.assertFalse(button["visible"])
        self.assertTrue(button["interactive"])

        full_question = "What do you think of this image?"
        with patch(
            "CYTOLONE.app.get_main_context",
            return_value=(
                config,
                {full_question: "Full"},
                [],
                self.ORDER,
            ),
        ):
            guidance, button = show_manual_generation_with_current_config(
                full_question, {"Atrophy": 0.45, "Mild_dysplasia": 0.40}, "cervix"
            )
        self.assertFalse(guidance["visible"])
        self.assertFalse(button["visible"])
        self.assertTrue(button["interactive"])

    def test_manual_generation_uses_labels_without_llm_gen_gate(self):
        config = self._config(llm_gen=False)
        labels = {"Atrophy": 0.45, "Mild_dysplasia": 0.40}
        with patch(
            "CYTOLONE.app.llm_runtime.generate", return_value="generated findings"
        ) as generate_mock:
            output = generate_comments(self.QUESTION, labels, "cervix", config)

        self.assertEqual(output, "generated findings")
        messages = generate_mock.call_args.kwargs["messages"]
        self.assertIn("Atrophy", messages[1]["content"])
        self.assertIn("Mild dysplasia", messages[1]["content"])
        self.assertNotIn("image", messages[1]["content"].lower())

    def test_build_app_wires_reset_classify_condition_and_manual_click(self):
        app = build_app()
        components = app.config["components"]

        def component_id(predicate):
            return next(item for item in components if predicate(item))["id"]

        question_id = component_id(
            lambda item: item["props"].get("label") == "Question Type"
        )
        image_id = component_id(
            lambda item: item["props"].get("elem_id") == "cytolone-image-input"
        )
        capture_id = component_id(
            lambda item: item["type"] == "textbox"
            and item["props"].get("visible") is False
        )
        label_id = component_id(
            lambda item: item["props"].get("label") == "Result"
        )
        label_probs_state_id = component_id(
            lambda item: item["type"] == "state"
        )
        guidance_id = component_id(
            lambda item: item["type"] == "markdown"
            and item["props"].get("visible") is False
            and item["props"].get("value") == ""
        )
        button_id = component_id(
            lambda item: item["type"] == "button"
            and item["props"].get("value") == MANUAL_GENERATION_BUTTON_LABELS["en"]
        )
        button_component = next(item for item in components if item["id"] == button_id)
        self.assertFalse(button_component["props"].get("visible"))
        self.assertTrue(button_component["props"].get("interactive"))
        comment_id = component_id(
            lambda item: item["props"].get("elem_classes") == ["comment-box"]
        )
        language_id = component_id(
            lambda item: item["props"].get("label") == "LANGUAGE"
        )

        dependencies = app.config["dependencies"]
        reset_outputs = {
            label_id,
            label_probs_state_id,
            guidance_id,
            button_id,
            comment_id,
            capture_id,
        }
        reset_events = [
            dependency
            for dependency in dependencies
            if set(dependency["outputs"]) == reset_outputs
        ]
        self.assertEqual(len(reset_events), 4)

        classify_events = [
            dependency
            for dependency in dependencies
            if dependency["inputs"] == [question_id, image_id, capture_id]
            and dependency["outputs"] == [label_id, label_probs_state_id]
        ]
        self.assertEqual(len(classify_events), 1)
        self.assertIn("canvas", classify_events[0]["js"])

        condition_events = [
            dependency
            for dependency in dependencies
            if dependency["inputs"] == [question_id, label_probs_state_id]
            and dependency["outputs"] == [guidance_id, button_id]
        ]
        self.assertEqual(len(condition_events), 1)

        manual_events = [
            dependency
            for dependency in dependencies
            if dependency["targets"] == [(button_id, "click")]
            and dependency["inputs"] == [question_id, label_probs_state_id]
            and dependency["outputs"] == [comment_id]
        ]
        self.assertEqual(len(manual_events), 1)
        self.assertFalse(manual_events[0].get("js"))
        self.assertEqual(
            len(
                [
                    dependency
                    for dependency in reset_events
                    if dependency["targets"] == [(language_id, "change")]
                    and dependency["inputs"] == [language_id]
                ]
            ),
            1,
        )


class RuntimeAdapterTests(unittest.TestCase):
    def test_missing_application_model_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "CYTOLONE.app.models_path", return_value=Path(temporary)
        ):
            with self.assertRaises(gr.Error) as context:
                load_application_model("v1.1")
        self.assertIn("Model Management", str(context.exception))
        self.assertIn("application model", str(context.exception))

    def test_mlx_vlm_global_stream_is_replaced_for_each_worker(self):
        old_stream = object()

        class ThreadLocalStreamSentinel:
            pass

        thread_local_streams = [
            ThreadLocalStreamSentinel(),
            ThreadLocalStreamSentinel(),
        ]
        generation_module = types.SimpleNamespace(generation_stream=old_stream)
        mlx_core = types.SimpleNamespace(
            ThreadLocalStream=ThreadLocalStreamSentinel,
            default_device=Mock(return_value="gpu device"),
            new_thread_local_stream=Mock(side_effect=thread_local_streams),
        )

        def import_module(name):
            return {
                "mlx_vlm.generate": generation_module,
                "mlx.core": mlx_core,
            }[name]

        results = []

        def run_in_worker():
            results.append(_set_mlx_vlm_thread_local_stream())

        with patch(
            "CYTOLONE.llm_runtime.importlib.import_module",
            side_effect=import_module,
        ):
            for _ in range(2):
                worker = threading.Thread(target=run_in_worker)
                worker.start()
                worker.join()

        self.assertEqual(results, thread_local_streams)
        self.assertIs(generation_module.generation_stream, thread_local_streams[-1])
        self.assertEqual(mlx_core.new_thread_local_stream.call_count, 2)
        for stream_call in mlx_core.new_thread_local_stream.call_args_list:
            self.assertEqual(stream_call.args, ("gpu device",))

    def test_qwen_runtime_is_text_only_and_disables_thinking(self):
        with tempfile.TemporaryDirectory() as temporary:
            model_path = Path(temporary) / "qwen"
            make_model_directory(model_path)

            class NonCallableTokenizerWrapper:
                def __init__(self, tokenizer):
                    self._tokenizer = tokenizer

                def __getattr__(self, name):
                    return getattr(self._tokenizer, name)

            class CallableTokenizer:
                def __init__(self):
                    self.apply_chat_template = Mock(
                        return_value="formatted prompt"
                    )

                def __call__(self, *args, **kwargs):
                    return {"input_ids": [[0]]}

            tokenizer = CallableTokenizer()
            wrapper = NonCallableTokenizerWrapper(tokenizer)
            detokenizer = object()
            detokenizer_class = Mock(return_value=detokenizer)
            model = types.SimpleNamespace(
                config=types.SimpleNamespace(eos_token_id=151645)
            )
            generated = types.SimpleNamespace(text="mock answer")
            qwen_module = types.SimpleNamespace(
                load=Mock(),
                generate=Mock(return_value=generated),
            )
            qwen_utils = types.SimpleNamespace(
                load_model=Mock(return_value=model),
                StoppingCriteria=Mock(return_value="stopping criteria"),
            )
            tokenizer_utils = types.SimpleNamespace(
                load_tokenizer=Mock(
                    side_effect=lambda path, return_tokenizer=True: (
                        wrapper if return_tokenizer else detokenizer_class
                    )
                )
            )
            with patch(
                "transformers.AutoTokenizer.from_pretrained",
                return_value=tokenizer,
            ) as from_pretrained, patch.dict(
                sys.modules,
                {
                    "mlx_vlm": qwen_module,
                    "mlx_vlm.utils": qwen_utils,
                    "mlx_vlm.tokenizer_utils": tokenizer_utils,
                },
            ):
                runtime = LocalLLMRuntime()
                output = runtime.generate(
                    "qwen3.5-9b-4bit",
                    model_path,
                    [
                        {"role": "system", "content": "system"},
                        {"role": "user", "content": "user"},
                    ],
                )

            self.assertEqual(output, "mock answer")
            qwen_module.load.assert_not_called()
            qwen_utils.load_model.assert_called_once_with(model_path, lazy=True)
            tokenizer_utils.load_tokenizer.assert_called_once_with(
                model_path, return_tokenizer=False
            )
            from_pretrained.assert_called_once_with(
                model_path, local_files_only=True
            )
            detokenizer_class.assert_called_once_with(tokenizer)
            self.assertFalse(callable(wrapper))
            self.assertTrue(callable(tokenizer))
            self.assertIs(runtime._processor, tokenizer)
            self.assertIs(tokenizer.detokenizer, detokenizer)
            qwen_utils.StoppingCriteria.assert_called_once_with(151645, tokenizer)
            self.assertEqual(tokenizer.stopping_criteria, "stopping criteria")
            call = qwen_module.generate.call_args
            self.assertNotIn("image", call.kwargs)
            self.assertNotIn("enable_thinking", call.kwargs)
            self.assertEqual(call.kwargs["max_tokens"], 512)
            tokenizer.apply_chat_template.assert_called_once()
            self.assertFalse(
                tokenizer.apply_chat_template.call_args.kwargs.get(
                    "enable_thinking", True
                )
            )

    def test_switching_models_replaces_the_active_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            qwen_path = Path(temporary) / "qwen"
            legacy_path = Path(temporary) / "legacy"
            make_model_directory(qwen_path)
            make_model_directory(legacy_path)
            qwen_model = types.SimpleNamespace(
                config=types.SimpleNamespace(eos_token_id=1)
            )
            qwen_tokenizer = Mock()
            qwen_module = types.SimpleNamespace(
                load=Mock(),
                generate=Mock(return_value="qwen answer"),
            )
            qwen_utils = types.SimpleNamespace(
                load_model=Mock(return_value=qwen_model),
                StoppingCriteria=Mock(),
            )
            tokenizer_utils = types.SimpleNamespace(
                load_tokenizer=Mock(return_value=qwen_tokenizer)
            )
            legacy_module = types.SimpleNamespace(
                load=Mock(return_value=("legacy-model", "legacy-tokenizer")),
                generate=Mock(return_value="legacy answer"),
            )
            with patch.dict(
                sys.modules,
                {
                    "mlx_vlm": qwen_module,
                    "mlx_vlm.utils": qwen_utils,
                    "mlx_vlm.tokenizer_utils": tokenizer_utils,
                    "mlx_lm": legacy_module,
                },
            ), patch(
                "transformers.AutoTokenizer.from_pretrained",
                return_value=qwen_tokenizer,
            ), patch(
                "CYTOLONE.llm_runtime._set_mlx_vlm_thread_local_stream"
            ) as set_stream:
                runtime = LocalLLMRuntime()
                runtime.generate("qwen3.5-9b-4bit", qwen_path, [])
                self.assertEqual(runtime.active_model_key, "qwen3.5-9b-4bit")
                runtime.generate("qwen3.5-9b-4bit", qwen_path, [])
                runtime.generate("gpt-oss-120b", legacy_path, [])

            self.assertEqual(runtime.active_model_key, "gpt-oss-120b")
            qwen_module.load.assert_not_called()
            qwen_utils.load_model.assert_called_once_with(qwen_path, lazy=True)
            self.assertEqual(qwen_module.generate.call_count, 2)
            self.assertEqual(legacy_module.load.call_count, 1)
            self.assertEqual(legacy_module.generate.call_count, 1)
            self.assertEqual(set_stream.call_count, 2)

    def test_qwen_generation_is_serialized_across_workers(self):
        active_calls = 0
        max_active_calls = 0
        call_count = 0
        state_lock = threading.Lock()
        first_call_entered = threading.Event()
        release_first_call = threading.Event()
        second_call_started = threading.Event()
        second_call_finished = threading.Event()
        outputs = []

        def generate_text(*args, **kwargs):
            nonlocal active_calls, max_active_calls, call_count
            with state_lock:
                call_count += 1
                current_call = call_count
                active_calls += 1
                max_active_calls = max(max_active_calls, active_calls)
            try:
                if current_call == 1:
                    first_call_entered.set()
                    release_first_call.wait()
                return "qwen answer"
            finally:
                with state_lock:
                    active_calls -= 1

        with tempfile.TemporaryDirectory() as temporary, patch(
            "CYTOLONE.llm_runtime.model_directory_is_complete",
            return_value=True,
        ), patch(
            "CYTOLONE.llm_runtime._set_mlx_vlm_thread_local_stream"
        ) as set_stream:
            runtime = LocalLLMRuntime()
            runtime._active_model_key = "qwen3.5-9b-4bit"
            runtime._model = object()
            runtime._processor = Mock()
            runtime._generate = generate_text
            model_path = Path(temporary) / "qwen"

            def run_first_worker():
                outputs.append(runtime.generate("qwen3.5-9b-4bit", model_path, []))

            def run_second_worker():
                second_call_started.set()
                outputs.append(runtime.generate("qwen3.5-9b-4bit", model_path, []))
                second_call_finished.set()

            first_worker = threading.Thread(target=run_first_worker)
            second_worker = threading.Thread(target=run_second_worker)
            first_worker.start()
            try:
                self.assertTrue(first_call_entered.wait(timeout=1))
                second_worker.start()
                self.assertTrue(second_call_started.wait(timeout=1))
                self.assertFalse(second_call_finished.wait(timeout=0.1))
            finally:
                release_first_call.set()
                first_worker.join(timeout=1)
                second_worker.join(timeout=1)

        self.assertEqual(outputs, ["qwen answer", "qwen answer"])
        self.assertEqual(max_active_calls, 1)
        self.assertEqual(set_stream.call_count, 2)

    def test_qwen_load_error_includes_underlying_one_line_detail(self):
        with tempfile.TemporaryDirectory() as temporary:
            model_path = Path(temporary) / "qwen"
            make_model_directory(model_path)
            qwen_module = types.SimpleNamespace(load=Mock(), generate=Mock())
            qwen_utils = types.SimpleNamespace(
                load_model=Mock(
                    side_effect=RuntimeError(
                        "Metal allocation failed\nwhile loading weights"
                    )
                ),
                StoppingCriteria=Mock(),
            )
            tokenizer_utils = types.SimpleNamespace(load_tokenizer=Mock())
            with patch.dict(
                sys.modules,
                {
                    "mlx_vlm": qwen_module,
                    "mlx_vlm.utils": qwen_utils,
                    "mlx_vlm.tokenizer_utils": tokenizer_utils,
                },
            ):
                with self.assertRaises(LLMRuntimeError) as context:
                    LocalLLMRuntime().generate(
                        "qwen3.5-9b-4bit", model_path, []
                    )

            message = str(context.exception)
            self.assertIn(
                "RuntimeError: Metal allocation failed while loading weights",
                message,
            )
            self.assertNotIn("force re-download", message)

    def test_missing_model_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(MissingLLMModelError) as context:
                LocalLLMRuntime().generate(
                    "qwen3.5-9b-4bit",
                    Path(temporary) / "missing",
                    [],
                )
            self.assertIn("Model Management", str(context.exception))


class DownloadIntegrityTests(unittest.TestCase):
    def test_download_models_loads_config_when_omitted(self):
        config = {
            "MODEL": "v1.1",
            "LLM_MODEL": "qwen3.5-9b-4bit",
            "LLM_GEN": False,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch(
                "CYTOLONE.download_models.load_config", return_value=config
            ) as load, patch(
                "CYTOLONE.download_models.download_registered_model"
            ) as registered:
                downloaded = download_models(output_root=root)

            load.assert_called_once_with()
            self.assertEqual(registered.call_count, 2)
            self.assertEqual(
                downloaded,
                ["kuri54/mlx-CYTOLONE-v1.1", "mlx-community/Qwen3.5-9B-4bit"],
            )

    def test_download_cli_defaults_to_only_application_model(self):
        config = {
            "MODEL": "v1.1",
            "LLM_MODEL": "qwen3.5-27b-8bit",
        }
        with patch.object(sys, "argv", ["download-model"]), patch(
            "CYTOLONE.download_models.load_config", return_value=config
        ), patch(
            "CYTOLONE.download_models.download_registered_model"
        ) as download:
            download_main()

        download.assert_called_once_with("application", "v1.1", force=False)

    def test_download_cli_can_explicitly_download_one_llm_with_force(self):
        config = {
            "MODEL": "v1.1",
            "LLM_MODEL": "qwen3.5-27b-8bit",
        }
        with patch.object(sys, "argv", ["download-model", "llm", "--force"]), patch(
            "CYTOLONE.download_models.load_config", return_value=config
        ), patch(
            "CYTOLONE.download_models.download_registered_model"
        ) as download:
            download_main()

        download.assert_called_once_with("llm", "qwen3.5-27b-8bit", force=True)

    def test_shard_without_index_is_not_installed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "sharded-without-index"
            make_sharded_model_directory(
                directory,
                missing_shard=True,
                include_index=False,
            )
            self.assertFalse(model_directory_is_complete(directory))

    def test_download_status_final_yield_refreshes_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = {
                "MODEL": "v1.1",
                "LLM_MODEL": "qwen3.5-9b-4bit",
                "LLM_GEN": False,
            }
            output_root = Path(temporary)

            def install_mock_model(model_id, base_output_dir, force=False):
                make_model_directory(Path(base_output_dir) / model_id)

            with patch("CYTOLONE.download_models.load_config", return_value=config), patch(
                "CYTOLONE.download_models.models_path", return_value=output_root
            ), patch(
                "CYTOLONE.download_models.download_and_flatten",
                side_effect=install_mock_model,
            ):
                updates = list(download_models_with_status())

            status, summary = updates[-1]
            self.assertIn("Model check completed", status)
            self.assertEqual(len(updates[-1]), 2)
            self.assertEqual(summary.count("| yes |"), 2)

    def test_model_download_summary_reflects_current_installed_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = {
                "MODEL": "v1.1",
                "LLM_MODEL": "qwen3.5-9b-4bit",
                "LLM_GEN": False,
            }
            output_root = Path(temporary)
            before = model_download_summary(config, output_root)
            self.assertIn("Qwen3.5 9B (4-bit)", before)
            self.assertIn("| yes | not installed | — | 5.95 GB | 16 GB or more |", before)

            make_model_directory(output_root / "mlx-community" / "Qwen3.5-9B-4bit")
            after = model_download_summary(config, output_root)
            self.assertIn("| yes | installed |", after)

    def test_sharded_index_requires_every_referenced_shard(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "sharded"
            make_sharded_model_directory(directory, missing_shard=True)
            self.assertFalse(model_directory_is_complete(directory))

            (directory / "model-00002-of-00002.safetensors").write_bytes(b"shard 2")
            self.assertTrue(model_directory_is_complete(directory))

    def test_broken_weight_index_is_not_installed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "broken-index"
            make_model_directory(directory)
            (directory / "model.safetensors.index.json").write_text("{broken", encoding="utf-8")
            self.assertFalse(model_directory_is_complete(directory))

            (directory / "model.safetensors.index.json").write_text(
                json.dumps({"weight_map": {}}), encoding="utf-8"
            )
            self.assertFalse(model_directory_is_complete(directory))

    def test_partial_directory_is_not_installed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "partial"
            directory.mkdir()
            (directory / "partial.safetensors").write_bytes(b"partial")
            self.assertFalse(model_directory_is_complete(directory))
            self.assertFalse(model_is_installed("partial", Path(temporary)))

    def test_staging_promotes_only_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "models"

            def direct_download(repo_id, local_dir, local_files_only):
                make_model_directory(Path(local_dir))
                return str(local_dir)

            with patch(
                "CYTOLONE.download_models.snapshot_download",
                side_effect=direct_download,
            ) as snapshot:
                download_and_flatten("mock/repo", destination)
            self.assertTrue(model_is_installed("mock/repo", destination))
            called_local_dir = Path(snapshot.call_args.kwargs["local_dir"])
            self.assertEqual(called_local_dir.parent, destination.resolve() / "mock")
            self.assertFalse(called_local_dir.exists())

    def test_failed_forced_replacement_preserves_complete_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "models"
            existing = destination / "mock" / "repo"
            make_model_directory(existing)

            def incomplete_download(repo_id, local_dir, local_files_only):
                (Path(local_dir) / "partial.safetensors").write_bytes(b"partial")
                return str(local_dir)

            with patch(
                "CYTOLONE.download_models.snapshot_download",
                side_effect=incomplete_download,
            ):
                with self.assertRaises(RuntimeError):
                    download_and_flatten("mock/repo", destination, force=True)
            self.assertTrue(model_is_installed("mock/repo", destination))
            self.assertEqual((existing / "model.safetensors").read_bytes(), b"mock weights")


class ModelDeletionTests(unittest.TestCase):
    def test_delete_requires_confirmation_and_releases_cache_first(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "Models"
            target = root / "kuri54" / "mlx-CYTOLONE-v1.1"
            make_model_directory(target)
            released = []

            with patch("CYTOLONE.download_models.models_path", return_value=root):
                with self.assertRaises(ModelDeletionConfirmationRequired):
                    delete_registered_model("application", "v1.1")
                self.assertTrue(target.exists())
                deleted = delete_registered_model(
                    "application",
                    "v1.1",
                    confirmation=True,
                    release_callback=lambda spec: released.append(
                        (spec.role, spec.key, target.exists())
                    ),
                )

            self.assertTrue(deleted)
            self.assertEqual(released, [("application", "v1.1", True)])
            self.assertFalse(target.exists())

    def test_delete_allows_one_incomplete_registered_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "Models"
            target = root / "mlx-community" / "Qwen3.5-9B-4bit"
            target.mkdir(parents=True)
            (target / "config.json").write_text("{}", encoding="utf-8")
            (target / "tokenizer.json").write_text("{}", encoding="utf-8")
            (target / "model-00001-of-00002.safetensors").write_bytes(b"partial")
            released = Mock()

            with patch("CYTOLONE.download_models.models_path", return_value=root):
                deleted = delete_registered_model(
                    "llm",
                    "qwen3.5-9b-4bit",
                    confirmation=True,
                    release_callback=released,
                )

            self.assertTrue(deleted)
            released.assert_called_once()
            self.assertFalse(target.exists())

    def test_delete_is_registry_and_managed_root_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            managed_root = Path(temporary) / "Models"
            other_root = Path(temporary) / "SharedCache"
            shared = other_root / "kuri54" / "mlx-CYTOLONE-v1.1"
            make_model_directory(shared)

            with patch("CYTOLONE.download_models.models_path", return_value=managed_root):
                with self.assertRaisesRegex(ValueError, "Unknown application model"):
                    delete_registered_model(
                        "application", "../other", confirmation=True
                    )
                with self.assertRaisesRegex(ValueError, "restricted"):
                    delete_registered_model(
                        "application",
                        "v1.1",
                        base_output_dir=other_root,
                        confirmation=True,
                    )

            self.assertTrue(shared.exists())

    def test_delete_refuses_symlinked_repository_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "Models"
            outside = Path(temporary) / "Outside"
            make_model_directory(outside / "mlx-CYTOLONE-v1.1")
            root.mkdir()
            (root / "kuri54").symlink_to(outside, target_is_directory=True)

            with patch("CYTOLONE.download_models.models_path", return_value=root):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    delete_registered_model(
                        "application", "v1.1", confirmation=True
                    )

            self.assertTrue((outside / "mlx-CYTOLONE-v1.1").exists())

    def test_delete_refuses_symlinked_models_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            outside = Path(temporary) / "SharedCache"
            make_model_directory(outside / "kuri54" / "mlx-CYTOLONE-v1.1")
            root = Path(temporary) / "Models"
            root.symlink_to(outside, target_is_directory=True)

            with patch("CYTOLONE.download_models.models_path", return_value=root):
                with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                    delete_registered_model(
                        "application", "v1.1", confirmation=True
                    )

            self.assertTrue((outside / "kuri54" / "mlx-CYTOLONE-v1.1").exists())

    def test_inventory_reports_incomplete_and_actual_size(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "mlx-community" / "Qwen3.5-9B-4bit"
            target.mkdir(parents=True)
            (target / "partial.safetensors").write_bytes(b"x" * 2048)
            summary = model_management_summary(
                {
                    "MODEL": "v1.1",
                    "LLM_MODEL": "qwen3.5-9b-4bit",
                },
                root,
            )
            self.assertIn("| incomplete | 2.0 KB | 5.95 GB |", summary)

    def test_individual_download_refreshes_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = {
                "MODEL": "v1.1",
                "LLM_MODEL": "qwen3.5-9b-4bit",
                "LLM_GEN": False,
            }

            def install(role, key, base_output_dir, force=False):
                make_model_directory(
                    Path(base_output_dir) / "mlx-community" / "Qwen3.5-9B-4bit"
                )

            with patch("CYTOLONE.download_models.load_config", return_value=config), patch(
                "CYTOLONE.download_models.models_path", return_value=root
            ), patch(
                "CYTOLONE.download_models.download_registered_model",
                side_effect=install,
            ):
                updates = list(
                    download_model_with_status("llm", "qwen3.5-9b-4bit")
                )

            self.assertEqual(len(updates), 2)
            self.assertIn("| installed |", updates[-1][1])


class ModelManagementWiringTests(unittest.TestCase):
    def test_brand_theme_tokens_and_application_blocks_wiring(self):
        self.assertEqual(CYTOLONE_THEME.primary_500, CYTOLONE_GREEN)
        self.assertEqual(CYTOLONE_THEME.secondary_500, CYTOLONE_PURPLE)
        self.assertEqual(CYTOLONE_THEME.color_accent, CYTOLONE_GREEN)
        self.assertEqual(CYTOLONE_THEME.input_border_color_focus, CYTOLONE_GREEN_DARK)
        self.assertEqual(
            CYTOLONE_THEME.button_secondary_background_fill_dark,
            CYTOLONE_PURPLE_DARK,
        )
        primary_backgrounds = (
            CYTOLONE_THEME.button_primary_background_fill,
            CYTOLONE_THEME.button_primary_background_fill_dark,
            CYTOLONE_THEME.button_primary_background_fill_hover,
            CYTOLONE_THEME.button_primary_background_fill_hover_dark,
        )
        self.assertNotIn(CYTOLONE_GREEN, primary_backgrounds)
        self.assertTrue(
            all(
                color in {CYTOLONE_GREEN_DARK, CYTOLONE_GREEN_HOVER}
                for color in primary_backgrounds
            )
        )
        self.assertEqual(
            primary_backgrounds,
            (
                CYTOLONE_GREEN_DARK,
                CYTOLONE_GREEN_DARK,
                CYTOLONE_GREEN_HOVER,
                CYTOLONE_GREEN_HOVER,
            ),
        )

        app = build_app()
        self.assertIs(app.theme, CYTOLONE_THEME)

    def test_run_launches_with_cytolone_theme(self):
        app = Mock()
        with patch("CYTOLONE.app.build_app", return_value=app):
            run_app()

        app.launch.assert_called_once()
        self.assertIs(app.launch.call_args.kwargs["theme"], CYTOLONE_THEME)

    def test_management_and_settings_pages_build_with_expected_controls(self):
        with gr.Blocks() as management:
            management_components = build_model_management_page()
        self.assertEqual(len(management_components), 5)
        change_events = [
            dependency
            for dependency in management.config["dependencies"]
            if any(event == "change" for _, event in dependency["targets"])
        ]
        self.assertEqual(len(change_events), 2)
        self.assertTrue(all(not event["inputs"] for event in change_events))
        self.assertEqual(
            {event["outputs"][0] for event in change_events},
            {management_components[3]._id, management_components[4]._id},
        )

        with gr.Blocks():
            settings_components, _, _ = build_settings_page()
        self.assertEqual(len(settings_components), 5)
        labels = {component.label for component in settings_components}
        self.assertNotIn("LLM_GEN", labels)
        for hidden_key in (
            "LLM_GEN_THRESHOLD",
            "LLM_MAX_TOKENS",
            "LLM_TEMPERATURE",
            "LLM_TOP_P",
            "LLM_TOP_K",
            "LLM_SEED",
        ):
            self.assertNotIn(hidden_key, labels)

    def test_download_and_delete_callbacks_return_refreshed_controls(self):
        with patch(
            "CYTOLONE.app.download_model_with_status",
            return_value=iter([("started", "summary before"), ("done", "summary after")]),
        ):
            download_updates = list(
                download_model_from_ui(
                    "application", "v1.1", False, "qwen3.5-9b-4bit"
                )
            )
        self.assertEqual(download_updates[-1][:2], ("done", "summary after"))
        self.assertEqual(len(download_updates[-1]), 6)

        with patch(
            "CYTOLONE.app.delete_model_with_status",
            return_value=("deleted", "summary after delete"),
        ) as delete_mock:
            delete_update = delete_model_from_ui(
                "llm", "qwen3.5-9b-4bit", True, "v1.1"
            )
        self.assertEqual(delete_update[:2], ("deleted", "summary after delete"))
        self.assertEqual(len(delete_update), 6)
        self.assertTrue(delete_mock.call_args.kwargs["release_callback"])


if __name__ == "__main__":
    unittest.main()
