# Comparison validation and general fixes

## Observed failures

The user supplied a before scene with nine visible aircraft and an after scene with twelve, including a cloud-obscured aircraft at the far end of the apron. The previous run reported 11 before, 11 after, Stable/Low priority.

Before contained two shifted tile-edge fragments in addition to their complete aircraft predictions. Full-polygon overlap over the smaller box was below the existing containment cutoff, so these were counted twice. In after, the primary model found eleven aircraft; the obscured aircraft received a primary score below the automatic acceptance threshold.

## General changes

1. **Field-of-view comparison:** crop-boundary fragments are compared with the complete prediction after both are clipped to the fragment's observed tile. The complete prediction must cross that same tile boundary. The existing polygon IoU threshold is reused; it was not lowered for this image.
2. **Cross-model candidate review:** the default primary aerial detector can gather weak aircraft candidates down to 10% and verify unmatched ones with a second aerial detector at the user's normal confidence threshold. Both must overlap at the configured polygon IoU threshold. Candidates keep both original scores and remain flagged for manual confirmation. Secondary-only detections are not added.
3. **Provisional totals:** reports show primary counts separately from candidate-inclusive counts. Exact change is marked provisional when retained review candidates contribute. Cloud/shadow and unequal-visibility caveats accompany the assessment.
4. **Failure recovery:** an unavailable verifier preserves primary detections with a warning. It does not silently promote weak candidates or fail an otherwise successful primary analysis.
5. **Evidence retention:** benchmark results are separated by input-content hash to avoid overwriting evidence from another scene.

No model weights were trained or altered. The production pipeline does not contain these images' coordinates, filenames, dates, expected counts, cloud positions, or airport layouts. Counts below are validation observations, not inputs to inference.

## Results with unchanged model weights

| Input | Primary detections | Candidate-inclusive observations | Review candidates |
| --- | ---: | ---: | ---: |
| Original before | 9 | 9 | 0 |
| Original after | 11 | 12 | 1 |
| Before resized to half dimensions | 9 | 9 | 0 |
| After resized to half dimensions | 10 | 11 | 1 |
| Earlier four-aircraft scene | 4 | 4 | 0 |

The original pair's displayed total change is +3, with a primary-only change of +2. Trend is Increased and review priority High. The remaining candidate has a primary score of about 16%, supporting score of about 42%, and polygon IoU about 0.40. It is visibly partial and must be confirmed by a human; scores were not inflated.

The resized after image still misses an aircraft. This was recorded rather than adjusting parameters or forcing twelve detections. The earlier scene remains four distinct aircraft, including its central aircraft, without the previous upper-left duplicate.

## Public reference checks

The standard DOTA8 reference archive supplied by Ultralytics was evaluated using its existing aircraft labels, with the production settings unchanged. Both labeled aircraft across the eight images were matched. Five of six images without aircraft labels produced no detections. The sixth produced an unmatched primary detection in a dark non-airport scene, demonstrating a remaining false-positive risk. Three additional detections in the aircraft scenes correspond to partly cropped aircraft visible near image borders but absent from the provided plane labels; raw label-based evaluation records them as unmatched/false positives.

These results do not justify a broad accuracy claim. DOTA8 is a small regression utility from the same dataset family as the pretrained models, not a newly constructed held-out satellite benchmark. Labels near image borders are incomplete. The public check was used to expose limitations, not to tune thresholds or change model weights.

Raw reference evaluation and resizing records remain local ignored files under `outputs/verification/`. No customer imagery or public dataset archive is committed.

## Reproduce

```powershell
.\.venv\Scripts\python.exe run_change_detection.py --before "path\to\before.png" --after "path\to\after.png"
.\.venv\Scripts\python.exe tools/validate_references.py "path\to\dota8"
.\.venv\Scripts\python.exe -m pytest
```

The validator matches class-0 YOLO-OBB plane labels at the configured polygon IoU threshold. It reports label-based true/false positives and false negatives and does not modify production configuration.
