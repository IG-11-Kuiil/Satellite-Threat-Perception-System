# Athena product walkthrough

A suggested 60-90 second narrated screen recording of the actual local application. This is a recording outline, not a completed or hosted video. Keep original image provenance and usage permissions in mind before publishing imagery.

| Time | Show | Explain |
| --- | --- | --- |
| 0-10 seconds | Athena workspace and the two workflows | "Athena is a satellite imagery analysis prototype for aircraft detection and before/after comparison." |
| 10-25 seconds | Upload a permitted single scene, then show its real completed analysis | "The aerial model finds candidate aircraft. I can check every box against the original image and inspect its score." |
| 25-45 seconds | Upload a comparable pair, then show the completed comparison | "The application compares detected totals and grouping. It does not track individual aircraft or prove arrivals and departures." |
| 45-60 seconds | A review candidate and its supporting score | "Weak candidates need agreement from another model and stay flagged. Primary counts and candidate-inclusive counts are reported separately." |
| 60-75 seconds | Assessment, caveats, and downloads | "Presence and priority are explainable prototype rules. The report preserves the settings, evidence, and uncertainty." |
| 75-90 seconds | Recent runs and project documentation | "Analyses are saved locally. Next steps are a representative labeled benchmark and better comparison of matched ground coverage." |

Show real inference progress. If processing takes too long for the recording, cut from submission to completion and label the cut; do not imply real-time processing or fabricate results. Use saved runs to demonstrate review features without repeating inference.

For the documented comparison example, say "nine before, eleven primary after, plus one review candidate" rather than presenting twelve as a confirmed ground-truth detection count. The known-candidate delta is +2 to +3; it does not account for aircraft missed by both models.

This project uses pretrained Ultralytics detection models. Explain the application engineering separately: upload validation, tile deduplication, candidate review, spatial reasoning, exports, and history. Do not claim training a new model, aircraft-type recognition, operational deployment, customer adoption, or validated military threat prediction.

A video link can be added to the README after a real recording is published. A recording is optional; the screenshots, setup instructions, and reproducible validation notes already let someone inspect the project.
