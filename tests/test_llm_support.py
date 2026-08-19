import json
import sys
import tempfile
import threading
import types
import unittest
import warnings
from pathlib import Path
from unittest.mock import Mock, patch

import gradio as gr

from CYTOLONE.app import (
    _cytolone_blocks,
    build_app,
    build_model_management_page,
    build_settings_page,
    CONCISE_GENERATION_BUTTON_LABELS,
    apply_settings_and_refresh_main,
    delete_application_model_from_ui,
    delete_model_from_ui,
    delete_llm_model_from_ui,
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
from CYTOLONE.llm_prompt import build_concise_prompt_v2, build_prompt_v2
from CYTOLONE.llm_runtime import (
    LLMRuntimeError,
    LocalLLMRuntime,
    MissingLLMModelError,
    _set_mlx_vlm_thread_local_stream,
)
from CYTOLONE.model import (
    LLM_MODEL_CHOICES,
    LLM_MODEL_REGISTRY,
    LLM_MODEL_DISPLAY_CHOICES,
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
    def test_registry_and_choices_contain_only_the_public_llm_roster(self):
        expected_keys = [
            "qwen3.5-27b-5bit",
            "gpt-oss-120b",
            "gpt-oss-20b",
        ]
        self.assertEqual(list(LLM_MODEL_REGISTRY), expected_keys)
        self.assertEqual(LLM_MODEL_CHOICES, expected_keys)
        self.assertEqual(
            [key for _, key in LLM_MODEL_DISPLAY_CHOICES],
            expected_keys,
        )
        self.assertEqual(
            LLM_MODEL_DISPLAY_CHOICES[0],
            ("Qwen3.5 27B (5-bit)", "qwen3.5-27b-5bit"),
        )
        self.assertEqual(get_llm_spec("qwen3.5-27b-5bit").tier, "Recommended")
        self.assertEqual(get_llm_spec("qwen3.5-27b-5bit").runtime, "mlx-vlm")
        self.assertEqual(get_llm_spec("qwen3.5-27b-5bit").generation_defaults.max_tokens, 512)
        self.assertFalse(get_llm_spec("qwen3.5-27b-5bit").generation_defaults.enable_thinking)
        self.assertEqual(
            get_llm_spec("qwen3.5-27b-5bit").memory_recommendation,
            "64 GB or more",
        )
        self.assertEqual(get_llm_spec("gpt-oss-120b").runtime, "mlx-lm")
        self.assertTrue(get_llm_spec("gpt-oss-120b").legacy)

        self.assertEqual(get_llm_spec("gpt-oss-20b").runtime, "mlx-lm")
        self.assertTrue(get_llm_spec("gpt-oss-20b").legacy)
        self.assertEqual(get_llm_spec("gpt-oss-20b").download_size, "12.1 GB")
        self.assertEqual(
            get_llm_spec("gpt-oss-20b").memory_recommendation,
            "64 GB or more",
        )

    def test_model_management_summary_lists_only_public_llm_roster(self):
        with tempfile.TemporaryDirectory() as temporary:
            summary = model_management_summary(
                {"MODEL": "v1.1", "LLM_MODEL": "qwen3.5-27b-5bit"},
                Path(temporary),
            )

        for key in LLM_MODEL_CHOICES:
            self.assertIn(f"`{key}`", summary)
        self.assertIn("| 12.1 GB | 64 GB or more |", summary)
        for removed_key in (
            "qwen3.5-9b-4bit",
            "qwen3.5-9b-8bit",
            "qwen3.5-27b-8bit",
            "qwen3.8-27b-4bit",
            "qwen3.8-27b-8bit",
            "deepseek-r1",
        ):
            self.assertNotIn(removed_key, summary)

    def test_download_targets_include_selected_llm_when_generation_is_disabled(self):
        targets = get_download_targets(
            {
                "MODEL": "v1.1",
                "LLM_MODEL": "qwen3.5-27b-5bit",
                "LLM_GEN": False,
            }
        )
        self.assertEqual(len(targets), 2)
        self.assertIn("mlx-community/Qwen3.5-27B-5bit", targets)


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
        self.assertIn("write exactly 4 bullets, one sentence and one line each", english)
        self.assertIn("directly compare both candidates in the same sentence", english)
        self.assertIn("rather than listing candidates separately", english)
        self.assertIn("typical general patterns", english)
        self.assertIn("N/C ratio", english)
        self.assertIn("Keep Section 2 to at most 1 short, one-sentence bullet", english)
        self.assertIn("Keep Section 3 to at most 1 short, one-sentence bullet", english)
        self.assertIn("Clinical information to confirm for the differential", english)
        self.assertIn(
            "Missing case-specific patient information does not mean that no relevant clinical factor exists",
            english,
        )
        self.assertIn(
            "state it as a conditional item to confirm even when it was not provided",
            english,
        )
        self.assertIn(
            'Say "Not provided" only when no highly relevant clinical item needs confirmation',
            english,
        )
        self.assertIn("actual cytology, clinical findings, and standard management guidance", english)
        self.assertIn("do not automatically recommend invasive tests, procedures, or treatment", english)
        self.assertIn("multiple recognized morphological patterns or overlap", english)
        self.assertIn("across each comparison axis", english)
        self.assertNotIn("serum hormone measurement", english)

        self.assertIn("箇条書きは全体で最大6個", japanese)
        self.assertIn("結論の反復や追加の要約は書かない", japanese)
        self.assertIn("第1セクションを最も詳しく", japanese)
        self.assertIn("箇条書きはちょうど4個、各1文・1行", japanese)
        self.assertIn("2候補を同じ文で直接比較", japanese)
        self.assertIn("候補ごとに別々に列挙せず", japanese)
        self.assertIn("N/C比", japanese)
        self.assertIn("第2セクションは最大1個の短い箇条書き（1文）", japanese)
        self.assertIn("第3セクションも最大1個の短い箇条書き（1文）", japanese)
        self.assertIn("鑑別のために確認すべき臨床情報", japanese)
        self.assertIn("症例固有の患者情報が未入力であることは", japanese)
        self.assertIn("未提供でも「確認すべき項目」として条件付き", japanese)
        self.assertIn("本当にない場合だけ「情報なし」", japanese)
        self.assertIn("実際の細胞診・臨床所見と標準的な管理指針", japanese)
        self.assertIn("侵襲的検査、処置、治療を自動的に勧めない", japanese)
        self.assertIn("複数の既知形態パターンや重なり", japanese)
        self.assertIn("各比較軸で反映", japanese)
        self.assertNotIn("血清ホルモン測定", japanese)

    def test_detailed_prompt_has_no_diagnosis_specific_clinical_rules(self):
        for language in ("en", "ja"):
            system = build_prompt_v2(
                "cervix", language, "Atrophy", "Adeno_carcinoma"
            ).system
            for forbidden in ("Atrophy", "Adenocarcinoma", "menopause", "年齢", "閉経"):
                self.assertNotIn(forbidden, system)
            self.assertNotRegex(system, r"\bage\b")

    def test_concise_prompt_is_morphology_only_and_symmetric(self):
        english = build_concise_prompt_v2(
            "cervix",
            "en",
            "Mild_dysplasia",
            "Atrophy",
        )
        japanese = build_concise_prompt_v2(
            "cervix",
            "ja",
            "Mild_dysplasia",
            "Atrophy",
        )

        self.assertIn("exactly 4 short Markdown bullet points", english.system)
        self.assertIn('start exactly with "- "', english.system)
        self.assertIn("one sentence and one line per bullet", english.system)
        self.assertIn("same quality, comparison-axis, and morphological variation/overlap contract", english.system)
        self.assertIn("stop immediately after the 4 bullets", english.system)
        self.assertIn("morphology-based differential findings", english.system)
        self.assertIn("direct comparison of both candidates", english.system)
        self.assertIn("Do not output headings, clinical information, additional tests, management, procedures, treatment, a conclusion, or a summary", english.system)
        self.assertNotIn("at most 2 bullet points total", english.system)
        self.assertIn("have not inspected the cell image", english.system)
        self.assertIn("do not make a final diagnosis", english.system)
        self.assertNotIn("0.45", english.user)
        self.assertNotIn("question", english.user.lower())
        self.assertNotIn("probabilit", english.system.lower())
        self.assertNotIn("question", english.system.lower())

        self.assertIn("箇条書きはちょうど4個", japanese.system)
        self.assertIn("必ず半角ハイフン+半角スペースの「- 」で開始", japanese.system)
        self.assertIn("詳細版の第1セクションと同じ品質", japanese.system)
        self.assertIn("4個の箇条書きを出したら直ちに停止", japanese.system)
        self.assertIn("細胞形態学的な鑑別所見だけ", japanese.system)
        self.assertIn("2候補の直接比較", japanese.system)
        self.assertIn("見出し、臨床情報、追加検査、管理、処置、治療、結論、要約は絶対に書かない", japanese.system)
        self.assertNotIn("最大2個", japanese.system)
        self.assertIn("細胞画像を見ていません", japanese.system)
        self.assertIn("最終診断を行わない", japanese.system)
        self.assertNotIn("0.45", japanese.user)
        self.assertNotIn("質問", japanese.user)
        self.assertNotIn("確率", japanese.system)
        self.assertNotIn("質問", japanese.system)

    def test_prompt_uses_only_normalized_labels_without_question_or_probability(self):
        prompt = build_prompt_v2(
            "cervix",
            "en",
            "Mild_dysplasia",
            "Atrophy",
        )
        self.assertIn("Mild dysplasia", prompt.user)
        self.assertIn("Atrophy", prompt.user)
        self.assertNotIn("0.45", prompt.user)
        self.assertNotIn("probability", prompt.user.lower())
        self.assertNotIn("Which differential findings should be reviewed?", prompt.user)
        self.assertNotIn("image data", prompt.user.lower())

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

    def test_readmes_describe_both_generation_routes_and_label_boundary(self):
        english = Path("README.md").read_text(encoding="utf-8")
        japanese = Path("README_JA.md").read_text(encoding="utf-8")
        expected_model_keys = [
            "qwen3.5-27b-5bit",
            "gpt-oss-120b",
            "gpt-oss-20b",
        ]
        removed_model_keys = (
            "qwen3.5-9b-4bit",
            "qwen3.5-9b-8bit",
            "qwen3.5-27b-8bit",
            "qwen3.8-27b-4bit",
            "qwen3.8-27b-8bit",
            "deepseek-r1",
        )
        for content in (english, japanese):
            model_keys = [
                line.split("`")[1]
                for line in content.splitlines()
                if line.startswith("| `")
            ]
            self.assertEqual(model_keys, expected_model_keys)
            for removed_key in removed_model_keys:
                self.assertNotIn(removed_key, content)

        self.assertIn("Concise differential findings", english)
        self.assertIn("four morphology-only comparison points", english)
        self.assertIn("Detailed differential findings", english)
        self.assertIn("clinical information to confirm for the differential", english)
        self.assertIn("potentially useful additional tests", english)
        self.assertIn("Both modes pass no image to the LLM.", english)
        self.assertIn("top two normalized", english)
        self.assertIn("support information and are not final diagnoses.", english)
        self.assertIn("Unified-memory guidance", english)
        self.assertIn(
            "`gpt-oss-20b` (Legacy compatibility) | `mlx-community/gpt-oss-20b-MXFP4-Q8` | 12.1 GB | 64 GB or more",
            english,
        )

        self.assertIn("簡潔な鑑別所見", japanese)
        self.assertIn("細胞形態学的な鑑別所見のみを4項目", japanese)
        self.assertIn("詳細な鑑別所見", japanese)
        self.assertIn("確認すべき臨床情報", japanese)
        self.assertIn("役立つ可能性のある追加検査", japanese)
        self.assertIn("LLMへ画像を渡さず", japanese)
        self.assertIn("上位2つの正規化済み判定ラベルだけ", japanese)
        self.assertIn("最終診断ではありません", japanese)
        self.assertIn("ユニファイドメモリ目安", japanese)
        self.assertIn(
            "`gpt-oss-20b`（Legacy互換） | `mlx-community/gpt-oss-20b-MXFP4-Q8` | 12.1 GB | 64 GB以上",
            japanese,
        )


class SettingsCompatibilityTests(unittest.TestCase):
    def test_new_default_recommends_qwen35_27b_5bit(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            "os.environ", {"CYTOLONE_DATA_ROOT": temporary}
        ):
            config = read_config()
        self.assertEqual(config["SETTINGS"]["LLM_MODEL"], "qwen3.5-27b-5bit")

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

    def test_removed_or_unknown_llm_config_falls_back_and_preserves_settings(self):
        for old_llm_model in ("qwen3.8-27b-4bit", "unknown-local-model"):
            with tempfile.TemporaryDirectory() as temporary:
                old_path = Path(temporary) / "config.ini"
                old_path.write_text(
                    "[SETTINGS]\n"
                    "LANGUAGE = ja\n"
                    "MODEL = v1.0\n"
                    f"LLM_MODEL = {old_llm_model}\n"
                    "LLM_GEN = True\n"
                    "LLM_GEN_THRESHOLD = 0.4\n"
                    "WEBCAM_IMAGE_SIZE = 900\n"
                    "DEBUG = True\n",
                    encoding="utf-8",
                )

                settings = read_config(old_path)["SETTINGS"]

            self.assertEqual(settings["LLM_MODEL"], "qwen3.5-27b-5bit")
            self.assertEqual(settings["LANGUAGE"], "ja")
            self.assertEqual(settings["MODEL"], "v1.0")
            self.assertEqual(settings["LLM_GEN_THRESHOLD"], "0.4")
            self.assertEqual(settings["WEBCAM_IMAGE_SIZE"], "900")
            self.assertEqual(settings["DEBUG"], "True")

    def test_settings_dropdown_uses_fallback_for_removed_config_model(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            "os.environ", {"CYTOLONE_DATA_ROOT": temporary}
        ):
            config = read_config()
            config["SETTINGS"]["LLM_MODEL"] = "qwen3.8-27b-4bit"
            write_config(config)
            with gr.Blocks():
                settings_components, _, _ = build_settings_page()

        self.assertEqual(settings_components[2].value, "qwen3.5-27b-5bit")
        self.assertEqual(settings_components[2].choices, LLM_MODEL_DISPLAY_CHOICES)

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
                        "qwen3.5-27b-5bit",
                        0,
                        False,
                    )
                self.assertEqual(Path(temporary, "config.ini").read_text(encoding="utf-8"), before)

    def test_valid_settings_bounds_are_explicit(self):
        values = validate_settings(
            "en",
            "v1.1",
            "qwen3.5-27b-5bit",
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
                    "ja", "v1.0", "qwen3.5-27b-5bit", 900, True
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

    def test_normal_settings_callback_persists_selected_llm_model(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            "os.environ", {"CYTOLONE_DATA_ROOT": temporary}
        ):
            config = read_config()
            config["SETTINGS"]["LLM_MODEL"] = "qwen3.5-27b-5bit"
            write_config(config)
            result = apply_settings_and_refresh_main(
                "ja", "v1.0", "qwen3.5-27b-5bit", 900, True
            )
            after = read_config()["SETTINGS"]

        self.assertEqual(after["LLM_MODEL"], "qwen3.5-27b-5bit")
        self.assertEqual(len(result), 16)
        summary = result[7]
        llm_row = next(
            row for row in summary.to_dict("records") if row["Item"] == "LLM Model"
        )
        self.assertEqual(llm_row["Value"], "Qwen3.5 27B (5-bit)")

    def test_normal_settings_values_and_main_summary_are_concise(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict("os.environ", {"CYTOLONE_DATA_ROOT": temporary}):
                values = get_settings_values()
            frame = build_config_df(
                {
                    "LANGUAGE": "en",
                    "MODEL": "v1.1",
                    "LLM_MODEL": "qwen3.5-27b-5bit",
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
            self.assertIn(values[2], LLM_MODEL_REGISTRY)
            self.assertEqual(len(frame), 4)
            llm_row = next(
                row for row in frame.to_dict("records") if row["Item"] == "LLM Model"
            )
            self.assertEqual(llm_row["Section"], "Model")
            self.assertEqual(llm_row["Value"], "Qwen3.5 27B (5-bit)")
            self.assertNotIn("Generate", set(frame["Item"]))
            self.assertNotIn("Threshold", set(frame["Item"]))
            self.assertNotIn("Temperature", set(frame["Item"]))

    def test_main_summary_uses_registry_display_names_for_qwen_and_legacy(self):
        base_config = {
            "LANGUAGE": "en",
            "MODEL": "v1.1",
            "WEBCAM_IMAGE_SIZE": 1024,
        }
        for key, display_name in (
            ("qwen3.5-27b-5bit", "Qwen3.5 27B (5-bit)"),
            ("gpt-oss-120b", "GPT-OSS 120B (Legacy)"),
        ):
            frame = build_config_df({**base_config, "LLM_MODEL": key})
            llm_row = next(
                row for row in frame.to_dict("records") if row["Item"] == "LLM Model"
            )
            self.assertEqual(llm_row["Section"], "Model")
            self.assertEqual(llm_row["Value"], display_name)
            self.assertNotIn(key, llm_row["Value"])
            self.assertFalse(
                set(
                    [
                        "LLM_GEN",
                        "LLM_GEN_THRESHOLD",
                        "LLM_TEMPERATURE",
                        "LLM_TOP_P",
                        "LLM_TOP_K",
                        "LLM_SEED",
                    ]
                )
                & set(frame["Item"])
            )

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

    def test_cli_accepts_gpt_oss_20b_registry_choice(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict("os.environ", {"CYTOLONE_DATA_ROOT": temporary}):
                config = read_config()
                write_config(config)
                with patch.object(
                    sys,
                    "argv",
                    ["cytolone-config", "--LLM_MODEL", "gpt-oss-20b"],
                ):
                    config_main()

                self.assertEqual(
                    read_config()["SETTINGS"]["LLM_MODEL"], "gpt-oss-20b"
                )

    def test_cli_rejects_removed_llm_choice_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict("os.environ", {"CYTOLONE_DATA_ROOT": temporary}):
                config = read_config()
                write_config(config)
                config_path = Path(temporary, "config.ini")
                before = config_path.read_text(encoding="utf-8")

                with patch.object(
                    sys,
                    "argv",
                    ["cytolone-config", "--LLM_MODEL", "qwen3.8-27b-4bit"],
                ):
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
            "LLM_MODEL": "qwen3.5-27b-5bit",
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

    def test_reset_clears_results_and_prepares_both_language_specific_buttons(self):
        for language in ("ja", "en"):
            (
                label,
                label_probs,
                guidance,
                concise_button,
                detailed_button,
                comment,
                capture,
            ) = reset_analysis_outputs(language)
            self.assertIsNone(label["value"])
            self.assertEqual(label_probs, {})
            self.assertEqual(guidance["value"], "")
            self.assertFalse(guidance["visible"])
            self.assertEqual(
                concise_button["value"], CONCISE_GENERATION_BUTTON_LABELS[language]
            )
            self.assertEqual(
                detailed_button["value"], MANUAL_GENERATION_BUTTON_LABELS[language]
            )
            for button in (concise_button, detailed_button):
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
            guidance, concise_button, detailed_button = show_manual_generation_with_current_config(
                question, labels, "cervix"
            )

        self.assertTrue(guidance["visible"])
        self.assertEqual(guidance["value"], MANUAL_GENERATION_GUIDANCE["ja"])
        self.assertTrue(concise_button["visible"])
        self.assertTrue(detailed_button["visible"])
        self.assertTrue(concise_button["interactive"])
        self.assertTrue(detailed_button["interactive"])
        self.assertEqual(
            concise_button["value"], CONCISE_GENERATION_BUTTON_LABELS["ja"]
        )
        self.assertEqual(
            detailed_button["value"], MANUAL_GENERATION_BUTTON_LABELS["ja"]
        )

    def test_manual_offer_is_hidden_for_non_diagnosis_or_non_close_results(self):
        config = self._config()
        with patch(
            "CYTOLONE.app.get_main_context",
            return_value=(config, self.QUESTION_MAP, [], self.ORDER),
        ):
            guidance, concise_button, detailed_button = show_manual_generation_with_current_config(
                self.QUESTION, {"Atrophy": 0.8, "Mild_dysplasia": 0.1}, "cervix"
            )
        self.assertFalse(guidance["visible"])
        self.assertFalse(concise_button["visible"])
        self.assertFalse(detailed_button["visible"])
        self.assertTrue(concise_button["interactive"])
        self.assertTrue(detailed_button["interactive"])

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
            guidance, concise_button, detailed_button = show_manual_generation_with_current_config(
                full_question, {"Atrophy": 0.45, "Mild_dysplasia": 0.40}, "cervix"
            )
        self.assertFalse(guidance["visible"])
        self.assertFalse(concise_button["visible"])
        self.assertFalse(detailed_button["visible"])
        self.assertTrue(concise_button["interactive"])
        self.assertTrue(detailed_button["interactive"])

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
        self.assertNotIn(self.QUESTION, messages[1]["content"])
        self.assertNotIn("0.45", messages[1]["content"])

    def test_concise_manual_generation_uses_384_token_hidden_budget(self):
        config = self._config(llm_gen=False)
        labels = {"Atrophy": 0.45, "Mild_dysplasia": 0.40}
        with patch(
            "CYTOLONE.app.llm_runtime.generate", return_value="generated findings"
        ) as generate_mock:
            output = generate_comments(
                self.QUESTION, labels, "cervix", config, mode="concise"
            )

        self.assertEqual(output, "generated findings")
        self.assertEqual(
            generate_mock.call_args.kwargs["settings"]["LLM_MAX_TOKENS"], 384
        )
        self.assertIn(
            "morphology-based differential findings",
            generate_mock.call_args.kwargs["messages"][0]["content"],
        )

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
        active_language = read_config()["SETTINGS"]["LANGUAGE"]
        concise_button_id = component_id(
            lambda item: item["type"] == "button"
            and item["props"].get("value")
            == CONCISE_GENERATION_BUTTON_LABELS[active_language]
        )
        detailed_button_id = component_id(
            lambda item: item["type"] == "button"
            and item["props"].get("value")
            == MANUAL_GENERATION_BUTTON_LABELS[active_language]
        )
        for button_id in (concise_button_id, detailed_button_id):
            button_component = next(
                item for item in components if item["id"] == button_id
            )
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
            concise_button_id,
            detailed_button_id,
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
            and dependency["outputs"]
            == [guidance_id, concise_button_id, detailed_button_id]
        ]
        self.assertEqual(len(condition_events), 1)

        manual_events = [
            dependency
            for dependency in dependencies
            if dependency["targets"]
            in [[(concise_button_id, "click")], [(detailed_button_id, "click")]]
            and dependency["inputs"] == [question_id, label_probs_state_id]
            and dependency["outputs"] == [comment_id]
        ]
        self.assertEqual(len(manual_events), 2)
        self.assertTrue(all(not event.get("js") for event in manual_events))
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

    def test_mlx_vlm_06_stream_replacement_updates_split_generation_modules(self):
        old_stream = object()
        stream = object()
        generation_module = types.SimpleNamespace(generation_stream=old_stream)
        split_modules = {
            name: types.SimpleNamespace(generation_stream=old_stream)
            for name in (
                "mlx_vlm.generate.common",
                "mlx_vlm.generate.ar",
                "mlx_vlm.generate.dispatch",
                "mlx_vlm.generate.diffusion",
            )
        }
        mlx_core = types.SimpleNamespace(
            default_device=Mock(return_value="gpu device"),
            new_thread_local_stream=Mock(return_value=stream),
        )

        def import_module(name):
            return {
                "mlx_vlm.generate": generation_module,
                "mlx.core": mlx_core,
            }[name]

        with patch(
            "CYTOLONE.llm_runtime.importlib.import_module",
            side_effect=import_module,
        ), patch.dict(
            sys.modules,
            {"mlx_vlm.generate": generation_module, **split_modules},
        ):
            self.assertIs(_set_mlx_vlm_thread_local_stream(), stream)

        self.assertIs(generation_module.generation_stream, stream)
        for module in split_modules.values():
            self.assertIs(module.generation_stream, stream)

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
                    "qwen3.5-27b-5bit",
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
                runtime.generate("qwen3.5-27b-5bit", qwen_path, [])
                self.assertEqual(runtime.active_model_key, "qwen3.5-27b-5bit")
                runtime.generate("qwen3.5-27b-5bit", qwen_path, [])
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
            runtime._active_model_key = "qwen3.5-27b-5bit"
            runtime._model = object()
            runtime._processor = Mock()
            runtime._generate = generate_text
            model_path = Path(temporary) / "qwen"

            def run_first_worker():
                outputs.append(runtime.generate("qwen3.5-27b-5bit", model_path, []))

            def run_second_worker():
                second_call_started.set()
                outputs.append(runtime.generate("qwen3.5-27b-5bit", model_path, []))
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
                        "qwen3.5-27b-5bit", model_path, []
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
                    "qwen3.5-27b-5bit",
                    Path(temporary) / "missing",
                    [],
                )
            self.assertIn("Model Management", str(context.exception))


class DownloadIntegrityTests(unittest.TestCase):
    def test_download_models_loads_config_when_omitted(self):
        config = {
            "MODEL": "v1.1",
            "LLM_MODEL": "qwen3.5-27b-5bit",
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
                ["kuri54/mlx-CYTOLONE-v1.1", "mlx-community/Qwen3.5-27B-5bit"],
            )

    def test_download_cli_defaults_to_only_application_model(self):
        config = {
            "MODEL": "v1.1",
            "LLM_MODEL": "qwen3.5-27b-5bit",
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
            "LLM_MODEL": "qwen3.5-27b-5bit",
        }
        with patch.object(sys, "argv", ["download-model", "llm", "--force"]), patch(
            "CYTOLONE.download_models.load_config", return_value=config
        ), patch(
            "CYTOLONE.download_models.download_registered_model"
        ) as download:
            download_main()

        download.assert_called_once_with("llm", "qwen3.5-27b-5bit", force=True)

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
            "LLM_MODEL": "qwen3.5-27b-5bit",
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
            "LLM_MODEL": "qwen3.5-27b-5bit",
                "LLM_GEN": False,
            }
            output_root = Path(temporary)
            before = model_download_summary(config, output_root)
            self.assertIn("Qwen3.5 27B (5-bit)", before)
            self.assertIn("| yes | not installed | — | 19.4 GB | 64 GB or more |", before)

            make_model_directory(output_root / "mlx-community" / "Qwen3.5-27B-5bit")
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
            target = root / "mlx-community" / "Qwen3.5-27B-5bit"
            target.mkdir(parents=True)
            (target / "config.json").write_text("{}", encoding="utf-8")
            (target / "tokenizer.json").write_text("{}", encoding="utf-8")
            (target / "model-00001-of-00002.safetensors").write_bytes(b"partial")
            released = Mock()

            with patch("CYTOLONE.download_models.models_path", return_value=root):
                deleted = delete_registered_model(
                    "llm",
                    "qwen3.5-27b-5bit",
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
            target = root / "mlx-community" / "Qwen3.5-27B-5bit"
            target.mkdir(parents=True)
            (target / "partial.safetensors").write_bytes(b"x" * 2048)
            summary = model_management_summary(
                {
                    "MODEL": "v1.1",
                    "LLM_MODEL": "qwen3.5-27b-5bit",
                },
                root,
            )
            self.assertIn("| incomplete | 2.0 KB | 19.4 GB |", summary)
            self.assertIn("| Unified memory guidance |", summary)

    def test_individual_download_refreshes_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = {
                "MODEL": "v1.1",
                    "LLM_MODEL": "qwen3.5-27b-5bit",
                "LLM_GEN": False,
            }

            def install(role, key, base_output_dir, force=False):
                make_model_directory(
                    Path(base_output_dir) / "mlx-community" / "Qwen3.5-27B-5bit"
                )

            with patch("CYTOLONE.download_models.load_config", return_value=config), patch(
                "CYTOLONE.download_models.models_path", return_value=root
            ), patch(
                "CYTOLONE.download_models.download_registered_model",
                side_effect=install,
            ):
                updates = list(
                    download_model_with_status("llm", "qwen3.5-27b-5bit")
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

    def test_blocks_constructor_does_not_emit_gradio_theme_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            app = _cytolone_blocks()

        self.assertIs(app.theme, CYTOLONE_THEME)
        self.assertFalse(
            any(
                "theme" in str(item.message).lower()
                and "blocks constructor" in str(item.message).lower()
                for item in caught
            )
        )

    def test_run_launches_with_cytolone_theme(self):
        app = Mock()
        with patch("CYTOLONE.app.build_app", return_value=app):
            run_app()

        app.launch.assert_called_once()
        self.assertIs(app.launch.call_args.kwargs["theme"], CYTOLONE_THEME)

    def test_management_and_settings_pages_build_with_expected_controls(self):
        with gr.Blocks() as management:
            management_components = build_model_management_page()
        self.assertEqual(len(management_components), 4)
        shared_confirm = management_components[3]
        change_events = [
            dependency
            for dependency in management.config["dependencies"]
            if any(event == "change" for _, event in dependency["targets"])
        ]
        self.assertEqual(len(change_events), 2)
        self.assertTrue(all(not event["inputs"] for event in change_events))
        self.assertEqual(
            {event["outputs"][0] for event in change_events},
            {shared_confirm._id},
        )
        confirmation_components = [
            item
            for item in management.config["components"]
            if item["type"] == "checkbox"
            and item["props"].get("label")
            == "Confirm deletion of the selected model"
        ]
        self.assertEqual(
            len(confirmation_components),
            1,
        )
        self.assertEqual(confirmation_components[0]["id"], shared_confirm._id)
        delete_events = [
            dependency
            for dependency in management.config["dependencies"]
            if any(event == "click" for _, event in dependency["targets"])
            and dependency["outputs"][-1] == shared_confirm._id
        ]
        self.assertEqual(len(delete_events), 4)
        app_delete_event = next(
            event
            for event in delete_events
            if event["inputs"]
            == [
                management_components[1]._id,
                shared_confirm._id,
                management_components[2]._id,
            ]
        )
        llm_delete_event = next(
            event
            for event in delete_events
            if event["inputs"]
            == [
                management_components[2]._id,
                shared_confirm._id,
                management_components[1]._id,
            ]
        )
        self.assertIsNotNone(app_delete_event)
        self.assertIsNotNone(llm_delete_event)

        with gr.Blocks():
            settings_components, _, _ = build_settings_page()
        self.assertEqual(len(settings_components), 5)
        labels = {component.label for component in settings_components}
        self.assertNotIn("LLM_GEN", labels)
        self.assertIn("LLM_MODEL", labels)
        self.assertEqual(settings_components[2].choices, LLM_MODEL_DISPLAY_CHOICES)
        self.assertIn(
            ("Qwen3.5 27B (5-bit)", "qwen3.5-27b-5bit"),
            settings_components[2].choices,
        )
        self.assertIn(
            ("GPT-OSS 120B (Legacy)", "gpt-oss-120b"),
            settings_components[2].choices,
        )
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
                    "application", "v1.1", False, "qwen3.5-27b-5bit"
                )
            )
        self.assertEqual(download_updates[-1][:2], ("done", "summary after"))
        self.assertEqual(len(download_updates[-1]), 5)

        with patch(
            "CYTOLONE.app.delete_model_with_status",
            return_value=("deleted", "summary after delete"),
        ) as delete_mock:
            delete_update = delete_model_from_ui(
            "llm", "qwen3.5-27b-5bit", True, "v1.1"
            )
        self.assertEqual(delete_update[:2], ("deleted", "summary after delete"))
        self.assertEqual(len(delete_update), 5)
        self.assertTrue(delete_mock.call_args.kwargs["release_callback"])

        with patch(
            "CYTOLONE.app.delete_model_with_status",
            return_value=("application deleted", "application summary"),
        ) as app_delete_mock:
            delete_application_model_from_ui("v1.1", True, "qwen3.5-27b-5bit")
        self.assertEqual(
            app_delete_mock.call_args.args[:3], ("application", "v1.1", True)
        )

        with patch(
            "CYTOLONE.app.delete_model_with_status",
            return_value=("llm deleted", "llm summary"),
        ) as llm_delete_mock:
            delete_llm_model_from_ui("qwen3.5-27b-5bit", True, "v1.1")
        self.assertEqual(
            llm_delete_mock.call_args.args[:3], ("llm", "qwen3.5-27b-5bit", True)
        )


if __name__ == "__main__":
    unittest.main()
