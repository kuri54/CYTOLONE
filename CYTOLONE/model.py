models = {
    "v1.0": {"model_id": "kuri54/mlx-CYTOLONE-v1"},
    "v1.1": {"model_id": "kuri54/mlx-CYTOLONE-v1.1"},

    "deepseek-r1":{"model_id": "mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit"},
    "gpt-oss-120b":{"model_id": "mlx-community/gpt-oss-120b-MXFP4-Q4"},
    "gpt-oss-20b":{"model_id": "mlx-community/gpt-oss-20b-MXFP4-Q8"},
    }

def get_model_id(version):
    return models[version]["model_id"]

def get_llm_id(llm_model):
    return models[llm_model]["model_id"]
