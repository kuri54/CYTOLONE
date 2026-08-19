question_text = {
     "cervix": {
        "en": {
            "What do you think of this image?": "Full",
            "Is this image anomaly or normal?": "Anomaly",
            "Is this image benign or malignant?": "Malignancy",
            "What is the Bethesda classification of this image?": "System",
            "What is the diagnosis for this image?": "Diagnosis"
            },

        "ja": {
            "この画像はどう思う?": "Full",
            "この画像は正常？異常?": "Anomaly",
            "この画像は良性？悪性?": "Malignancy",
            "この画像のベセスダ分類は?": "System",
            "この画像の診断は?": "Diagnosis"
            },
    }
    }

classification_label = {
    "cervix": [
        "Normal Benign NILM Negative",
        "Normal Benign NILM Atrophy",
        "Anomaly Dysplasia LSIL Mild_dysplasia",
        "Anomaly Dysplasia HSIL Moderate_dysplasia",
        "Anomaly Dysplasia HSIL Severe_dysplasia",
        "Anomaly Carcinoma SCC Squamous_cell_carcinoma",
        "Anomaly Carcinoma ADC Adeno_carcinoma"
        ],
        }

order = {
    "cervix": ["Full", "Anomaly", "Malignancy", "System", "Diagnosis"]
}

DIAGNOSIS_CANDIDATE_LABELS = {
    "cervix": (
        "Normal Benign NILM Atrophy",
        "Anomaly Dysplasia LSIL Mild_dysplasia",
        "Anomaly Dysplasia HSIL Moderate_dysplasia",
        "Anomaly Dysplasia HSIL Severe_dysplasia",
        "Anomaly Carcinoma SCC Squamous_cell_carcinoma",
        "Anomaly Carcinoma ADC Adeno_carcinoma",
    ),
}

LLM_DIAGNOSIS_LABELS = {
    "cervix": {
        "Atrophy": "Atrophy",
        "Mild_dysplasia": "Mild dysplasia",
        "Moderate_dysplasia": "Moderate dysplasia",
        "Severe_dysplasia": "Severe dysplasia",
        "Squamous_cell_carcinoma": "Squamous cell carcinoma",
        "Adeno_carcinoma": "Adenocarcinoma",
    }
}

def get_label_caption(specimen, language):
    return question_text[specimen][language], classification_label[specimen], order[specimen]

def get_order_type(specimen, language, choice_caption):
    return question_text[specimen][language][choice_caption]


def get_diagnosis_candidate_labels(specimen, labels=None):
    try:
        eligible_labels = set(DIAGNOSIS_CANDIDATE_LABELS[specimen])
    except KeyError as exc:
        raise ValueError(
            f"No Diagnosis candidates are defined for specimen={specimen!r}"
        ) from exc

    labels = classification_label[specimen] if labels is None else labels
    return [label for label in labels if label in eligible_labels]


def get_llm_diagnosis_label(specimen, label):
    try:
        diagnosis_labels = LLM_DIAGNOSIS_LABELS[specimen]
    except KeyError as exc:
        raise ValueError(
            f"No LLM diagnosis labels are defined for specimen={specimen!r}"
        ) from exc
    try:
        return diagnosis_labels[label]
    except KeyError as exc:
        raise ValueError(
            f"Unknown diagnosis label {label!r} for specimen={specimen!r}"
        ) from exc

