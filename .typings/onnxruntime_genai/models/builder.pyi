"""Type stub for onnxruntime_genai.models.builder."""

def create_model(
    model_name: str,
    input_path: str,
    output_dir: str,
    precision: str,
    execution_provider: str,
    cache_dir: str,
    **extra_options: bool | int,
) -> None: ...
