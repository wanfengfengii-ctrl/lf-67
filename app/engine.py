import math
from datetime import date, datetime
from typing import Optional
from app.models import (
    SimulationRequest,
    SimulationResult,
    LayerInfo,
    LoadingOrder,
    GrainType,
    SeaState,
    ComparisonItem,
    ComparisonResult,
    MitigationAdvice,
    SchemePlan,
    MultiSchemeResult,
    RecommendationStatus,
    PriorityTarget,
    BatchCompareRequest,
    BatchCell,
    BatchCompareResult,
    DailyMonitorInput,
    DailyMonitorOutput,
    WarningRecordOutput,
    WarningLevel,
    DisposalStatus,
    BagCheckStatus,
    RockingLevel,
    AbnormalEventType,
    AbnormalEventInput,
    RiskTrendPoint,
    DisposalUpdateInput,
    AbnormalReportInput,
    VoyageSummaryOutput,
    WARNING_LEVEL_LABELS,
    DISPOSAL_STATUS_LABELS,
    BAG_STATUS_LABELS,
    ROCKING_LEVEL_LABELS,
    ABNORMAL_EVENT_LABELS,
    Ship,
    ShipStatus,
    SHIP_STATUS_LABELS,
    Port,
    WeatherCondition,
    WeatherForecast,
    VoyagePriority,
    VOYAGE_PRIORITY_LABELS,
    VoyageStatus,
    VOYAGE_STATUS_LABELS,
    VoyageSchedule,
    ScheduleConflict,
    PortCongestionInfo,
    ResourceShortage,
    DispatchRecommendation,
    DispatchDashboard,
    RiskRankItem,
    DelayImpactItem,
    SchedulePlanInput,
    DispatchResult,
    ShipCreateInput,
    PortCreateInput,
    VoyageCreateInput,
    VoyageUpdateInput,
    WeatherCreateInput,
    BatchStatus,
    BatchQualityLevel,
    AbnormalSeverity,
    AbnormalStatus,
    TransportIssueType,
    ResponsibilityType,
    BATCH_STATUS_LABELS,
    BATCH_QUALITY_LABELS,
    ABNORMAL_SEVERITY_LABELS,
    ABNORMAL_STATUS_LABELS,
    TRANSPORT_ISSUE_LABELS,
    RESPONSIBILITY_LABELS,
    BatchInspectionResult,
    BatchAbnormalRecord,
    TransportQualityRecord,
    GrainBatch,
    BatchCreateInput,
    BatchUpdateInput,
    BatchInspectionInput,
    AbnormalRecordInput,
    AbnormalUpdateInput,
    TransportRecordInput,
    QualityTrendPoint,
    LossTraceItem,
    BatchQualityReport,
    BatchSearchQuery,
)

GRAIN_DENSITY_FACTOR = {
    GrainType.rice: 1.0,
    GrainType.wheat: 1.05,
    GrainType.millet: 0.85,
    GrainType.sorghum: 0.95,
    GrainType.soybean: 1.10,
}

GRAIN_MOISTURE_SENSITIVITY = {
    GrainType.rice: 0.8,
    GrainType.wheat: 0.6,
    GrainType.millet: 0.9,
    GrainType.sorghum: 0.7,
    GrainType.soybean: 0.75,
}

GRAIN_COMPRESSION_RESISTANCE = {
    GrainType.rice: 5.0,
    GrainType.wheat: 5.5,
    GrainType.millet: 4.0,
    GrainType.sorghum: 4.8,
    GrainType.soybean: 5.2,
}

GRAIN_NAME_CN = {
    GrainType.rice: "稻米",
    GrainType.wheat: "小麦",
    GrainType.millet: "粟米",
    GrainType.sorghum: "高粱",
    GrainType.soybean: "大豆",
}

SEA_STATE_PRESSURE_MULTIPLIER = {
    SeaState.calm: 1.0,
    SeaState.slight: 1.08,
    SeaState.moderate: 1.20,
    SeaState.rough: 1.40,
    SeaState.very_rough: 1.70,
}

SEA_STATE_SHAKING_FACTOR = {
    SeaState.calm: 0.0,
    SeaState.slight: 0.02,
    SeaState.moderate: 0.06,
    SeaState.rough: 0.12,
    SeaState.very_rough: 0.22,
}

SEA_STATE_LABELS = {
    SeaState.calm: "平静",
    SeaState.slight: "轻微摇晃",
    SeaState.moderate: "中等摇晃",
    SeaState.rough: "剧烈摇晃",
    SeaState.very_rough: "极端摇晃",
}

LOADING_ORDER_LABELS = {
    LoadingOrder.bottom_heavy: "底层加重",
    LoadingOrder.top_heavy: "顶层加重",
    LoadingOrder.even: "均匀分布",
    LoadingOrder.pyramid: "金字塔式",
}

MAX_SAFE_LAYERS = 8
CRITICAL_LAYERS = 12
CRITICAL_PRESSURE_KPA = 6.0
WARN_PRESSURE_KPA = 3.5
HIGH_LOSS_THRESHOLD = 10.0
MEDIUM_LOSS_THRESHOLD = 5.0


