"""Approved, user-opened urine review flow; no inference or external lookup."""

from html import escape


URINE_GUIDANCE = {
    "ja": {
        "button": "判定に迷ったとき",
        "nodes": [
            "反応性変化か悪性か、判定に迷う",
            "標本・臨床情報を確認\n細胞量・変性・採取方法\n炎症・結石・処置／治療歴\n過去の細胞診・病理診断",
            "標本を再検討\n必要に応じて細胞診専門医と確認",
            "疑問・所見の不一致が残る？",
            "解消した → 所見と臨床情報を踏まえて報告",
            "残る → 臨床側と相談し、必要な対応を検討",
            "再採取・細胞診の再検\n経過の確認",
            "補助検査\n免疫細胞化学・FISHなど",
            "臨床所見・病理診断との照合\n必要に応じて内視鏡・組織学的評価",
            "得られた情報を合わせて再評価",
        ],
        "notes": [
            "下段の3つは順番に全て行う手順ではなく、症例に応じた選択肢。検査の選択・時期は細胞診専門医／担当医が判断する。",
            "悪性を疑う所見が強い場合は臨床側への共有を優先し、補助検査の結果待ちを必須にしない。",
            "細胞診・尿中マーカーは、必要な内視鏡・組織学的評価を置き換えない。",
        ],
        "caption": "下記文献を参考にCYTOLONE用に作成した確認フロー。既存ガイドライン掲載図の転載ではありません。参考資料確認日：2026年10月19日。",
        "references": [
            "検体の量的・質的問題、細胞診専門医との連携、臨床・病理診断との不一致例の検討。",
            "細胞量、感染、結石、膀胱内治療による評価への影響と、疑わしい細胞診の再評価。",
            "筋層非浸潤性膀胱癌患者の判定不明瞭な細胞診に対するUroVysion FISH等の補助的使用。全尿検体への一律実施を支持するものではない。",
            "尿細胞診への免疫細胞化学の補助的利用を検討した研究。特定の染色・判定基準を必須化する根拠にはしない。",
        ],
    },
    "en": {
        "button": "When the interpretation is uncertain",
        "nodes": [
            "Uncertain whether the changes are reactive or malignant",
            "Check the specimen and clinical information\nCellularity, degeneration, collection method\nInflammation, stones, procedure / treatment history\nPrevious cytology and histological diagnoses",
            "Review the specimen\nConsult a cytopathologist as needed",
            "Do questions or discordant findings remain?",
            "Resolved → Report considering the findings and clinical information",
            "Remain → Discuss with the clinical team and consider appropriate action",
            "Repeat collection / cytology\nReview follow-up",
            "Ancillary tests\nImmunocytochemistry, FISH, etc.",
            "Correlate with clinical findings and histological diagnosis\nEndoscopy / histological evaluation as needed",
            "Reassess all the information obtained",
        ],
        "notes": [
            "The three options below are selected according to the case, not steps that must all be performed in order. The cytopathologist / treating physician determines test selection and timing.",
            "If findings strongly suggest malignancy, prioritize sharing them with the clinical team; waiting for ancillary test results is not required.",
            "Cytology and urinary markers do not replace necessary endoscopy or histological evaluation.",
        ],
        "caption": "A review flow created for CYTOLONE with reference to the sources below. It is not a reproduction of a guideline figure. Sources reviewed: October 19, 2026.",
        "references": [
            "Specimen quantity / quality, collaboration with cytopathologists, and review of discordance with clinical / histological diagnoses.",
            "Effects of cellularity, infection, stones and intravesical treatment on assessment, and reassessment of suspicious cytology.",
            "Ancillary use of UroVysion FISH, etc., for equivocal cytology in patients with non-muscle-invasive bladder cancer. This does not support routine use for all urine specimens.",
            "A study of ancillary immunocytochemistry in urine cytology; it does not mandate a particular stain or interpretation criteria.",
        ],
    },
}

REFERENCES = [
    ("日本臨床細胞学会．細胞診業務の精度管理ガイドライン．2023年3月18日改定。", "https://jscc.or.jp/files/guideline-18.pdf"),
    ("EAU Guidelines on Non-muscle-invasive Bladder Cancer. Diagnosis, §5.5–5.9.", "https://uroweb.org/guidelines/non-muscle-invasive-bladder-cancer/chapter/diagnosis"),
    ("AUA/SUO. Diagnosis and Treatment of Non-Muscle Invasive Bladder Cancer. 2024 amendment, Statement 11.", "https://www.auanet.org/documents/Guidelines/PDF/clinical-guidance/NMIBC%20Amendment%2002-28-24%20Final%20v3.pdf"),
    ("Choi SY, et al. Diagnostic significance of dual immunocytochemical staining of p53/cytokeratin20 on liquid-based urine cytology to detect urothelial carcinoma. CytoJournal. 2020;17:3. doi:10.25259/Cytojournal_88_2019.", "https://pmc.ncbi.nlm.nih.gov/articles/PMC7111538/"),
]


def urine_guidance_html(language):
    content = URINE_GUIDANCE[language]

    def box(text):
        return '<div style="border:1px solid #888;border-radius:8px;padding:12px;margin:6px;white-space:pre-line">' + escape(text) + '</div>'

    nodes = content["nodes"]
    arrow = '<div style="text-align:center">↓</div>'
    flow = arrow.join(box(node) for node in nodes[:4])
    # The resolved branch ends at reporting; only the unresolved branch continues.
    unresolved = box(nodes[5]) + arrow
    unresolved += '<div style="display:flex;flex-wrap:wrap">'
    unresolved += ''.join('<div style="flex:1;min-width:170px">' + box(node) + arrow + '</div>' for node in nodes[6:9])
    unresolved += '</div>' + box(nodes[9])
    flow += arrow + '<div style="display:flex;flex-wrap:wrap"><div style="flex:1;min-width:220px">' + box(nodes[4]) + '</div><div style="flex:2;min-width:300px">' + unresolved + '</div></div>'
    notes = '<ul>' + ''.join('<li>' + escape(note) + '</li>' for note in content["notes"]) + '</ul>'
    references = '<ol>' + ''.join(
        '<li><a href="' + url + '" target="_blank" rel="noopener noreferrer">' + escape(title) + '</a> — ' + escape(note) + '</li>'
        for (title, url), note in zip(REFERENCES, content["references"])
    ) + '</ol>'
    return flow + notes + '<p>' + escape(content["caption"]) + '</p>' + references
