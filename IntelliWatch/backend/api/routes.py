from pathlib import Path
from typing import List, Optional, Union
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from backend.schemas.health import HealthResponse
from backend.schemas.video import VideoMetadataSchema, VideoInspectRequest
from backend.schemas.scene_graph import FrameScene
from backend.schemas.risk import FrameRiskAssessment, RiskEvent, RiskLevel
from backend.schemas.prediction import FramePredictionAssessment, EarlyWarningIndicator
from configs.settings import get_settings
from vision.preprocessing.video_reader import VideoReader, VideoFileNotFoundError, VideoOpenError

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def get_health() -> HealthResponse:
    """
    Health check endpoint to verify backend operational readiness.
    Must always return {"status": "ok", "project": "IntelliWatch"}.
    """
    return HealthResponse(status="ok", project=settings.PROJECT_NAME)


@router.get("/api/v1/config", tags=["Configuration"])
async def get_public_config():
    """
    Exposes sanitized non-sensitive runtime configurations.
    """
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "fps": settings.FPS_SETTINGS,
        "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
        "preprocessing": {
            "target_width": settings.TARGET_WIDTH,
            "target_height": settings.TARGET_HEIGHT,
            "resize_enabled": settings.RESIZE_ENABLED,
            "preserve_aspect_ratio": settings.PRESERVE_ASPECT_RATIO,
            "frame_sampling_interval": settings.FRAME_SAMPLING_INTERVAL,
        },
        "detection": {
            "model_path": settings.DETECTION_MODEL_PATH,
            "confidence_threshold": settings.DETECTION_CONFIDENCE_THRESHOLD,
            "iou_threshold": settings.DETECTION_IOU_THRESHOLD,
            "device": settings.DETECTION_DEVICE,
        },
        "tracking": {
            "enabled": settings.TRACKING_ENABLED,
            "tracker_type": settings.TRACKER_TYPE,
            "track_history_length": settings.TRACK_HISTORY_LENGTH,
            "track_high_thresh": settings.TRACK_HIGH_THRESH,
            "track_low_thresh": settings.TRACK_LOW_THRESH,
            "track_match_thresh": settings.TRACK_MATCH_THRESH,
            "track_buffer": settings.TRACK_BUFFER,
        },
        "ppe": {
            "enabled": settings.PPE_ENABLED,
            "model_path": settings.PPE_MODEL_PATH,
            "confidence_threshold": settings.PPE_CONFIDENCE_THRESHOLD,
            "iou_threshold": settings.PPE_IOU_THRESHOLD,
            "device": settings.PPE_DEVICE,
            "compliance_enabled": settings.PPE_COMPLIANCE_ENABLED,
            "required_classes": settings.PPE_REQUIRED_CLASSES,
            "association_iou_threshold": settings.PPE_ASSOCIATION_IOU_THRESHOLD,
            "center_containment_threshold": settings.PPE_CENTER_CONTAINMENT_THRESHOLD,
            "violation_confirmation_frames": settings.PPE_VIOLATION_CONFIRMATION_FRAMES,
        },
        "zones": {
            "enabled": settings.ZONE_DETECTION_ENABLED,
            "confirmation_frames": settings.ZONE_ENTRY_CONFIRMATION_FRAMES,
            "max_dwell_seconds": settings.ZONE_MAX_DWELL_SECONDS,
            "config_path": settings.ZONE_CONFIG_PATH,
        },
        "depth": {
            "enabled": settings.DEPTH_ENABLED,
            "model_name": settings.DEPTH_MODEL_NAME,
            "device": settings.DEPTH_DEVICE,
            "input_size": settings.DEPTH_INPUT_SIZE,
            "output_mode": settings.DEPTH_OUTPUT_MODE,
        },
        "scene_graph": {
            "enabled": settings.SCENE_GRAPH_ENABLED,
            "near_distance_threshold": settings.SCENE_NEAR_DISTANCE_THRESHOLD,
            "far_distance_threshold": settings.SCENE_FAR_DISTANCE_THRESHOLD,
            "confirmation_frames": settings.SCENE_RELATION_CONFIRMATION_FRAMES,
            "end_confirmation_frames": settings.SCENE_RELATION_END_CONFIRMATION_FRAMES,
            "approaching_enabled": settings.SCENE_APPROACHING_ENABLED,
            "depth_relation_enabled": settings.SCENE_DEPTH_RELATION_ENABLED,
            "depth_near_threshold": settings.SCENE_DEPTH_NEAR_THRESHOLD,
        },
        "risk": {
            "enabled": settings.RISK_ENGINE_ENABLED,
            "confirmation_frames": settings.RISK_EVENT_CONFIRMATION_FRAMES,
            "end_confirmation_frames": settings.RISK_EVENT_END_CONFIRMATION_FRAMES,
            "cooldown_frames": settings.RISK_EVENT_COOLDOWN_FRAMES,
            "compound_enabled": settings.RISK_COMPOUND_EVENT_ENABLED,
            "thresholds": {
                "info": settings.RISK_LEVEL_INFO_THRESHOLD,
                "low": settings.RISK_LEVEL_LOW_THRESHOLD,
                "medium": settings.RISK_LEVEL_MEDIUM_THRESHOLD,
                "high": settings.RISK_LEVEL_HIGH_THRESHOLD,
                "critical": settings.RISK_LEVEL_CRITICAL_THRESHOLD,
            },
        },
        "prediction": {
            "enabled": settings.PREDICTION_ENABLED,
            "history_frames": settings.PREDICTION_HISTORY_FRAMES,
            "horizon_frames": settings.PREDICTION_HORIZON_FRAMES,
            "min_track_history": settings.PREDICTION_MIN_TRACK_HISTORY,
            "confirmation_frames": settings.PREDICTION_CONFIRMATION_FRAMES,
            "end_confirmation_frames": settings.PREDICTION_END_CONFIRMATION_FRAMES,
            "risk_history_frames": settings.PREDICTION_RISK_HISTORY_FRAMES,
            "risk_escalation_threshold": settings.PREDICTION_RISK_ESCALATION_THRESHOLD,
            "zone_margin_px": settings.PREDICTION_ZONE_MARGIN,
            "anomaly_window": settings.PREDICTION_ANOMALY_WINDOW,
            "repeat_event_window": settings.PREDICTION_REPEAT_EVENT_WINDOW,
            "persistence_threshold": settings.PREDICTION_PERSISTENCE_THRESHOLD,
        },
    }



