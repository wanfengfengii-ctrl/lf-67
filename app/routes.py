from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.models import (
    SimulationRequest,
    SimulationResult,
    ComparisonResult,
    MultiSchemeResult,
    BatchCompareRequest,
    BatchCompareResult,
    PriorityTarget,
    DailyMonitorInput,
    DailyMonitorOutput,
    WarningRecordOutput,
    DisposalUpdateInput,
    WarningConfirmInput,
    AbnormalReportInput,
    VoyageSummaryOutput,
    Ship,
    Port,
    VoyageSchedule,
    ShipCreateInput,
    PortCreateInput,
    VoyageCreateInput,
    VoyageUpdateInput,
    WeatherForecast,
    WeatherCreateInput,
    SchedulePlanInput,
    DispatchResult,
    GrainBatch,
    BatchCreateInput,
    BatchUpdateInput,
    BatchInspectionInput,
    BatchInspectionResult,
    BatchAbnormalRecord,
    AbnormalRecordInput,
    AbnormalUpdateInput,
    TransportQualityRecord,
    TransportRecordInput,
    BatchQualityReport,
    BatchSearchQuery,
)
from app.engine import (
    simulate,
    compare_schemes,
    generate_multi_schemes,
    batch_compare,
    create_daily_record,
    get_voyage_records,
    get_record_detail,
    get_voyage_warnings,
    confirm_warning,
    update_disposal,
    report_abnormal,
    get_voyage_summary,
    get_disposal_suggestion_api,
    get_all_ships,
    get_ship,
    create_ship,
    update_ship,
    delete_ship,
    get_all_ports,
    get_port,
    create_port,
    get_all_voyages,
    get_voyage_schedule,
    create_voyage_schedule,
    update_voyage_schedule,
    get_weather_forecasts,
    create_weather_forecast,
    generate_dispatch_plan,
    create_grain_batch,
    get_grain_batch,
    get_all_grain_batches,
    update_grain_batch,
    delete_grain_batch,
    search_grain_batches,
    add_batch_inspection,
    get_batch_inspections,
    create_abnormal_record,
    get_abnormal_records,
    update_abnormal_record,
    create_transport_record,
    get_transport_records,
    generate_quality_report,
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


@router.post("/monitor/daily-record", response_model=DailyMonitorOutput)
def api_create_daily_record(inp: DailyMonitorInput):
    try:
        return create_daily_record(inp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/monitor/voyage/{voyage_id}/records", response_model=list[DailyMonitorOutput])
def api_get_voyage_records(voyage_id: str):
    return get_voyage_records(voyage_id)


@router.get("/monitor/record/{record_id}", response_model=DailyMonitorOutput)
def api_get_record_detail(record_id: str):
    result = get_record_detail(record_id)
    if not result:
        raise HTTPException(status_code=404, detail="记录不存在")
    return result


@router.get("/monitor/voyage/{voyage_id}/warnings", response_model=list[WarningRecordOutput])
def api_get_voyage_warnings(voyage_id: str):
    return get_voyage_warnings(voyage_id)


@router.post("/monitor/warning/{warning_id}/confirm", response_model=WarningRecordOutput)
def api_confirm_warning(warning_id: str, inp: WarningConfirmInput):
    result = confirm_warning(warning_id, inp.confirmed)
    if not result:
        raise HTTPException(status_code=404, detail="预警不存在")
    return result


@router.post("/monitor/record/{record_id}/disposal", response_model=DailyMonitorOutput)
def api_update_disposal(record_id: str, upd: DisposalUpdateInput):
    try:
        result = update_disposal(record_id, upd)
        if not result:
            raise HTTPException(status_code=404, detail="记录不存在")
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/monitor/abnormal-report", response_model=WarningRecordOutput)
def api_report_abnormal(inp: AbnormalReportInput):
    return report_abnormal(inp)


@router.get("/monitor/voyage/{voyage_id}/summary", response_model=VoyageSummaryOutput)
def api_get_voyage_summary(voyage_id: str):
    result = get_voyage_summary(voyage_id)
    if not result:
        raise HTTPException(status_code=404, detail="航次无监测记录")
    return result


@router.get("/monitor/disposal-suggestion")
def api_get_disposal_suggestion(
    warning_type: str = Query(...),
    warning_level: str = Query(...)
):
    return get_disposal_suggestion_api(warning_type, warning_level)


@router.get("/dispatch/ships", response_model=list[Ship])
def api_get_all_ships():
    return get_all_ships()


@router.get("/dispatch/ships/{ship_id}", response_model=Ship)
def api_get_ship(ship_id: str):
    result = get_ship(ship_id)
    if not result:
        raise HTTPException(status_code=404, detail="船只不存在")
    return result


@router.post("/dispatch/ships", response_model=Ship)
def api_create_ship(inp: ShipCreateInput):
    try:
        return create_ship(inp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/dispatch/ships/{ship_id}")
def api_delete_ship(ship_id: str):
    if not delete_ship(ship_id):
        raise HTTPException(status_code=404, detail="船只不存在")
    return {"status": "success", "message": "船只已删除"}


@router.get("/dispatch/ports", response_model=list[Port])
def api_get_all_ports():
    return get_all_ports()


@router.get("/dispatch/ports/{port_id}", response_model=Port)
def api_get_port(port_id: str):
    result = get_port(port_id)
    if not result:
        raise HTTPException(status_code=404, detail="港口不存在")
    return result


@router.post("/dispatch/ports", response_model=Port)
def api_create_port(inp: PortCreateInput):
    try:
        return create_port(inp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/dispatch/voyages", response_model=list[VoyageSchedule])
def api_get_all_voyages():
    return get_all_voyages()


@router.get("/dispatch/voyages/{voyage_id}", response_model=VoyageSchedule)
def api_get_voyage_schedule(voyage_id: str):
    result = get_voyage_schedule(voyage_id)
    if not result:
        raise HTTPException(status_code=404, detail="航次不存在")
    return result


@router.post("/dispatch/voyages", response_model=VoyageSchedule)
def api_create_voyage_schedule(inp: VoyageCreateInput):
    try:
        return create_voyage_schedule(inp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/dispatch/voyages/{voyage_id}", response_model=VoyageSchedule)
def api_update_voyage_schedule(voyage_id: str, inp: VoyageUpdateInput):
    result = update_voyage_schedule(voyage_id, inp)
    if not result:
        raise HTTPException(status_code=404, detail="航次不存在")
    return result


@router.get("/dispatch/weather", response_model=list[WeatherForecast])
def api_get_weather_forecasts(port_id: Optional[str] = Query(None)):
    return get_weather_forecasts(port_id)


@router.post("/dispatch/weather", response_model=WeatherForecast)
def api_create_weather_forecast(inp: WeatherCreateInput):
    try:
        return create_weather_forecast(inp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/dispatch/plan", response_model=DispatchResult)
def api_generate_dispatch_plan(inp: SchedulePlanInput):
    try:
        return generate_dispatch_plan(inp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/trace/batches", response_model=list[GrainBatch])
def api_get_all_batches():
    return get_all_grain_batches()


@router.get("/trace/batches/{batch_id}", response_model=GrainBatch)
def api_get_batch(batch_id: str):
    result = get_grain_batch(batch_id)
    if not result:
        raise HTTPException(status_code=404, detail="批次不存在")
    return result


@router.post("/trace/batches", response_model=GrainBatch)
def api_create_batch(inp: BatchCreateInput):
    try:
        return create_grain_batch(inp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/trace/batches/{batch_id}", response_model=GrainBatch)
def api_update_batch(batch_id: str, inp: BatchUpdateInput):
    try:
        result = update_grain_batch(batch_id, inp)
        if not result:
            raise HTTPException(status_code=404, detail="批次不存在")
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/trace/batches/{batch_id}")
def api_delete_batch(batch_id: str):
    if not delete_grain_batch(batch_id):
        raise HTTPException(status_code=404, detail="批次不存在")
    return {"status": "success", "message": "批次已删除"}


@router.post("/trace/batches/search", response_model=list[GrainBatch])
def api_search_batches(query: BatchSearchQuery):
    return search_grain_batches(query)


@router.get("/trace/batches/{batch_id}/inspections", response_model=list[BatchInspectionResult])
def api_get_batch_inspections(batch_id: str):
    return get_batch_inspections(batch_id)


@router.post("/trace/inspections", response_model=BatchInspectionResult)
def api_add_batch_inspection(inp: BatchInspectionInput):
    try:
        return add_batch_inspection(inp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/trace/abnormal", response_model=list[BatchAbnormalRecord])
def api_get_abnormal_records(batch_id: Optional[str] = Query(None)):
    return get_abnormal_records(batch_id)


@router.post("/trace/abnormal", response_model=BatchAbnormalRecord)
def api_create_abnormal_record(inp: AbnormalRecordInput):
    try:
        return create_abnormal_record(inp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/trace/abnormal/{abnormal_id}", response_model=BatchAbnormalRecord)
def api_update_abnormal_record(abnormal_id: str, inp: AbnormalUpdateInput):
    result = update_abnormal_record(abnormal_id, inp)
    if not result:
        raise HTTPException(status_code=404, detail="异常记录不存在")
    return result


@router.get("/trace/batches/{batch_id}/transport-records", response_model=list[TransportQualityRecord])
def api_get_transport_records(batch_id: str):
    return get_transport_records(batch_id)


@router.post("/trace/transport-records", response_model=TransportQualityRecord)
def api_create_transport_record(inp: TransportRecordInput):
    try:
        return create_transport_record(inp)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/trace/batches/{batch_id}/quality-report", response_model=BatchQualityReport)
def api_get_quality_report(batch_id: str):
    result = generate_quality_report(batch_id)
    if not result:
        raise HTTPException(status_code=404, detail="批次不存在")
    return result


@router.post("/trace/batches/{batch_id}/mark-qualified", response_model=GrainBatch)
def api_mark_batch_qualified(batch_id: str):
    try:
        result = update_grain_batch(
            batch_id,
            BatchUpdateInput(status="qualified")
        )
        if not result:
            raise HTTPException(status_code=404, detail="批次不存在")
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
