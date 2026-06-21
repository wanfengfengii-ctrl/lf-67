from fastapi import APIRouter, HTTPException
from app.models import (
    SimulationRequest,
    SimulationResult,
    ComparisonResult,
    MultiSchemeResult,
    BatchCompareRequest,
    BatchCompareResult,
    PriorityTarget,
)
from app.engine import (
    simulate,
    compare_schemes,
    generate_multi_schemes,
    batch_compare,
)

router = APIRouter()


@router.post("/simulate", response_model=SimulationResult)
def run_simulation(req: SimulationRequest):
    try:
        return simulate(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/compare", response_model=ComparisonResult)
def run_comparison(req: SimulationRequest):
    try:
        return compare_schemes(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/multi-schemes", response_model=MultiSchemeResult)
def run_multi_schemes(req: SimulationRequest):
    try:
        return generate_multi_schemes(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/batch-compare", response_model=BatchCompareResult)
def run_batch_compare(req: BatchCompareRequest):
    try:
        return batch_compare(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/grain-types")
def get_grain_types():
    from app.models import GrainType
    return [{"value": g.value, "label": {
        "rice": "稻米", "wheat": "小麦", "millet": "粟米",
        "sorghum": "高粱", "soybean": "大豆"
    }[g.value]} for g in GrainType]


@router.get("/loading-orders")
def get_loading_orders():
    from app.models import LoadingOrder
    return [{"value": o.value, "label": {
        "bottom_heavy": "底层加重", "top_heavy": "顶层加重",
        "even": "均匀分布", "pyramid": "金字塔式"
    }[o.value]} for o in LoadingOrder]


@router.get("/sea-states")
def get_sea_states():
    from app.models import SeaState
    return [{"value": s.value, "label": {
        "calm": "平静", "slight": "轻微摇晃",
        "moderate": "中等摇晃", "rough": "剧烈摇晃",
        "very_rough": "极端摇晃"
    }[s.value]} for s in SeaState]


@router.get("/priority-targets")
def get_priority_targets():
    return [
        {"value": PriorityTarget.min_loss.value, "label": "最小损耗优先"},
        {"value": PriorityTarget.max_capacity.value, "label": "最大容量优先"},
        {"value": PriorityTarget.min_pressure.value, "label": "最低承压优先"},
        {"value": PriorityTarget.balance.value, "label": "综合平衡（推荐）"},
    ]
