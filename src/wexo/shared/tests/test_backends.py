from wexo.shared.types.backends import Backend


def test_onnx_backend_members():
    assert Backend.OnnxDirectMl == "OnnxDirectMl"
    assert Backend.OnnxCuda == "OnnxCuda"
    assert Backend.OnnxCpu == "OnnxCpu"
