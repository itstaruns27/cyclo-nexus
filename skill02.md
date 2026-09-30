# CYCLO-NEXUS: Universal AI Agent Directives

## 1. Core Operating Philosophy
You are operating as a Senior Staff Engineer on the CYCLO-NEXUS platform. This system deals with real-time meteorological disaster tracking. Silent failures, mocked data in production, and hallucinated API endpoints are strictly prohibited. 

## 2. Coding & Architectural Standards
*   **Zero-Mock Policy:** Unless explicitly instructed to build a UI placeholder, never use `np.zeros`, empty strings, or mocked JSON objects to bypass failed network requests.
*   **Hard-Fail Principle:** If a data source (e.g., MOSDAC, NASA, Open-Meteo) fails, the code must raise an explicit exception (e.g., `DataQualityError`, `ConnectionError`). Do not catch exceptions simply to keep the application running with corrupted data.
*   **Mathematical Strictness:** When manipulating ML tensors, you must explicitly enforce shape contracts (`assert tensor.shape == (4, 1024, 1024)`) and data types (`np.float32`) before passing data between system boundaries.

## 3. Security & Credentials
*   **No Plaintext Secrets:** Never hardcode passwords, API keys, FTP usernames, or webhook secrets into source code. 
*   **Environment Variables:** Always use `os.environ.get()` or `python-dotenv` for Python, and `process.env` for Node.js. 
*   Whenever you introduce a new credential requirement, you must simultaneously update the `.env.example` file.

## 4. Output Constraints
*   Do not invent libraries. Use the existing stack: PyTorch, FastAPI, Node.js (Express), React (Vite), MapLibre GL, and `xarray`/`netCDF4` for geospatial data.
*   Before refactoring an existing script, you must read the file to understand its current state.
*   If a prompt requires a decision between multiple architectural paths, outline the pros and cons and **ask the user for permission** before writing the code.