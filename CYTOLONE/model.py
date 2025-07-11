models = {
    "v1.0": {"model_id": "kuri54/mlx-CYTOLONE-v1"},
    "v1.1": {"model_id": "kuri54/mlx-CYTOLONE-v1.1"},

    "LLM":{"model_id": "mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit"}
    }

def get_model_id(version):
    return models[version]["model_id"]

def get_llm_id():
    return models["LLM"]["model_id"]
