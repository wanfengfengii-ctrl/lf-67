from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from enum import Enum


class GrainType(str, Enum):
    rice = "rice"
    wheat = "wheat"
    millet = "millet"
    sorghum = "sorghum"
    soybean = "soybean"


class LoadingOrder(str, Enum):
    bottom_heavy = "bottom_heavy"
    top_heavy = "top_heavy"
    even = "even"
    pyramid = "pyramid"


class SeaState(str, Enum):
    calm = "calm"
    slight = "slight"
    moderate = "moderate"
    rough = "rough"
    very_rough = "very_rough"


class PriorityTarget(str, Enum):
    min_loss = "min_loss"
    max_capacity = "max_capacity"
    min_pressure = "min_pressure"
    balance = "balance"


class RecommendationStatus(str, Enum):
    recommended = "recommended"
    alternative = "alternative"
    high_risk = "high_risk"
    informal = "informal"


class CabinConfig(BaseModel):
    length: float
    width: float
    height: float

    @field_validator("length", "width", "height")
    @classmethod
    def dimensions_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("船舱尺寸必须大于0")
        return v


class BagSpec(BaseModel):
    length: float
    width: float
    height: float
    weight: float

    @field_validator("length", "width", "height", "weight")
    @classmethod
    def bag_dimensions_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("粮包规格和重量必须大于0")
        return v


class SimulationRequest(BaseModel):
    cabin: CabinConfig
    bag: BagSpec
    layers: int
    grain_type: GrainType
    humidity: Optional[float] = None
    voyage_days: int
    loading_order: LoadingOrder = LoadingOrder.even
    sea_state: SeaState = SeaState.calm
    max_loss_rate: Optional[float] = 10.0
    max_layers: Optional[int] = None
    priority_target: PriorityTarget = PriorityTarget.balance

    @field_validator("layers")
    @classmethod
    def layers_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("堆码层数必须大于0")
        return v

    @field_validator("voyage_days")
    @classmethod
    def voyage_days_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("航行天数必须大于0")
        return v

    @field_validator("humidity")
    @classmethod
    def humidity_range(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("湿度范围为0-100%")
        return v

    @field_validator("max_loss_rate")
    @classmethod
    def max_loss_rate_range(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("最大允许损耗率范围为0-100%")
        return v

    @model_validator(mode="after")
    def check_capacity(self):
        if self.bag.length > self.cabin.length:
            raise ValueError(
                f"粮包长度({self.bag.length:.2f}m)大于船舱长度({self.cabin.length:.2f}m)，无法放入"
            )
        if self.bag.width > self.cabin.width:
            raise ValueError(
                f"粮包宽度({self.bag.width:.2f}m)大于船舱宽度({self.cabin.width:.2f}m)，无法放入"
            )
        if self.bag.height > self.cabin.height:
            raise ValueError(
                f"粮包高度({self.bag.height:.2f}m)大于船舱高度({self.cabin.height:.2f}m)，无法放入"
            )
        cabin_vol = self.cabin.length * self.cabin.width * self.cabin.height
        bags_per_layer_x = int(self.cabin.length // self.bag.length)
        bags_per_layer_y = int(self.cabin.width // self.bag.width)
        if bags_per_layer_x <= 0 or bags_per_layer_y <= 0:
            raise ValueError("粮包尺寸过大，船舱内无法放置任何粮包")
        bags_per_layer = bags_per_layer_x * bags_per_layer_y
        total_height = self.layers * self.bag.height
        if total_height > self.cabin.height:
            raise ValueError(
                f"粮包堆码总高度({total_height:.2f}m)超出船舱高度({self.cabin.height:.2f}m)"
            )
        total_bags = bags_per_layer * self.layers
        bag_vol = self.bag.length * self.bag.width * self.bag.height
        total_bag_vol = total_bags * bag_vol
        if total_bag_vol > cabin_vol:
            raise ValueError(
                f"粮包总体积({total_bag_vol:.2f}m³)超出船舱容量({cabin_vol:.2f}m³)，不能装载"
            )
        return self


class LayerInfo(BaseModel):
    layer: int
    bags_count: int
    pressure_kpa: float
    moisture_risk: float


class MitigationAdvice(BaseModel):
    pressure_advice: List[str] = []
    moisture_advice: List[str] = []
    loss_advice: List[str] = []
    stability_advice: List[str] = []
    general_advice: List[str] = []


class SimulationResult(BaseModel):
    total_bags: int
    bottom_pressure_kpa: float
    avg_pressure_kpa: float
    max_compression_ratio: float
    moisture_risk_level: str
    moisture_risk_score: float
    estimated_loss_rate: float
    layer_details: List[LayerInfo]
    warnings: List[str]
    is_high_risk: bool
    can_execute: bool
    capacity_used_pct: float
    is_formal_assessment: bool
    mitigation_advice: MitigationAdvice = MitigationAdvice()
    feasibility_score: float = 0.0


class ComparisonItem(BaseModel):
    loading_order: LoadingOrder
    result: SimulationResult


class ComparisonResult(BaseModel):
    items: List[ComparisonItem]
    best_order: LoadingOrder
    best_loss_rate: float
    is_formal_assessment: bool


class SchemePlan(BaseModel):
    scheme_id: str
    scheme_name: str
    loading_order: LoadingOrder
    layers: int
    bags_per_layer: int
    total_bags: int
    result: SimulationResult
    status: RecommendationStatus
    score: float
    rank: int = 0


class MultiSchemeResult(BaseModel):
    schemes: List[SchemePlan]
    recommended_count: int
    alternative_count: int
    high_risk_count: int
    informal_count: int
    best_scheme_id: Optional[str] = None
    is_formal_assessment: bool
    priority_target: PriorityTarget


class BatchCompareRequest(BaseModel):
    cabin: CabinConfig
    bag: BagSpec
    grain_type: GrainType
    voyage_days: int
    loading_order: LoadingOrder = LoadingOrder.even
    humidity_values: List[float]
    sea_state_values: List[SeaState]
    layers: Optional[int] = None
    max_loss_rate: Optional[float] = 10.0
    max_layers: Optional[int] = None
    priority_target: PriorityTarget = PriorityTarget.balance

    @field_validator("humidity_values")
    @classmethod
    def validate_humidity_values(cls, v):
        if not v:
            raise ValueError("至少需要指定一个湿度值")
        for h in v:
            if h < 0 or h > 100:
                raise ValueError(f"湿度值 {h} 超出范围(0-100)")
        return v

    @field_validator("sea_state_values")
    @classmethod
    def validate_sea_state_values(cls, v):
        if not v:
            raise ValueError("至少需要指定一个海况值")
        return v


class BatchCell(BaseModel):
    humidity: float
    sea_state: SeaState
    result: Optional[SimulationResult] = None
    error: Optional[str] = None
    is_high_risk: bool = False
    is_formal: bool = True


class BatchCompareResult(BaseModel):
    humidity_values: List[float]
    sea_state_values: List[SeaState]
    cells: List[List[BatchCell]]
    best_cell: Optional[dict] = None
    is_any_formal: bool
