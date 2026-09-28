"""
vision/detection/merged_detector.py
Multi-Detector Aggregator & Cross-Model Deduplication Engine (Step 6 & Step 11).

Combines:
  1. YOLODetector (YOLO11n): High-speed detection of workers and standard COCO entities.
  2. IndustrialDetector (YOLO-World): Open-vocabulary detection of industrial assets
     (forklifts, industrial vehicles, machinery, robotic arms, conveyors, pallets, safety barriers, electrical cabinets).
  3. Domain Filter: Rejects nonsensical COCO classes (e.g. boat, sports ball, bench) in industrial environments.
  4. Cross-Model IoU Merging & Priority Resolution: Resolves overlapping detections between detectors.
"""
import logging
from typing import Dict, List, Optional, Set, Tuple, Union
import numpy as np

from backend.schemas.detection import BoundingBox, ClassGroup, DetectionResult, FrameDetections, infer_class_group
from configs.settings import get_settings
from vision.detection.base import BaseDetector
from vision.detection.industrial_detector import IndustrialDetector
from vision.detection.yolo_detector import YOLODetector
from vision.preprocessing.frame import FrameData

logger = logging.getLogger("intelliwatch.merged_detector")


def compute_box_iou(box_a: BoundingBox, box_b: BoundingBox) -> float:
    """Computes Intersection-over-Union (IoU) between two bounding boxes."""
    x_left = max(box_a.x1, box_b.x1)
    y_top = max(box_a.y1, box_b.y1)
    x_right = min(box_a.x2, box_b.x2)
    y_bottom = min(box_a.y2, box_b.y2)

    if x_right <= x_left or y_bottom <= y_top:
        return 0.0

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    area_a = max(0.0, box_a.x2 - box_a.x1) * max(0.0, box_a.y2 - box_a.y1)
    area_b = max(0.0, box_b.x2 - box_b.x1) * max(0.0, box_b.y2 - box_b.y1)
    union_area = area_a + area_b - intersection_area

    if union_area <= 0.0:
        return 0.0

    return float(intersection_area / union_area)