@router.get("/api/v1/video/metadata", response_model=VideoMetadataSchema, tags=["Video"])
async def get_video_metadata(
    video_path: str = Query(..., description="Path to local video file")
) -> VideoMetadataSchema:
    """
    Inspects a local video source and returns its stream metadata.
    """
    try:
        reader = VideoReader(video_path)
        meta = reader.open()
        reader.release()
        return VideoMetadataSchema(
            source_path=meta.source_path,
            fps=meta.fps,
            width=meta.width,
            height=meta.height,
            total_frames=meta.total_frames,
            duration_sec=meta.duration_sec,
        )
    except VideoFileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Video file not found: {video_path}")
    except VideoOpenError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error inspecting video: {e}")


@router.post("/api/v1/video/inspect", response_model=VideoMetadataSchema, tags=["Video"])
async def inspect_video(payload: VideoInspectRequest) -> VideoMetadataSchema:
    """
    POST endpoint to inspect local video metadata.
    """
    return await get_video_metadata(video_path=payload.video_path)


@router.get("/api/v1/scene/current", response_model=FrameScene, tags=["Scene Graph"])
async def get_current_scene() -> FrameScene:
    """
    Returns the current situational scene graph representation and summary.
    """
    from backend.services.scene_store import get_scene_store
    return get_scene_store().get_current_scene()


@router.get("/api/v1/risk/current", response_model=FrameRiskAssessment, tags=["Risk & Events"])
async def get_current_risk() -> FrameRiskAssessment:
    """
    Returns the current frame risk assessment, active events, and risk summary.
    """
    from backend.services.risk_store import get_risk_store
    return get_risk_store().get_current_assessment()


@router.get("/api/v1/events/current", response_model=List[RiskEvent], tags=["Risk & Events"])
async def get_current_events() -> List[RiskEvent]:
    """
    Returns the active confirmed safety and operational events currently detected.
    """
    from backend.services.risk_store import get_risk_store
    assessment = get_risk_store().get_current_assessment()
    return assessment.active_events


@router.get(
    "/api/v1/prediction/current",
    response_model=FramePredictionAssessment,
    tags=["Prediction & Early Warning"],
)
async def get_current_prediction() -> FramePredictionAssessment:
    """
    Returns the most recently computed early-warning prediction assessment,
    including projected trajectories, active early-warning indicators,
    and maximum indicator severity for the current video frame.
    """
    from backend.services.prediction_store import get_prediction_store
    return get_prediction_store().get_current_assessment()


