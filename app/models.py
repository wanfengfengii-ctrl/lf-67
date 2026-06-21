from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List, Dict
from enum import Enum
from datetime import date, datetime


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


class WarningLevel(str, Enum):
    normal = "normal"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class DisposalStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    processing = "processing"
    completed = "completed"
    closed = "closed"


class BagCheckStatus(str, Enum):
    normal = "normal"
    compressed = "compressed"
    damp = "damp"
    moldy = "moldy"
    damaged = "damaged"


class RockingLevel(str, Enum):
    calm = "calm"
    slight = "slight"
    moderate = "moderate"
    rough = "rough"
    very_rough = "very_rough"


class AbnormalEventType(str, Enum):
    humidity_spike = "humidity_spike"
    temp_spike = "temp_spike"
    pressure_worsen = "pressure_worsen"
    moisture_spread = "moisture_spread"
    bag_damage = "bag_damage"
    hull_shake = "hull_shake"
    water_leak = "water_leak"
    other = "other"


WARNING_LEVEL_LABELS = {
    WarningLevel.normal: "正常",
    WarningLevel.low: "低风险预警",
    WarningLevel.medium: "中风险预警",
    WarningLevel.high: "高风险预警",
    WarningLevel.critical: "极高风险预警",
}

DISPOSAL_STATUS_LABELS = {
    DisposalStatus.pending: "待确认",
    DisposalStatus.confirmed: "已确认",
    DisposalStatus.processing: "处置中",
    DisposalStatus.completed: "已处置",
    DisposalStatus.closed: "已闭环",
}

BAG_STATUS_LABELS = {
    BagCheckStatus.normal: "正常",
    BagCheckStatus.compressed: "压损变形",
    BagCheckStatus.damp: "受潮",
    BagCheckStatus.moldy: "发霉",
    BagCheckStatus.damaged: "破损",
}

ROCKING_LEVEL_LABELS = {
    RockingLevel.calm: "平静",
    RockingLevel.slight: "轻微",
    RockingLevel.moderate: "中等",
    RockingLevel.rough: "剧烈",
    RockingLevel.very_rough: "极端",
}

ABNORMAL_EVENT_LABELS = {
    AbnormalEventType.humidity_spike: "湿度突升",
    AbnormalEventType.temp_spike: "温度异常",
    AbnormalEventType.pressure_worsen: "压损恶化",
    AbnormalEventType.moisture_spread: "受潮扩散",
    AbnormalEventType.bag_damage: "粮包破损",
    AbnormalEventType.hull_shake: "船体剧烈摇晃",
    AbnormalEventType.water_leak: "渗水漏水",
    AbnormalEventType.other: "其他异常",
}


class AbnormalEventInput(BaseModel):
    event_type: AbnormalEventType
    description: str = ""


class DailyMonitorInput(BaseModel):
    voyage_id: str
    record_date: date
    cabin_humidity: float
    cabin_temperature: float
    rocking_level: RockingLevel
    bag_check_status: BagCheckStatus = BagCheckStatus.normal
    bag_check_note: str = ""
    abnormal_events: List[AbnormalEventInput] = []
    note: str = ""

    @field_validator("cabin_humidity")
    @classmethod
    def humidity_range(cls, v):
        if v < 0 or v > 100:
            raise ValueError("舱内湿度范围为0-100%")
        return v

    @field_validator("cabin_temperature")
    @classmethod
    def temperature_range(cls, v):
        if v < -20 or v > 60:
            raise ValueError("舱内温度范围-20~60°C")
        return v


class WarningRecordOutput(BaseModel):
    warning_id: str
    voyage_id: str
    record_date: date
    warning_level: WarningLevel
    warning_type: str
    warning_message: str
    disposal_status: DisposalStatus = DisposalStatus.pending
    disposal_action: str = ""
    disposal_time: Optional[str] = None
    risk_score: float = 0.0
    is_high_risk_unresolved: bool = False