class MultiDetectorAggregator(BaseDetector):
    """
    Unified multi-detector perception engine combining general COCO YOLO11n
    and industrial open-vocabulary YOLO-World with domain-specific filtering
    and cross-model deduplication.
    """

    def __init__(
        self,
        general_detector: Optional[YOLODetector] = None,
        industrial_detector: Optional[IndustrialDetector] = None,
        cross_model_iou_thresh: float = 0.40,
        filter_irrelevant_coco: Optional[bool] = None,
        irrelevant_classes: Optional[List[str]] = None,
    ):
        settings = get_settings()
        self.general_detector = general_detector
        self.industrial_detector = industrial_detector
        self.cross_model_iou_thresh = cross_model_iou_thresh

        self.filter_irrelevant_coco = (
            filter_irrelevant_coco
            if filter_irrelevant_coco is not None
            else getattr(settings, "FILTER_IRRELEVANT_COCO_CLASSES", True)
        )
        self.irrelevant_classes: Set[str] = set(
            c.lower().strip()
            for c in (
                irrelevant_classes
                if irrelevant_classes is not None
                else getattr(settings, "IRRELEVANT_COCO_CLASSES", [])
            )
        )

    def load_model(self, model_path: str) -> None:
        """Delegates loading to general detector if provided."""
        if self.general_detector:
            self.general_detector.load_model(model_path)

    def filter_detections(self, detections: List[DetectionResult]) -> List[DetectionResult]:
        """Filters out nonsensical non-industrial COCO classes."""
        if not self.filter_irrelevant_coco or not self.irrelevant_classes:
            return detections

        filtered: List[DetectionResult] = []
        for det in detections:
            cname = det.class_name.lower().strip()
            # If from general COCO detector and in irrelevant list, drop it
            if det.source_model == "yolo11n" and cname in self.irrelevant_classes:
                logger.debug(f"Filtering out irrelevant COCO class '{cname}' (conf: {det.confidence:.2f})")
                continue
            filtered.append(det)
        return filtered

    def merge_detections(
        self,
        general_dets: List[DetectionResult],
        industrial_dets: List[DetectionResult],
    ) -> List[DetectionResult]:
        """
        Merges general and industrial detections with IoU deduplication and priority resolution:
          - If boxes overlap significantly (IoU >= threshold):
              * Industrial classification takes precedence over generic COCO vehicles/objects (e.g. boat/car/truck -> forklift).
              * For persons, the detection with higher confidence is kept.
              * Otherwise, the higher confidence detection is retained.
          - Non-overlapping detections are both kept.
        """
        if not general_dets:
            return list(industrial_dets)
        if not industrial_dets:
            return list(general_dets)

        # Industrial detections take precedence for vehicles and machinery
        suppressed_general_indices: Set[int] = set()
        suppressed_industrial_indices: Set[int] = set()

        for g_idx, g_det in enumerate(general_dets):
            for i_idx, i_det in enumerate(industrial_dets):
                if i_idx in suppressed_industrial_indices or g_idx in suppressed_general_indices:
                    continue

                iou = compute_box_iou(g_det.bbox, i_det.bbox)
                if iou >= self.cross_model_iou_thresh:
                    # Overlapping detection found! Resolve priority:
                    g_is_person = g_det.class_group == ClassGroup.PERSON
                    i_is_person = i_det.class_group == ClassGroup.PERSON

                    if g_is_person and i_is_person:
                        # Both detect person: choose higher confidence
                        if g_det.confidence >= i_det.confidence:
                            suppressed_industrial_indices.add(i_idx)
                        else:
                            suppressed_general_indices.add(g_idx)
                    elif i_det.class_group in (ClassGroup.VEHICLE, ClassGroup.MACHINE, ClassGroup.INFRASTRUCTURE):
                        # Industrial detector classified as vehicle/machine/infra: prioritize industrial
                        suppressed_general_indices.add(g_idx)
                    elif g_det.confidence > i_det.confidence + 0.20:
                        # General detector has substantially higher confidence
                        suppressed_industrial_indices.add(i_idx)
                    else:
                        # Default to industrial model for domain-specific perception
                        suppressed_general_indices.add(g_idx)

        merged: List[DetectionResult] = []
        for g_idx, g_det in enumerate(general_dets):
            if g_idx not in suppressed_general_indices:
                merged.append(g_det)

        for i_idx, i_det in enumerate(industrial_dets):
            if i_idx not in suppressed_industrial_indices:
                merged.append(i_det)

        return merged

    def detect(
        self,
        frame: Union[np.ndarray, FrameData],
        frame_id: Optional[int] = None,
        timestamp: Optional[float] = None,
    ) -> FrameDetections:
        """
        Executes multi-detector perception on the input frame.
        """
        fid = frame.frame_index if isinstance(frame, FrameData) and frame_id is None else (frame_id or 0)
        ts = frame.timestamp if isinstance(frame, FrameData) and timestamp is None else (timestamp or 0.0)

        # 1. Run General Detector (YOLO11n)
        general_dets: List[DetectionResult] = []
        source_w, source_h = None, None
        if self.general_detector is not None:
            raw_gen = self.general_detector.detect(frame, frame_id=fid, timestamp=ts)
            general_dets = raw_gen.detections
            source_w = raw_gen.frame_width
            source_h = raw_gen.frame_height

        # 2. Filter irrelevant COCO classes
        filtered_general = self.filter_detections(general_dets)

        # 3. Run Industrial Detector (YOLO-World)
        industrial_dets: List[DetectionResult] = []
        if self.industrial_detector is not None:
            raw_ind = self.industrial_detector.detect(frame, frame_id=fid, timestamp=ts)
            industrial_dets = raw_ind.detections
            if source_w is None:
                source_w = raw_ind.frame_width
                source_h = raw_ind.frame_height

        # 4. Merge detections with IoU deduplication
        final_detections = self.merge_detections(filtered_general, industrial_dets)

        return FrameDetections(
            frame_id=fid,
            timestamp=round(ts, 4),
            detections=final_detections,
            frame_width=source_w,
            frame_height=source_h,
        )
