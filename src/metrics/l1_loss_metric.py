from typing import NamedTuple
from statictorch import Tensor0d, Tensor1d, Tensor2d
import torch

from basic_utilities.kahan_accumulator import KahanAccumulator
from criterions.stft_losses.mrstft_loss import MrstftLoss
from metrics.metric import Metric


class L1LossMetric(Metric[Tensor1d | Tensor2d]):
    def __init__(self, device: torch.device):
        self._loss = torch.nn.L1Loss().to(device)
        self._accumulator = KahanAccumulator()
        self._count = 0
    
    def append(self, actual: Tensor1d | Tensor2d, predicted: Tensor1d | Tensor2d) -> dict[str, float]:
        loss: float = float(self._loss(predicted, actual))

        self._accumulator.add(loss)
        self._count += 1
        
        return {
            "value": loss
        }
        
    def result(self) -> dict[str, float]:
        return {
            "value": self._accumulator.value() / self._count
        }