def _calculate_bags_per_layer(req: SimulationRequest) -> int:
    x_count = int(req.cabin.length // req.bag.length)
    y_count = int(req.cabin.width // req.bag.width)
    if x_count <= 0 or y_count <= 0:
        return 0
    return x_count * y_count


def _max_possible_layers(req: SimulationRequest) -> int:
    by_height = int(req.cabin.height // req.bag.height)
    cabin_vol = req.cabin.length * req.cabin.width * req.cabin.height
    bag_vol = req.bag.length * req.bag.width * req.bag.height
    bags_per_layer = _calculate_bags_per_layer(req)
    if bags_per_layer <= 0:
        return 0
    by_volume = int(cabin_vol / (bag_vol * bags_per_layer))
    return max(1, min(by_height, by_volume, CRITICAL_LAYERS + 4))


def _loading_order_factor(order: LoadingOrder, layer: int, total_layers: int) -> float:
    if order == LoadingOrder.bottom_heavy:
        return 1.2 - 0.4 * (layer / max(total_layers, 1))
    elif order == LoadingOrder.top_heavy:
        return 0.8 + 0.4 * (layer / max(total_layers, 1))
    elif order == LoadingOrder.pyramid:
        mid = total_layers / 2
        dist = abs(layer - mid) / max(mid, 1)
        return 1.0 + 0.2 * (1 - dist)
    else:
        return 1.0


def _calculate_layer_pressure(
    req: SimulationRequest, layer_idx: int, total_layers: int
) -> float:
    layers_above = total_layers - layer_idx - 1
    density_factor = GRAIN_DENSITY_FACTOR[req.grain_type]
    order_factor = _loading_order_factor(req.loading_order, layer_idx, total_layers)
    sea_factor = SEA_STATE_PRESSURE_MULTIPLIER.get(req.sea_state, 1.0)
    base_weight = req.bag.weight * density_factor * 9.81 / 1000.0
    pressure = base_weight * layers_above * order_factor * sea_factor
    return pressure


def _calculate_moisture_risk(
    req: SimulationRequest, layer_idx: int, total_layers: int
) -> float:
    if req.humidity is None:
        return 0.0
    base_moisture = req.humidity / 100.0
    sensitivity = GRAIN_MOISTURE_SENSITIVITY[req.grain_type]
    bottom_factor = 1.0 - 0.3 * (layer_idx / max(total_layers - 1, 1))
    time_factor = 1.0 + 0.02 * (req.voyage_days - 1)
    risk = base_moisture * sensitivity * bottom_factor * min(time_factor, 2.0)
    return min(risk, 1.0)


def _moisture_risk_level(score: float) -> str:
    if score < 0.2:
        return "低风险"
    elif score < 0.5:
        return "中等风险"
    elif score < 0.75:
        return "高风险"
    else:
        return "极高风险"


def _generate_mitigation_advice(
    req: SimulationRequest, result: SimulationResult
) -> MitigationAdvice:
    advice = MitigationAdvice()

    if result.bottom_pressure_kpa > CRITICAL_PRESSURE_KPA:
        advice.pressure_advice.append(
            f"底层承压({result.bottom_pressure_kpa:.2f}kPa)严重超标，必须减少堆码层数至{max(1, req.layers - 3)}层以下"
        )
        advice.pressure_advice.append("建议在底层铺设承重木板或钢架分散压力")
    elif result.bottom_pressure_kpa > WARN_PRESSURE_KPA:
        advice.pressure_advice.append(
            f"底层承压({result.bottom_pressure_kpa:.2f}kPa)偏高，建议减少1-2层或改用金字塔式装载"
        )

    if result.avg_pressure_kpa > WARN_PRESSURE_KPA * 0.7:
        advice.pressure_advice.append(
            "平均承压较高，建议采用底层加重方式降低上层压力传导"
        )

    if result.moisture_risk_score > 0.6:
        advice.moisture_advice.append(
            f"受潮风险极高(风险指数{result.moisture_risk_score:.3f})，必须加装除湿设备，舱内放置干燥剂"
        )
        advice.moisture_advice.append("建议在粮包之间铺设防潮隔层，底部垫高10cm以上")
    elif result.moisture_risk_score > 0.35:
        advice.moisture_advice.append(
            f"受潮风险中等(风险指数{result.moisture_risk_score:.3f})，建议舱内通风并放置干燥剂"
        )
        advice.moisture_advice.append("粮包底部使用托盘或木条架空防潮")
    elif req.humidity is not None and req.humidity > 70:
        advice.moisture_advice.append("环境湿度较高，航行期间每日检查舱内结露情况")

    if result.estimated_loss_rate > HIGH_LOSS_THRESHOLD:
        advice.loss_advice.append(
            f"预计损耗率({result.estimated_loss_rate:.2f}%)超出阈值，强烈建议优化装载方案"
        )
        advice.loss_advice.append("可考虑分装多舱或减少载量以降低单位承压")
    elif result.estimated_loss_rate > (req.max_loss_rate or HIGH_LOSS_THRESHOLD):
        advice.loss_advice.append(
            f"预计损耗率({result.estimated_loss_rate:.2f}%)超过允许值({req.max_loss_rate:.2f}%)，需调整层数或装载方式"
        )
    elif result.estimated_loss_rate > MEDIUM_LOSS_THRESHOLD:
        advice.loss_advice.append(
            f"预计损耗率({result.estimated_loss_rate:.2f}%)中等，航行中加强监控可进一步降低"
        )

    if req.sea_state in (SeaState.rough, SeaState.very_rough):
        advice.stability_advice.append(
            f"海况恶劣（{SEA_STATE_LABELS[req.sea_state]}），必须加固绑绳，舱内加设防移挡板"
        )
        advice.stability_advice.append("航行中降低航速，避免剧烈横摇")
    elif req.sea_state == SeaState.moderate:
        advice.stability_advice.append(
            "海况存在摇晃，建议粮包之间使用角铁或木楔固定"
        )

    if req.layers >= CRITICAL_LAYERS:
        advice.stability_advice.append(f"堆码{req.layers}层过高，倒塌风险极大，必须降低层数")
    elif req.layers >= MAX_SAFE_LAYERS:
        advice.stability_advice.append(f"堆码{req.layers}层偏高，建议加装顶部压袋网防止滑落")

    if result.capacity_used_pct > 90:
        advice.general_advice.append(
            f"船舱使用率({result.capacity_used_pct:.1f}%)接近满载，预留通风空间不足"
        )
    elif result.capacity_used_pct < 50:
        advice.general_advice.append(
            f"船舱使用率({result.capacity_used_pct:.1f}%)较低，可考虑合并批次提高效率"
        )

    grain_name = GRAIN_NAME_CN.get(req.grain_type, "粮食")
    if req.voyage_days > 20:
        advice.general_advice.append(
            f"航程{req.voyage_days}天较长，{grain_name}品质衰减风险增加，建议投保运输险"
        )

    if req.humidity is None:
        advice.general_advice.append(
            "⚠ 湿度数据缺失，当前为非正式评估，补充湿度后可生成正式方案"
        )

    if not advice.pressure_advice and not advice.moisture_advice and not advice.loss_advice and not advice.stability_advice:
        advice.general_advice.append("方案参数合理，按常规装载作业流程执行即可")
        advice.general_advice.append("建议装载后抽样检查底层粮包完整性，启航前确认绑固措施")

    return advice


def _calculate_feasibility_score(
    req: SimulationRequest, result: SimulationResult
) -> float:
    score = 100.0

    score -= min(30, result.estimated_loss_rate * 2.0)

    if result.moisture_risk_score > 0.5:
        score -= (result.moisture_risk_score - 0.5) * 60
    elif result.moisture_risk_score > 0.3:
        score -= (result.moisture_risk_score - 0.3) * 30

    if result.bottom_pressure_kpa > WARN_PRESSURE_KPA:
        score -= (result.bottom_pressure_kpa - WARN_PRESSURE_KPA) * 8
    if result.bottom_pressure_kpa > CRITICAL_PRESSURE_KPA:
        score -= 30

    if req.layers > MAX_SAFE_LAYERS:
        score -= (req.layers - MAX_SAFE_LAYERS) * 5

    sea_penalty = {
        SeaState.calm: 0,
        SeaState.slight: 2,
        SeaState.moderate: 6,
        SeaState.rough: 15,
        SeaState.very_rough: 25,
    }
    score -= sea_penalty.get(req.sea_state, 0)

    if result.capacity_used_pct > 95:
        score -= 10
    elif result.capacity_used_pct < 30:
        score -= 5

    if not result.is_formal_assessment:
        score -= 10

    return max(0.0, min(100.0, round(score, 2)))


def simulate(req: SimulationRequest) -> SimulationResult:
    warnings = []
    bags_per_layer = _calculate_bags_per_layer(req)
    total_bags = bags_per_layer * req.layers

    cabin_vol = req.cabin.length * req.cabin.width * req.cabin.height
    bag_vol = req.bag.length * req.bag.width * req.bag.height
    capacity_used = (total_bags * bag_vol) / cabin_vol * 100

    if capacity_used > 95:
        warnings.append(f"船舱容量使用率过高({capacity_used:.1f}%)，接近满载")

    if req.layers >= CRITICAL_LAYERS:
        warnings.append(f"堆码层数({req.layers}层)严重过高，存在倒塌风险！")
    elif req.layers >= MAX_SAFE_LAYERS:
        warnings.append(f"堆码层数({req.layers}层)较高，建议降低层数")

    if req.humidity is None:
        warnings.append("湿度数据缺失，无法生成正式损耗评估")

    sea_label = SEA_STATE_LABELS.get(req.sea_state, "未知")
    if req.sea_state in (SeaState.rough, SeaState.very_rough):
        warnings.append(f"海况恶劣（{sea_label}），粮包压损与倒塌风险显著增加")
    elif req.sea_state == SeaState.moderate:
        warnings.append(f"海况存在摇晃（{sea_label}），需关注堆码稳定性")

    layer_details = []
    total_pressure = 0.0
    bottom_pressure = 0.0
    max_compression = 0.0
    total_moisture_risk = 0.0

    for i in range(req.layers):
        pressure = _calculate_layer_pressure(req, i, req.layers)
        moisture = _calculate_moisture_risk(req, i, req.layers)

        resistance = GRAIN_COMPRESSION_RESISTANCE[req.grain_type]
        compression = max(0, (pressure / max(resistance, 0.01)) - 0.3) * 0.1
        max_compression = max(max_compression, compression)

        if i == 0:
            bottom_pressure = pressure

        total_pressure += pressure
        total_moisture_risk += moisture

        layer_details.append(
            LayerInfo(
                layer=i + 1,
                bags_count=bags_per_layer,
                pressure_kpa=round(pressure, 3),
                moisture_risk=round(moisture, 4),
            )
        )

    avg_pressure = total_pressure / max(req.layers, 1)
    avg_moisture = total_moisture_risk / max(req.layers, 1)

    pressure_loss = max_compression * 0.6
    moisture_loss = avg_moisture * 0.15
    time_loss = 0.001 * req.voyage_days
    shaking_loss = SEA_STATE_SHAKING_FACTOR.get(req.sea_state, 0.0) * (req.layers / MAX_SAFE_LAYERS)

    if req.humidity is None:
        estimated_loss = pressure_loss + time_loss + shaking_loss
    else:
        estimated_loss = pressure_loss + moisture_loss + time_loss + shaking_loss

    estimated_loss = min(round(estimated_loss * 100, 2), 100.0)
    moisture_risk_score = round(avg_moisture, 4)

    has_severe_warning = any("严重" in w or "超出" in w or "倒塌" in w for w in warnings)
    is_high_risk = estimated_loss > 10 or moisture_risk_score > 0.6 or req.sea_state == SeaState.very_rough or bottom_pressure > CRITICAL_PRESSURE_KPA
    can_execute = not is_high_risk and not has_severe_warning

    max_loss = req.max_loss_rate or HIGH_LOSS_THRESHOLD
    if estimated_loss > max_loss:
        warnings.append(f"预计损耗率({estimated_loss:.2f}%)超过最大允许值({max_loss:.2f}%)")

    if req.max_layers is not None and req.layers > req.max_layers:
        warnings.append(f"堆码层数({req.layers})超过设定的最大层数({req.max_layers})")
        is_high_risk = True
        can_execute = False

    is_formal = req.humidity is not None

    if is_high_risk:
        warnings.append("⚠ 该方案为高风险方案，不得作为正式推荐方案")

    result = SimulationResult(
        total_bags=total_bags,
        bottom_pressure_kpa=round(bottom_pressure, 3),
        avg_pressure_kpa=round(avg_pressure, 3),
        max_compression_ratio=round(max_compression, 4),
        moisture_risk_level=_moisture_risk_level(moisture_risk_score),
        moisture_risk_score=moisture_risk_score,
        estimated_loss_rate=estimated_loss,
        layer_details=layer_details,
        warnings=warnings,
        is_high_risk=is_high_risk,
        can_execute=can_execute,
        capacity_used_pct=round(min(capacity_used, 100), 1),
        is_formal_assessment=is_formal,
    )

    result.mitigation_advice = _generate_mitigation_advice(req, result)
    result.feasibility_score = _calculate_feasibility_score(req, result)

    return result


def compare_schemes(req: SimulationRequest) -> ComparisonResult:
    items = []
    best_order = LoadingOrder.even
    best_loss = float("inf")

    for order in LoadingOrder:
        mod_req = req.model_copy(update={"loading_order": order})
        result = simulate(mod_req)
        items.append(ComparisonItem(loading_order=order, result=result))
        if result.estimated_loss_rate < best_loss:
            best_loss = result.estimated_loss_rate
            best_order = order

    return ComparisonResult(
        items=items,
        best_order=best_order,
        best_loss_rate=best_loss,
        is_formal_assessment=req.humidity is not None,
    )


def _score_scheme_by_priority(
    plan: SchemePlan, priority: PriorityTarget, result: SimulationResult,
    layers: int, bags_per_layer: int
) -> float:
    if priority == PriorityTarget.min_loss:
        loss_score = max(0, 100 - result.estimated_loss_rate * 8)
        return 0.5 * loss_score + 0.3 * result.feasibility_score + 0.2 * (100 - result.bottom_pressure_kpa * 10)
    elif priority == PriorityTarget.max_capacity:
        capacity_score = result.capacity_used_pct
        return 0.5 * capacity_score + 0.2 * result.feasibility_score + 0.3 * max(0, 100 - result.estimated_loss_rate * 5)
    elif priority == PriorityTarget.min_pressure:
        press_score = max(0, 100 - result.bottom_pressure_kpa * 15)
        layer_score = max(0, 100 - layers * 5)
        return 0.5 * press_score + 0.2 * layer_score + 0.3 * result.feasibility_score
    else:
        return 0.3 * result.feasibility_score + 0.25 * max(0, 100 - result.estimated_loss_rate * 6) + 0.2 * result.capacity_used_pct + 0.25 * max(0, 100 - result.bottom_pressure_kpa * 10)


def generate_multi_schemes(req: SimulationRequest) -> MultiSchemeResult:
    schemes = []
    max_layers_allowed = req.max_layers if req.max_layers else _max_possible_layers(req)
    max_loss = req.max_loss_rate or HIGH_LOSS_THRESHOLD

    base_layers = req.layers
    layer_candidates = set()
    for delta in [-3, -2, -1, 0, 1, 2]:
        candidate = base_layers + delta
        if 1 <= candidate <= max_layers_allowed:
            layer_candidates.add(candidate)
    layer_candidates.add(max(1, min(base_layers, max_layers_allowed)))

    scheme_idx = 0
    for layers in sorted(layer_candidates):
        for order in LoadingOrder:
            try:
                mod_req = req.model_copy(update={
                    "layers": layers,
                    "loading_order": order,
                })
                result = simulate(mod_req)
            except ValueError:
                continue

            bags_per_layer = _calculate_bags_per_layer(mod_req)
            total_bags = bags_per_layer * layers

            is_formal = req.humidity is not None
            is_high_risk = result.is_high_risk
            loss_over = result.estimated_loss_rate > max_loss

            if is_high_risk:
                status = RecommendationStatus.high_risk
            elif not is_formal:
                status = RecommendationStatus.informal
            elif loss_over:
                status = RecommendationStatus.alternative
            elif result.can_execute and result.feasibility_score >= 60:
                status = RecommendationStatus.recommended
            else:
                status = RecommendationStatus.alternative

            score = _score_scheme_by_priority(
                SchemePlan(
                    scheme_id="", scheme_name="", loading_order=order,
                    layers=layers, bags_per_layer=bags_per_layer, total_bags=total_bags,
                    result=result, status=status, score=0
                ),
                req.priority_target, result, layers, bags_per_layer
            )

            scheme_idx += 1
            order_label = LOADING_ORDER_LABELS[order]
            scheme_name = f"{layers}层 · {order_label}"
            scheme_id = f"scheme_{scheme_idx:03d}_{layers}_{order.value}"

            schemes.append(SchemePlan(
                scheme_id=scheme_id,
                scheme_name=scheme_name,
                loading_order=order,
                layers=layers,
                bags_per_layer=bags_per_layer,
                total_bags=total_bags,
                result=result,
                status=status,
                score=round(score, 2),
            ))

    def sort_key(s):
        status_rank = {
            RecommendationStatus.recommended: 0,
            RecommendationStatus.alternative: 1,
            RecommendationStatus.informal: 2,
            RecommendationStatus.high_risk: 3,
        }
        return (status_rank[s.status], -s.score)

    schemes.sort(key=sort_key)
    for i, s in enumerate(schemes):
        s.rank = i + 1

    recommended = [s for s in schemes if s.status == RecommendationStatus.recommended]
    best_scheme_id = recommended[0].scheme_id if recommended else (
        schemes[0].scheme_id if schemes else None
    )

    return MultiSchemeResult(
        schemes=schemes,
        recommended_count=sum(1 for s in schemes if s.status == RecommendationStatus.recommended),
        alternative_count=sum(1 for s in schemes if s.status == RecommendationStatus.alternative),
        high_risk_count=sum(1 for s in schemes if s.status == RecommendationStatus.high_risk),
        informal_count=sum(1 for s in schemes if s.status == RecommendationStatus.informal),
        best_scheme_id=best_scheme_id,
        is_formal_assessment=req.humidity is not None,
        priority_target=req.priority_target,
    )


def batch_compare(req: BatchCompareRequest) -> BatchCompareResult:
    humidity_values = req.humidity_values
    sea_state_values = req.sea_state_values

    max_layers_allowed = req.max_layers if req.max_layers else _max_possible_layers(
        SimulationRequest(
            cabin=req.cabin, bag=req.bag, layers=1, grain_type=req.grain_type,
            voyage_days=req.voyage_days, loading_order=req.loading_order,
        )
    )
    layers_to_use = req.layers if req.layers else min(max_layers_allowed, 6)

    cells = []
    best_loss = float("inf")
    best_cell_info = None
    is_any_formal = False

    for row_idx, h in enumerate(humidity_values):
        row = []
        for col_idx, ss in enumerate(sea_state_values):
            try:
                sim_req = SimulationRequest(
                    cabin=req.cabin,
                    bag=req.bag,
                    layers=layers_to_use,
                    grain_type=req.grain_type,
                    humidity=h,
                    voyage_days=req.voyage_days,
                    loading_order=req.loading_order,
                    sea_state=ss,
                    max_loss_rate=req.max_loss_rate,
                    max_layers=req.max_layers,
                    priority_target=req.priority_target,
                )
                result = simulate(sim_req)
                is_formal = True
                is_any_formal = True
                cell = BatchCell(
                    humidity=h,
                    sea_state=ss,
                    result=result,
                    is_high_risk=result.is_high_risk,
                    is_formal=is_formal,
                )
                if not result.is_high_risk and result.estimated_loss_rate < best_loss:
                    best_loss = result.estimated_loss_rate
                    best_cell_info = {
                        "humidity": h,
                        "sea_state": ss.value,
                        "loss_rate": result.estimated_loss_rate,
                        "row": row_idx,
                        "col": col_idx,
                    }
            except ValueError as e:
                cell = BatchCell(
                    humidity=h,
                    sea_state=ss,
                    error=str(e),
                    is_high_risk=True,
                    is_formal=True,
                )
            row.append(cell)
        cells.append(row)

    return BatchCompareResult(
        humidity_values=humidity_values,
        sea_state_values=sea_state_values,
        cells=cells,
        best_cell=best_cell_info,
        is_any_formal=is_any_formal,
    )


_monitor_store: dict = {}
_warning_store: dict = {}
_record_counter = 0
_warning_counter = 0


def _next_record_id():
    global _record_counter
    _record_counter += 1
    return f"rec_{_record_counter:05d}"


def _next_warning_id():
    global _warning_counter
    _warning_counter += 1
    return f"warn_{_warning_counter:05d}"


ROCKING_RISK_SCORE = {
    RockingLevel.calm: 0.0,
    RockingLevel.slight: 0.15,
    RockingLevel.moderate: 0.35,
    RockingLevel.rough: 0.65,
    RockingLevel.very_rough: 0.90,
}

BAG_STATUS_RISK_SCORE = {
    BagCheckStatus.normal: 0.0,
    BagCheckStatus.compressed: 0.3,
    BagCheckStatus.damp: 0.5,
    BagCheckStatus.moldy: 0.7,
    BagCheckStatus.damaged: 0.85,
}

HUMIDITY_RISK_THRESHOLD_LOW = 55.0
HUMIDITY_RISK_THRESHOLD_MED = 70.0
HUMIDITY_RISK_THRESHOLD_HIGH = 85.0
TEMP_RISK_THRESHOLD_LOW = 28.0
TEMP_RISK_THRESHOLD_MED = 33.0
TEMP_RISK_THRESHOLD_HIGH = 38.0


def _calculate_pressure_risk(rocking_level: RockingLevel, bag_status: BagCheckStatus) -> float:
    base = ROCKING_RISK_SCORE.get(rocking_level, 0.0)
    bag_factor = BAG_STATUS_RISK_SCORE.get(bag_status, 0.0)
    return min(1.0, base * 0.6 + bag_factor * 0.4) if bag_status == BagCheckStatus.compressed else base * 0.7


def _calculate_moisture_risk_monitor(humidity: float, temperature: float, bag_status: BagCheckStatus) -> float:
    hum_score = 0.0
    if humidity >= HUMIDITY_RISK_THRESHOLD_HIGH:
        hum_score = 0.9
    elif humidity >= HUMIDITY_RISK_THRESHOLD_MED:
        hum_score = 0.6
    elif humidity >= HUMIDITY_RISK_THRESHOLD_LOW:
        hum_score = 0.3

    temp_score = 0.0
    if temperature >= TEMP_RISK_THRESHOLD_HIGH:
        temp_score = 0.8
    elif temperature >= TEMP_RISK_THRESHOLD_MED:
        temp_score = 0.5
    elif temperature >= TEMP_RISK_THRESHOLD_LOW:
        temp_score = 0.2

    bag_factor = 0.0
    if bag_status in (BagCheckStatus.damp, BagCheckStatus.moldy):
        bag_factor = BAG_STATUS_RISK_SCORE.get(bag_status, 0.0) * 0.5

    return min(1.0, hum_score * 0.5 + temp_score * 0.25 + bag_factor * 0.25)


def _calculate_shake_risk(rocking_level: RockingLevel) -> float:
    return ROCKING_RISK_SCORE.get(rocking_level, 0.0)


def _compute_risk_score(
    humidity: float, temperature: float, rocking_level: RockingLevel,
    bag_status: BagCheckStatus
) -> tuple:
    pressure_risk = _calculate_pressure_risk(rocking_level, bag_status)
    moisture_risk = _calculate_moisture_risk_monitor(humidity, temperature, bag_status)
    shake_risk = _calculate_shake_risk(rocking_level)

    composite = pressure_risk * 0.3 + moisture_risk * 0.4 + shake_risk * 0.3
    return round(min(1.0, composite), 4), pressure_risk, moisture_risk, shake_risk


def _risk_score_to_warning_level(score: float) -> WarningLevel:
    if score < 0.2:
        return WarningLevel.normal
    elif score < 0.4:
        return WarningLevel.low
    elif score < 0.6:
        return WarningLevel.medium
    elif score < 0.8:
        return WarningLevel.high
    else:
        return WarningLevel.critical


def _generate_warnings_for_record(
    voyage_id: str, rec_date: date, humidity: float, temperature: float,
    rocking_level: RockingLevel, bag_status: BagCheckStatus,
    risk_score: float, pressure_risk: float, moisture_risk: float,
    shake_risk: float, abnormal_events: list
) -> list:
    warnings = []

    if humidity >= HUMIDITY_RISK_THRESHOLD_HIGH:
        warnings.append(WarningRecordOutput(
            warning_id=_next_warning_id(),
            voyage_id=voyage_id,
            record_date=rec_date,
            warning_level=WarningLevel.high if humidity < 92 else WarningLevel.critical,
            warning_type="humidity_spike",
            warning_message=f"舱内湿度{humidity}%严重超标（阈值{HUMIDITY_RISK_THRESHOLD_HIGH}%），受潮扩散风险极高",
            risk_score=moisture_risk,
        ))
    elif humidity >= HUMIDITY_RISK_THRESHOLD_MED:
        warnings.append(WarningRecordOutput(
            warning_id=_next_warning_id(),
            voyage_id=voyage_id,
            record_date=rec_date,
            warning_level=WarningLevel.medium,
            warning_type="humidity_spike",
            warning_message=f"舱内湿度{humidity}%偏高（阈值{HUMIDITY_RISK_THRESHOLD_MED}%），需加强通风和除湿",
            risk_score=moisture_risk,
        ))

    if temperature >= TEMP_RISK_THRESHOLD_HIGH:
        warnings.append(WarningRecordOutput(
            warning_id=_next_warning_id(),
            voyage_id=voyage_id,
            record_date=rec_date,
            warning_level=WarningLevel.critical,
            warning_type="temp_spike",
            warning_message=f"舱内温度{temperature}°C严重超标（阈值{TEMP_RISK_THRESHOLD_HIGH}°C），粮食品质快速衰减",
            risk_score=moisture_risk,
        ))
    elif temperature >= TEMP_RISK_THRESHOLD_MED:
        warnings.append(WarningRecordOutput(
            warning_id=_next_warning_id(),
            voyage_id=voyage_id,
            record_date=rec_date,
            warning_level=WarningLevel.medium,
            warning_type="temp_spike",
            warning_message=f"舱内温度{temperature}°C偏高（阈值{TEMP_RISK_THRESHOLD_MED}°C），需关注粮温变化",
            risk_score=moisture_risk * 0.6,
        ))

    if rocking_level in (RockingLevel.rough, RockingLevel.very_rough):
        warnings.append(WarningRecordOutput(
            warning_id=_next_warning_id(),
            voyage_id=voyage_id,
            record_date=rec_date,
            warning_level=WarningLevel.high if rocking_level == RockingLevel.rough else WarningLevel.critical,
            warning_type="hull_shake",
            warning_message=f"船体摇晃等级{ROCKING_LEVEL_LABELS[rocking_level]}，粮包移位和压损恶化风险显著",
            risk_score=shake_risk,
        ))

    if bag_status == BagCheckStatus.compressed:
        warnings.append(WarningRecordOutput(
            warning_id=_next_warning_id(),
            voyage_id=voyage_id,
            record_date=rec_date,
            warning_level=WarningLevel.medium,
            warning_type="pressure_worsen",
            warning_message="抽检发现粮包压损变形，底层承压可能超标，需检查堆码稳定性",
            risk_score=pressure_risk,
        ))
    elif bag_status == BagCheckStatus.damp:
        warnings.append(WarningRecordOutput(
            warning_id=_next_warning_id(),
            voyage_id=voyage_id,
            record_date=rec_date,
            warning_level=WarningLevel.high,
            warning_type="moisture_spread",
            warning_message="抽检发现粮包受潮，受潮区域可能正在扩散，需紧急处置",
            risk_score=moisture_risk,
        ))
    elif bag_status == BagCheckStatus.moldy:
        warnings.append(WarningRecordOutput(
            warning_id=_next_warning_id(),
            voyage_id=voyage_id,
            record_date=rec_date,
            warning_level=WarningLevel.critical,
            warning_type="moisture_spread",
            warning_message="抽检发现粮包发霉，品质已受损，必须立即处置防止扩散",
            risk_score=moisture_risk,
        ))
    elif bag_status == BagCheckStatus.damaged:
        warnings.append(WarningRecordOutput(
            warning_id=_next_warning_id(),
            voyage_id=voyage_id,
            record_date=rec_date,
            warning_level=WarningLevel.high,
            warning_type="bag_damage",
            warning_message="抽检发现粮包破损，粮食散漏风险增大，需加固补包",
            risk_score=0.6,
        ))

    for evt in abnormal_events:
        evt_type = evt.get("event_type", evt.event_type if hasattr(evt, "event_type") else "other")
        evt_desc = evt.get("description", evt.description if hasattr(evt, "description") else "")
        evt_label = ABNORMAL_EVENT_LABELS.get(AbnormalEventType(evt_type), evt_type) if isinstance(evt_type, str) else str(evt_type)
        if evt_type in ("water_leak", "pressure_worsen"):
            lvl = WarningLevel.critical
        elif evt_type in ("moisture_spread", "bag_damage"):
            lvl = WarningLevel.high
        else:
            lvl = WarningLevel.medium
        warnings.append(WarningRecordOutput(
            warning_id=_next_warning_id(),
            voyage_id=voyage_id,
            record_date=rec_date,
            warning_level=lvl,
            warning_type=evt_type,
            warning_message=f"异常事件：{evt_label}" + (f" - {evt_desc}" if evt_desc else ""),
            risk_score=risk_score,
        ))

    return warnings


def _detect_trend_anomalies(records: list) -> list:
    anomalies = []
    if len(records) < 2:
        return anomalies

    sorted_recs = sorted(records, key=lambda r: r["record_date"])
    for i in range(1, len(sorted_recs)):
        prev = sorted_recs[i - 1]
        curr = sorted_recs[i]

        hum_delta = curr["cabin_humidity"] - prev["cabin_humidity"]
        if hum_delta > 15:
            anomalies.append({
                "type": "humidity_spike",
                "date": str(curr["record_date"]),
                "message": f"湿度日增幅{hum_delta:.1f}%（{prev['cabin_humidity']:.1f}%→{curr['cabin_humidity']:.1f}%），异常波动",
            })

        temp_delta = curr["cabin_temperature"] - prev["cabin_temperature"]
        if temp_delta > 8:
            anomalies.append({
                "type": "temp_spike",
                "date": str(curr["record_date"]),
                "message": f"温度日增幅{temp_delta:.1f}°C（{prev['cabin_temperature']:.1f}°C→{curr['cabin_temperature']:.1f}°C），异常波动",
            })

        prev_risk = prev.get("risk_score", 0)
        curr_risk = curr.get("risk_score", 0)
        risk_delta = curr_risk - prev_risk
        if risk_delta > 0.25:
            anomalies.append({
                "type": "risk_surge",
                "date": str(curr["record_date"]),
                "message": f"风险指数日增幅{risk_delta:.2f}（{prev_risk:.2f}→{curr_risk:.2f}），风险快速恶化",
            })

        prev_bag = prev.get("bag_check_status", "normal")
        curr_bag = curr.get("bag_check_status", "normal")
        bag_order = ["normal", "compressed", "damp", "moldy", "damaged"]
        if bag_order.index(curr_bag) > bag_order.index(prev_bag) + 1:
            anomalies.append({
                "type": "pressure_worsen",
                "date": str(curr["record_date"]),
                "message": f"粮包状态跨级恶化（{BAG_STATUS_LABELS.get(BagCheckStatus(prev_bag), prev_bag)}→{BAG_STATUS_LABELS.get(BagCheckStatus(curr_bag), curr_bag)}），压损恶化",
            })

    return anomalies


def _get_disposal_suggestion(warning_level: WarningLevel, warning_type: str) -> str:
    suggestions = {
        "humidity_spike": {
            WarningLevel.low: "增加通风频次，放置干燥剂",
            WarningLevel.medium: "启动除湿设备，检查舱体密封性，加强巡检至每4小时一次",
            WarningLevel.high: "紧急除湿，排查渗漏源，对受潮区域粮包加铺防潮层",
            WarningLevel.critical: "立即启动应急除湿，转移高风险粮包，上报指挥部",
        },
        "temp_spike": {
            WarningLevel.medium: "加强通风散热，检查粮温是否异常升温",
            WarningLevel.high: "启动降温设备，开舱散热（如海况允许），检查是否有自热现象",
            WarningLevel.critical: "紧急降温，排查自热或火情隐患，转移高温区域粮包",
        },
        "hull_shake": {
            WarningLevel.high: "加固绑绳和挡板，降低航速，检查堆码是否有位移",
            WarningLevel.critical: "紧急停航避风，全面检查粮包位移和损伤情况",
        },
        "pressure_worsen": {
            WarningLevel.medium: "检查底层粮包承压状况，必要时减层降压",
            WarningLevel.high: "对压损区域粮包进行抽检和补包，调整堆码结构",
        },
        "moisture_spread": {
            WarningLevel.high: "标记受潮扩散边界，对受潮粮包隔离处置，加大除湿力度",
            WarningLevel.critical: "紧急隔离发霉粮包，全面消杀，防止霉变蔓延",
        },
        "bag_damage": {
            WarningLevel.high: "对破损粮包紧急补包或换包，加固周围粮包防止连锁位移",
        },
        "water_leak": {
            WarningLevel.critical: "紧急堵漏，排水，转移浸水粮包，上报指挥部请求靠港",
        },
    }
    type_suggestions = suggestions.get(warning_type, {})
    return type_suggestions.get(warning_level, "密切关注，按规范巡检处置")


def create_daily_record(inp: DailyMonitorInput) -> DailyMonitorOutput:
    risk_score, pressure_risk, moisture_risk, shake_risk = _compute_risk_score(
        inp.cabin_humidity, inp.cabin_temperature, inp.rocking_level, inp.bag_check_status
    )

    warning_level = _risk_score_to_warning_level(risk_score)

    abnormal_dicts = [
        {"event_type": e.event_type.value, "description": e.description}
        for e in inp.abnormal_events
    ]

    generated_warnings = _generate_warnings_for_record(
        inp.voyage_id, inp.record_date, inp.cabin_humidity, inp.cabin_temperature,
        inp.rocking_level, inp.bag_check_status, risk_score, pressure_risk,
        moisture_risk, shake_risk, abnormal_dicts
    )

    record_id = _next_record_id()
    record = {
        "record_id": record_id,
        "voyage_id": inp.voyage_id,
        "record_date": inp.record_date,
        "cabin_humidity": inp.cabin_humidity,
        "cabin_temperature": inp.cabin_temperature,
        "rocking_level": inp.rocking_level.value,
        "bag_check_status": inp.bag_check_status.value,
        "bag_check_note": inp.bag_check_note,
        "abnormal_events": abnormal_dicts,
        "note": inp.note,
        "warning_level": warning_level.value,
        "risk_score": risk_score,
        "pressure_risk": pressure_risk,
        "moisture_risk": moisture_risk,
        "shake_risk": shake_risk,
        "disposal_status": DisposalStatus.pending.value,
        "transport_status": "正常",
        "created_at": datetime.now().isoformat(),
    }

    _monitor_store[record_id] = record

    for w in generated_warnings:
        w.is_high_risk_unresolved = (
            w.warning_level in (WarningLevel.high, WarningLevel.critical)
            and w.disposal_status != DisposalStatus.closed
        )
        _warning_store[w.warning_id] = w.model_dump()

    voyage_recs = [r for r in _monitor_store.values() if r["voyage_id"] == inp.voyage_id]
    anomalies = _detect_trend_anomalies(voyage_recs)
    for a in anomalies:
        a_warn = WarningRecordOutput(
            warning_id=_next_warning_id(),
            voyage_id=inp.voyage_id,
            record_date=inp.record_date,
            warning_level=WarningLevel.medium,
            warning_type=a["type"],
            warning_message=a["message"],
            risk_score=risk_score,
        )
        _warning_store[a_warn.warning_id] = a_warn.model_dump()

    _recalculate_record_status(record_id)

    all_warnings = _get_warnings_for_record(record_id)

    return DailyMonitorOutput(
        record_id=record_id,
        voyage_id=inp.voyage_id,
        record_date=inp.record_date,
        cabin_humidity=inp.cabin_humidity,
        cabin_temperature=inp.cabin_temperature,
        rocking_level=inp.rocking_level,
        bag_check_status=inp.bag_check_status,
        bag_check_note=inp.bag_check_note,
        abnormal_events=abnormal_dicts,
        note=inp.note,
        warning_level=warning_level,
        risk_score=risk_score,
        warnings=all_warnings,
        disposal_status=DisposalStatus(record["disposal_status"]),
        transport_status=record["transport_status"],
        created_at=record["created_at"],
    )


def _get_warnings_for_record(record_id: str) -> list:
    record = _monitor_store.get(record_id)
    if not record:
        return []
    return [
        WarningRecordOutput(**w) for w in _warning_store.values()
        if w.get("voyage_id") == record["voyage_id"]
        and str(w.get("record_date")) == str(record["record_date"])
    ]


def _recalculate_record_status(record_id: str) -> None:
    record = _monitor_store.get(record_id)
    if not record:
        return

    warnings = _get_warnings_for_record(record_id)

    if not warnings:
        record["disposal_status"] = DisposalStatus.closed.value
        record["transport_status"] = "正常"
        return

    level_order = {
        WarningLevel.normal: 0,
        WarningLevel.low: 1,
        WarningLevel.medium: 2,
        WarningLevel.high: 3,
        WarningLevel.critical: 4,
    }
    max_level = WarningLevel.normal
    for w in warnings:
        if level_order.get(w.warning_level, 0) > level_order.get(max_level, 0):
            max_level = w.warning_level

    if max_level in (WarningLevel.high, WarningLevel.critical):
        record["transport_status"] = "异常待处置"
    else:
        record["transport_status"] = "正常"

    status_order = {
        DisposalStatus.closed: 0,
        DisposalStatus.completed: 1,
        DisposalStatus.processing: 2,
        DisposalStatus.confirmed: 3,
        DisposalStatus.pending: 4,
    }
    worst_status = DisposalStatus.closed
    for w in warnings:
        if status_order.get(w.disposal_status, 0) > status_order.get(worst_status, 0):
            worst_status = w.disposal_status

    record["disposal_status"] = worst_status.value


def get_voyage_records(voyage_id: str) -> list:
    records = sorted(
        [r for r in _monitor_store.values() if r["voyage_id"] == voyage_id],
        key=lambda r: r["record_date"]
    )
    results = []
    for r in records:
        warnings = _get_warnings_for_record(r["record_id"])
        results.append(DailyMonitorOutput(
            record_id=r["record_id"],
            voyage_id=r["voyage_id"],
            record_date=r["record_date"],
            cabin_humidity=r["cabin_humidity"],
            cabin_temperature=r["cabin_temperature"],
            rocking_level=RockingLevel(r["rocking_level"]),
            bag_check_status=BagCheckStatus(r["bag_check_status"]),
            bag_check_note=r["bag_check_note"],
            abnormal_events=r["abnormal_events"],
            note=r["note"],
            warning_level=WarningLevel(r["warning_level"]),
            risk_score=r["risk_score"],
            warnings=warnings,
            disposal_status=DisposalStatus(r["disposal_status"]),
            transport_status=r["transport_status"],
            created_at=r["created_at"],
        ))
    return results


def get_record_detail(record_id: str) -> Optional[DailyMonitorOutput]:
    r = _monitor_store.get(record_id)
    if not r:
        return None
    warnings = _get_warnings_for_record(r["record_id"])
    return DailyMonitorOutput(
        record_id=r["record_id"],
        voyage_id=r["voyage_id"],
        record_date=r["record_date"],
        cabin_humidity=r["cabin_humidity"],
        cabin_temperature=r["cabin_temperature"],
        rocking_level=RockingLevel(r["rocking_level"]),
        bag_check_status=BagCheckStatus(r["bag_check_status"]),
        bag_check_note=r["bag_check_note"],
        abnormal_events=r["abnormal_events"],
        note=r["note"],
        warning_level=WarningLevel(r["warning_level"]),
        risk_score=r["risk_score"],
        warnings=warnings,
        disposal_status=DisposalStatus(r["disposal_status"]),
        transport_status=r["transport_status"],
        created_at=r["created_at"],
    )


def get_voyage_warnings(voyage_id: str) -> list:
    return [
        WarningRecordOutput(**w) for w in _warning_store.values()
        if w.get("voyage_id") == voyage_id
    ]


def confirm_warning(warning_id: str, confirmed: bool = True) -> Optional[WarningRecordOutput]:
    w = _warning_store.get(warning_id)
    if not w:
        return None
    if confirmed:
        w["disposal_status"] = DisposalStatus.confirmed.value
    else:
        w["disposal_status"] = DisposalStatus.pending.value
    w["is_high_risk_unresolved"] = (
        w["warning_level"] in (WarningLevel.high.value, WarningLevel.critical.value)
        and w["disposal_status"] != DisposalStatus.closed.value
    )
    _warning_store[warning_id] = w

    voyage_id = w.get("voyage_id")
    record_date = w.get("record_date")
    if voyage_id and record_date:
        for rec in _monitor_store.values():
            if rec["voyage_id"] == voyage_id and str(rec["record_date"]) == str(record_date):
                _recalculate_record_status(rec["record_id"])
                break

    return WarningRecordOutput(**w)


def update_disposal(record_id: str, upd: DisposalUpdateInput) -> Optional[DailyMonitorOutput]:
    r = _monitor_store.get(record_id)
    if not r:
        return None

    warning_level = WarningLevel(r["warning_level"])

    if upd.transport_status == "运输正常":
        voyage_warnings = [
            w for w in _warning_store.values()
            if w.get("voyage_id") == r["voyage_id"]
            and str(w.get("record_date")) == str(r["record_date"])
            and w["warning_level"] in (WarningLevel.high.value, WarningLevel.critical.value)
            and w["disposal_status"] not in (DisposalStatus.completed.value, DisposalStatus.closed.value)
        ]
        if voyage_warnings:
            raise ValueError("存在高风险未处置预警，不能标记为运输正常")

    r["disposal_status"] = upd.disposal_status.value
    if upd.disposal_action:
        r["disposal_action"] = upd.disposal_action
    if upd.transport_status:
        r["transport_status"] = upd.transport_status

    if upd.disposal_status in (DisposalStatus.completed, DisposalStatus.closed):
        rec_date = r["record_date"]
        for w in _warning_store.values():
            if (w.get("voyage_id") == r["voyage_id"]
                    and str(w.get("record_date")) == str(rec_date)):
                w["disposal_status"] = upd.disposal_status.value
                w["disposal_action"] = upd.disposal_action or w.get("disposal_action", "")
                w["disposal_time"] = datetime.now().isoformat()
                w["is_high_risk_unresolved"] = False

    _monitor_store[record_id] = r
    return get_record_detail(record_id)


def report_abnormal(inp: AbnormalReportInput) -> WarningRecordOutput:
    warning_id = _next_warning_id()
    evt_label = ABNORMAL_EVENT_LABELS.get(inp.event_type, inp.event_type.value)
    w = WarningRecordOutput(
        warning_id=warning_id,
        voyage_id=inp.voyage_id,
        record_date=inp.record_date,
        warning_level=inp.severity,
        warning_type=inp.event_type.value,
        warning_message=f"异常上报：{evt_label}" + (f" - {inp.description}" if inp.description else ""),
        risk_score=0.5,
        is_high_risk_unresolved=inp.severity in (WarningLevel.high, WarningLevel.critical),
    )
    _warning_store[warning_id] = w.model_dump()

    for rec in _monitor_store.values():
        if rec["voyage_id"] == inp.voyage_id and str(rec["record_date"]) == str(inp.record_date):
            _recalculate_record_status(rec["record_id"])
            break

    return w


def get_voyage_summary(voyage_id: str) -> Optional[VoyageSummaryOutput]:
    records = [r for r in _monitor_store.values() if r["voyage_id"] == voyage_id]
    if not records:
        return None

    sorted_recs = sorted(records, key=lambda r: r["record_date"])
    total_days = len(sorted_recs)
    avg_humidity = sum(r["cabin_humidity"] for r in sorted_recs) / total_days
    avg_temperature = sum(r["cabin_temperature"] for r in sorted_recs) / total_days
    max_risk = max(r["risk_score"] for r in sorted_recs)

    all_warnings = [w for w in _warning_store.values() if w.get("voyage_id") == voyage_id]
    warning_count = len(all_warnings)
    high_risk_count = sum(1 for w in all_warnings if w["warning_level"] in (WarningLevel.high.value, WarningLevel.critical.value))
    unresolved_count = sum(1 for w in all_warnings if w["disposal_status"] not in (DisposalStatus.completed.value, DisposalStatus.closed.value))
    closed_count = sum(1 for w in all_warnings if w["disposal_status"] in (DisposalStatus.completed.value, DisposalStatus.closed.value))

    trend = []
    for r in sorted_recs:
        trend.append(RiskTrendPoint(
            record_date=r["record_date"],
            risk_score=r["risk_score"],
            humidity=r["cabin_humidity"],
            temperature=r["cabin_temperature"],
            warning_level=WarningLevel(r["warning_level"]),
            pressure_risk=r.get("pressure_risk", 0),
            moisture_risk=r.get("moisture_risk", 0),
            shake_risk=r.get("shake_risk", 0),
        ))

    disposal_comparison = None
    disposed_records = [r for r in sorted_recs if r["disposal_status"] in (DisposalStatus.completed.value, DisposalStatus.closed.value)]
    if disposed_records:
        before_recs = [r for r in sorted_recs if r["disposal_status"] in (DisposalStatus.pending.value, DisposalStatus.confirmed.value, DisposalStatus.processing.value)]
        if before_recs:
            before_avg_risk = sum(r["risk_score"] for r in before_recs) / len(before_recs)
            after_avg_risk = sum(r["risk_score"] for r in disposed_records) / len(disposed_records)
            disposal_comparison = {
                "before_avg_risk": round(before_avg_risk, 4),
                "after_avg_risk": round(after_avg_risk, 4),
                "risk_reduction": round(before_avg_risk - after_avg_risk, 4),
                "before_count": len(before_recs),
                "after_count": len(disposed_records),
            }

    return VoyageSummaryOutput(
        voyage_id=voyage_id,
        total_days=total_days,
        avg_humidity=round(avg_humidity, 2),
        avg_temperature=round(avg_temperature, 2),
        max_risk_score=round(max_risk, 4),
        warning_count=warning_count,
        high_risk_count=high_risk_count,
        unresolved_count=unresolved_count,
        closed_count=closed_count,
        trend=trend,
        pressure_risk_trend=trend,
        moisture_risk_trend=trend,
        disposal_comparison=disposal_comparison,
    )


def get_disposal_suggestion_api(warning_type: str, warning_level: str) -> dict:
    try:
        wl = WarningLevel(warning_level)
    except ValueError:
        wl = WarningLevel.medium
    suggestion = _get_disposal_suggestion(wl, warning_type)
    return {"warning_type": warning_type, "warning_level": warning_level, "suggestion": suggestion}


_ship_store: dict = {}
_voyage_schedule_store: dict = {}
_port_store: dict = {}
_weather_store: dict = {}
_ship_counter = 0
_voyage_schedule_counter = 0
_port_counter = 0
_weather_counter = 0
_dispatch_counter = 0
_conflict_counter = 0


def _next_ship_id():
    global _ship_counter
    _ship_counter += 1
    return f"SHIP_{_ship_counter:04d}"


def _next_voyage_schedule_id():
    global _voyage_schedule_counter
    _voyage_schedule_counter += 1
    return f"VSD_{_voyage_schedule_counter:04d}"


def _next_port_id():
    global _port_counter
    _port_counter += 1
    return f"PORT_{_port_counter:03d}"


def _next_weather_id():
    global _weather_counter
    _weather_counter += 1
    return f"WTH_{_weather_counter:05d}"


def _next_dispatch_id():
    global _dispatch_counter
    _dispatch_counter += 1
    return f"DSP_{_dispatch_counter:04d}"


def _next_conflict_id():
    global _conflict_counter
    _conflict_counter += 1
    return f"CNF_{_conflict_counter:04d}"


def _calculate_voyage_risk(voyage: VoyageSchedule) -> float:
    base_risk = 0.0
    if voyage.humidity is not None:
        if voyage.humidity >= 85:
            base_risk += 0.4
        elif voyage.humidity >= 70:
            base_risk += 0.25
        elif voyage.humidity >= 55:
            base_risk += 0.1
    sea_factors = {
        SeaState.calm: 0.0,
        SeaState.slight: 0.1,
        SeaState.moderate: 0.25,
        SeaState.rough: 0.45,
        SeaState.very_rough: 0.65,
    }
    base_risk += sea_factors.get(voyage.sea_state, 0.2)
    if voyage.voyage_days > 20:
        base_risk += 0.15
    elif voyage.voyage_days > 15:
        base_risk += 0.08
    if voyage.layers > 8:
        base_risk += 0.1
    elif voyage.layers > 6:
        base_risk += 0.05
    if voyage.delay_days > 5:
        base_risk += 0.15
    elif voyage.delay_days > 2:
        base_risk += 0.08
    return min(1.0, base_risk)


def _init_default_data():
    if not _port_store:
        default_ports = [
            {"port_name": "苏州港", "berth_count": 5, "loading_rate": 200.0, "unloading_rate": 250.0, "storage_capacity": 5000.0},
            {"port_name": "扬州港", "berth_count": 4, "loading_rate": 180.0, "unloading_rate": 220.0, "storage_capacity": 4000.0},
            {"port_name": "淮安港", "berth_count": 3, "loading_rate": 150.0, "unloading_rate": 180.0, "storage_capacity": 3000.0},
            {"port_name": "徐州港", "berth_count": 4, "loading_rate": 160.0, "unloading_rate": 200.0, "storage_capacity": 3500.0},
            {"port_name": "北京通州港", "berth_count": 6, "loading_rate": 220.0, "unloading_rate": 280.0, "storage_capacity": 6000.0},
        ]
        for p in default_ports:
            pid = _next_port_id()
            _port_store[pid] = Port(port_id=pid, **p).model_dump()

    if not _ship_store:
        default_ships = [
            {"ship_name": "漕运一号", "cabin_length": 8.0, "cabin_width": 3.0, "cabin_height": 2.5, "capacity_tons": 120.0, "max_speed": 8.0, "status": ShipStatus.available, "current_port": "PORT_001", "crew_count": 12},
            {"ship_name": "漕运二号", "cabin_length": 10.0, "cabin_width": 3.5, "cabin_height": 2.8, "capacity_tons": 180.0, "max_speed": 7.5, "status": ShipStatus.available, "current_port": "PORT_002", "crew_count": 15},
            {"ship_name": "漕运三号", "cabin_length": 7.5, "cabin_width": 2.8, "cabin_height": 2.2, "capacity_tons": 90.0, "max_speed": 9.0, "status": ShipStatus.available, "current_port": "PORT_003", "crew_count": 10},
            {"ship_name": "永乐号", "cabin_length": 12.0, "cabin_width": 4.0, "cabin_height": 3.0, "capacity_tons": 250.0, "max_speed": 6.5, "status": ShipStatus.maintenance, "current_port": "PORT_001", "crew_count": 20},
            {"ship_name": "宣德号", "cabin_length": 9.0, "cabin_width": 3.2, "cabin_height": 2.6, "capacity_tons": 150.0, "max_speed": 8.5, "status": ShipStatus.available, "current_port": "PORT_004", "crew_count": 14},
        ]
        for s in default_ships:
            sid = _next_ship_id()
            _ship_store[sid] = Ship(ship_id=sid, **s).model_dump()

    if not _voyage_schedule_store:
        today = date.today()
        from datetime import timedelta
        default_voyages = [
            {"ship_id": "SHIP_0001", "grain_type": GrainType.rice, "grain_weight": 100.0, "origin_port": "PORT_001", "destination_port": "PORT_005", "priority": VoyagePriority.high, "planned_departure_date": today, "planned_arrival_date": today + timedelta(days=15), "voyage_days": 15, "sea_state": SeaState.slight, "humidity": 65.0, "loading_order": LoadingOrder.even, "layers": 6, "status": VoyageStatus.sailing},
            {"ship_id": "SHIP_0002", "grain_type": GrainType.wheat, "grain_weight": 160.0, "origin_port": "PORT_002", "destination_port": "PORT_005", "priority": VoyagePriority.normal, "planned_departure_date": today + timedelta(days=1), "planned_arrival_date": today + timedelta(days=18), "voyage_days": 17, "sea_state": SeaState.moderate, "humidity": 72.0, "loading_order": LoadingOrder.bottom_heavy, "layers": 7, "status": VoyageStatus.loading},
            {"ship_id": "SHIP_0003", "grain_type": GrainType.soybean, "grain_weight": 80.0, "origin_port": "PORT_003", "destination_port": "PORT_005", "priority": VoyagePriority.emergency, "planned_departure_date": today + timedelta(days=-3), "planned_arrival_date": today + timedelta(days=10), "voyage_days": 13, "sea_state": SeaState.calm, "humidity": 58.0, "loading_order": LoadingOrder.pyramid, "layers": 5, "status": VoyageStatus.sailing},
            {"ship_id": "SHIP_0005", "grain_type": GrainType.millet, "grain_weight": 120.0, "origin_port": "PORT_004", "destination_port": "PORT_005", "priority": VoyagePriority.low, "planned_departure_date": today + timedelta(days=5), "planned_arrival_date": today + timedelta(days=22), "voyage_days": 17, "sea_state": SeaState.slight, "humidity": 60.0, "loading_order": LoadingOrder.even, "layers": 6, "status": VoyageStatus.pending},
            {"ship_id": "SHIP_0001", "grain_type": GrainType.sorghum, "grain_weight": 110.0, "origin_port": "PORT_005", "destination_port": "PORT_001", "priority": VoyagePriority.normal, "planned_departure_date": today + timedelta(days=20), "planned_arrival_date": today + timedelta(days=35), "voyage_days": 15, "sea_state": SeaState.calm, "humidity": 55.0, "loading_order": LoadingOrder.even, "layers": 6, "status": VoyageStatus.pending},
        ]
        for v in default_voyages:
            vid = _next_voyage_schedule_id()
            ship = _ship_store.get(v["ship_id"], {})
            ship_name = ship.get("ship_name", "")
            vs = VoyageSchedule(voyage_id=vid, ship_name=ship_name, **v)
            vs.risk_score = _calculate_voyage_risk(vs)
            vs.risk_level = _risk_score_to_warning_level(vs.risk_score)
            vs.warning_count = 2 if vs.risk_score > 0.5 else 1 if vs.risk_score > 0.3 else 0
            vs.high_risk_warning_count = 1 if vs.risk_score > 0.7 else 0
            vs.has_unresolved_high_risk = vs.risk_score > 0.7 and v["status"] != VoyageStatus.completed
            vs.disposal_progress = 0.0 if vs.has_unresolved_high_risk else 1.0
            _voyage_schedule_store[vid] = vs.model_dump()


_init_default_data()


def get_all_ships() -> list:
    return [Ship(**s) for s in _ship_store.values()]


def get_ship(ship_id: str) -> Optional[Ship]:
    s = _ship_store.get(ship_id)
    return Ship(**s) if s else None


def create_ship(inp: ShipCreateInput) -> Ship:
    sid = _next_ship_id()
    ship = Ship(ship_id=sid, **inp.model_dump())
    _ship_store[sid] = ship.model_dump()
    return ship


def update_ship(ship_id: str, inp: dict) -> Optional[Ship]:
    if ship_id not in _ship_store:
        return None
    _ship_store[ship_id].update(inp)
    return Ship(**_ship_store[ship_id])


def delete_ship(ship_id: str) -> bool:
    if ship_id not in _ship_store:
        return False
    del _ship_store[ship_id]
    return True


def get_all_ports() -> list:
    return [Port(**p) for p in _port_store.values()]


def get_port(port_id: str) -> Optional[Port]:
    p = _port_store.get(port_id)
    return Port(**p) if p else None


def create_port(inp: PortCreateInput) -> Port:
    pid = _next_port_id()
    port = Port(port_id=pid, **inp.model_dump())
    _port_store[pid] = port.model_dump()
    return port


def get_all_voyages() -> list:
    return [VoyageSchedule(**v) for v in _voyage_schedule_store.values()]


def get_voyage_schedule(voyage_id: str) -> Optional[VoyageSchedule]:
    v = _voyage_schedule_store.get(voyage_id)
    return VoyageSchedule(**v) if v else None


def create_voyage_schedule(inp: VoyageCreateInput) -> VoyageSchedule:
    vid = _next_voyage_schedule_id()
    ship = _ship_store.get(inp.ship_id, {})
    ship_name = ship.get("ship_name", "")
    vs = VoyageSchedule(voyage_id=vid, ship_name=ship_name, **inp.model_dump())
    vs.risk_score = _calculate_voyage_risk(vs)
    vs.risk_level = _risk_score_to_warning_level(vs.risk_score)
    _voyage_schedule_store[vid] = vs.model_dump()
    return vs


def update_voyage_schedule(voyage_id: str, inp: VoyageUpdateInput) -> Optional[VoyageSchedule]:
    if voyage_id not in _voyage_schedule_store:
        return None
    update_data = {k: v for k, v in inp.model_dump().items() if v is not None}
    _voyage_schedule_store[voyage_id].update(update_data)
    vs = VoyageSchedule(**_voyage_schedule_store[voyage_id])
    vs.risk_score = _calculate_voyage_risk(vs)
    vs.risk_level = _risk_score_to_warning_level(vs.risk_score)
    _voyage_schedule_store[voyage_id] = vs.model_dump()
    return vs


def get_weather_forecasts(port_id: Optional[str] = None) -> list:
    forecasts = [WeatherForecast(**w) for w in _weather_store.values()]
    if port_id:
        forecasts = [w for w in forecasts if w.port_id == port_id]
    return forecasts


def create_weather_forecast(inp: WeatherCreateInput) -> WeatherForecast:
    wid = _next_weather_id()
    wf = WeatherForecast(**inp.model_dump())
    _weather_store[wid] = wf.model_dump()
    return wf


def _generate_dashboard() -> DispatchDashboard:
    ships = get_all_ships()
    voyages = get_all_voyages()
    available_ships = sum(1 for s in ships if s.status == ShipStatus.available)
    pending_voyages = sum(1 for v in voyages if v.status == VoyageStatus.pending)
    sailing_voyages = sum(1 for v in voyages if v.status == VoyageStatus.sailing)
    completed_voyages = sum(1 for v in voyages if v.status == VoyageStatus.completed)
    delayed_voyages = sum(1 for v in voyages if v.status == VoyageStatus.delayed or v.delay_days > 0)
    high_risk_voyages = sum(1 for v in voyages if v.risk_level in (WarningLevel.high, WarningLevel.critical))
    total_warnings = sum(v.warning_count for v in voyages)
    unresolved_warnings = sum(v.high_risk_warning_count for v in voyages if v.has_unresolved_high_risk)
    avg_progress = 0.0
    if voyages:
        avg_progress = sum(v.disposal_progress for v in voyages) / len(voyages)
    return DispatchDashboard(
        total_ships=len(ships),
        available_ships=available_ships,
        total_voyages=len(voyages),
        pending_voyages=pending_voyages,
        sailing_voyages=sailing_voyages,
        completed_voyages=completed_voyages,
        delayed_voyages=delayed_voyages,
        high_risk_voyages=high_risk_voyages,
        total_warnings=total_warnings,
        unresolved_warnings=unresolved_warnings,
        avg_disposal_progress=round(avg_progress, 4),
    )


def _generate_risk_ranking() -> list:
    voyages = get_all_voyages()
    sorted_voyages = sorted(voyages, key=lambda v: v.risk_score, reverse=True)
    ranking = []
    for i, v in enumerate(sorted_voyages):
        ranking.append(RiskRankItem(
            rank=i + 1,
            voyage_id=v.voyage_id,
            ship_name=v.ship_name,
            grain_type=GRAIN_NAME_CN.get(v.grain_type, v.grain_type),
            risk_score=v.risk_score,
            risk_level=WARNING_LEVEL_LABELS.get(v.risk_level, v.risk_level),
            warning_count=v.warning_count,
            high_risk_count=v.high_risk_warning_count,
            has_unresolved=v.has_unresolved_high_risk,
            priority=VOYAGE_PRIORITY_LABELS.get(v.priority, v.priority),
            status=VOYAGE_STATUS_LABELS.get(v.status, v.status),
        ))
    return ranking


def _generate_delay_assessment() -> list:
    voyages = get_all_voyages()
    delayed = [v for v in voyages if v.delay_days > 0 or v.status == VoyageStatus.delayed]
    sorted_delayed = sorted(delayed, key=lambda v: v.delay_days, reverse=True)
    result = []
    for v in sorted_delayed:
        from datetime import timedelta
        estimated_arrival = v.planned_arrival_date + timedelta(days=v.delay_days)
        grain_loss = v.grain_weight * (v.delay_days * 0.005 + v.risk_score * 0.02)
        economic_loss = grain_loss * 3.5
        impact_level = "严重" if v.delay_days > 7 else "中等" if v.delay_days > 3 else "轻微"
        affected = []
        for other in voyages:
            if other.voyage_id != v.voyage_id and other.ship_id == v.ship_id:
                affected.append(other.voyage_id)
        suggestion = ""
        if impact_level == "严重":
            suggestion = "建议立即启动应急预案，协调备用船只或改变航线，同时加强粮包监测"
        elif impact_level == "中等":
            suggestion = "建议优化靠港顺序，加快装卸速度，减少后续航次影响"
        else:
            suggestion = "建议密切关注天气变化，适时调整航速"
        result.append(DelayImpactItem(
            voyage_id=v.voyage_id,
            ship_name=v.ship_name,
            grain_type=GRAIN_NAME_CN.get(v.grain_type, v.grain_type),
            original_arrival=v.planned_arrival_date,
            estimated_arrival=estimated_arrival,
            delay_days=v.delay_days,
            delay_reason=v.delay_reason or "天气原因/港口拥堵",
            impact_level=impact_level,
            grain_loss_estimate=round(grain_loss, 2),
            economic_loss_estimate=round(economic_loss, 2),
            affected_other_voyages=affected,
            suggestion=suggestion,
        ))
    return result


def _detect_conflicts() -> list:
    conflicts = []
    voyages = get_all_voyages()
    ships = get_all_ships()
    ship_voyages = {}
    for v in voyages:
        if v.status in (VoyageStatus.completed, VoyageStatus.cancelled):
            continue
        if v.ship_id not in ship_voyages:
            ship_voyages[v.ship_id] = []
        ship_voyages[v.ship_id].append(v)
    for ship_id, vlist in ship_voyages.items():
        if len(vlist) > 1:
            active = [v for v in vlist if v.status in (VoyageStatus.sailing, VoyageStatus.loading, VoyageStatus.unloading)]
            pending = [v for v in vlist if v.status == VoyageStatus.pending]
            if len(active) > 1:
                ship = _ship_store.get(ship_id, {})
                conflicts.append(ScheduleConflict(
                    conflict_id=_next_conflict_id(),
                    conflict_type="船只冲突",
                    severity=WarningLevel.high,
                    description=f"船只 {ship.get('ship_name', ship_id)} 同时分配给 {len(active)} 个航次执行",
                    involved_voyages=[v.voyage_id for v in active],
                    involved_ships=[ship_id],
                    involved_ports=[v.origin_port for v in active] + [v.destination_port for v in active],
                    suggestion="建议重新分配船只或调整航次时间，避免同一船只并发执行",
                ))
    port_voyages = {}
    for v in voyages:
        if v.status in (VoyageStatus.completed, VoyageStatus.cancelled):
            continue
        for port_id in [v.origin_port, v.destination_port]:
            if port_id not in port_voyages:
                port_voyages[port_id] = []
            port_voyages[port_id].append(v)
    for port_id, vlist in port_voyages.items():
        port = _port_store.get(port_id, {})
        berth_count = port.get("berth_count", 3)
        active_count = sum(1 for v in vlist if v.status in (VoyageStatus.loading, VoyageStatus.unloading, VoyageStatus.sailing))
        if active_count > berth_count:
            conflicts.append(ScheduleConflict(
                conflict_id=_next_conflict_id(),
                conflict_type="港口拥堵",
                severity=WarningLevel.medium,
                description=f"{port.get('port_name', port_id)} 泊位不足，{active_count} 艘船竞争 {berth_count} 个泊位",
                involved_voyages=[v.voyage_id for v in vlist],
                involved_ships=[v.ship_id for v in vlist],
                involved_ports=[port_id],
                suggestion="建议调整靠港时间，错峰装卸，或申请临时增加作业泊位",
            ))
    return conflicts


def _analyze_port_congestion() -> list:
    congestions = []
    voyages = get_all_voyages()
    for port_id, port_data in _port_store.items():
        port = Port(**port_data)
        active_voyages = [v for v in voyages if (v.origin_port == port_id or v.destination_port == port_id) and v.status not in (VoyageStatus.completed, VoyageStatus.cancelled)]
        usage_ratio = len(active_voyages) / max(port.berth_count, 1)
        waiting = sum(1 for v in active_voyages if v.status == VoyageStatus.pending)
        wait_days = waiting * 1.5
        if usage_ratio >= 1.0:
            level = "严重拥堵"
        elif usage_ratio >= 0.7:
            level = "中度拥堵"
        elif usage_ratio >= 0.4:
            level = "轻度拥堵"
        else:
            level = "畅通"
        congestions.append(PortCongestionInfo(
            port_id=port_id,
            port_name=port.port_name,
            current_berth_usage=round(usage_ratio, 2),
            waiting_voyages=waiting,
            estimated_wait_days=round(wait_days, 1),
            congestion_level=level,
        ))
    return sorted(congestions, key=lambda x: x.current_berth_usage, reverse=True)


def _analyze_resource_shortages() -> list:
    shortages = []
    voyages = get_all_voyages()
    ships = get_all_ships()
    pending_voyages = [v for v in voyages if v.status == VoyageStatus.pending]
    available_ships = [s for s in ships if s.status == ShipStatus.available]
    if len(pending_voyages) > len(available_ships):
        shortages.append(ResourceShortage(
            resource_type="可用船只",
            shortage_amount=len(pending_voyages) - len(available_ships),
            severity=WarningLevel.medium if len(pending_voyages) - len(available_ships) <= 2 else WarningLevel.high,
            description=f"待调度航次 {len(pending_voyages)} 个，但可用船只仅 {len(available_ships)} 艘",
            affected_voyages=[v.voyage_id for v in pending_voyages[len(available_ships):]],
        ))
    total_pending_weight = sum(v.grain_weight for v in pending_voyages)
    total_capacity = sum(s.capacity_tons for s in available_ships)
    if total_pending_weight > total_capacity:
        shortages.append(ResourceShortage(
            resource_type="运载能力",
            shortage_amount=round(total_pending_weight - total_capacity, 1),
            severity=WarningLevel.high,
            description=f"待运粮食 {total_pending_weight:.0f} 吨，可用运力 {total_capacity:.0f} 吨，运力不足",
            affected_voyages=[v.voyage_id for v in pending_voyages],
        ))
    return shortages


def _generate_recommendations(inp: SchedulePlanInput) -> list:
    voyages = get_all_voyages()
    ships = get_all_ships()
    recommendations = []
    pending_voyages = [v for v in voyages if v.status == VoyageStatus.pending]
    priority_order = {VoyagePriority.emergency: 0, VoyagePriority.high: 1, VoyagePriority.normal: 2, VoyagePriority.low: 3}
    pending_voyages.sort(key=lambda v: (priority_order.get(v.priority, 2), v.risk_score))
    available_ships = [s for s in ships if s.status == ShipStatus.available]
    if not inp.consider_ship_availability:
        available_ships = ships
    used_ships = set()
    for voyage in pending_voyages:
        is_blocked = inp.high_risk_block and voyage.has_unresolved_high_risk
        suitable_ships = [s for s in available_ships if s.ship_id not in used_ships and s.capacity_tons >= voyage.grain_weight]
        if not suitable_ships:
            suitable_ships = [s for s in available_ships if s.ship_id not in used_ships]
        if suitable_ships:
            ship = suitable_ships[0]
            used_ships.add(ship.ship_id)
            priority_score = _calculate_priority_score(voyage, ship, inp)
            reason_parts = []
            if voyage.priority == VoyagePriority.emergency:
                reason_parts.append("紧急优先级航次")
            elif voyage.priority == VoyagePriority.high:
                reason_parts.append("高优先级航次")
            if voyage.risk_level == WarningLevel.normal:
                reason_parts.append("风险较低")
            elif voyage.risk_level == WarningLevel.low:
                reason_parts.append("风险可控")
            else:
                reason_parts.append(f"风险等级: {WARNING_LEVEL_LABELS.get(voyage.risk_level, voyage.risk_level)}")
            reason = "；".join(reason_parts)
            risk_assessment = f"风险指数 {voyage.risk_score:.3f}，{WARNING_LEVEL_LABELS.get(voyage.risk_level, voyage.risk_level)}"
            if is_blocked:
                recommendations.append(DispatchRecommendation(
                    recommendation_id=_next_dispatch_id(),
                    voyage_id=voyage.voyage_id,
                    ship_id=ship.ship_id,
                    recommended_action="暂不调度（高风险未闭环）",
                    recommended_departure_date=None,
                    priority_score=priority_score,
                    reason=f"高风险且未闭环，按照规则暂不推荐调度。{reason}",
                    risk_assessment=risk_assessment,
                    is_recommended=False,
                ))
            else:
                recommendations.append(DispatchRecommendation(
                    recommendation_id=_next_dispatch_id(),
                    voyage_id=voyage.voyage_id,
                    ship_id=ship.ship_id,
                    recommended_action="建议立即调度",
                    recommended_departure_date=voyage.planned_departure_date,
                    priority_score=priority_score,
                    reason=reason,
                    risk_assessment=risk_assessment,
                    is_recommended=True,
                ))
    recommendations.sort(key=lambda r: r.priority_score, reverse=True)
    return recommendations


def _calculate_priority_score(voyage: VoyageSchedule, ship: Ship, inp: SchedulePlanInput) -> float:
    score = 0.0
    priority_weights = {VoyagePriority.emergency: 40, VoyagePriority.high: 25, VoyagePriority.normal: 15, VoyagePriority.low: 5}
    score += priority_weights.get(voyage.priority, 15)
    risk_factor = 1.0 - voyage.risk_score
    score += risk_factor * 25
    capacity_match = min(ship.capacity_tons, voyage.grain_weight) / max(ship.capacity_tons, voyage.grain_weight, 0.01)
    score += capacity_match * 15
    score += 20 * (voyage.grain_weight / max(ship.capacity_tons, 0.01))
    return round(score, 2)


def generate_dispatch_plan(inp: SchedulePlanInput) -> DispatchResult:
    dashboard = _generate_dashboard()
    recommendations = _generate_recommendations(inp)
    risk_ranking = _generate_risk_ranking()
    delay_assessment = _generate_delay_assessment()
    conflicts = _detect_conflicts()
    port_congestions = _analyze_port_congestion()
    resource_shortages = _analyze_resource_shortages()
    return DispatchResult(
        dashboard=dashboard,
        recommended_schedules=recommendations,
        risk_ranking=risk_ranking,
        delay_assessment=delay_assessment,
        conflicts=conflicts,
        port_congestions=port_congestions,
        resource_shortages=resource_shortages,
        generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


_batch_store: dict = {}
_batch_abnormal_store: dict = {}
_transport_record_store: dict = {}
_batch_counter = 0
_batch_abnormal_counter = 0
_transport_record_counter = 0
_batch_inspection_counter = 0


def _next_batch_id():
    global _batch_counter
    _batch_counter += 1
    return f"BATCH_{_batch_counter:05d}"


def _next_abnormal_id():
    global _batch_abnormal_counter
    _batch_abnormal_counter += 1
    return f"ABN_{_batch_abnormal_counter:05d}"


def _next_transport_record_id():
    global _transport_record_counter
    _transport_record_counter += 1
    return f"TQR_{_transport_record_counter:05d}"


def _next_inspection_id():
    global _batch_inspection_counter
    _batch_inspection_counter += 1
    return f"INS_{_batch_inspection_counter:05d}"


def _calculate_quality_score(
    moisture_rate: float, damage_rate: float, moldy_rate: float,
    impurity_rate: float = 0.0
) -> tuple:
    score = 100.0
    score -= moisture_rate * 1.5
    score -= damage_rate * 2.0
    score -= moldy_rate * 3.0
    score -= impurity_rate * 1.0
    score = max(0.0, min(100.0, score))

    if score >= 90:
        level = BatchQualityLevel.excellent
    elif score >= 75:
        level = BatchQualityLevel.good
    elif score >= 60:
        level = BatchQualityLevel.medium
    elif score >= 40:
        level = BatchQualityLevel.poor
    else:
        level = BatchQualityLevel.critical

    return round(score, 2), level


def _recalculate_batch_status(batch_id: str) -> None:
    batch = _batch_store.get(batch_id)
    if not batch:
        return

    abnormal_records = [
        a for a in _batch_abnormal_store.values()
        if a["batch_id"] == batch_id
    ]

    abnormal_count = len(abnormal_records)
    severe_abnormal_count = sum(
        1 for a in abnormal_records
        if a["severity"] in (AbnormalSeverity.severe.value, AbnormalSeverity.critical.value)
    )
    unresolved_severe = any(
        a["severity"] in (AbnormalSeverity.severe.value, AbnormalSeverity.critical.value)
        and a["status"] not in (AbnormalStatus.resolved.value, AbnormalStatus.closed.value)
        for a in abnormal_records
    )

    batch["abnormal_count"] = abnormal_count
    batch["severe_abnormal_count"] = severe_abnormal_count
    batch["unresolved_severe_abnormal"] = unresolved_severe

    transport_records = [
        r for r in _transport_record_store.values()
        if r["batch_id"] == batch_id
    ]
    if transport_records:
        latest = max(transport_records, key=lambda r: r["record_date"])
        batch["current_moisture_rate"] = latest["moisture_rate"]
        batch["current_damage_rate"] = latest["damage_rate"]
        batch["current_moldy_rate"] = latest["moldy_rate"]
        q_score, q_level = _calculate_quality_score(
            latest["moisture_rate"],
            latest["damage_rate"],
            latest["moldy_rate"]
        )
        batch["quality_score"] = q_score
        batch["quality_level"] = q_level.value

    if batch["total_weight"] > 0:
        batch["total_loss_rate"] = round(
            batch["total_loss_weight"] / batch["total_weight"] * 100, 2
        )

    _batch_store[batch_id] = batch


def _can_mark_qualified(batch_id: str) -> bool:
    batch = _batch_store.get(batch_id)
    if not batch:
        return False

    if batch.get("unresolved_severe_abnormal", False):
        return False

    abnormal_records = [
        a for a in _batch_abnormal_store.values()
        if a["batch_id"] == batch_id
    ]
    for a in abnormal_records:
        if a["severity"] in (AbnormalSeverity.severe.value, AbnormalSeverity.critical.value):
            if a["status"] not in (AbnormalStatus.resolved.value, AbnormalStatus.closed.value):
                return False

    return True


def create_grain_batch(inp: BatchCreateInput) -> GrainBatch:
    bid = _next_batch_id()
    quality_score, quality_level = _calculate_quality_score(
        inp.initial_moisture_rate, 0.0, 0.0, inp.initial_impurity_rate
    )

    batch = GrainBatch(
        batch_id=bid,
        batch_code=inp.batch_code,
        grain_type=inp.grain_type,
        origin=inp.origin,
        origin_port=inp.origin_port,
        destination_port=inp.destination_port,
        warehouse_date=inp.warehouse_date,
        initial_moisture_rate=inp.initial_moisture_rate,
        initial_impurity_rate=inp.initial_impurity_rate,
        total_weight=inp.total_weight,
        bag_count=inp.bag_count,
        voyage_id=inp.voyage_id,
        current_moisture_rate=inp.initial_moisture_rate,
        quality_score=quality_score,
        quality_level=quality_level,
        warehouse_manager=inp.warehouse_manager,
        note=inp.note,
        created_at=datetime.now().isoformat(),
    )

    _batch_store[bid] = batch.model_dump()
    return batch


def get_grain_batch(batch_id: str) -> Optional[GrainBatch]:
    b = _batch_store.get(batch_id)
    return GrainBatch(**b) if b else None


def get_all_grain_batches() -> list:
    return [GrainBatch(**b) for b in _batch_store.values()]


def update_grain_batch(batch_id: str, inp: BatchUpdateInput) -> Optional[GrainBatch]:
    if batch_id not in _batch_store:
        return None

    update_data = {k: v for k, v in inp.model_dump().items() if v is not None}
    _batch_store[batch_id].update(update_data)

    if "status" in update_data:
        new_status = update_data["status"]
        if new_status == BatchStatus.qualified.value:
            if not _can_mark_qualified(batch_id):
                raise ValueError("存在严重异常且未处理完成，不得标记为合格批次")
            _batch_store[batch_id]["is_qualified"] = True
        else:
            _batch_store[batch_id]["is_qualified"] = False

    _recalculate_batch_status(batch_id)
    return GrainBatch(**_batch_store[batch_id])


def delete_grain_batch(batch_id: str) -> bool:
    if batch_id not in _batch_store:
        return False

    del _batch_store[batch_id]

    for aid in list(_batch_abnormal_store.keys()):
        if _batch_abnormal_store[aid]["batch_id"] == batch_id:
            del _batch_abnormal_store[aid]

    for rid in list(_transport_record_store.keys()):
        if _transport_record_store[rid]["batch_id"] == batch_id:
            del _transport_record_store[rid]

    return True


def search_grain_batches(query: BatchSearchQuery) -> list:
    batches = list(_batch_store.values())

    if query.batch_code:
        batches = [b for b in batches if query.batch_code.lower() in b["batch_code"].lower()]

    if query.grain_type:
        batches = [b for b in batches if b["grain_type"] == query.grain_type.value]

    if query.status:
        batches = [b for b in batches if b["status"] == query.status.value]

    if query.origin:
        batches = [b for b in batches if query.origin.lower() in b["origin"].lower()]

    if query.voyage_id:
        batches = [b for b in batches if query.voyage_id in b["voyage_id"]]

    if query.has_abnormal is not None:
        if query.has_abnormal:
            batches = [b for b in batches if b["abnormal_count"] > 0]
        else:
            batches = [b for b in batches if b["abnormal_count"] == 0]

    if query.is_qualified is not None:
        batches = [b for b in batches if b["is_qualified"] == query.is_qualified]

    if query.start_date:
        batches = [b for b in batches if b["warehouse_date"] >= query.start_date]

    if query.end_date:
        batches = [b for b in batches if b["warehouse_date"] <= query.end_date]

    return [GrainBatch(**b) for b in batches]


def add_batch_inspection(inp: BatchInspectionInput) -> BatchInspectionResult:
    if inp.batch_id not in _batch_store:
        raise ValueError("批次不存在")

    iid = _next_inspection_id()
    quality_score, quality_level = _calculate_quality_score(
        inp.moisture_rate, inp.damage_rate, inp.moldy_rate, inp.impurity_rate
    )

    result = BatchInspectionResult(
        inspection_id=iid,
        inspection_date=inp.inspection_date,
        inspector=inp.inspector,
        moisture_rate=inp.moisture_rate,
        impurity_rate=inp.impurity_rate,
        damage_rate=inp.damage_rate,
        moldy_rate=inp.moldy_rate,
        quality_score=quality_score,
        quality_level=quality_level,
        note=inp.note,
    )

    batch = _batch_store[inp.batch_id]
    if "inspection_results" not in batch:
        batch["inspection_results"] = []
    batch["inspection_results"].append(result.model_dump())

    batch["current_moisture_rate"] = inp.moisture_rate
    batch["current_damage_rate"] = inp.damage_rate
    batch["current_moldy_rate"] = inp.moldy_rate
    batch["quality_score"] = quality_score
    batch["quality_level"] = quality_level.value

    _batch_store[inp.batch_id] = batch
    _recalculate_batch_status(inp.batch_id)

    return result


def get_batch_inspections(batch_id: str) -> list:
    batch = _batch_store.get(batch_id)
    if not batch:
        return []
    return [BatchInspectionResult(**r) for r in batch.get("inspection_results", [])]


def create_abnormal_record(inp: AbnormalRecordInput) -> BatchAbnormalRecord:
    if inp.batch_id not in _batch_store:
        raise ValueError("批次不存在")

    aid = _next_abnormal_id()
    record = BatchAbnormalRecord(
        abnormal_id=aid,
        batch_id=inp.batch_id,
        record_date=inp.record_date,
        issue_type=inp.issue_type,
        severity=inp.severity,
        description=inp.description,
        affected_weight=inp.affected_weight,
        location=inp.location,
        responsible_party=inp.responsible_party,
        recorded_by=inp.recorded_by,
        created_at=datetime.now().isoformat(),
    )

    _batch_abnormal_store[aid] = record.model_dump()

    batch = _batch_store[inp.batch_id]
    if inp.affected_weight > 0:
        batch["total_loss_weight"] = round(
            batch.get("total_loss_weight", 0.0) + inp.affected_weight, 2
        )

    _recalculate_batch_status(inp.batch_id)

    return record


def get_abnormal_records(batch_id: Optional[str] = None) -> list:
    records = list(_batch_abnormal_store.values())
    if batch_id:
        records = [r for r in records if r["batch_id"] == batch_id]
    records.sort(key=lambda r: r["record_date"], reverse=True)
    return [BatchAbnormalRecord(**r) for r in records]


def update_abnormal_record(abnormal_id: str, inp: AbnormalUpdateInput) -> Optional[BatchAbnormalRecord]:
    if abnormal_id not in _batch_abnormal_store:
        return None

    update_data = {k: v for k, v in inp.model_dump().items() if v is not None}
    _batch_abnormal_store[abnormal_id].update(update_data)

    batch_id = _batch_abnormal_store[abnormal_id]["batch_id"]
    _recalculate_batch_status(batch_id)

    return BatchAbnormalRecord(**_batch_abnormal_store[abnormal_id])


def create_transport_record(inp: TransportRecordInput) -> TransportQualityRecord:
    if inp.batch_id not in _batch_store:
        raise ValueError("批次不存在")

    rid = _next_transport_record_id()
    quality_score, quality_level = _calculate_quality_score(
        inp.moisture_rate, inp.damage_rate, inp.moldy_rate
    )

    record = TransportQualityRecord(
        record_id=rid,
        batch_id=inp.batch_id,
        record_date=inp.record_date,
        voyage_id=inp.voyage_id,
        stage=inp.stage,
        moisture_rate=inp.moisture_rate,
        temperature=inp.temperature,
        humidity=inp.humidity,
        pressure_loss_rate=inp.pressure_loss_rate,
        damp_rate=inp.damp_rate,
        moldy_rate=inp.moldy_rate,
        damage_rate=inp.damage_rate,
        bag_status=inp.bag_status,
        quality_score=quality_score,
        quality_level=quality_level,
        operator=inp.operator,
        note=inp.note,
        created_at=datetime.now().isoformat(),
    )

    _transport_record_store[rid] = record.model_dump()
    _recalculate_batch_status(inp.batch_id)

    return record


def get_transport_records(batch_id: str) -> list:
    records = [
        r for r in _transport_record_store.values()
        if r["batch_id"] == batch_id
    ]
    records.sort(key=lambda r: r["record_date"])
    return [TransportQualityRecord(**r) for r in records]


def generate_quality_report(batch_id: str) -> Optional[BatchQualityReport]:
    batch = _batch_store.get(batch_id)
    if not batch:
        return None

    transport_records = [
        r for r in _transport_record_store.values()
        if r["batch_id"] == batch_id
    ]
    transport_records.sort(key=lambda r: r["record_date"])

    quality_trend = []
    for r in transport_records:
        quality_trend.append(QualityTrendPoint(
            record_date=r["record_date"],
            quality_score=r["quality_score"],
            quality_level=BatchQualityLevel(r["quality_level"]),
            moisture_rate=r["moisture_rate"],
            damage_rate=r["damage_rate"],
            moldy_rate=r["moldy_rate"],
            damp_rate=r["damp_rate"],
        ))

    if not quality_trend:
        quality_score, quality_level = _calculate_quality_score(
            batch["initial_moisture_rate"], 0.0, 0.0
        )
        quality_trend.append(QualityTrendPoint(
            record_date=batch["warehouse_date"],
            quality_score=quality_score,
            quality_level=quality_level,
            moisture_rate=batch["initial_moisture_rate"],
            damage_rate=0.0,
            moldy_rate=0.0,
            damp_rate=0.0,
        ))

    loss_trace = _generate_loss_trace(batch_id)

    abnormal_records = [
        a for a in _batch_abnormal_store.values()
        if a["batch_id"] == batch_id
    ]

    responsible_analysis = _analyze_responsibility(abnormal_records, batch)
    disposal_suggestion = _generate_disposal_suggestion(batch, abnormal_records)

    can_mark = _can_mark_qualified(batch_id)

    return BatchQualityReport(
        batch_id=batch["batch_id"],
        batch_code=batch["batch_code"],
        grain_type=GRAIN_NAME_CN.get(GrainType(batch["grain_type"]), batch["grain_type"]),
        total_weight=batch["total_weight"],
        quality_score=batch["quality_score"],
        quality_level=BATCH_QUALITY_LABELS.get(BatchQualityLevel(batch["quality_level"]), batch["quality_level"]),
        initial_moisture_rate=batch["initial_moisture_rate"],
        current_moisture_rate=batch["current_moisture_rate"],
        total_loss_weight=batch.get("total_loss_weight", 0.0),
        total_loss_rate=batch.get("total_loss_rate", 0.0),
        abnormal_count=batch["abnormal_count"],
        severe_abnormal_count=batch["severe_abnormal_count"],
        unresolved_severe=batch["unresolved_severe_abnormal"],
        quality_trend=quality_trend,
        loss_trace=loss_trace,
        responsible_analysis=responsible_analysis,
        disposal_suggestion=disposal_suggestion,
        is_qualified=batch["is_qualified"],
        can_mark_qualified=can_mark,
    )


def _generate_loss_trace(batch_id: str) -> list:
    transport_records = [
        r for r in _transport_record_store.values()
        if r["batch_id"] == batch_id
    ]
    transport_records.sort(key=lambda r: r["record_date"])

    batch = _batch_store[batch_id]
    total_weight = batch["total_weight"] or 1.0

    loss_trace = []
    stages = []

    if transport_records:
        initial_loss = transport_records[0]["damage_rate"] + transport_records[0]["moldy_rate"]
        stages.append({
            "stage": "入仓验收",
            "loss_weight": round(total_weight * batch["initial_impurity_rate"] / 100, 2),
            "loss_rate": batch["initial_impurity_rate"],
            "main_cause": "原始杂质",
            "abnormal_count": 0,
            "severe_count": 0,
        })

        stage_groups = {}
        for r in transport_records:
            stage = r["stage"] or "运输途中"
            if stage not in stage_groups:
                stage_groups[stage] = {
                    "stage": stage,
                    "records": [],
                }
            stage_groups[stage]["records"].append(r)

        for stage_name, group in stage_groups.items():
            records = group["records"]
            max_damage = max(r["damage_rate"] for r in records)
            max_moldy = max(r["moldy_rate"] for r in records)
            max_damp = max(r["damp_rate"] for r in records)
            total_loss_pct = max_damage + max_moldy + max_damp * 0.5

            abnormal_count = sum(
                1 for a in _batch_abnormal_store.values()
                if a["batch_id"] == batch_id and a.get("location", "") == stage_name
            )
            severe_count = sum(
                1 for a in _batch_abnormal_store.values()
                if a["batch_id"] == batch_id
                and a.get("location", "") == stage_name
                and a["severity"] in (AbnormalSeverity.severe.value, AbnormalSeverity.critical.value)
            )

            main_cause = "正常损耗"
            if max_moldy > max_damage and max_moldy > max_damp:
                main_cause = "发霉变质"
            elif max_damage > max_damp:
                main_cause = "压损破损"
            elif max_damp > 0:
                main_cause = "受潮影响"

            stages.append({
                "stage": stage_name,
                "loss_weight": round(total_weight * total_loss_pct / 100, 2),
                "loss_rate": round(total_loss_pct, 2),
                "main_cause": main_cause,
                "abnormal_count": abnormal_count,
                "severe_count": severe_count,
            })
    else:
        stages.append({
            "stage": "仓储阶段",
            "loss_weight": 0.0,
            "loss_rate": 0.0,
            "main_cause": "暂无数据",
            "abnormal_count": 0,
            "severe_count": 0,
        })

    return [LossTraceItem(**s) for s in stages]


def _analyze_responsibility(abnormal_records: list, batch: dict) -> str:
    if not abnormal_records:
        return "批次无异常记录，责任认定：各环节正常"

    resp_counts = {}
    for a in abnormal_records:
        resp = a["responsible_party"]
        resp_counts[resp] = resp_counts.get(resp, 0) + 1

    if not resp_counts:
        return "责任待认定"

    main_resp = max(resp_counts.keys(), key=lambda k: resp_counts[k])
    main_resp_label = RESPONSIBILITY_LABELS.get(ResponsibilityType(main_resp), main_resp)

    details = []
    for resp, count in resp_counts.items():
        label = RESPONSIBILITY_LABELS.get(ResponsibilityType(resp), resp)
        details.append(f"{label}：{count}起")

    return f"主要责任方：{main_resp_label}。各环节异常分布：{'; '.join(details)}"


def _generate_disposal_suggestion(batch: dict, abnormal_records: list) -> str:
    suggestions = []

    if batch.get("unresolved_severe_abnormal"):
        suggestions.append("⚠ 存在严重未处理异常，必须先完成所有严重异常的处置闭环后，方可进行最终验收")

    quality_level = batch.get("quality_level", "good")
    if quality_level in (BatchQualityLevel.poor.value, BatchQualityLevel.critical.value):
        suggestions.append("批次质量较差，建议进行复检和专项处理，必要时降级使用")

    moldy_rate = batch.get("current_moldy_rate", 0)
    if moldy_rate > 2:
        suggestions.append("发霉率较高，需进行熏蒸消杀处理，防止霉变扩散")

    damage_rate = batch.get("current_damage_rate", 0)
    if damage_rate > 3:
        suggestions.append("破损率较高，需进行筛选整理，重新包装")

    moisture_rate = batch.get("current_moisture_rate", 0)
    if moisture_rate > 14:
        suggestions.append("含水率偏高，需进行干燥处理")

    if not suggestions:
        suggestions.append("批次质量良好，按正常流程验收即可")

    return "；".join(suggestions)
