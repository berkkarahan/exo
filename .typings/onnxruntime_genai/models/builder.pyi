"""Type stub for onnxruntime_genai.models.builder (create_model, used by exo's rank conversion adapter)."""

def create_model(
    model_name: str,
    input_path: str,
    output_dir: str,
    precision: str,
    execution_provider: str,
    cache_dir: str,
    **extra_options: bool | int,
) -> None: ...
