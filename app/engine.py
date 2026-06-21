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

    if warning_level in (WarningLevel.high, WarningLevel.critical):
        record["transport_status"] = "异常待处置"
        record["disposal_status"] = DisposalStatus.pending.value

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
