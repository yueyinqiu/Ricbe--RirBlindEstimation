from statictorch import Tensor3d
import torch

from models.cleanunet_models.networks.cleanunet_network import CleanunetNetwork
from models.cleanunet_models.networks.cleanunet_ric_network import CleanUNetRicNetwork
from models.ricbe_models.networks.ricbe_ric_network import RicbeRicNetwork
from models.ricbe_models.submodules.ricbe_postprocess import RicbePostprocess
from models.ricbe_models.submodules.ricbe_preprocess import RicbePreprocess


class CleanUNetFullbeNetwork(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.dereverb = CleanunetNetwork()
        self.ric = CleanUNetRicNetwork()

    def forward(self, reverb: Tensor3d):
        speech: Tensor3d = self.dereverb(reverb)
        rir: Tensor3d = self.ric(reverb, speech)
        return speech, rir
