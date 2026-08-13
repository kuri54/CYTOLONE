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
上位2候補は補助情報にすぎません。実際の細胞診、臨床所見、標準的な管理指針に依存する条件付きの一般論として述べ、分類器のラベルだけから侵襲的検査、処置、治療を自動的に勧めないでください。
出力言語は日本語に限定してください。次の3セクションをこの順番で使用してください。
{sections[0]}
{sections[1]}
{sections[2]}
第1セクションを最も詳しくし、4〜6個の箇条書きにしてください。各箇条書きは1〜2文とし、上位2候補それぞれの一般的な典型像を述べて直接比較してください。見ていない今回の画像にその所見があるとは断定しないでください。
N/C比、核サイズ・核輪郭、クロマチン、核小体・分裂像、細胞質、細胞配列・結合性、背景などから、この鑑別で特に関連性の高い比較軸を選んでください。すべての軸を機械的に列挙しないでください。
第2セクションと第3セクションはそれぞれ最大2個の箇条書きにし、鑑別への関連が高い内容だけを簡潔に述べてください。上限を埋めるために一般論や鑑別に直接寄与しない低優先度検査を追加せず、該当する高価値の情報がなければ「情報なし」としてください。追加検査は実際の細胞診・臨床所見と標準的な管理指針に基づく条件表現にしてください。"""
        user = f"""検体情報: {context}
分類器が出力した上位2つの診断候補（英語名）:
1. {get_llm_diagnosis_label(specimen, label_top1)}
2. {get_llm_diagnosis_label(specimen, label_top2)}"""
    else:
        system = f"""You are a local cytology support assistant.
You have not inspected the cell image. Treat the classifier labels only as support information and do not make a final diagnosis.
The specimen context is {context}. Do not invent image observations, patient facts, test results, numeric claims, or literature citations.
The top two candidates are support information only. Give conditional general guidance that depends on the actual cytology, clinical findings, and standard management guidance; do not automatically recommend invasive tests, procedures, or treatment from classifier labels alone.
Respond only in English. Use exactly these three sections in this order.
{sections[0]}
{sections[1]}
{sections[2]}
Make Section 1 the most detailed: write 4–6 bullet points, each 1–2 sentences. Describe the typical general pattern associated with each top candidate and directly compare them. Do not claim that either pattern is present in this unseen image.
Choose the comparison axes most relevant to this differential, such as N/C ratio; nuclear size and contour; chromatin; nucleoli or mitotic activity; cytoplasm; cell arrangement or cohesion; and background. Do not mechanically list every axis.
Keep Sections 2 and 3 concise, with at most 2 bullet points in each, and include only points highly relevant to the differential. Do not pad the limit with generalities or low-priority tests that do not directly contribute to the differential; if no high-value information is available, say "Not provided". Keep additional tests conditional on actual cytology, clinical findings, and standard management guidance."""
        user = f"""Specimen context: {context}
Top two diagnosis candidates (English names) from the classifier:
1. {get_llm_diagnosis_label(specimen, label_top1)}
2. {get_llm_diagnosis_label(specimen, label_top2)}"""

    return PromptV2(system=system, user=user)


def build_prompt_messages(specimen, language, label_top1, label_top2):
    return build_prompt_v2(specimen, language, label_top1, label_top2).messages
