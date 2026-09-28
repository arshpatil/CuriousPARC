import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Union
import numpy as np
from ultralytics import YOLO

from backend.schemas.detection import BoundingBox, DetectionResult, FrameDetections
from configs.settings import get_settings
from vision.detection.base import BaseDetector
from vision.detection.coordinates import unpad_and_rescale_bbox
from vision.preprocessing.frame import FrameData

logger = logging.getLogger("intelliwatch.yolo_detector")


class ModelLoadError(Exception):
    """Raised when YOLO weights fail to load."""
    pass


class InferenceError(Exception):
    """Raised when model inference fails on a frame."""
    pass


class YOLODetector(BaseDetector):
    """
    Production-grade YOLO detector integrated with IntelliWatch perception schemas.
    Supports:
      - YOLO11 / YOLOv8 pretrained or custom checkpoints.
      - Confidence thresholding & Non-Maximum Suppression (IoU) configuration.
      - Dynamic class name/ID filtering.
      - Automatic coordinate re-projection to original CCTV aspect ratio and resolution.
    """
    # Default class attributes for uninitialized instances
    _model: Optional[YOLO] = None
    _class_names: Dict[int, str] = {}

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
        device: Optional[str] = "cpu",
        classes: Optional[List[Union[str, int]]] = None,
        imgsz: int = 640,
        map_to_original: bool = True,
    ):
        settings = get_settings()
        self.model_path = model_path or getattr(settings, "DETECTION_MODEL_PATH", settings.MODEL_PATH)
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else getattr(settings, "DETECTION_CONFIDENCE_THRESHOLD", 0.25)
        )
        self.iou_threshold = iou_threshold if iou_threshold is not None else settings.IOU_THRESHOLD
        self.device = device or getattr(settings, "DETECTION_DEVICE", "cpu")
        self.imgsz = imgsz
        self.map_to_original = map_to_original

        self._filter_classes: Optional[Set[Union[str, int]]] = set(classes) if classes else None
        self._model: Optional[YOLO] = None
        self._class_names: Dict[int, str] = {}

        if self.model_path:
            self.load_model(self.model_path)

    @property
    def class_names(self) -> Dict[int, str]:
        """Returns map of class IDs to human-readable names."""
        return self._class_names

    @property
    def is_loaded(self) -> bool:
        """Returns True if model weights are loaded and ready."""
        return self._model is not None

    def load_model(self, model_path: str) -> None:
        """
        Loads YOLO model weights via Ultralytics.
        """
        logger.info(f"Loading YOLO model weights from: {model_path} on device [{self.device}]")
        try:
            resolved_path = Path(model_path)
            # If path points to non-existent local file, check weights/ subdirectory
            if not resolved_path.exists():
                fallback = Path("weights") / resolved_path.name
                if fallback.exists():
                    resolved_path = fallback

            self._model = YOLO(str(resolved_path))
            self.model_path = str(resolved_path)
            self._class_names = dict(self._model.names) if hasattr(self._model, "names") else {}

            logger.info(
                f"Successfully loaded YOLO model [{self.model_path}] with {len(self._class_names)} classes."
            )
        except Exception as e:
            msg = f"Failed to load YOLO model from '{model_path}': {e}"
            logger.error(msg)
            raise ModelLoadError(msg) from e

    def set_class_filter(self, classes: Optional[List[Union[str, int]]]) -> None:
        """
        Configures an active class filter.
        Only detections whose class name or ID is in the set will be returned.
        Pass None to disable filtering and return all detections.
        """
        self._filter_classes = set(classes) if classes else None
        logger.info(f"Active class filter set to: {self._filter_classes}")

    def detect(
        self,
        frame: Union[np.ndarray, FrameData],
        frame_id: Optional[int] = None,
        timestamp: Optional[float] = None,
    ) -> FrameDetections:
        """
        Executes YOLO inference on a frame or preprocessed FrameData.

        Returns:
            FrameDetections containing bounding boxes transformed back to
            the original video coordinates.
        """
        if self._model is None:
            raise ModelLoadError("Model must be loaded before running inference.")

        if frame is None:
            raise ValueError("Input frame cannot be None.")

        # Determine input representation
        is_frame_data = isinstance(frame, FrameData)
        if is_frame_data:
            img = frame.image
            fid = frame.frame_index if frame_id is None else frame_id
            ts = frame.timestamp if timestamp is None else timestamp
            scale_factor = frame.scale_factor
            pad_offset = frame.pad_offset
            orig_shape = frame.original_shape
            source_w = orig_shape[1] if orig_shape else frame.width
            source_h = orig_shape[0] if orig_shape else frame.height
        else:
            img = frame
            fid = 0 if frame_id is None else frame_id
            ts = 0.0 if timestamp is None else timestamp
            scale_factor = None
            pad_offset = None
            orig_shape = None
            source_w = frame.shape[1] if frame.ndim >= 2 else None
            source_h = frame.shape[0] if frame.ndim >= 2 else None

        if not isinstance(img, np.ndarray) or img.size == 0:
            raise ValueError("Frame image must be a non-empty numpy.ndarray.")

        # Execute YOLO inference
        try:
            results = self._model(
                source=img,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                imgsz=self.imgsz,
                device=self.device,
                verbose=False,
            )
        except Exception as e:
            msg = f"Inference failed on frame {fid}: {e}"
            logger.error(msg)
            raise InferenceError(msg) from e

        detections: List[DetectionResult] = []

        if results and len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            for box in boxes:
                conf = float(box.conf[0])
                if conf < self.confidence_threshold:
                    continue

                cls_id = int(box.cls[0])
                cls_name = self._class_names.get(cls_id, f"class_{cls_id}")

                # Apply class filtering if active
                if self._filter_classes is not None:
                    if cls_id not in self._filter_classes and cls_name not in self._filter_classes:
                        continue

                coords = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                raw_bbox = BoundingBox(
                    x1=float(coords[0]),
                    y1=float(coords[1]),
                    x2=float(coords[2]),
                    y2=float(coords[3]),
                )

                # Map back to original CCTV coordinates if letterboxing was applied
                if self.map_to_original and (scale_factor is not None or pad_offset is not None):
                    final_bbox = unpad_and_rescale_bbox(
                        bbox=raw_bbox,
                        scale_factor=scale_factor,
                        pad_offset=pad_offset,
                        original_shape=orig_shape,
                    )
                else:
                    # Clamp raw bbox to image dimensions
                    max_w = float(source_w or img.shape[1])
                    max_h = float(source_h or img.shape[0])
                    final_bbox = BoundingBox(
                        x1=round(max(0.0, min(max_w, raw_bbox.x1)), 2),
                        y1=round(max(0.0, min(max_h, raw_bbox.y1)), 2),
                        x2=round(max(0.0, min(max_w, max(raw_bbox.x1, raw_bbox.x2))), 2),
                        y2=round(max(0.0, min(max_h, max(raw_bbox.y1, raw_bbox.y2))), 2),
                    )

                detections.append(
                    DetectionResult(
                        class_id=cls_id,
                        class_name=cls_name,
                        confidence=round(conf, 4),
                        bbox=final_bbox,
                        source_model="yolo11n",
                        frame_index=fid,
                        timestamp=round(ts, 4),
                    )
                )

        return FrameDetections(
            frame_id=fid,
            timestamp=round(ts, 4),
            detections=detections,
            frame_width=source_w,
            frame_height=source_h,
        )
