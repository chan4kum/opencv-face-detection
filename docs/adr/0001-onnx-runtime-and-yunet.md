# ADR 0001: YuNet on ONNX Runtime instead of Haar cascades / cv2.dnn

**Status:** accepted

**Context.** The original project used OpenCV Haar cascades (2001-era, high false-positive rate, no landmarks, poor with pose/lighting).
We need a modern, permissively licensed detector that is small and fast on CPU and portable across clouds.

**Decision.** Use YuNet (MIT, 230 KB) exported to ONNX and run it on ONNX Runtime, implementing output decoding and NMS ourselves.

**Consequences.**
- (+) Far better accuracy than Haar; landmarks come for free; ~16 ms/image on one CPU thread.
- (+) Runtime-agnostic: CPU today, CUDA/TensorRT/OpenVINO/CoreML by swapping execution providers.
- (+) No dependency on `cv2.dnn`, whose backend changed substantially in OpenCV 5.
- (-) We own the post-processing. Mitigated by a parity test against OpenCV's reference implementation.
- (-) Model is vendored in git (230 KB) to keep builds hermetic; upgrades are explicit and checksum-pinned.
