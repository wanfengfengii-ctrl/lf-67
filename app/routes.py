from fastapi import APIRouter, HTTPException
from app.models import SimulationRequest, SimulationResult, ComparisonResult
from app.engine import simulate, compare_schemes

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
