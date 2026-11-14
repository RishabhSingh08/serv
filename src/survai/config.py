from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt, model_validator

Coordinate = Annotated[float, Field(ge=0, le=1)]
NormalizedPoint = tuple[Coordinate, Coordinate]


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counter_zone: list[NormalizedPoint] = Field(min_length=3)
    exit_line: tuple[NormalizedPoint, NormalizedPoint]
    wait_seconds: PositiveFloat = 10
    queue_count: PositiveInt = 3
    crowd_count: PositiveInt = 4
    bag_seconds: PositiveFloat = 4
    bag_radius: PositiveFloat = 0.17
    bag_motion: PositiveFloat = 0.035
    cooldown_seconds: PositiveFloat = 20
    snapshot_days: PositiveInt = 2
    image_size: int = Field(default=416, ge=32, multiple_of=32)
    weights: str = "yolov8n.pt"
    summary_model: str = "gpt-4.1-mini"

    @model_validator(mode="after")
    def check_geometry(self) -> Self:
        area = sum(
            ax * by - bx * ay
            for (ax, ay), (bx, by) in zip(
                self.counter_zone, self.counter_zone[1:] + self.counter_zone[:1]
            )
        )
        if abs(area) < 1e-8 or self.exit_line[0] == self.exit_line[1]:
            raise ValueError("Draw a counter polygon with area and two distinct exit endpoints")
        return self


def load_config(path: Path) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text()))


def save_config(path: Path, config: BaseModel) -> None:
    temporary = path.with_suffix(".yaml.tmp")
    temporary.write_text(yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False))
    temporary.replace(path)


Polygon = Annotated[list[NormalizedPoint], Field(min_length=3)]


class WalkoutConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor: Literal["center", "bottom_center"] = "center"
    dining_zone: Polygon
    pay_zone: Polygon
    exit_band: Polygon | None = None
    exit_line: tuple[NormalizedPoint, NormalizedPoint] | None = None
    min_dwell_seconds: PositiveFloat = 120
    pay_dwell_seconds: PositiveFloat = 5
    lost_grace_seconds: PositiveFloat = 2
    occlusion_seconds: PositiveFloat = 5
    alert_cooldown_seconds: PositiveFloat = 20
    evidence_retention_days: PositiveInt = 2
    reassociation_distance: Annotated[float, Field(gt=0, le=1)] = 0.08

    @model_validator(mode="after")
    def check_geometry(self) -> Self:
        if (self.exit_band is None) == (self.exit_line is None):
            raise ValueError("Configure exactly one of exit_band and exit_line")
        if self.exit_line is not None and self.exit_line[0] == self.exit_line[1]:
            raise ValueError("Draw the exit line with two distinct endpoints")
        for name in ("dining_zone", "pay_zone", "exit_band"):
            polygon = getattr(self, name)
            if polygon is None:
                continue
            area = sum(
                ax * by - bx * ay
                for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1])
            )
            if abs(area) < 1e-8:
                raise ValueError(f"{name} must enclose an area")
        return self


def load_walkout_config(path: Path) -> WalkoutConfig:
    return WalkoutConfig.model_validate(yaml.safe_load(path.read_text()))
