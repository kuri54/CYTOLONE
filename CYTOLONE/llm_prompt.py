from dataclasses import dataclass

from CYTOLONE.label_caption import get_llm_diagnosis_label


@dataclass(frozen=True)
class SpecimenPromptProfile:
    key: str
    context: dict
    sections: dict


@dataclass(frozen=True)
class PromptV2:
    system: str
    user: str

    @property
    def messages(self):
        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": self.user},
        ]


SPECIMEN_PROMPT_PROFILES = {
    "cervix": SpecimenPromptProfile(
        key="cervix",
        context={
            "en": "cervical cytology",
            "ja": "子宮頸部細胞診",
        },
        sections={
            "en": (
                "1. Differential cytomorphologic findings",
                "2. Relevant clinical context",
                "3. Potentially useful additional tests",
            ),
            "ja": (
                "1. 細胞形態学的な鑑別所見",
                "2. 鑑別に関連する臨床情報",
                "3. 鑑別に役立つ可能性のある追加検査",
            ),
        },
    ),
}


def get_specimen_prompt_profile(specimen):
    try:
        return SPECIMEN_PROMPT_PROFILES[specimen]
    except KeyError as exc:
        raise ValueError(f"Unsupported specimen profile: {specimen}") from exc


def build_prompt_v2(specimen, language, label_top1, label_top2):
    """Build the product prompt without image data or classifier internals."""

    profile = get_specimen_prompt_profile(specimen)
    if language not in profile.context:
        raise ValueError(f"Unsupported prompt language: {language}")

    context = profile.context[language]
    sections = profile.sections[language]
    if language == "ja":
        system = f"""あなたはローカルで動作する細胞診支援アシスタントです。
あなたは細胞画像を見ていません。入力された分類結果だけを補助情報として扱い、最終診断を行わないでください。
対象は{context}です。画像で観察したかのような所見、患者情報、検査結果、数値、文献引用を作らないでください。
鑑別に役立つ一般的な細胞形態、関連する臨床情報、追加検査の候補だけを簡潔に述べてください。
出力言語は日本語に限定してください。次の3セクションをこの順番で使用し、各セクションは最大3項目にしてください。
{sections[0]}
{sections[1]}
{sections[2]}
情報が与えられていない場合は、推測せず「情報なし」と記載してください。"""
        user = f"""検体情報: {context}
分類器が出力した上位2つの診断候補（英語名）:
1. {get_llm_diagnosis_label(specimen, label_top1)}
2. {get_llm_diagnosis_label(specimen, label_top2)}"""
    else:
        system = f"""You are a local cytology support assistant.
You have not inspected the cell image. Treat the classifier labels only as support information and do not make a final diagnosis.
The specimen context is {context}. Do not invent image observations, patient facts, test results, numeric claims, or literature citations.
Discuss only concise general cytomorphologic distinctions, relevant clinical context, and potentially useful additional tests.
Respond only in English. Use exactly these three sections in this order, with at most three concise items per section.
{sections[0]}
{sections[1]}
{sections[2]}
If information was not provided, say "Not provided" rather than guessing."""
        user = f"""Specimen context: {context}
Top two diagnosis candidates (English names) from the classifier:
1. {get_llm_diagnosis_label(specimen, label_top1)}
2. {get_llm_diagnosis_label(specimen, label_top2)}"""

    return PromptV2(system=system, user=user)


def build_prompt_messages(specimen, language, label_top1, label_top2):
    return build_prompt_v2(specimen, language, label_top1, label_top2).messages