@router.get(
    "/api/v1/prediction/indicators",
    response_model=List[EarlyWarningIndicator],
    tags=["Prediction & Early Warning"],
)
async def get_active_indicators() -> List[EarlyWarningIndicator]:
    """
    Returns only the currently active (CONFIRMED or ACTIVE lifecycle state)
    early-warning safety indicators from the most recent prediction assessment.
    """
    from backend.services.prediction_store import get_prediction_store
    assessment = get_prediction_store().get_current_assessment()
    return assessment.active_indicators


# ------------------------------------------------------------------------------
# STEP 15 ENDPOINTS: TEMPORAL INTELLIGENCE
# ------------------------------------------------------------------------------
from backend.schemas.temporal import TemporalLogEntry, TemporalEntityProfile


@router.get(
    "/api/v1/temporal/timeline",
    tags=["Temporal Intelligence"],
    summary="Recent temporal event timeline",
)
async def get_temporal_timeline(n: int = Query(default=30, ge=1, le=200)):
    """
    Returns up to N most recent meaningful state-change events across all entities.
    Only significant transitions are logged (behavior change, spatial tier change,
    risk escalation, early warning, incident confirmed). Not every frame.
    """
    from backend.services.temporal_log import get_temporal_log
    log = get_temporal_log()
    entries = log.recent_timeline(n=n)
    return [e.model_dump() for e in entries]


@router.get(
    "/api/v1/temporal/entities",
    tags=["Temporal Intelligence"],
    summary="Temporal entity profiles",
)
async def get_temporal_entity_profiles():
    """
    Returns temporal intelligence profiles for all currently tracked entities,
    including confirmed behavior, proximity state, risk trend, active early
    warnings, and per-entity transition timeline.
    """
    from backend.services.temporal_log import get_temporal_log
    from backend.services.assessment_store import get_assessment_store
    log = get_temporal_log()
    assessment = get_assessment_store().get_current_assessment()
    profiles = log.get_all_entity_profiles(assessment)
    return [p.model_dump() for p in profiles]


@router.get(
    "/api/v1/temporal/entity/{entity_id}",
    tags=["Temporal Intelligence"],
    summary="Single entity temporal profile",
)
async def get_temporal_entity(entity_id: str):
    """
    Returns the temporal profile for a specific entity by its scene-graph node ID
    (e.g. 'person_1', 'forklift_2').
    """
    from backend.services.temporal_log import get_temporal_log
    from backend.services.assessment_store import get_assessment_store
    log = get_temporal_log()
    assessment = get_assessment_store().get_current_assessment()
    profile = log.get_entity_profile(entity_id, assessment)
    if profile is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found in temporal log.")
    return profile.model_dump()


# ------------------------------------------------------------------------------
# STEP 12 ENDPOINTS: FRAME ASSESSMENT, INCIDENT EVIDENCE & SYSTEM STATUS
# ------------------------------------------------------------------------------
from typing import Optional
from fastapi.responses import FileResponse
from backend.schemas.assessment import FrameAssessment
from backend.schemas.evidence import IncidentRecord, SystemStatusResponse
from backend.schemas.explanation import (
    AnalyticsSummary,
    IncidentExplanationResponse,
    IncidentTimelineEntry,
)


@router.get(
    "/api/v1/assessment/current",
    response_model=FrameAssessment,
    tags=["Scene Assessment"],
)
async def get_current_assessment() -> FrameAssessment:
    """
    Returns the comprehensive, end-to-end scene understanding assessment for the current frame,
    combining detections, tracking, worker PPE compliance, zone occupancy, relative depth,
    temporal behavior, scene graph, safety risk assessment, and early warnings.
    """
    from backend.services.assessment_store import get_assessment_store
    return get_assessment_store().get_current_assessment()


