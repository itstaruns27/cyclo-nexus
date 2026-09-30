import pytest
import numpy as np
from datetime import datetime
from unittest.mock import patch, MagicMock
from data_pipeline.ingestion.jaxa_gpm_worker import JaxaGpmIngestionWorker

@patch("ftplib.FTP")
def test_jaxa_gpm_ingest(mock_ftp_class):
    # Setup mock FTP to prevent real network calls during testing
    mock_ftp = MagicMock()
    mock_ftp_class.return_value = mock_ftp
    
    worker = JaxaGpmIngestionWorker()
    worker.authenticate("test_user", "test_pass")
    
    # Verify authentication mapped correctly to ftp library
    mock_ftp.login.assert_called_with(user="test_user", passwd="test_pass")
    
    target_time = datetime(2024, 5, 24, 12, 0, 0)
    res = worker.stream_and_subgrid_gpm(target_time, (0, 32, 50, 102))
    
    # The worker fallback returns a properly shaped zero tensor
    assert res.shape == (1024, 1024)
    assert np.all(res == 0)
