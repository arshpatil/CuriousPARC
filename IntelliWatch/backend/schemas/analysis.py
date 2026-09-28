"""
backend/schemas/analysis.py
Schemas for Dashboard Media Upload and Direct Analysis.
Supports single-frame image perception and multi-frame video reasoning jobs.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.schemas.assessment import FrameAssessment
from backend.schemas.risk import RiskLevel


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class ImageAnalysisResponse(BaseModel):
    """
    Response schema for synchronous or direct image analysis.
    Explicitly discloses single-frame limitations to maintain technical honesty.
    """
    job_id: str = Field(..., description="Unique analysis job identifier")
    media_type: MediaType = Field(default=MediaType.IMAGE, description="Analyzed media type")
    status: JobStatus = Field(default=JobStatus.COMPLETED, description="Analysis job status")
    filename: str = Field(..., description="Original uploaded filename (sanitized for display)")
    annotated_media_url: str = Field(..., description="URL to retrieve the visual annotated result")
    original_media_url: Optional[str] = Field(default=None, description="URL to retrieve original uploaded image")
    is_single_frame: bool = Field(default=True, description="Indicates single-frame spatial perception")
    temporal_notice: str = Field(
        default="Not available for single-frame analysis",
        description="Explicit limitation notice regarding temporal tracking and movement",
    )
    assessment: FrameAssessment = Field(..., description="Full end-to-end frame assessment")
    detections_count: int = Field(default=0, description="Total detected objects count")
    workers_count: int = Field(default=0, description="Total detected workers count")
    non_compliant_count: int = Field(default=0, description="Count of workers with PPE violations")
    highest_risk_level: RiskLevel = Field(default=RiskLevel.INFO, description="Peak active risk tier")
    highest_risk_score: float = Field(default=0.0, description="Peak active risk score")
    new_incident_ids: List[str] = Field(default_factory=list, description="IDs of any confirmed incidents recorded")


class VideoJobSubmitResponse(BaseModel):
    """
    Response schema returned immediately upon video upload.
    Indicates asynchronous queue status to prevent HTTP request timeouts.
    """
    job_id: str = Field(..., description="Unique asynchronous video processing job ID")
    status: JobStatus = Field(default=JobStatus.QUEUED, description="Initial job status")
    media_type: MediaType = Field(default=MediaType.VIDEO, description="Type of media submitted")
    filename: str = Field(..., description="Uploaded filename (sanitized)")
    message: str = Field(
        default="Video analysis job queued successfully. Poll status endpoint for progress.",
        description="Status description",
    )


class AnalysisStatusResponse(BaseModel):
    """
    Polling telemetry response schema during video analysis.
    Uses real measured metrics; does not fabricate progress or FPS.
    """
    job_id: str = Field(..., description="Unique analysis job identifier")
    media_type: MediaType = Field(..., description="Media type being processed")
    status: JobStatus = Field(..., description="Current lifecycle status")
    progress_pct: float = Field(default=0.0, description="Actual processed progress percentage (0-100)")
    current_frame: int = Field(default=0, description="Index of most recently processed frame")
    processed_frames: int = Field(default=0, description="Total frames processed so far")
    total_frames: int = Field(default=0, description="Total detectable frames in video source")
    processing_fps: float = Field(default=0.0, description="Actual measured throughput in FPS on CPU")
    avg_latency_ms: float = Field(default=0.0, description="Actual measured latency per frame in ms")
    current_risk_level: str = Field(default="INFO", description="Current frame risk tier")
    active_tracks: int = Field(default=0, description="Active persistent tracks count")
    incidents_count: int = Field(default=0, description="Total confirmed incidents recorded so far")
    annotated_media_url: Optional[str] = Field(default=None, description="URL to completed annotated video")
    latest_frame_url: Optional[str] = Field(default=None, description="URL to current frame visual preview")
    error_message: Optional[str] = Field(default=None, description="User-safe error explanation if failed")


class VideoAnalysisResultResponse(BaseModel):
    """
    Final comprehensive summary response schema upon video analysis completion.
    """
    job_id: str = Field(..., description="Unique analysis job identifier")
    media_type: MediaType = Field(default=MediaType.VIDEO, description="Media type")
    status: JobStatus = Field(default=JobStatus.COMPLETED, description="Final job status")
    filename: str = Field(..., description="Uploaded video filename")
    annotated_video_url: Optional[str] = Field(default=None, description="Downloadable/playable video URL")
    total_frames: int = Field(default=0, description="Total frames present in video")
    processed_frames: int = Field(default=0, description="Total frames processed by orchestrator")
    average_fps: float = Field(default=0.0, description="Actual measured processing throughput (FPS)")
    average_latency_ms: float = Field(default=0.0, description="Average measured latency per frame (ms)")
    total_incidents: int = Field(default=0, description="Total confirmed safety incidents recorded")
    highest_risk_tier: str = Field(default="INFO", description="Highest risk tier observed across all frames")
    highest_risk_score: float = Field(default=0.0, description="Peak risk score observed across all frames")
    new_incident_ids: List[str] = Field(default_factory=list, description="IDs of all confirmed incidents recorded")
    error_message: Optional[str] = Field(default=None, description="User-safe error explanation if failed")