class DailyMonitorOutput(BaseModel):
    record_id: str
    voyage_id: str
    record_date: date
    cabin_humidity: float
    cabin_temperature: float
    rocking_level: RockingLevel
    bag_check_status: BagCheckStatus
    bag_check_note: str
    abnormal_events: List[Dict] = []
    note: str
    warning_level: WarningLevel = WarningLevel.normal
    risk_score: float = 0.0
    warnings: List[WarningRecordOutput] = []
    disposal_status: DisposalStatus = DisposalStatus.pending
    transport_status: str = "正常"
    created_at: str = ""


class RiskTrendPoint(BaseModel):
    record_date: date
    risk_score: float
    humidity: float
    temperature: float
    warning_level: WarningLevel
    pressure_risk: float = 0.0
    moisture_risk: float = 0.0
    shake_risk: float = 0.0


class DisposalUpdateInput(BaseModel):
    disposal_status: DisposalStatus
    disposal_action: str = ""
    transport_status: Optional[str] = None


class WarningConfirmInput(BaseModel):
    confirmed: bool = True


class AbnormalReportInput(BaseModel):
    voyage_id: str
    record_date: date
    event_type: AbnormalEventType
    description: str
    severity: WarningLevel = WarningLevel.medium


class VoyageSummaryOutput(BaseModel):
    voyage_id: str
    total_days: int
    avg_humidity: float
    avg_temperature: float
    max_risk_score: float
    warning_count: int
    high_risk_count: int
    unresolved_count: int
    closed_count: int
    trend: List[RiskTrendPoint]
    pressure_risk_trend: List[RiskTrendPoint]
    moisture_risk_trend: List[RiskTrendPoint]
    disposal_comparison: Optional[Dict] = None


class ShipStatus(str, Enum):
    available = "available"
    in_voyage = "in_voyage"
    maintenance = "maintenance"
    loading = "loading"
    unloading = "unloading"


SHIP_STATUS_LABELS = {
    ShipStatus.available: "可用",
    ShipStatus.in_voyage: "航行中",
    ShipStatus.maintenance: "维护中",
    ShipStatus.loading: "装货中",
    ShipStatus.unloading: "卸货中",
}


class Ship(BaseModel):
    ship_id: str
    ship_name: str
    cabin_length: float
    cabin_width: float
    cabin_height: float
    capacity_tons: float
    max_speed: float
    status: ShipStatus = ShipStatus.available
    current_port: str = ""
    crew_count: int = 0
    last_maintenance_date: Optional[date] = None
    note: str = ""


class Port(BaseModel):
    port_id: str
    port_name: str
    berth_count: int
    loading_rate: float
    unloading_rate: float
    storage_capacity: float
    note: str = ""


class WeatherCondition(str, Enum):
    sunny = "sunny"
    cloudy = "cloudy"
    rainy = "rainy"
    stormy = "stormy"
    foggy = "foggy"


WEATHER_CONDITION_LABELS = {
    WeatherCondition.sunny: "晴朗",
    WeatherCondition.cloudy: "多云",
    WeatherCondition.rainy: "雨天",
    WeatherCondition.stormy: "暴风雨",
    WeatherCondition.foggy: "大雾",
}


class WeatherForecast(BaseModel):
    port_id: str
    forecast_date: date
    condition: WeatherCondition
    wind_level: int
    sea_state: SeaState
    visibility_km: float
    affect_voyage: bool = False


class VoyagePriority(str, Enum):
    emergency = "emergency"
    high = "high"
    normal = "normal"
    low = "low"


VOYAGE_PRIORITY_LABELS = {
    VoyagePriority.emergency: "紧急",
    VoyagePriority.high: "高优先级",
    VoyagePriority.normal: "普通",
    VoyagePriority.low: "低优先级",
}


class VoyageStatus(str, Enum):
    pending = "pending"
    loading = "loading"
    sailing = "sailing"
    unloading = "unloading"
    completed = "completed"
    delayed = "delayed"
    cancelled = "cancelled"