@router.get(
    "/api/v1/incidents",
    response_model=List[IncidentRecord],
    tags=["Incident Evidence"],
)
async def list_incidents(
    status: Optional[str] = Query(None, description="Filter by lifecycle status: CONFIRMED, ACTIVE, ENDED"),
    risk_level: Optional[str] = Query(None, description="Filter by risk tier: INFO, LOW, MEDIUM, HIGH, CRITICAL"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    track_id: Optional[int] = Query(None, description="Filter by participating track ID"),
    zone: Optional[str] = Query(None, description="Filter by zone name or area"),
    limit: int = Query(50, ge=1, le=200, description="Max incidents to return"),
) -> List[IncidentRecord]:
    """
    Returns structured incident evidence records in reverse chronological order (newest first).
    Supports filtering by lifecycle status, classified risk severity, event type, track ID, and zone.
    """
    from backend.services.incident_store import get_incident_store
    return get_incident_store().list_incidents(
        status=status,
        risk_level=risk_level,
        event_type=event_type,
        track_id=track_id,
        zone=zone,
        limit=limit,
    )


@router.get(
    "/api/v1/incidents/{incident_id}",
    response_model=IncidentRecord,
    tags=["Incident Evidence"],
)
async def get_incident_by_id(incident_id: str) -> IncidentRecord:
    """
    Returns full structured details for a specific safety incident evidence record.
    """
    from backend.services.incident_store import get_incident_store
    inc = get_incident_store().get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")
    return inc


@router.get(
    "/api/v1/incidents/{incident_id}/explanation",
    response_model=IncidentExplanationResponse,
    tags=["Explainability & Evidence"],
    summary="Deterministic Five-W and risk breakdown explanation",
)
async def get_incident_explanation(incident_id: str) -> IncidentExplanationResponse:
    """
    Returns a comprehensive, deterministic Five-W incident explanation (WHO, WHAT, WHERE, WHEN, WHY),
    mathematical risk score breakdown, chronological incident timeline, and risk trend data.
    Zero generative AI or external LLMs used.
    """
    from backend.services.explanation_service import get_explanation_service
    expl = get_explanation_service().get_incident_explanation(incident_id)
    if not expl:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")
    return expl


@router.get(
    "/api/v1/incidents/{incident_id}/timeline",
    response_model=List[IncidentTimelineEntry],
    tags=["Explainability & Evidence"],
    summary="Chronological incident event progression timeline",
)
async def get_incident_timeline(incident_id: str) -> List[IncidentTimelineEntry]:
    """
    Returns chronological progression of state transitions (detection, behaviors,
    zones, risk escalation, early warnings) surrounding the specified incident.
    """
    from backend.services.explanation_service import get_explanation_service
    expl = get_explanation_service().get_incident_explanation(incident_id)
    if not expl:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")
    return expl.timeline


@router.get(
    "/api/v1/incidents/{incident_id}/package",
    tags=["Explainability & Evidence"],
    summary="Downloadable JSON evidence audit package",
)
async def get_incident_evidence_package(incident_id: str):
    """
    Returns a self-contained, auditable JSON evidence package combining metadata,
    Five-W explanation, risk breakdown, timeline, scene relationships, and predictive indicators.
    """
    from backend.services.explanation_service import get_explanation_service
    expl = get_explanation_service().get_incident_explanation(incident_id)
    if not expl:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    return {
        "format": "IntelliWatch Audit Evidence Package v1.0",
        "incident_id": expl.incident_id,
        "event_type": expl.event_type.value if hasattr(expl.event_type, "value") else str(expl.event_type),
        "risk_level": expl.risk_level.value if hasattr(expl.risk_level, "value") else str(expl.risk_level),
        "risk_score": expl.risk_score,
        "lifecycle_state": expl.lifecycle_state.value if hasattr(expl.lifecycle_state, "value") else str(expl.lifecycle_state),
        "timestamp_seconds": expl.timestamp,
        "frame_id": expl.frame_id,
        "camera_id": expl.camera_id,
        "five_w_explanation": expl.five_w.model_dump(),
        "risk_score_breakdown": expl.risk_breakdown.model_dump(),
        "chronological_timeline": [t.model_dump() for t in expl.timeline],
        "risk_trend_trajectory": [p.model_dump() for p in expl.risk_trend],
        "scene_relationships": expl.scene_relationships,
        "early_warning_indicators": expl.early_warnings,
        "has_visual_snapshot": expl.has_snapshot,
        "snapshot_url": expl.snapshot_url,
        "evidence_notice": expl.evidence_notice,
        "disclaimer": (
            "Explanations are generated deterministically from structured perception, tracking, "
            "compliance, and risk reasoning outputs; no generative AI is used for incident explanations."
        ),
    }


@router.get(
    "/api/v1/incidents/{incident_id}/evidence",
    tags=["Incident Evidence"],
)
async def get_incident_evidence(incident_id: str):
    """
    Retrieves the raw captured image evidence snapshot associated with a confirmed incident.
    Returns 404 with explainable detail if no visual snapshot was captured or stored.
    """
    from backend.services.incident_store import get_incident_store
    inc = get_incident_store().get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")
    if not inc.has_snapshot or not inc.snapshot_path:
        raise HTTPException(
            status_code=404,
            detail=f"No image snapshot evidence available for incident '{incident_id}' (metadata-only record)",
        )

    snap_path = Path(inc.snapshot_path)
    if not snap_path.exists():
        raise HTTPException(status_code=404, detail="Evidence snapshot file not found on disk")
    return FileResponse(str(snap_path), media_type="image/jpeg")


@router.get(
    "/api/v1/analytics/summary",
    response_model=AnalyticsSummary,
    tags=["Safety Analytics"],
    summary="Descriptive safety analytics summary metrics",
)
async def get_analytics_summary() -> AnalyticsSummary:
    """
    Returns descriptive statistical aggregations across all recorded safety incidents,
    including severity tier breakdown, event category distribution, and active zone frequencies.
    Technically honest: descriptive metrics only, zero worker ranking or employee profiling.
    """
    from backend.services.explanation_service import get_explanation_service
    return get_explanation_service().compute_analytics()


@router.get(
    "/api/v1/status",
    response_model=SystemStatusResponse,
    tags=["System Telemetry"],
)
async def get_system_status() -> SystemStatusResponse:
    """
    Returns operational telemetry, processing latency, device execution mode (CPU/CUDA),
    active models, and incident counts.
    """
    from backend.services.pipeline_manager import get_pipeline_manager
    return get_pipeline_manager().get_status()


# ------------------------------------------------------------------------------
# MEDIA UPLOAD & DIRECT ANALYSIS ENDPOINTS
# ------------------------------------------------------------------------------
from backend.schemas.analysis import (
    AnalysisStatusResponse,
    ImageAnalysisResponse,
    VideoAnalysisResultResponse,
    VideoJobSubmitResponse,
)
from backend.services.job_manager import get_job_manager

MEDIA_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
}


