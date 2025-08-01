import csv
from pathlib import Path
import sys
import time
from typing import Any, Callable, TypeVar

import csfile
from statictorch import Tensor2d
from tomlkit import value
import torch
from torch.utils.data import DataLoader
from basic_utilities.kahan_accumulator import KahanAccumulator
from basic_utilities.static_class import StaticClass
from inputs_and_outputs.checkpoint_managers.checkpoints_directory import CheckpointsDirectory
from inputs_and_outputs.checkpoint_managers.epoch_and_path import EpochAndPath
from inputs_and_outputs.csv_accessors.csv_writer import CsvWriter
from inputs_and_outputs.data_providers.data_batch import DataBatch
from inputs_and_outputs.data_providers.train_data_provider import TrainDataProvider
from inputs_and_outputs.data_providers.validation_or_test_dataset import ValidationOrTestDataset
from metrics.metric import Metric
from trainers.checkpoint_policies.checkpoint_policy import CheckpointPolicy
from trainers.trainable import Trainable


class Trainer(StaticClass):
    @classmethod
    def load_model(cls,
                   model: Trainable,
                   checkpoint: Path):
        checkpoint_content: Any = torch.load(checkpoint, weights_only=True)
        model.set_state(checkpoint_content["model"])

    @classmethod
    def train(cls,
              checkpoints: CheckpointsDirectory, 
              train_data: TrainDataProvider, 
              model: Trainable,
              checkpoint_policy: CheckpointPolicy):
        batch_index: int = 1
        def save_checkpoint() -> None:
            path: Path = checkpoints.get_path(batch_index)
            torch.save({
                "model": model.get_state(),
                "data": train_data.state_dict(),
                "checkpoint_policy": checkpoint_policy.get_state()
            }, path)
        latest_checkpoint: tuple[int, Path] | None = checkpoints.get_latest()
        if latest_checkpoint is None:
            save_checkpoint()
        else:
            checkpoint_path: Path
            batch_index, checkpoint_path = latest_checkpoint
            checkpoint: Any = torch.load(checkpoint_path, weights_only=True)
            model.set_state(checkpoint["model"])
            train_data.load_state_dict(checkpoint["data"])
            checkpoint_policy.set_state(checkpoint["checkpoint_policy"])
        
        rir_batch: Tensor2d
        speech_batch: Tensor2d
        reverb_batch: Tensor2d
        rir_batch, speech_batch, reverb_batch = train_data.get()
        details: dict[str, float] = model.prepare_train_on(reverb_batch, rir_batch, speech_batch)
        
        print_csv: CsvWriter = csv.writer(sys.stdout)
        detail_keys: list[str] = list(details.keys())
        def print_details():
            print_csv.writerow((batch_index, 
                                time.time_ns(), 
                                *(details[key] for key in detail_keys)))
            sys.stdout.flush()
        print_csv.writerow(("batch", "time", *detail_keys))

        while True:
            print_details()
            if checkpoint_policy.check(batch_index, details):
                save_checkpoint()
                print(f"# Checkpoint saved at {batch_index}.")
            model.train_prepared()
            train_data.next()
            
            batch_index += 1
            rir_batch, speech_batch, reverb_batch = train_data.get()
            details = model.prepare_train_on(reverb_batch, rir_batch, speech_batch)
    
    @classmethod
    def validate(cls,
                 checkpoints: CheckpointsDirectory, 
                 validation_data: DataLoader, 
                 model: Trainable,
                 start_checkpoint: int):
        with torch.no_grad():
            batch_count: int = validation_data.__len__()
            print(f"# Batch count: {batch_count}")
            epoches_to_scores: dict[int, float] = {}

            csv_print: CsvWriter = csv.writer(sys.stdout)
            csv_print.writerow(["epoch", "batch", "metric", "value"])
            epoch_index: int
            path: Path
            for epoch_index, path in checkpoints.get_all():
                if epoch_index < start_checkpoint:
                    continue
                
                Trainer.load_model(model, path)
            
                score_accumulator: KahanAccumulator = KahanAccumulator()
                accumulators: dict[str, KahanAccumulator] = {}

                batch_index: int
                batch: DataBatch
                for batch_index, batch in enumerate(validation_data):
                    score: float
                    all_values: dict[str, float]
                    score, all_values = model.validate_on(batch.reverb, batch.rir, batch.speech)

                    score_accumulator.add(score)
                    csv_print.writerow([epoch_index, batch_index, "main", score])

                    key: str
                    for key in all_values:
                        if key not in accumulators:
                            accumulators[key] = KahanAccumulator()
                        accumulators[key].add(all_values[key])
                        csv_print.writerow([epoch_index, batch_index, key, all_values[key]])

                epoches_to_scores[epoch_index] = score_accumulator.value() / batch_count
                csv_print.writerow([epoch_index, "average", "main", 
                                    epoches_to_scores[epoch_index]])
                for key in accumulators:
                    csv_print.writerow([epoch_index, "average", key, 
                                        accumulators[key].value() / batch_count])

            csfile.write_all_lines(
                checkpoints.get_path(None) / "validation_rank.txt", 
                [str(key) for key in sorted(epoches_to_scores.keys(), 
                                            key=lambda key: epoches_to_scores[key])])
