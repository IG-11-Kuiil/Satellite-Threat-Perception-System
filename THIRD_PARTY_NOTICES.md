# Third-party licensing notes

This is a focused licensing note, not a complete dependency or asset audit. Athena's original-code rights notice is not a substitute for dependency compliance.

## Ultralytics software and model weights

`requirements.txt` includes `ultralytics>=8.4,<9`. The locally installed version at this review was 8.4.175, whose package metadata lists AGPL-3.0. The application directly imports this package; current profiles use YOLO11s-OBB, YOLO26m-OBB, and optional legacy YOLOv8s model weights.

[Ultralytics' licensing page](https://www.ultralytics.com/license) describes AGPL-3.0 and paid Enterprise routes and states that its trained models are covered by AGPL-3.0 by default. The vendor describes Enterprise licensing for proprietary integration without the associated source-release obligations. AGPL itself is not a blanket ban on commercial use; compliance depends on its terms and the covered work.

Weights are downloaded separately and excluded from Git. That does not eliminate licensing obligations for using or distributing the integrated application. This repository provides no evidence of an Enterprise grant and makes no claim that its rights-reserved notice is compatible with all current integration/distribution scenarios.

Before proprietary deployment or distribution, obtain suitable vendor licensing, replace affected dependencies and weights with compatible alternatives, or adopt compliant terms for the covered application. Have the intended architecture and distribution reviewed before treating it as commercially cleared. Publishing source for viewing alone is not equivalent to granting AGPL permissions.

## Other dependencies and assets

FastAPI, Uvicorn, python-multipart, OpenCV, NumPy, Pillow, PyTorch, torchvision, and their transitive dependencies retain their upstream terms. Check the exact versions and any bundled libraries used in a release; this document does not certify their license compatibility or reproduce a complete notice inventory. External imagery and datasets also require their own rights review.

## Previously published Athena code

Athena revisions through `a792e613fa24bae22dea69469bcff280d8752e03` carried an MIT license. Existing permissions remain for that code. The unmodified copyright and license text is retained in [docs/licenses/MIT-previous.txt](docs/licenses/MIT-previous.txt); the new rights notice applies only to new original contributions first published under it.

Public GitHub viewing and forking are governed by [GitHub's platform terms and licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository). A restrictive notice does not disable those platform capabilities.
