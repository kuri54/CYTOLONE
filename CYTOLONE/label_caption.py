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

caption ={
    "cervix": {
        "en": {
            "caption":
                """
                [Instruction]
                Your output must be in English.
                You are an expert in pathology and cytology.
                Please concisely describe the differential diagnostic features between {label_top1} and {label_top2} in cervical cytology.
                If there is any relevant clinical information or additional tests required for the differentiation, please include them.

                Please follow the output format below:
                [Format]
                1. Differential diagnostic points in cytology
                   List up to three concise features
                2. Relevant clinical information for differentiation
                3. Additional tests potentially useful for differentiation

                These pieces of information are extremely important for clinicians to determine the next steps. Please ensure they are described based on evidence.
                For section 3, consider tests that facilitate interdepartmental decision-making and prompt clinical action.
                """
        },

        "ja": {
            "caption":
                """
                [指令]
                出力は必ず**日本語**で行うこと。
                あなたは病理・細胞診のエキスパートです。
                子宮頸部の細胞診における{label_top1}と{label_top2}の鑑別所見を簡潔に述べてください。
                鑑別に必要な臨床情報や検査あれば追記してください。

                出力は以下のフォーマットで出力してください。
                **フォーマット**
                1. 細胞診の鑑別ポイント
                最大3つまでの簡潔な鑑別所見
                2. 鑑別に有効な臨床情報
                3. 鑑別に必要と思われる検査

                これらは臨床医が次の処置を行うために非常に重要であるため、エビデンスに基づいて述べるように厳重に注意してください。
                3. に関しては臨床医が次の行動に移りやすいように他科横断的に考えてください。
                """
        },
     }
}

def get_label_caption(specimen, language):
    return question_text[specimen][language], classification_label[specimen], order[specimen]

def get_order_type(specimen, language, choice_caption):
    return question_text[specimen][language][choice_caption]

def get_caption(specimen, language, label_top1, label_top2):
    return caption[specimen][language]["caption"].format(label_top1=label_top1, label_top2=label_top2)