VOYAGE_STATUS_LABELS = {
    VoyageStatus.pending: "待调度",
    VoyageStatus.loading: "装货中",
    VoyageStatus.sailing: "航行中",
    VoyageStatus.unloading: "卸货中",
    VoyageStatus.completed: "已完成",
    VoyageStatus.delayed: "延期中",
    VoyageStatus.cancelled: "已取消",
}


class VoyageSchedule(BaseModel):
    voyage_id: str
    ship_id: str
    ship_name: str = ""
    grain_type: GrainType
    grain_weight: float
    origin_port: str
    destination_port: str
    priority: VoyagePriority = VoyagePriority.normal
    status: VoyageStatus = VoyageStatus.pending
    planned_departure_date: date
    planned_arrival_date: date
    actual_departure_date: Optional[date] = None
    actual_arrival_date: Optional[date] = None
    voyage_days: int
    sea_state: SeaState = SeaState.calm
    humidity: Optional[float] = None
    loading_order: LoadingOrder = LoadingOrder.even
    layers: int = 6
    risk_score: float = 0.0
    risk_level: WarningLevel = WarningLevel.normal
    has_unresolved_high_risk: bool = False
    warning_count: int = 0
    high_risk_warning_count: int = 0
    disposal_progress: float = 0.0
    scheme_id: Optional[str] = None
    scheme_result: Optional[SimulationResult] = None
    delay_days: int = 0
    delay_reason: str = ""
    note: str = ""


class ScheduleConflict(BaseModel):
    conflict_id: str
    conflict_type: str
    severity: WarningLevel
    description: str
    involved_voyages: List[str]
    involved_ships: List[str]
    involved_ports: List[str]
    suggestion: str = ""


class PortCongestionInfo(BaseModel):
    port_id: str
    port_name: str
    current_berth_usage: float
    waiting_voyages: int
    estimated_wait_days: float
    congestion_level: str


class ResourceShortage(BaseModel):
    resource_type: str
    shortage_amount: float
    severity: WarningLevel
    description: str
    affected_voyages: List[str]


class DispatchRecommendation(BaseModel):
    recommendation_id: str
    voyage_id: str
    ship_id: str
    recommended_action: str
    recommended_departure_date: Optional[date] = None
    priority_score: float
    reason: str
    risk_assessment: str
    is_recommended: bool = True


class DispatchDashboard(BaseModel):
    total_ships: int
    available_ships: int
    total_voyages: int
    pending_voyages: int
    sailing_voyages: int
    completed_voyages: int
    delayed_voyages: int
    high_risk_voyages: int
    total_warnings: int
    unresolved_warnings: int
    avg_disposal_progress: float


class RiskRankItem(BaseModel):
    rank: int
    voyage_id: str
    ship_name: str
    grain_type: str
    risk_score: float
    risk_level: str
    warning_count: int
    high_risk_count: int
    has_unresolved: bool
    priority: str
    status: str


class DelayImpactItem(BaseModel):
    voyage_id: str
    ship_name: str
    grain_type: str
    original_arrival: date
    estimated_arrival: date
    delay_days: int
    delay_reason: str
    impact_level: str
    grain_loss_estimate: float
    economic_loss_estimate: float
    affected_other_voyages: List[str]
    suggestion: str


class SchedulePlanInput(BaseModel):
    target_date: Optional[date] = None
    consider_weather: bool = True
    consider_port_capacity: bool = True
    consider_ship_availability: bool = True
    high_risk_block: bool = True


class DispatchResult(BaseModel):
    dashboard: DispatchDashboard
    recommended_schedules: List[DispatchRecommendation]
    risk_ranking: List[RiskRankItem]
    delay_assessment: List[DelayImpactItem]
    conflicts: List[ScheduleConflict]
    port_congestions: List[PortCongestionInfo]
    resource_shortages: List[ResourceShortage]
    generation_time: str


