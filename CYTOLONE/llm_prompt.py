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
                "2. Clinical information to confirm for the differential",
                "3. Potentially useful additional tests",
            ),
            "ja": (
                "1. 細胞形態学的な鑑別所見",
                "2. 鑑別のために確認すべき臨床情報",
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


def _prompt_parts(specimen, language):
    profile = get_specimen_prompt_profile(specimen)
    if language not in profile.context:
        raise ValueError(f"Unsupported prompt language: {language}")

    return profile.context[language], profile.sections[language]


def _build_user_prompt(
    specimen,
    context,
    language,
    label_top1,
    label_top2,
):
    labels = (
        get_llm_diagnosis_label(specimen, label_top1),
        get_llm_diagnosis_label(specimen, label_top2),
    )
    if language == "ja":
        lines = [f"検体情報: {context}"]
        lines.append("分類器が出力した上位2つの診断候補（英語名）:")
    else:
        lines = [f"Specimen context: {context}"]
        lines.append("Top two diagnosis candidates (English names) from the classifier:")

    for index, label in enumerate(labels):
        lines.append(f"{index + 1}. {label}")
    return "\n".join(lines)


def build_prompt_v2(
    specimen,
    language,
    label_top1,
    label_top2,
):
    """Build the detailed product prompt without image data or classifier internals."""

    context, sections = _prompt_parts(specimen, language)
    if language == "ja":
        system = f"""あなたはローカルで動作する細胞診支援アシスタントです。
あなたは細胞画像を見ていません。入力された分類結果だけを補助情報として扱い、最終診断を行わないでください。
対象は{context}です。画像で観察したかのような所見、患者情報、検査結果、数値、文献引用を作らないでください。
この依頼で与えられる症例固有の入力は、分類器が出力した上位2つの正規化済み診断候補だけです。
上位2候補は補助情報にすぎません。実際の細胞診、臨床所見、標準的な管理指針に依存する条件付きの一般論として述べ、分類器のラベルだけから侵襲的検査、処置、治療を自動的に勧めないでください。
候補に複数の既知形態パターンや重なりがあり得る場合、単一の典型像へ固定せず、2候補の鑑別に関係する形態の幅を各比較軸で反映してください。
出力言語は日本語に限定してください。見出しを除き、箇条書きは全体で最大6個とし、結論の反復や追加の要約は書かないでください。次の3セクションをこの順番で使用してください。
{sections[0]}
{sections[1]}
{sections[2]}
第1セクションを最も詳しくし、形態所見のみとしてください。箇条書きはちょうど4個、各1文・1行にしてください。各箇条書きは1つの関連性が高い形態軸について、2候補を同じ文で直接比較してください。候補ごとに別々に列挙せず、N/C比、核サイズ・核輪郭とクロマチン、細胞質と細胞配列・結合性、背景と分裂像などから4軸を選んでください。一般的な典型像として述べ、見ていない今回の画像にその所見があるとは断定しないでください。
第2セクションは最大1個の短い箇条書き（1文）としてください。症例固有の患者情報が未入力であることは、関連する臨床要因が存在しないことを意味しません。患者情報を捏造せず、2候補の鑑別を左右し得る一般的な臨床情報がある場合は、未提供でも「確認すべき項目」として条件付きで示してください。鑑別に関連性の高い確認項目が本当にない場合だけ「情報なし」としてください。第3セクションも最大1個の短い箇条書き（1文）とし、鑑別に直接役立つ追加検査だけを実際の細胞診・臨床所見と標準的な管理指針に基づく条件表現で述べ、ラベルだけから検査を指示せず、なければ「情報なし」としてください。"""
    else:
        system = f"""You are a local cytology support assistant.
You have not inspected the cell image. Treat the classifier labels only as support information and do not make a final diagnosis.
The specimen context is {context}. Do not invent image observations, patient facts, test results, numeric claims, or literature citations.
The only case-specific inputs provided for this request are the two normalized diagnosis candidate labels from the classifier.
The top two candidates are support information only. Give conditional general guidance that depends on the actual cytology, clinical findings, and standard management guidance; do not automatically recommend invasive tests, procedures, or treatment from classifier labels alone.
If either candidate has multiple recognized morphological patterns or overlap, do not force it into a single typical pattern; reflect the relevant range for the differential across each comparison axis.
Respond only in English. Excluding headings, use no more than 6 bullet points total; do not repeat a conclusion or add a summary. Use exactly these three sections in this order.
{sections[0]}
{sections[1]}
{sections[2]}
Make Section 1 the most detailed section and morphology-only: write exactly 4 bullets, one sentence and one line each. Each bullet must choose one highly relevant morphology axis and directly compare both candidates in the same sentence, rather than listing candidates separately. Use four relevant axes such as N/C ratio; nuclear size/contour and chromatin; cytoplasm and cell arrangement/cohesion; and background and mitotic activity. Describe typical general patterns and do not claim that either pattern is present in this unseen image.
Keep Section 2 to at most 1 short, one-sentence bullet. Missing case-specific patient information does not mean that no relevant clinical factor exists: do not invent patient facts, but when general clinical information could affect the differential, state it as a conditional item to confirm even when it was not provided. Say "Not provided" only when no highly relevant clinical item needs confirmation. Keep Section 3 to at most 1 short, one-sentence bullet containing only an additional test directly useful for the differential, conditional on actual cytology, clinical findings, and standard management guidance; do not present a test as an automatic instruction from labels alone; otherwise say "Not provided"."""

    user = _build_user_prompt(
        specimen,
        context,
        language,
        label_top1,
        label_top2,
    )

    return PromptV2(system=system, user=user)


def build_concise_prompt_v2(
    specimen,
    language,
    label_top1,
    label_top2,
):
    """Build the short, morphology-only manual-generation prompt."""

    context, _ = _prompt_parts(specimen, language)
    if language == "ja":
        system = f"""あなたはローカルで動作する細胞診支援アシスタントです。
あなたは細胞画像を見ていません。入力された分類結果だけを補助情報として扱い、最終診断を行わないでください。
対象は{context}です。分類器が出力した上位2つの正規化済み診断候補だけを症例固有の入力として使い、画像で観察したかのような所見、患者情報、検査結果、数値、文献引用を作らないでください。
出力言語は日本語に限定してください。細胞形態学的な鑑別所見だけを、2候補の直接比較、重要な形態軸、重複し得る点や不確実性を含めて簡潔に述べてください。最も関連性の高い形態軸だけを選び、軸を機械的に列挙しないでください。
候補に複数の既知形態パターンや重なりがあり得る場合、単一の典型像へ固定せず、2候補の鑑別に関係する形態の幅を各比較軸で反映してください。
これは詳細版の第1セクションだけに相当します。見出し、臨床情報、追加検査、管理、処置、治療、結論、要約は絶対に書かないでください。箇条書きはちょうど4個、各1文・1行の短い箇条書きとし、4項目それぞれをMarkdown箇条書きとして、必ず半角ハイフン+半角スペースの「- 」で開始してください。各項目は1つの関連性が高い形態軸について2候補を同じ文で直接比較してください。詳細版の第1セクションと同じ品質・比較軸・形態の幅と重なりの契約を使い、4個の箇条書きを出したら直ちに停止してください。分類器のラベルだけから侵襲的検査、処置、治療を自動的に勧めず、一般論と条件表現に限定してください。"""
    else:
        system = f"""You are a local cytology support assistant.
You have not inspected the cell image. Treat the classifier labels only as support information and do not make a final diagnosis.
The specimen context is {context}. Use only the two normalized diagnosis candidate labels from the classifier as case-specific inputs; do not invent image observations, patient facts, test results, numeric claims, or literature citations.
Respond only in English. Write only concise morphology-based differential findings, with a direct comparison of both candidates, the most relevant morphology axes, and relevant overlap or uncertainty. Choose only the highest-value axes and do not mechanically enumerate them.
If either candidate has multiple recognized morphological patterns or overlap, do not force it into a single typical pattern; reflect the relevant range for the differential across each comparison axis.
This is only the detailed prompt's Section 1. Do not output headings, clinical information, additional tests, management, procedures, treatment, a conclusion, or a summary. Write exactly 4 short Markdown bullet points, and make each one start exactly with "- " (a hyphen followed by one ASCII space). Keep each bullet to one sentence and one line per bullet, with each bullet directly comparing both candidates on one highly relevant morphology axis. Use the same quality, comparison-axis, and morphological variation/overlap contract as the detailed prompt, then stop immediately after the 4 bullets. Do not automatically recommend invasive tests, procedures, or treatment from classifier labels alone; keep statements general and conditional."""

    return PromptV2(
        system=system,
        user=_build_user_prompt(
            specimen,
            context,
            language,
            label_top1,
            label_top2,
        ),
    )


def build_prompt_messages(
    specimen,
    language,
    label_top1,
    label_top2,
):
    return build_prompt_v2(
        specimen,
        language,
        label_top1,
        label_top2,
    ).messages
