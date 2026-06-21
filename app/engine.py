import math
from app.models import (
    SimulationRequest,
    SimulationResult,
    LayerInfo,
    LoadingOrder,
    GrainType,
    SeaState,
    ComparisonItem,
    ComparisonResult,
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

MAX_SAFE_LAYERS = 8
CRITICAL_LAYERS = 12


def _calculate_bags_per_layer(req: SimulationRequest) -> int:
    x_count = int(req.cabin.length // req.bag.length)
    y_count = int(req.cabin.width // req.bag.width)
    if x_count <= 0 or y_count <= 0:
        return 0
    return x_count * y_count


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
    is_high_risk = estimated_loss > 10 or moisture_risk_score > 0.6 or req.sea_state == SeaState.very_rough
    can_execute = not is_high_risk and not has_severe_warning
    is_formal = req.humidity is not None

    if is_high_risk:
        warnings.append("该方案为高风险方案，不可标记为可执行")

    return SimulationResult(
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