@router.post(
    "/api/v1/analyze/image",
    response_model=ImageAnalysisResponse,
    tags=["Media Analysis"],
)
async def analyze_image(
    file: UploadFile = File(..., description="Uploaded image file (JPG, JPEG, PNG)"),
) -> ImageAnalysisResponse:
    """
    Directly analyzes an uploaded single-frame image through the full intelligence pipeline.
    Maintains strict technical honesty regarding single-frame perception vs temporal motion.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file selected for image upload.")

    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded image data: {e}")

    try:
        response = get_job_manager().process_image(
            file_bytes=content,
            original_filename=file.filename,
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IOError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis error: {e}")


@router.post(
    "/api/v1/analyze/video",
    response_model=VideoJobSubmitResponse,
    status_code=202,
    tags=["Media Analysis"],
)
async def analyze_video(
    file: UploadFile = File(..., description="Uploaded video file (MP4, AVI, MOV, MKV)"),
) -> VideoJobSubmitResponse:
    """
    Accepts video upload, registers an asynchronous processing job, and immediately
    returns job_id. Prevents HTTP request timeout while background worker executes pipeline.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file selected for video upload.")

    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded video data: {e}")

    try:
        submit_res = get_job_manager().start_video_job(
            file_bytes=content,
            original_filename=file.filename,
        )
        return submit_res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IOError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video analysis initialization error: {e}")


@router.get(
    "/api/v1/analyze/status/{job_id}",
    response_model=AnalysisStatusResponse,
    tags=["Media Analysis"],
)
async def get_analysis_status(job_id: str) -> AnalysisStatusResponse:
    """
    Returns live progress telemetry for a video or image analysis job.
    Designed for frontend polling at ~1 second intervals.
    """
    status_res = get_job_manager().get_job_status(job_id)
    if not status_res:
        raise HTTPException(status_code=404, detail=f"Analysis job '{job_id}' not found")
    return status_res


