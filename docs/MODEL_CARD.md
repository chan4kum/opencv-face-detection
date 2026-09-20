# Model card: YuNet face detector

| | |
|---|---|
| **Model** | YuNet (`face_detection_yunet_2026may.onnx`), from [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) |
| **Task** | Face *detection*: bounding box, confidence and 5 facial landmarks |
| **License** | MIT (upstream). See `models/LICENSE`, `models/README.md` for provenance and checksum |
| **Size / speed** | 230 KB; about 16 ms per 512x512 image on one CPU thread in this service (Apple M4 Pro, containerised) |
| **Intended use** | Locating faces in images: counting, cropping, blurring/anonymising, downstream pipelines |
| **Out of scope** | Identification / recognition, emotion or attribute inference, surveillance of individuals, any decision with legal or similarly significant effect on a person |

## Known limitations

* Trained to detect faces of roughly **10x10 to 300x300 px** (upstream note). Very large faces relative to the network
  input are down-scaled by the service (`FD_INFERENCE_MAX_SIDE`); very small ones may be missed.
* Accuracy drops on heavy occlusion, extreme pose, low light, and motion blur. Upstream reports WIDER Face validation
  AP (Easy/Medium/Hard) in its README; those figures were **not independently reproduced here** and the upstream README
  is not internally consistent about them, so treat them as indicative only. Evaluate on your own data before relying on it.
* Detection performance can vary across demographic groups and imaging conditions. This service has **not been audited
  for demographic bias**. If you deploy it where such variation matters, measure it on a representative dataset first.
* Output coordinates are relative to the EXIF-corrected image. Animated images are decoded as their first frame.

## Privacy and responsible use

* Faces are personal data (and in some jurisdictions biometric data) under GDPR and similar laws. You are responsible for
  having a lawful basis, providing notice, and honouring retention limits.
* The service is designed to minimise retention: images are deleted after processing, results contain geometry only, and
  everything expires by TTL. It never writes raw images to logs.
* Do not use this software to identify or track people without their knowledge, or in contexts prohibited by local law.

## How the service was validated

* Decoder parity with OpenCV's reference YuNet implementation on the same weights (unit test `test_matches_opencv_reference_implementation`).
* Coordinate correctness under resizing, padding and clipping (`test_scale_invariance_of_coordinates` and related).
* Checksum pinning: the service refuses to start with any other model file.
