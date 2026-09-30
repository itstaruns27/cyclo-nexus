# CYCLO-NEXUS: Pre-Training Systems Audit & Strategic Analysis

**Date:** 2026-09-21
**Phase:** Transition from Phase 5 (Frontend) to Phase 6 (AI Training)
**Context:** Analysis of unit test failures following the implementation of the live ingestion pipeline, and strategic alignment with the Master Blueprint.

---

## 1. Test Failures & Root Cause Analysis

**The Root Cause: The "Mock-to-Live" Paradigm Shift**
The 6 Python test failures are **not** bugs in the application logic; they are a classic symptom of test rot occurring during a rapid transition from a "mocked" state to a "live" state. 

In the early stages of Phase 1 (Data Ingestion), the architecture was built using `MosdacIngestionWorker` and `JaxaGpmIngestionWorker` with synthetic, mocked data (e.g., generating arrays of zeros instead of downloading real satellite imagery) to lay down the initial pipeline. The tests (`test_mosdac_ingest.py` and `test_jaxa_gpm_ingest.py`) were written against these mock interfaces.

However, in **Task #21 (Live Multi-Source Ingestion & Tensor Assembly Pipeline)**, these workers were upgraded to connect to real-world live APIs (ISRO/MOSDAC THREDDS and NASA/JAXA EarthData FTP).
*   The `JaxaGpmIngestionWorker` was upgraded to perform actual FTP authentication. The test `test_jaxa_gpm_ingest` calls `.authenticate("test", "test")` without mocking the FTP library, causing a real network call to JAXA which gets rejected with `530 Login incorrect`.
*   The `MosdacIngestionWorker` had its `.api_key` attribute removed in favor of securely mapping credentials from a `config.json` file. The test expects `.api_key` to exist and crashes.
*   The method signatures changed (e.g., `download_granule` now takes a metadata dictionary instead of a string ID).
*   The array shapes were standardized to `(1024, 1024)` to match the AI model's input requirements, but the old tests were asserting sizes of `0` or `(500, 500)`.

## 2. Alignment with Initial Masterplan & TDD

The masterplan *was* kept in mind for the architecture, but there was a lapse in **Test-Driven Development (TDD) discipline** during the execution of Task #21. 

When the live ingestion workers were implemented, a *new* test file (`tests/data_pipeline/test_live_pipeline.py`) was created to verify the work. However, the pre-existing unit tests were not updated or deprecated. In strict agile development, any modification to a core class requires refactoring all existing tests that rely on that class. Failing to do so left "orphaned" tests that enforce an outdated contract, creating technical debt and the illusion of a broken system.

## 3. Immediate Risks and Flaws

Because of this lapse, the current flaws and risks are:
1.  **False Negatives in CI/CD:** If pushed to GitHub Actions right now, the build would fail, halting deployment.
2.  **Unmocked Network Calls:** Having tests that execute real FTP/HTTP calls (like the failing JAXA test) is highly dangerous. It slows down the test suite, requires internet access to pass, and can lead to IP bans from the space agencies for rapid consecutive polling.
3.  **Data Dimension Mismatches:** If the live data ingestion unexpectedly changes resolution (e.g., INSAT upgrades its sensor), our fallback zero-padding logic (`1024x1024`) might mask the error instead of raising a clear exception, leading to silent AI hallucinations down the line.

## 4. Current Stage in the Masterplan Workflow

We are currently standing at the **Bridge between Phase 5 (Frontend) and Phase 6 (End-to-End Validation / AI Training)**.

Based on the audit of the repository:
*   **Phase 1 (Data):** Done. The ingestion workers, tensor assembler, and historical spoolers are built.
*   **Phase 2 (Vision AI):** Done. The custom 4-channel YOLO-OBB architecture, adapters, and physics-augmented loss functions are coded locally.
*   **Phase 3 (Spatiotemporal AI):** Done. The ConvLSTM forecaster is coded locally.
*   **Phase 4 (Backend):** Done. The Express.js gateway, Gemini integration, and Webhook receivers are built and tested (100% pass).
*   **Phase 5 (Frontend):** Done. The React, MapLibre GL, and i18n localization dashboard is built.
*   **Phase 6 (Validation & Training):** **In Progress.** We have generated the Jupyter Notebooks (`02_yolo_obb_training.ipynb` and `03_spatiotemporal_training.ipynb`) to port the local PyTorch models to the cloud, but the actual training hasn't occurred yet.

## 5. Parameter Integration Verification

Analysis of the 4 required data parameters:
1.  **MOSDAC (INSAT-3D/3DR TIR & WV):** **YES.** Implemented in `mosdac_worker.py`.
2.  **NASA GPM (Precipitation Proxy):** **YES.** Implemented in `jaxa_gpm_worker.py` which pulls the GSMaP data via JAXA's FTP server.
3.  **Historical Data:** **YES.** Implemented via `historical_spooler.py` and `imd_track_harmonizer.py`, which parses historical CSVs to simulate cyclone tracks for Hackathon demonstrations.
4.  **JAXA Himawari-8/9 (Clean IR):** The blueprint explicitly mentions Himawari Clean IR as a parameter. In the codebase, the `TensorAssembler` currently builds a 4-channel tensor (TIR1, TIR2, WV, and Precipitation) to match the custom `YOLO4ChannelAdapter`. This means Himawari IR was substituted for Precipitation in the 4th channel. While a scientifically sound adaptation, it represents a slight deviation from the 5-channel text in the blueprint.

## 6. Training Roadmap

AI Training is the **final external step** before the system goes live. 

Training on Google Colab will commence **immediately after fixing the 6 failing tests**. 
The precise sequence of events required:
1.  **Now:** Fix `test_mosdac_ingest.py` and `test_jaxa_gpm_ingest.py` to correctly mock the network and assert `(1024, 1024)` tensors. 
2.  **Validation:** Run the test suite and achieve 100% green status.
3.  **Final Audit:** Generate the `audit_report_v2.md` finalizing the local development phase.
4.  **Training Phase (External):** Execute the generated notebooks (`colab_notebooks/02_yolo_obb_training.ipynb` and `03_spatiotemporal_training.ipynb`) on Google Colab with a mounted Google Drive and T4/A100 GPU.
5.  **Deployment:** Download the resulting `.pt` (PyTorch weight files) and integrate them back into this repository for backend serving.