class ShipCreateInput(BaseModel):
    ship_name: str
    cabin_length: float
    cabin_width: float
    cabin_height: float
    capacity_tons: float
    max_speed: float
    status: ShipStatus = ShipStatus.available
    current_port: str = ""
    crew_count: int = 0
    note: str = ""


class VoyageCreateInput(BaseModel):
    ship_id: str
    grain_type: GrainType
    grain_weight: float
    origin_port: str
    destination_port: str
    priority: VoyagePriority = VoyagePriority.normal
    planned_departure_date: date
    planned_arrival_date: date
    voyage_days: int
    sea_state: SeaState = SeaState.calm
    humidity: Optional[float] = None
    loading_order: LoadingOrder = LoadingOrder.even
    layers: int = 6
    note: str = ""


class VoyageUpdateInput(BaseModel):
    status: Optional[VoyageStatus] = None
    actual_departure_date: Optional[date] = None
    actual_arrival_date: Optional[date] = None
    delay_days: Optional[int] = None
    delay_reason: Optional[str] = None
    note: Optional[str] = None


class WeatherCreateInput(BaseModel):
    port_id: str
    forecast_date: date
    condition: WeatherCondition
    wind_level: int
    sea_state: SeaState
    visibility_km: float
    affect_voyage: bool = False


class PortCreateInput(BaseModel):
    port_name: str
    berth_count: int
    loading_rate: float
    unloading_rate: float
    storage_capacity: float
    note: str = ""


class BatchStatus(str, Enum):
    pending = "pending"
    in_transit = "in_transit"
    arrived = "arrived"
    qualified = "qualified"
    unqualified = "unqualified"


class BatchQualityLevel(str, Enum):
    excellent = "excellent"
    good = "good"
    medium = "medium"
    poor = "poor"
    critical = "critical"


class AbnormalSeverity(str, Enum):
    mild = "mild"
    moderate = "moderate"
    severe = "severe"
    critical = "critical"


class AbnormalStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    resolved = "resolved"
    closed = "closed"


class TransportIssueType(str, Enum):
    pressure_loss = "pressure_loss"
    damp = "damp"
    moldy = "moldy"
    damage = "damage"
    other = "other"


class ResponsibilityType(str, Enum):
    loading = "loading"
    transport = "transport"
    storage = "storage"
    weather = "weather"
    packaging = "packaging"
    unknown = "unknown"


BATCH_STATUS_LABELS = {
    BatchStatus.pending: "待装船",
    BatchStatus.in_transit: "运输中",
    BatchStatus.arrived: "已到港",
    BatchStatus.qualified: "合格",
    BatchStatus.unqualified: "不合格",
}

BATCH_QUALITY_LABELS = {
    BatchQualityLevel.excellent: "优秀",
    BatchQualityLevel.good: "良好",
    BatchQualityLevel.medium: "中等",
    BatchQualityLevel.poor: "较差",
    BatchQualityLevel.critical: "严重",
}

ABNORMAL_SEVERITY_LABELS = {
    AbnormalSeverity.mild: "轻微",
    AbnormalSeverity.moderate: "中等",
    AbnormalSeverity.severe: "严重",
    AbnormalSeverity.critical: "极严重",
}

ABNORMAL_STATUS_LABELS = {
    AbnormalStatus.pending: "待处理",
    AbnormalStatus.processing: "处理中",
    AbnormalStatus.resolved: "已解决",
    AbnormalStatus.closed: "已闭环",
}

TRANSPORT_ISSUE_LABELS = {
    TransportIssueType.pressure_loss: "压损",
    TransportIssueType.damp: "受潮",
    TransportIssueType.moldy: "发霉",
    TransportIssueType.damage: "破损",
    TransportIssueType.other: "其他",
}

