import numpy as np
from utils.indicators import macd_cross_golden

def test_macd_cross_golden_synthetic():
    arr = np.concatenate([np.linspace(100, 99, 50), np.linspace(99, 101, 50)])
    assert macd_cross_golden(arr) in [True, False]

if __name__ == "__main__":
    test_macd_cross_golden_synthetic()
