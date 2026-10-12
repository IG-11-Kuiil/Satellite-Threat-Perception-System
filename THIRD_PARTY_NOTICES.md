# Third-party licensing notes

This is a focused licensing note, not a complete dependency or asset audit. Athena's integrated application is released under AGPL-3.0-only. Its project license does not replace upstream component terms.

## Ultralytics software and model weights

`requirements.txt` includes `ultralytics>=8.4,<9`. The locally installed version at this review was 8.4.175, whose package metadata lists AGPL-3.0. The application directly imports this package; current profiles use YOLO11s-OBB, YOLO26m-OBB, and optional legacy YOLOv8s model weights.

[Ultralytics' licensing page](https://www.ultralytics.com/license) describes AGPL-3.0 and paid Enterprise routes and states that its trained models are covered by AGPL-3.0 by default. The vendor describes Enterprise licensing for proprietary integration without the associated source-release obligations. AGPL itself is not a blanket ban on commercial use; compliance depends on its terms and the covered work.

Weights are downloaded separately and excluded from Git. That does not eliminate licensing obligations for using or distributing the integrated application. This source release adopts AGPL-3.0-only for the integrated application. No Enterprise grant is included. Future binary/container distribution, weight bundling, or hosted deployment must meet the relevant source, notice, and installation obligations for the exact release.

Before proprietary deployment or distribution, obtain suitable vendor licensing, replace affected dependencies and weights with compatible alternatives, or adopt compliant terms for the covered application. Have the intended architecture and distribution reviewed before treating it as commercially cleared. Publishing source for viewing alone is not equivalent to granting AGPL permissions.

## Other dependencies and assets

FastAPI, Uvicorn, python-multipart, OpenCV, NumPy, Pillow, PyTorch, torchvision, and their transitive dependencies retain their upstream terms. Check the exact versions and any bundled libraries used in a release; this document does not certify their license compatibility or reproduce a complete notice inventory. External imagery and datasets also require their own rights review.

## Previously published Athena code

Athena revisions through `a792e613fa24bae22dea69469bcff280d8752e03` carried an MIT license. Existing permissions remain for that code. The unmodified copyright and license text is retained in [docs/licenses/MIT-previous.txt](docs/licenses/MIT-previous.txt); the integrated application is now offered as a whole under AGPL-3.0-only without retracting those separately granted MIT permissions. The prospective rights-reserved notice introduced afterward has been superseded for this release; see [NOTICE](NOTICE).

Public GitHub viewing and forking are governed by [GitHub's platform terms and licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository). The repository remains public with source available under the stated licenses.
