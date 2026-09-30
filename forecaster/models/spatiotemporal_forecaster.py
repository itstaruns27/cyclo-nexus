"""
Task 11: ConvLSTM + Bi-GRU Spatiotemporal Forecaster
════════════════════════════════════════════════════
Owner: Agent CHARLIE | Skill: [SKILL:SPATIOTEMPORAL_AI]

End-to-end spatiotemporal forecasting architecture.
Features:
1. Spatial Downsampling Stem (avoids VRAM OOM on 1024x1024 inputs).
2. Custom ConvLSTMCell for topology-preserving recurrent processing.
3. Bi-GRU Trajectory Head for sequence momentum modeling.
4. Multi-Task Output Head for (dx, dy), V_max, and central pressure drop.
"""

import torch
import torch.nn as nn


class ConvLSTMCell(nn.Module):
    """
    Custom Convolutional LSTM Cell.
    Replaces standard matrix multiplications with 2D convolutions to 
    preserve spatial topology across time steps.
    """
    def __init__(self, in_channels: int, hidden_channels: int, kernel_size: int = 3):
        super(ConvLSTMCell, self).__init__()
        self.hidden_channels = hidden_channels
        padding = kernel_size // 2
        
        # A single convolution computes all 4 gates simultaneously
        self.conv = nn.Conv2d(
            in_channels=in_channels + hidden_channels, 
            out_channels=4 * hidden_channels, 
            kernel_size=kernel_size, 
            padding=padding
        )

    def forward(self, x: torch.Tensor, state: tuple[torch.Tensor, torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor]:
        h_prev, c_prev = state
        
        # Concatenate along channel dimension
        combined = torch.cat([x, h_prev], dim=1)
        gates = self.conv(combined)
        
        # Split into Input, Forget, Output, and Cell gates
        i, f, o, g = torch.split(gates, self.hidden_channels, dim=1)
        
        i = torch.sigmoid(i)
        f = torch.sigmoid(f)
        o = torch.sigmoid(o)
        g = torch.tanh(g)
        
        # Update cell and hidden states
        c_next = f * c_prev + i * g
        h_next = o * torch.tanh(c_next)
        
        return h_next, c_next


class CycloneForecaster(nn.Module):
    """
    Complete Spatiotemporal Forecaster predicting track and intensity.
    """
    HORIZONS_H = (6, 12, 24, 48, 72)

    def __init__(self, in_channels: int = 4, conv_hidden: int = 64, gru_hidden: int = 128,
                 n_horizons: int = len(HORIZONS_H)):
        super(CycloneForecaster, self).__init__()
        
        # 1. Spatial Downsampling Stem
        # Drastically reduces 1024x1024 footprint before recurrent loops to save VRAM.
        self.stem = nn.Sequential(
            nn.Conv2d(in_channels, 16, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            
            nn.Conv2d(32, conv_hidden, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            
            nn.Conv2d(conv_hidden, conv_hidden, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2)
        )
        
        # 2. ConvLSTM Cell
        self.conv_lstm = ConvLSTMCell(
            in_channels=conv_hidden, 
            hidden_channels=conv_hidden, 
            kernel_size=3
        )
        
        # 3. Bi-GRU Trajectory Head
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.gru = nn.GRU(
            input_size=conv_hidden, 
            hidden_size=gru_hidden, 
            batch_first=True, 
            bidirectional=True
        )
        
        # 4. Multi-Task Output Heads, one output per lead time (master plan v4, Task 7).
        # n_horizons=1 reproduces the legacy single-horizon checkpoint layout.
        # Bidirectional output concatenates forward and backward hidden states
        gru_out_dim = gru_hidden * 2
        self.n_horizons = n_horizons

        self.track_head = nn.Linear(gru_out_dim, 2 * n_horizons)
        self.v_max_head = nn.Linear(gru_out_dim, n_horizons)
        self.dp_head = nn.Linear(gru_out_dim, n_horizons)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        """
        Forward pass.
        
        Args:
            x: Tensor of shape (Batch, Seq_Length, Channels, H, W)
            
        Returns:
            Dictionary containing track_delta, v_max_pred, and dp_pred tensors.
        """
        B, Seq, C, H, W = x.shape
        
        # Flatten temporal dimension into batch dimension for efficient 2D CNN downsampling
        x_reshaped = x.view(B * Seq, C, H, W)
        
        features = self.stem(x_reshaped)
        _, F_c, H_prime, W_prime = features.shape
        
        # Reshape back to Sequence
        features = features.view(B, Seq, F_c, H_prime, W_prime)
        
        # Initialize ConvLSTM hidden states
        h_t = torch.zeros(B, F_c, H_prime, W_prime, device=x.device, dtype=x.dtype)
        c_t = torch.zeros(B, F_c, H_prime, W_prime, device=x.device, dtype=x.dtype)
        
        # Recurrent Loop over Time
        h_seq = []
        for t in range(Seq):
            x_t = features[:, t, :, :, :]
            h_t, c_t = self.conv_lstm(x_t, (h_t, c_t))
            h_seq.append(h_t)
            
        h_seq_tensor = torch.stack(h_seq, dim=1)  # (B, Seq, F_c, H', W')
        
        # Collapse spatial dimensions
        pooled = self.pool(h_seq_tensor.view(B * Seq, F_c, H_prime, W_prime))
        pooled = pooled.view(B, Seq, F_c)  # Flattened to (B, Seq, F_c)
        
        # Sequence modeling with Bi-GRU
        gru_out, _ = self.gru(pooled)  # (B, Seq, gru_hidden * 2)
        
        # Extract the final time step's trajectory encoding
        final_out = gru_out[:, -1, :]  # (B, gru_hidden * 2)
        
        # Multi-task predictions. Multi-horizon: track (B, H, 2), v_max / dp (B, H).
        # Legacy (n_horizons=1): track (B, 2), v_max / dp (B, 1), as before.
        track = self.track_head(final_out)
        if self.n_horizons > 1:
            track = track.view(B, self.n_horizons, 2)
        return {
            "track_delta": track,
            "v_max_pred": self.v_max_head(final_out),
            "dp_pred": self.dp_head(final_out)
        }


def load_forecaster(weights_path, device="cpu") -> CycloneForecaster:
    """Load a checkpoint, detecting multi-horizon vs legacy single-horizon heads from its shapes."""
    state = torch.load(weights_path, map_location=device)
    n_horizons = state["v_max_head.weight"].shape[0]
    model = CycloneForecaster(n_horizons=n_horizons)
    model.load_state_dict(state)
    return model.to(device).eval()
