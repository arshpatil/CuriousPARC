"""
backend/services/job_manager.py
In-process job management and execution service for media upload and direct analysis.
Executes EndToEndPipelineOrchestrator across uploaded images and videos without external broker dependencies.
Guarantees thread safety, safe path validation, and technical honesty.
"""
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from backend.schemas.analysis import (
    AnalysisStatusResponse,
    ImageAnalysisResponse,
    JobStatus,
    MediaType,
    VideoAnalysisResultResponse,
    VideoJobSubmitResponse,
)
from backend.schemas.assessment import FrameAssessment
from backend.schemas.risk import RiskLevel
from backend.services.incident_store import get_incident_store
from backend.services.pipeline_manager import get_pipeline_manager
from configs.settings import get_settings

logger = logging.getLogger("intelliwatch.job_manager")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_UPLOADS_DIR = PROJECT_ROOT / "data" / "input" / "uploads"
OUTPUT_UPLOADS_DIR = PROJECT_ROOT / "data" / "output" / "uploads"

# Supported media extensions
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}

# File size limits (local prototype safety)
MAX_IMAGE_SIZE_BYTES = 25 * 1024 * 1024   # 25 MB
MAX_VIDEO_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


class JobManager:
    """
    Lightweight, in-process job manager coordinating synchronous image analysis
    and asynchronous background video processing.
    """

    def __init__(self):
        self.settings = get_settings()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

        # Deterministically guarantee storage directories exist
        INPUT_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        """Strips path traversal elements, returning a clean basename."""
        clean = Path(filename).name
        # Remove any non-alphanumeric chars except basic punctuation
        clean = re.sub(r"[^\w\.-]", "_", clean)
        return clean or "upload"

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves raw job record by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    # --------------------------------------------------------------------------
    # IMAGE ANALYSIS (Synchronous / Direct)
    # --------------------------------------------------------------------------
    def process_image(self, file_bytes: bytes, original_filename: str) -> ImageAnalysisResponse:
        """
        Validates, stores, and executes the complete intelligence pipeline on an uploaded image.
        Strictly observes single-frame spatial-only constraints (no fabricated temporal motion).
        """
        if not file_bytes or len(file_bytes) == 0:
            raise ValueError("Uploaded file is empty.")

        if len(file_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(f"Image size exceeds local maximum limit of {MAX_IMAGE_SIZE_BYTES // (1024*1024)}MB.")

        clean_name = self._sanitize_filename(original_filename)
        ext = Path(clean_name).suffix.lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError(
                f"Unsupported image format '{ext}'. Supported formats: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."
            )

        # Content validation: decode image buffer with OpenCV
        nparr = np.frombuffer(file_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            raise ValueError("Corrupted or unreadable image file. Failed to decode image pixels.")

        job_id = f"job_img_{uuid.uuid4().hex[:10]}"
        safe_input_name = f"{job_id}_input{ext}"
        safe_input_path = INPUT_UPLOADS_DIR / safe_input_name

        # Persist input image safely
        try:
            with open(safe_input_path, "wb") as f:
                f.write(file_bytes)
        except Exception as e:
            logger.error(f"Failed to save input image {safe_input_path}: {e}")
            raise IOError(f"Storage error saving uploaded image: {e}")

        # Execute end-to-end pipeline on single frame
        pipeline_mgr = get_pipeline_manager()
        orchestrator = pipeline_mgr.get_orchestrator()

        # Reset orchestrator to ensure tracking starts cleanly without state carryover
        orchestrator.reset()

        try:
            assessment, annotated_frame = orchestrator.process_frame(
                frame=image,
                frame_id=1,
                timestamp=0.0,
            )
        except Exception as e:
            logger.error(f"Pipeline error during image processing: {e}", exc_info=True)
            raise RuntimeError(f"Intelligence pipeline failed during image inference: {e}")

        # Save annotated image output
        safe_output_name = f"{job_id}_annotated.jpg"
        safe_output_path = OUTPUT_UPLOADS_DIR / safe_output_name
        try:
            cv2.imwrite(str(safe_output_path), annotated_frame)
        except Exception as e:
            logger.error(f"Failed to write annotated image {safe_output_path}: {e}")
            raise IOError(f"Storage error saving annotated image: {e}")

        # Extract summary counts
        detections_count = len(assessment.detections) if assessment.detections else 0
        workers_count = len(assessment.worker_inventories) if assessment.worker_inventories else 0
        non_compliant_count = assessment.non_compliant_workers_count
        highest_risk_level = assessment.highest_risk_level
        highest_risk_score = assessment.highest_risk_score
        new_incidents = assessment.new_incident_ids or []

        annotated_url = f"/api/v1/media/{safe_output_name}"
        original_url = f"/api/v1/media/{safe_input_name}"

        # Register completed job record
        job_record = {
            "job_id": job_id,
            "media_type": MediaType.IMAGE,
            "status": JobStatus.COMPLETED,
            "filename": clean_name,
            "input_path": safe_input_path,
            "output_path": safe_output_path,
            "annotated_media_url": annotated_url,
            "original_media_url": original_url,
            "assessment": assessment,
            "detections_count": detections_count,
            "workers_count": workers_count,
            "non_compliant_count": non_compliant_count,
            "highest_risk_level": highest_risk_level,
            "highest_risk_score": highest_risk_score,
            "new_incident_ids": new_incidents,
            "total_frames": 1,
            "processed_frames": 1,
            "created_at": time.time(),
            "completed_at": time.time(),
        }

        with self._lock:
            self._jobs[job_id] = job_record

        return ImageAnalysisResponse(
            job_id=job_id,
            media_type=MediaType.IMAGE,
            status=JobStatus.COMPLETED,
            filename=clean_name,
            annotated_media_url=annotated_url,
            original_media_url=original_url,
            is_single_frame=True,
            temporal_notice="Not available for single-frame analysis",
            assessment=assessment,
            detections_count=detections_count,
            workers_count=workers_count,
            non_compliant_count=non_compliant_count,
            highest_risk_level=highest_risk_level,
            highest_risk_score=highest_risk_score,
            new_incident_ids=new_incidents,
        )

    # --------------------------------------------------------------------------
    # VIDEO ANALYSIS (Asynchronous Background Job)
    # --------------------------------------------------------------------------
    def start_video_job(self, file_bytes: bytes, original_filename: str) -> VideoJobSubmitResponse:
        """
        Validates uploaded video, registers background job, and starts asynchronous processing.
        Does not block the HTTP request.
        """
        if not file_bytes or len(file_bytes) == 0:
            raise ValueError("Uploaded video file is empty.")

        if len(file_bytes) > MAX_VIDEO_SIZE_BYTES:
            raise ValueError(f"Video size exceeds local maximum limit of {MAX_VIDEO_SIZE_BYTES // (1024*1024)}MB.")

        clean_name = self._sanitize_filename(original_filename)
        ext = Path(clean_name).suffix.lower()
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise ValueError(
                f"Unsupported video format '{ext}'. Supported formats: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}."
            )

        job_id = f"job_vid_{uuid.uuid4().hex[:10]}"
        safe_input_name = f"{job_id}_input{ext}"
        safe_input_path = INPUT_UPLOADS_DIR / safe_input_name

        # Persist video input file
        try:
            with open(safe_input_path, "wb") as f:
                f.write(file_bytes)
        except Exception as e:
            logger.error(f"Failed to save uploaded video {safe_input_path}: {e}")
            raise IOError(f"Storage error saving uploaded video: {e}")

        # Content validation: verify OpenCV can open the video and it has > 0 frames
        cap = cv2.VideoCapture(str(safe_input_path))
        if not cap.isOpened():
            safe_input_path.unlink(missing_ok=True)
            raise ValueError("Corrupted or unreadable video file. Video stream could not be opened by decoder.")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 360

        # Attempt to read first frame to confirm decodability
        ret, first_frame = cap.read()
        cap.release()

        if not ret or first_frame is None:
            safe_input_path.unlink(missing_ok=True)
            raise ValueError("Corrupted video file: contains zero decodable video frames.")

        # Initialize job record
        job_record = {
            "job_id": job_id,
            "media_type": MediaType.VIDEO,
            "status": JobStatus.QUEUED,
            "filename": clean_name,
            "input_path": safe_input_path,
            "output_video_path": OUTPUT_UPLOADS_DIR / f"{job_id}_annotated.mp4",
            "latest_frame_path": OUTPUT_UPLOADS_DIR / f"{job_id}_latest.jpg",
            "annotated_frame_path": OUTPUT_UPLOADS_DIR / f"{job_id}_annotated.jpg",
            "total_frames": max(1, total_frames),
            "processed_frames": 0,
            "current_frame": 0,
            "progress_pct": 0.0,
            "processing_fps": 0.0,
            "avg_latency_ms": 0.0,
            "current_risk_level": "INFO",
            "highest_risk_tier": "INFO",
            "highest_risk_score": 0.0,
            "active_tracks": 0,
            "incidents_count": 0,
            "new_incident_ids": [],
            "error_message": None,
            "fps": fps,
            "width": width,
            "height": height,
            "created_at": time.time(),
            "completed_at": None,
        }

        with self._lock:
            self._jobs[job_id] = job_record

        # Launch background processing worker thread
        worker_thread = threading.Thread(
            target=self._run_video_worker,
            args=(job_id,),
            daemon=True,
            name=f"worker-{job_id}",
        )
        worker_thread.start()

        return VideoJobSubmitResponse(
            job_id=job_id,
            status=JobStatus.QUEUED,
            media_type=MediaType.VIDEO,
            filename=clean_name,
            message="Video analysis queued successfully. Polling status endpoint for live progress.",
        )

    def _run_video_worker(self, job_id: str) -> None:
        """
        Background worker executing the full IntelliWatch intelligence pipeline frame-by-frame.
        Updates AssessmentStore live so the operator dashboard reflects progress in real time.
        """
        job = self.get_job(job_id)
        if not job:
            return

        with self._lock:
            job["status"] = JobStatus.PROCESSING

        input_path = job["input_path"]
        output_video_path = job["output_video_path"]
        latest_frame_path = job["latest_frame_path"]
        annotated_frame_path = job["annotated_frame_path"]

        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            with self._lock:
                job["status"] = JobStatus.FAILED
                job["error_message"] = "Failed to open video source for decoding."
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 360
        total_frames = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))

        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(output_video_path), fourcc, fps, (width, height))

        pipeline_mgr = get_pipeline_manager()
        orchestrator = pipeline_mgr.get_orchestrator()
        incident_store = get_incident_store()

        # Reset orchestrator state so tracking IDs, zones, and risk start fresh for this video
        orchestrator.reset()

        frame_idx = 0
        all_new_incidents: List[str] = []
        highest_risk_score = 0.0
        highest_risk_tier = "INFO"
        risk_rank = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

        t_video_start = time.perf_counter()

        try:
            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                frame_idx += 1
                current_timestamp = frame_idx / fps

                # Run complete perception and intelligence pipeline
                assessment, annotated_frame = orchestrator.process_frame(
                    frame=frame,
                    frame_id=frame_idx,
                    timestamp=current_timestamp,
                )

                # Ensure dimensions match video writer
                if (annotated_frame.shape[1], annotated_frame.shape[0]) != (width, height):
                    annotated_frame_resized = cv2.resize(annotated_frame, (width, height))
                else:
                    annotated_frame_resized = annotated_frame

                if writer.isOpened():
                    writer.write(annotated_frame_resized)

                # Save latest frame snapshot periodically for real-time visual streaming
                try:
                    cv2.imwrite(str(latest_frame_path), annotated_frame_resized)
                except Exception:
                    pass

                # Update accumulated metrics
                curr_risk = assessment.highest_risk_level.value if hasattr(assessment.highest_risk_level, "value") else str(assessment.highest_risk_level)
                curr_score = assessment.highest_risk_score

                if curr_score > highest_risk_score:
                    highest_risk_score = curr_score
                if risk_rank.get(curr_risk, 0) > risk_rank.get(highest_risk_tier, 0):
                    highest_risk_tier = curr_risk

                if assessment.new_incident_ids:
                    all_new_incidents.extend(assessment.new_incident_ids)

                t_now = time.perf_counter()
                elapsed = max(0.001, t_now - t_video_start)
                current_fps = frame_idx / elapsed
                avg_latency = (elapsed / frame_idx) * 1000.0

                progress = min(100.0, round((frame_idx / total_frames) * 100.0, 1))

                # Update live job telemetry
                with self._lock:
                    job["current_frame"] = frame_idx
                    job["processed_frames"] = frame_idx
                    job["progress_pct"] = progress
                    job["processing_fps"] = round(current_fps, 1)
                    job["avg_latency_ms"] = round(avg_latency, 1)
                    job["current_risk_level"] = curr_risk
                    job["highest_risk_tier"] = highest_risk_tier
                    job["highest_risk_score"] = round(highest_risk_score, 1)
                    job["active_tracks"] = assessment.total_active_tracks
                    job["incidents_count"] = len(all_new_incidents)
                    job["new_incident_ids"] = list(set(all_new_incidents))

            # Loop completed successfully
            cap.release()
            if writer.isOpened():
                writer.release()

            # Save the final annotated frame as permanent representative snapshot
            if latest_frame_path.exists():
                try:
                    import shutil
                    shutil.copyfile(latest_frame_path, annotated_frame_path)
                except Exception:
                    pass

            perf = orchestrator.get_performance_stats()

            with self._lock:
                job["status"] = JobStatus.COMPLETED
                job["completed_at"] = time.time()
                job["progress_pct"] = 100.0
                job["annotated_video_url"] = f"/api/v1/media/{job_id}_annotated.mp4"
                job["latest_frame_url"] = f"/api/v1/media/{job_id}_annotated.jpg"
                job["average_fps"] = perf.get("processing_fps", round(job["processing_fps"], 1))
                job["average_latency_ms"] = perf.get("avg_latency_ms", round(job["avg_latency_ms"], 1))

            logger.info(
                f"Video job {job_id} COMPLETED: {frame_idx} frames, "
                f"{job.get('average_fps')} FPS, {len(all_new_incidents)} incidents."
            )

        except Exception as e:
            logger.error(f"Error during video worker execution for {job_id}: {e}", exc_info=True)
            cap.release()
            if writer.isOpened():
                writer.release()

            with self._lock:
                job["status"] = JobStatus.FAILED
                job["error_message"] = f"Pipeline execution failed: {str(e)}"
                job["completed_at"] = time.time()

    # --------------------------------------------------------------------------
    # STATUS & RESULTS RETRIEVAL
    # --------------------------------------------------------------------------
    def get_job_status(self, job_id: str) -> Optional[AnalysisStatusResponse]:
        """Returns structured status telemetry for polling."""
        job = self.get_job(job_id)
        if not job:
            return None

        annotated_url = None
        if job["status"] == JobStatus.COMPLETED:
            if job["media_type"] == MediaType.VIDEO:
                annotated_url = f"/api/v1/media/{job_id}_annotated.mp4"
            else:
                annotated_url = f"/api/v1/media/{job_id}_annotated.jpg"

        latest_url = f"/api/v1/media/{job_id}_latest.jpg" if (OUTPUT_UPLOADS_DIR / f"{job_id}_latest.jpg").exists() else None

        return AnalysisStatusResponse(
            job_id=job["job_id"],
            media_type=job["media_type"],
            status=job["status"],
            progress_pct=job.get("progress_pct", 0.0),
            current_frame=job.get("current_frame", 0),
            processed_frames=job.get("processed_frames", 0),
            total_frames=job.get("total_frames", 0),
            processing_fps=job.get("processing_fps", 0.0),
            avg_latency_ms=job.get("avg_latency_ms", 0.0),
            current_risk_level=job.get("current_risk_level", "INFO"),
            active_tracks=job.get("active_tracks", 0),
            incidents_count=job.get("incidents_count", 0),
            annotated_media_url=annotated_url,
            latest_frame_url=latest_url,
            error_message=job.get("error_message"),
        )

    def get_video_result(self, job_id: str) -> Optional[VideoAnalysisResultResponse]:
        """Returns final summary metrics for a completed video analysis job."""
        job = self.get_job(job_id)
        if not job:
            return None

        return VideoAnalysisResultResponse(
            job_id=job["job_id"],
            media_type=MediaType.VIDEO,
            status=job["status"],
            filename=job["filename"],
            annotated_video_url=f"/api/v1/media/{job_id}_annotated.mp4" if job["status"] == JobStatus.COMPLETED else None,
            total_frames=job.get("total_frames", 0),
            processed_frames=job.get("processed_frames", 0),
            average_fps=job.get("average_fps", job.get("processing_fps", 0.0)),
            average_latency_ms=job.get("average_latency_ms", job.get("avg_latency_ms", 0.0)),
            total_incidents=job.get("incidents_count", 0),
            highest_risk_tier=job.get("highest_risk_tier", "INFO"),
            highest_risk_score=job.get("highest_risk_score", 0.0),
            new_incident_ids=job.get("new_incident_ids", []),
            error_message=job.get("error_message"),
        )

    # --------------------------------------------------------------------------
    # SAFE MEDIA RETRIEVAL
    # --------------------------------------------------------------------------
    def get_media_file_path(self, media_id: str) -> Optional[Path]:
        """
        Safely retrieves a media file from upload directories.
        Guarantees strict path traversal prevention.
        """
        # Strict alphanumeric + underscore + hyphen + dot validation
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", media_id):
            return None

        if ".." in media_id or "/" in media_id or "\\" in media_id:
            return None

        # Check in output uploads directory first
        cand_out = (OUTPUT_UPLOADS_DIR / media_id).resolve()
        if cand_out.exists() and cand_out.is_file():
            try:
                if cand_out.is_relative_to(PROJECT_ROOT):
                    return cand_out
            except AttributeError:
                # Python < 3.9 compatibility fallback
                if str(cand_out).startswith(str(PROJECT_ROOT)):
                    return cand_out

        # Check in input uploads directory
        cand_in = (INPUT_UPLOADS_DIR / media_id).resolve()
        if cand_in.exists() and cand_in.is_file():
            try:
                if cand_in.is_relative_to(PROJECT_ROOT):
                    return cand_in
            except AttributeError:
                if str(cand_in).startswith(str(PROJECT_ROOT)):
                    return cand_in

        return None


# Global singleton instance
_job_manager_instance = JobManager()


def get_job_manager() -> JobManager:
    """Returns singleton JobManager instance."""
    return _job_manager_instance
