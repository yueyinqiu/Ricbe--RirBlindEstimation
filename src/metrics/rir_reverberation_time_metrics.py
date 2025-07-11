from statictorch import Tensor1d

from audio_processors.rir_acoustic_features import RirAcousticFeatures2d
from metrics.metric import Metric


class RirReverberationTimeMetrics(Metric[RirAcousticFeatures2d]):
    def __init__(self, 
                 decay_decibel: float,
                 sample_rate: int,
                 metrics_on_reverberation_time: dict[str, Metric[Tensor1d]]):
        self._decay_decibel = decay_decibel
        self._sample_rate = sample_rate
        self._metrics = metrics_on_reverberation_time
    
    def append(self, actual: RirAcousticFeatures2d, predicted: RirAcousticFeatures2d) -> dict[str, float]:
        actual_time: Tensor1d = actual.reverberation_time(self._decay_decibel,  self._sample_rate)
        actual_time = Tensor1d(actual_time * 60 / self._decay_decibel)

        predicted_time: Tensor1d = predicted.reverberation_time(self._decay_decibel, self._sample_rate)
        predicted_time = Tensor1d(predicted_time * 60 / self._decay_decibel)

        result: dict[str, float] = {}

        key_metric: str
        for key_metric in self._metrics:
            values: dict[str, float] = self._metrics[key_metric].append(actual_time, predicted_time)
            key_value: str
            for key_value in values:
                result[f"{key_metric}_{key_value}"] = values[key_value]

        return result
        
    def result(self) -> dict[str, float]:
        result: dict[str, float] = {}

        key_metric: str
        for key_metric in self._metrics:
            values: dict[str, float] = self._metrics[key_metric].result()
            key_value: str
            for key_value in values:
                result[f"{key_metric}_{key_value}"] = values[key_value]

        return result
