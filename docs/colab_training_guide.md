# CYCLO-NEXUS: Google Colab GPU Training Guide

This guide provides step-by-step instructions for porting our local AI architecture to Google Colab for heavy GPU training. 

---

## 1. The Models Being Trained

We are training two separate deep learning models in sequence:

1.  **Model 1: Multimodal Vision Engine (YOLO-OBB 4-Channel)**
    *   **Purpose:** Detects the cyclone's center, bounds its structure with an Oriented Bounding Box (OBB), and classifies its intensity according to IMD standards.
    *   **Architecture:** A custom YOLOv8 architecture where the standard 3-channel (RGB) input layer was surgically replaced with our `YOLO4ChannelAdapter` to accept the 4-channel satellite tensor (TIR1, TIR2, WV, Precipitation).
    *   **Notebook:** `02_yolo_obb_training.ipynb`

2.  **Model 2: Spatiotemporal Forecaster (ConvLSTM)**
    *   **Purpose:** Predicts the future trajectory (latitude/longitude coordinates) and intensity (wind speed) of the cyclone over the next 24-72 hours.
    *   **Architecture:** A sequence-to-sequence Convolutional LSTM that looks at the historical timeline of the extracted cyclone tensors to predict the future state, heavily constrained by our `MishraGuptaPhysicsLoss` to prevent physically impossible forecasts.
    *   **Notebook:** `03_spatiotemporal_training.ipynb`

---

## 2. Prerequisites & Setup

Google Colab instances are ephemeral and delete their storage when you close the tab. Google Drive acts as our persistent storage.

1. Open your **Google Drive**.
2. Create a folder named `cyclonegaurd` (or point `PROJECT_ROOT` in the notebooks to your chosen folder).
3. Create subfolders inside it:
   - `data/besttrack/`
   - `data/raw/`
   - `data/tensors/`
   - `weights/` (where the trained models will be saved)
4. **Automated Data Downloading:** You do NOT need to manually search portals or download gigabytes of satellite files or IMD archives. Notebook `01_data_preparation.ipynb` automates the entire ingestion pipeline directly into your Google Drive.

---

## 3. Step-by-Step Training Execution

### Step 0: Automated Historical Data Preparation (Notebook 01)

Before training the neural networks, run the automated data pipeline to fetch all ground-truth tracks and multi-spectral satellite imagery:

1. Go to [colab.research.google.com](https://colab.research.google.com/).
2. Click **File > Upload notebook** and select `colab_notebooks/01_data_preparation.ipynb`.
3. Run **Cell 1 & 2** (Installs required geospatial libraries and mounts your Google Drive).
4. Run **Cell 3 (Automated Best Track Ingestion)**:
   - Automatically downloads the official NOAA IBTrACS North Indian Ocean database (`IBTrACS.NI.list.v04r00.csv`).
   - Filters and harmonizes tracks for benchmark cyclones: **Cyclone Amphan (2020), Tauktae (2021), Biparjoy (2023), Fani (2019), and Michaung (2023)**.
   - Saves clean, standardized CSV and Parquet files into `data/besttrack/`.
5. Run **Cell 4 (Automated Satellite Ingestion & Fusion)**:
   - Chronologically queries ISRO MOSDAC (INSAT-3D/3DR TIR-1, TIR-2, WV) and JAXA (GSMaP precipitation) in 30-minute time steps.
   - Automatically assembles and reprojects all 4 channels into standardized `(4, 1024, 1024)` float32 tensors strictly bounded in `[0.0, 1.0]`.
   - Saves `.npy` tensors into `data/tensors/`.
6. Run **Cell 5 (Integrity Verification)**:
   - Verifies tensor shapes `(4, 1024, 1024)` and builds 6-step temporal sequence matrices for the ConvLSTM Forecaster.

---

### Step A: Initialize the Vision Model (YOLO-OBB)

1. Go to [colab.research.google.com](https://colab.research.google.com/).
2. Click **File > Upload notebook** and select `colab_notebooks/02_yolo_obb_training.ipynb` from your local computer.
3. **Crucial Step:** In the top menu, click **Runtime > Change runtime type**. 
    * Set the **Hardware accelerator** to **GPU** (T4 GPU is free and sufficient; A100 is faster if you have Colab Pro). 
    * Save the settings.
4. Run **Cell 1** (Installs PyTorch and Ultralytics).
5. Run **Cell 2** (Mounts Google Drive). A popup will ask for permission to connect to your Google Drive. Accept it.
6. Run the subsequent cells. The notebook is pre-configured to initialize our custom `YOLO4ChannelAdapter` and begin the training loop over the data assembled in Step 0.
7. Wait for training to complete (this will run over the assembled 4-channel tensors).
8. The best performing weights will automatically be saved to your Google Drive as `weights/yolo_4ch_best.pt`.

---

### Step B: Initialize the Spatiotemporal Forecaster (ConvLSTM)

1. Upload `colab_notebooks/03_spatiotemporal_training.ipynb` to Google Colab.
2. Ensure the GPU runtime is selected (Runtime > Change runtime type > GPU).
3. Run the setup cells to mount your Google Drive.
4. Execute the training loop. This notebook loads the 6-step temporal sequence matrices (`(Batch, 6, 4, 1024, 1024)`) generated in Step 0 and trains the ConvLSTM + Bi-GRU multi-task model.
5. When finished, it will save `weights/forecaster_weights.pth` to your Google Drive.

---

## 4. Post-Training Deployment

Once both models have finished training:

1.  Go back to your Google Drive (`cyclone_nexus_data/weights/`).
2.  Download `vision_best.pt` and `forecaster_best.pt` to your local computer.
3.  Move these files into your local CYCLO-NEXUS repository:
    *   Place `vision_best.pt` inside `vision/weights/`
    *   Place `forecaster_best.pt` inside `forecaster/weights/`
4.  Restart your Node.js backend (`npm start`). 

The CYCLO-NEXUS backend is now fully operational, weaponized with trained AI, and ready for the Smart India Hackathon live demonstration!