RESPONSIBILITY_LABELS = {
    ResponsibilityType.loading: "装货方",
    ResponsibilityType.transport: "运输方",
    ResponsibilityType.storage: "仓储方",
    ResponsibilityType.weather: "不可抗力",
    ResponsibilityType.packaging: "包装方",
    ResponsibilityType.unknown: "待认定",
}


class BatchInspectionResult(BaseModel):
    inspection_id: str
    inspection_date: date
    inspector: str = ""
    moisture_rate: float = 0.0
    impurity_rate: float = 0.0
    damage_rate: float = 0.0
    moldy_rate: float = 0.0
    quality_score: float = 0.0
    quality_level: BatchQualityLevel = BatchQualityLevel.good
    note: str = ""


class BatchAbnormalRecord(BaseModel):
    abnormal_id: str
    batch_id: str
    record_date: date
    issue_type: TransportIssueType
    severity: AbnormalSeverity
    description: str = ""
    affected_weight: float = 0.0
    location: str = ""
    status: AbnormalStatus = AbnormalStatus.pending
    responsible_party: ResponsibilityType = ResponsibilityType.unknown
    disposal_action: str = ""
    disposal_result: str = ""
    disposal_date: Optional[date] = None
    recorded_by: str = ""
    created_at: str = ""


class TransportQualityRecord(BaseModel):
    record_id: str
    batch_id: str
    record_date: date
    voyage_id: str = ""
    stage: str = ""
    moisture_rate: float = 0.0
    temperature: float = 0.0
    humidity: float = 0.0
    pressure_loss_rate: float = 0.0
    damp_rate: float = 0.0
    moldy_rate: float = 0.0
    damage_rate: float = 0.0
    bag_status: BagCheckStatus = BagCheckStatus.normal
    quality_score: float = 0.0
    quality_level: BatchQualityLevel = BatchQualityLevel.good
    operator: str = ""
    note: str = ""
    created_at: str = ""


class GrainBatch(BaseModel):
    batch_id: str
    batch_code: str
    grain_type: GrainType
    origin: str = ""
    origin_port: str = ""
    destination_port: str = ""
    warehouse_date: date
    initial_moisture_rate: float = 0.0
    initial_impurity_rate: float = 0.0
    total_weight: float = 0.0
    bag_count: int = 0
    loading_date: Optional[date] = None
    voyage_id: str = ""
    ship_name: str = ""
    arrival_date: Optional[date] = None
    status: BatchStatus = BatchStatus.pending
    is_qualified: bool = False
    quality_score: float = 0.0
    quality_level: BatchQualityLevel = BatchQualityLevel.good
    inspection_results: List[BatchInspectionResult] = []
    current_moisture_rate: float = 0.0
    current_damage_rate: float = 0.0
    current_moldy_rate: float = 0.0
    total_loss_weight: float = 0.0
    total_loss_rate: float = 0.0
    abnormal_count: int = 0
    severe_abnormal_count: int = 0
    unresolved_severe_abnormal: bool = False
    responsible_party: ResponsibilityType = ResponsibilityType.unknown
    warehouse_manager: str = ""
    loading_operator: str = ""
    transport_captain: str = ""
    note: str = ""
    created_at: str = ""


class BatchCreateInput(BaseModel):
    batch_code: str
    grain_type: GrainType
    origin: str = ""
    origin_port: str = ""
    destination_port: str = ""
    warehouse_date: date
    initial_moisture_rate: float = 0.0
    initial_impurity_rate: float = 0.0
    total_weight: float = 0.0
    bag_count: int = 0
    voyage_id: str = ""
    warehouse_manager: str = ""
    note: str = ""

    @field_validator("initial_moisture_rate", "initial_impurity_rate")
    @classmethod
    def rate_range(cls, v):
        if v < 0 or v > 100:
            raise ValueError("比率范围为0-100%")
        return v

    @field_validator("total_weight")
    @classmethod
    def weight_positive(cls, v):
        if v < 0:
            raise ValueError("重量不能为负数")
        return v


