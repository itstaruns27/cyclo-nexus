# Agent ALPHA: Data Engineering Pipeline

> **Owner:** Agent ALPHA (Tasks 1–5)  
> **Read Access:** Agent BRAVO, Agent CHARLIE

## Directory Structure

```
data_pipeline/
├── ingest/
│   ├── mosdac_insat3d.py       Task 1: MOSDAC HDF5 ingestion (h5py)
│   ├── jaxa_himawari.py        Task 2: Himawari-8/9 NetCDF ingestion
│   ├── nasa_gpm_imerg.py       Task 2: GPM IMERG precipitation pipeline
│   └── __init__.py
├── preprocess/
│   ├── reproject_epsg4326.py   Task 3: rasterio CRS reprojection
│   ├── radiometric_calibration.py  Task 4: DN→BT conversion
│   ├── tensor_assembler.py     Task 4: 4-channel Float32 stacking
│   └── __init__.py
├── catalog/
│   ├── imd_besttrack_harmonizer.py  Task 5: Best Track CSV→Parquet
│   └── __init__.py
├── config.py                   NIO bounds, tensor spec, paths
├── requirements.txt
└── tests/
```

## Output Contract

All outputs conform to `schemas/telemetry_contract.py`.
Final tensors: shape `(4, 1024, 1024)`, dtype `float32`, values in `[0.0, 1.0]`.
