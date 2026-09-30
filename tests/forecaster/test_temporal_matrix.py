"""
Task 10 Verification Harness: Spatiotemporal Matrix Pipeline
════════════════════════════════════════════════════════════
Owner: Agent CHARLIE | Skill: [SKILL:SPATIOTEMPORAL_AI]

Verifies:
    1. Perfect sequential filenames pass the validator.
    2. Missing timestamps (60 min gap) raise SequenceLeakageError.
    3. Unsorted filenames are strictly sorted chronologically before windowing.
    4. Matrix builder handles mock (empty) files and returns correct PyTorch shapes.
"""

from pathlib import Path
import pytest

from forecaster.data.temporal_matrix_builder import (
    TemporalMatrixBuilder, 
    LeakageValidator, 
    SequenceLeakageError
)


class TestLeakageValidator:
    def test_perfect_sequence_passes(self):
        """Mock a list of 6 perfectly sequential filenames."""
        paths = [
            Path("INSAT3D_L1C_20240524_120000.npy"),
            Path("INSAT3D_L1C_20240524_123000.npy"),
            Path("INSAT3D_L1C_20240524_130000.npy"),
            Path("INSAT3D_L1C_20240524_133000.npy"),
            Path("INSAT3D_L1C_20240524_140000.npy"),
            Path("INSAT3D_L1C_20240524_143000.npy"),
        ]
        assert LeakageValidator.validate_sequence(paths) is True

    def test_time_gap_raises_leakage_error(self):
        """Mock a list where step 3 jumps by 60 minutes instead of 30."""
        paths = [
            Path("INSAT3D_L1C_20240524_120000.npy"),
            Path("INSAT3D_L1C_20240524_123000.npy"),
            Path("INSAT3D_L1C_20240524_130000.npy"),
            Path("INSAT3D_L1C_20240524_140000.npy"), # 60 min gap!
            Path("INSAT3D_L1C_20240524_143000.npy"),
            Path("INSAT3D_L1C_20240524_150000.npy"),
        ]
        with pytest.raises(SequenceLeakageError, match="Invalid time gap"):
            LeakageValidator.validate_sequence(paths)

    def test_unsorted_raises_leakage_error(self):
        """Passing an unsorted list directly to validator should fail."""
        paths = [
            Path("INSAT3D_L1C_20240524_123000.npy"),
            Path("INSAT3D_L1C_20240524_120000.npy"), # Out of order
        ]
        with pytest.raises(SequenceLeakageError, match="chronologically sorted"):
            LeakageValidator.validate_sequence(paths)


class TestTemporalMatrixBuilder:
    def test_sorting_before_windowing(self):
        """
        Mock an unsorted list. Assert the builder sorts it chronologically 
        before windowing (resulting in a valid window that doesn't skip).
        """
        unsorted_paths = [
            Path("INSAT3D_L1C_20240524_140000.npy"),
            Path("INSAT3D_L1C_20240524_130000.npy"),
            Path("INSAT3D_L1C_20240524_133000.npy"),
            Path("INSAT3D_L1C_20240524_143000.npy"),
            Path("INSAT3D_L1C_20240524_120000.npy"),
            Path("INSAT3D_L1C_20240524_123000.npy"),
        ]
        
        # Build sequences (using seq_length 6)
        sequences = TemporalMatrixBuilder.build_sequences(unsorted_paths, seq_length=6)
        
        # If it didn't sort, LeakageValidator would reject it and return 0 sequences.
        assert len(sequences) == 1, "Builder failed to sort paths before windowing."
        
        # Check tensor shape (6, 4, 1024, 1024)
        seq_tensor = sequences[0]
        assert seq_tensor.shape == (6, 4, 1024, 1024)

    def test_skip_invalid_windows(self):
        """
        Provide 7 files with a gap.
        Valid window 1: 1200, 1230, 1300, 1330, 1400, 1430 (Valid)
        Valid window 2: 1230, 1300, 1330, 1400, 1430, 1530 (Gap! Should be skipped)
        """
        paths = [
            Path("INSAT3D_L1C_20240524_120000.npy"),
            Path("INSAT3D_L1C_20240524_123000.npy"),
            Path("INSAT3D_L1C_20240524_130000.npy"),
            Path("INSAT3D_L1C_20240524_133000.npy"),
            Path("INSAT3D_L1C_20240524_140000.npy"),
            Path("INSAT3D_L1C_20240524_143000.npy"),
            Path("INSAT3D_L1C_20240524_153000.npy"), # Gap here
        ]
        
        sequences = TemporalMatrixBuilder.build_sequences(paths, seq_length=6)
        
        # Only the first window should survive
        assert len(sequences) == 1
