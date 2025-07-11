import csv
from pathlib import Path
from random import Random
import sys
from typing import Callable
import csfile
from statictorch import Tensor1d, Tensor2d
import torch
from torch.utils.data import DataLoader

from audio_processors.rir_acoustic_features import RirAcousticFeatures2d
from audio_processors.rir_convolution import RirConvolution
from basic_utilities.kahan_accumulator import KahanAccumulator
from inputs_and_outputs.checkpoint_managers.checkpoints_directory import CheckpointsDirectory
from inputs_and_outputs.checkpoint_managers.epoch_and_path import EpochAndPath
from inputs_and_outputs.csv_accessors.csv_writer import CsvWriter
from inputs_and_outputs.data_providers.data_batch import DataBatch
from inputs_and_outputs.data_providers.validation_or_test_dataset import ValidationOrTestDataset
from metrics.bias_metric import BiasMetric
from metrics.l1_loss_metric import L1LossMetric
from metrics.metric import Metric
from metrics.mrstft_loss_metric import MrstftLossMetric
from metrics.pearson_correlation_metric import PearsonCorrelationMetric
from metrics.rir_direct_to_reverberant_energy_ratio_metrics import RirDirectToReverberantEnergyRatioMetrics
from metrics.rir_reverberation_time_metrics import RirReverberationTimeMetrics


def model(reverb: Tensor2d, speech: Tensor2d, rir_length: int = 16000):
    right: int = rir_length // 2
    reverb = Tensor2d(torch.nn.functional.pad(reverb, [right - 1, right]))
    return RirConvolution.inverse_convolve_full(reverb, speech)


def test(data: DataLoader, 
         rir_metrics: dict[str, Metric[Tensor2d]],
         feature_metrics: dict[str, Metric[RirAcousticFeatures2d]]):
    with torch.no_grad():
        print(f"# Batch count: {data.__len__()}")

        csv_print: CsvWriter = csv.writer(sys.stdout)
        csv_print.writerow(["batch", "metric", "submetric", "value"])

        batch_index: int
        batch: DataBatch
        for batch_index, batch in enumerate(data):
            predicted: Tensor2d = model(batch.reverb, batch.speech)

            metric: str
            for metric in rir_metrics:
                current: dict[str, float] = rir_metrics[metric].append(batch.rir, predicted)
                submetric: str
                for submetric in current:
                    csv_print.writerow([batch_index, metric, submetric, current[submetric]])

            actual_features: RirAcousticFeatures2d = RirAcousticFeatures2d(batch.rir)
            predicted_features: RirAcousticFeatures2d = RirAcousticFeatures2d(predicted)
            for metric in feature_metrics:
                current = feature_metrics[metric].append(actual_features, predicted_features)
                for submetric in current:
                    csv_print.writerow([batch_index, metric, submetric, current[submetric]])

        for metric in rir_metrics:
            value: float
            for submetric, value in rir_metrics[metric].result().items():
                csv_print.writerow(["all", metric, submetric, value])

        for metric in feature_metrics:
            for submetric, value in feature_metrics[metric].result().items():
                csv_print.writerow(["all", metric, submetric, value])


def main():
    from exe.frequency_domain_division import test_frequency_domain_division_config as config

    print("# Loading...")
    cpu: torch.device = torch.device("cpu")
    test(ValidationOrTestDataset(config.test_list, cpu).get_data_loader(32),
         {
             "mrstft": MrstftLossMetric.for_rir(cpu),
             "l1": L1LossMetric(cpu),
         },
         {
             "rt60": RirReverberationTimeMetrics(30, 16000, {
                 "bias": BiasMetric(),
                 "l1": L1LossMetric(cpu),
                 "pearson": PearsonCorrelationMetric()
             }),
             "drr": RirDirectToReverberantEnergyRatioMetrics({
                 "bias": BiasMetric(),
                 "l1": L1LossMetric(cpu),
                 "pearson": PearsonCorrelationMetric()
             }),
         })


if __name__ == "__main__":
    main()