class BatchUpdateInput(BaseModel):
    origin: Optional[str] = None
    origin_port: Optional[str] = None
    destination_port: Optional[str] = None
    warehouse_date: Optional[date] = None
    initial_moisture_rate: Optional[float] = None
    initial_impurity_rate: Optional[float] = None
    total_weight: Optional[float] = None
    bag_count: Optional[int] = None
    loading_date: Optional[date] = None
    voyage_id: Optional[str] = None
    ship_name: Optional[str] = None
    arrival_date: Optional[date] = None
    status: Optional[BatchStatus] = None
    warehouse_manager: Optional[str] = None
    loading_operator: Optional[str] = None
    transport_captain: Optional[str] = None
    note: Optional[str] = None


class BatchInspectionInput(BaseModel):
    batch_id: str
    inspection_date: date
    inspector: str = ""
    moisture_rate: float = 0.0
    impurity_rate: float = 0.0
    damage_rate: float = 0.0
    moldy_rate: float = 0.0
    note: str = ""

    @field_validator("moisture_rate", "impurity_rate", "damage_rate", "moldy_rate")
    @classmethod
    def rate_range(cls, v):
        if v < 0 or v > 100:
            raise ValueError("比率范围为0-100%")
        return v


class AbnormalRecordInput(BaseModel):
    batch_id: str
    record_date: date
    issue_type: TransportIssueType
    severity: AbnormalSeverity
    description: str = ""
    affected_weight: float = 0.0
    location: str = ""
    responsible_party: ResponsibilityType = ResponsibilityType.unknown
    recorded_by: str = ""


class AbnormalUpdateInput(BaseModel):
    status: Optional[AbnormalStatus] = None
    disposal_action: Optional[str] = None
    disposal_result: Optional[str] = None
    disposal_date: Optional[date] = None
    severity: Optional[AbnormalSeverity] = None
    responsible_party: Optional[ResponsibilityType] = None


class TransportRecordInput(BaseModel):
    batch_id: str
    record_date: date
    voyage_id: str = ""
    stage: str = ""
    moisture_rate: float = 0.0
    temperature: float = 0.0
    humidity: float = 0.0
    pressure_loss_rate: float = 0.0
    damp_rate: float = 0.0
    moldy_rate: float = 0.0
    damage_rate: float = 0.0
    bag_status: BagCheckStatus = BagCheckStatus.normal
    operator: str = ""
    note: str = ""

    @field_validator("moisture_rate", "humidity", "pressure_loss_rate", "damp_rate", "moldy_rate", "damage_rate")
    @classmethod
    def rate_range(cls, v):
        if v < 0 or v > 100:
            raise ValueError("比率范围为0-100%")
        return v


class QualityTrendPoint(BaseModel):
    record_date: date
    quality_score: float
    quality_level: BatchQualityLevel
    moisture_rate: float
    damage_rate: float
    moldy_rate: float
    damp_rate: float


class LossTraceItem(BaseModel):
    stage: str
    loss_weight: float
    loss_rate: float
    main_cause: str
    abnormal_count: int
    severe_count: int


class BatchQualityReport(BaseModel):
    batch_id: str
    batch_code: str
    grain_type: str
    total_weight: float
    quality_score: float
    quality_level: str
    initial_moisture_rate: float
    current_moisture_rate: float
    total_loss_weight: float
    total_loss_rate: float
    abnormal_count: int
    severe_abnormal_count: int
    unresolved_severe: bool
    quality_trend: List[QualityTrendPoint]
    loss_trace: List[LossTraceItem]
    responsible_analysis: str
    disposal_suggestion: str
    is_qualified: bool
    can_mark_qualified: bool


class BatchSearchQuery(BaseModel):
    batch_code: Optional[str] = None
    grain_type: Optional[GrainType] = None
    status: Optional[BatchStatus] = None
    origin: Optional[str] = None
    voyage_id: Optional[str] = None
    has_abnormal: Optional[bool] = None
    is_qualified: Optional[bool] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
