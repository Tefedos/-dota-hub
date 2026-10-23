from pydantic import Field, model_validator
from app.models.matches import StrictDTO


class PerformanceConfig(StrictDTO):
    model_version: str = 'ruiner_v1'
    # Design hypotheses, not population norms. Baselines come from this team's actual observations.
    core_weights: dict[str, float] = Field(default_factory=lambda: {
        'survival': .30, 'participation': .25, 'economy': .25, 'impact': .20,
    })
    fallback_weights: dict[str, float] = Field(default_factory=lambda: {'survival': .5, 'participation': .5})
    supported_modes: tuple[int, ...] = (1, 2, 22)
    minimum_duration_seconds: int = Field(default=900, ge=60)
    minimum_team_kills: int = Field(default=10, ge=1)
    minimum_team_deaths: int = Field(default=5, ge=1)
    minimum_cohort: int = Field(default=2, ge=2, le=5)
    minimum_axes: int = Field(default=2, ge=2, le=4)
    minimum_coverage: float = Field(default=.7, gt=0, le=1)
    maximum_positive_credit: float = Field(default=15, ge=0, le=25)
    selection_threshold: int = Field(default=70, ge=1, le=100)
    selection_margin: int = Field(default=15, ge=1, le=100)
    minimum_negative_axes: int = Field(default=2, ge=2, le=4)
    signal_threshold: float = Field(default=.2, gt=0, le=1)

    @model_validator(mode='after')
    def weights_valid(self) -> 'PerformanceConfig':
        for weights, keys in ((self.core_weights, {'survival', 'participation', 'economy', 'impact'}),
                              (self.fallback_weights, {'survival', 'participation'})):
            if set(weights) != keys or any(not 0 < w <= 1 for w in weights.values()) or abs(sum(weights.values()) - 1) > 1e-9:
                raise ValueError('positive weights must cover declared axes and sum to one')
        if not self.supported_modes or len(set(self.supported_modes)) != len(self.supported_modes):
            raise ValueError('supported modes must be nonempty and unique')
        return self