@router.get(
    "/api/v1/analyze/result/{job_id}",
    tags=["Media Analysis"],
)
async def get_analysis_result(job_id: str):
    """
    Returns the final detailed analysis results for a completed job.
    Supports both ImageAnalysisResponse and VideoAnalysisResultResponse.
    """
    job = get_job_manager().get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Analysis job '{job_id}' not found")

    media_type = job.get("media_type")
    if media_type == "image":
        return ImageAnalysisResponse(
            job_id=job["job_id"],
            media_type=job["media_type"],
            status=job["status"],
            filename=job["filename"],
            annotated_media_url=job.get("annotated_media_url", ""),
            original_media_url=job.get("original_media_url"),
            is_single_frame=True,
            temporal_notice="Not available for single-frame analysis",
            assessment=job["assessment"],
            detections_count=job.get("detections_count", 0),
            workers_count=job.get("workers_count", 0),
            non_compliant_count=job.get("non_compliant_count", 0),
            highest_risk_level=job.get("highest_risk_level", RiskLevel.INFO),
            highest_risk_score=job.get("highest_risk_score", 0.0),
            new_incident_ids=job.get("new_incident_ids", []),
        )
    elif media_type == "video":
        res = get_job_manager().get_video_result(job_id)
        if not res:
            raise HTTPException(status_code=500, detail="Failed to build video result response")
        return res
    else:
        raise HTTPException(status_code=400, detail=f"Unknown media type for job '{job_id}'")


@router.get(
    "/api/v1/media/{media_id}",
    tags=["Media Storage"],
)
async def get_media_file(media_id: str):
    """
    Safely retrieves uploaded and annotated media assets.
    Prevents path traversal and validates file location.
    """
    file_path = get_job_manager().get_media_file_path(media_id)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Media file '{media_id}' not found or inaccessible")

    ext = file_path.suffix.lower()
    media_type = MEDIA_MIME_TYPES.get(ext, "application/octet-stream")
    return FileResponse(str(file_path), media_type=media_type)


# ------------------------------------------------------------------------------
# STEP 16 ENDPOINTS: SAFETY ZONES CONFIGURATION & MANAGEMENT
# ------------------------------------------------------------------------------
from backend.schemas.zones import (
    RestrictedZone,
    ZoneCreateRequest,
    ZoneUpdateRequest,
)
from backend.services.zone_service import get_zone_service


@router.get(
    "/api/v1/zones",
    response_model=List[RestrictedZone],
    tags=["Safety Zones"],
    summary="List configured safety zones",
)
async def list_zones(enabled_only: bool = Query(default=False, description="Filter for enabled zones only")):
    """
    Returns list of all configured polygonal safety zones.
    """
    return get_zone_service().list_zones(enabled_only=enabled_only)


@router.get(
    "/api/v1/zones/{zone_id}",
    response_model=RestrictedZone,
    tags=["Safety Zones"],
    summary="Retrieve single safety zone",
)
async def get_zone(zone_id: str):
    """
    Retrieves details and polygon vertices for a specific zone by unique ID.
    """
    zone = get_zone_service().get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Safety zone '{zone_id}' not found")
    return zone


@router.post(
    "/api/v1/zones",
    response_model=RestrictedZone,
    status_code=201,
    tags=["Safety Zones"],
    summary="Create a new safety zone",
)
async def create_zone(request: ZoneCreateRequest):
    """
    Creates and persists a new operator-defined safety zone.
    Validates polygon geometry, bounds, and automatically updates the active ZoneEngine.
    """
    try:
        new_zone = get_zone_service().create_zone(request)
        return new_zone
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create safety zone: {e}")


@router.put(
    "/api/v1/zones/{zone_id}",
    response_model=RestrictedZone,
    tags=["Safety Zones"],
    summary="Update an existing safety zone",
)
async def update_zone(zone_id: str, request: ZoneUpdateRequest):
    """
    Updates configuration, polygon, or dwell limits for an existing safety zone.
    Immediately re-compiles contours in the active ZoneEngine and persists changes.
    """
    try:
        updated = get_zone_service().update_zone(zone_id, request)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Safety zone '{zone_id}' not found")
        return updated
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update safety zone: {e}")


@router.delete(
    "/api/v1/zones/{zone_id}",
    tags=["Safety Zones"],
    summary="Delete a safety zone",
)
async def delete_zone(zone_id: str):
    """
    Deletes an existing safety zone from active monitoring and configuration storage.
    """
    success = get_zone_service().delete_zone(zone_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Safety zone '{zone_id}' not found")
    return {"status": "deleted", "zone_id": zone_id}


@router.post(
    "/api/v1/zones/reload",
    tags=["Safety Zones"],
    summary="Reload zones from configuration file",
)
async def reload_zones():
    """
    Reloads safety zone definitions from the persistent configuration file.
    """
    count = get_zone_service().reload_from_disk()
    return {"status": "reloaded", "total_zones": count}



