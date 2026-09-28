import logging
from typing import Dict, List, Optional, Set, Tuple, Union

from backend.schemas.detection import BoundingBox, DetectionResult, FrameDetections
from backend.schemas.ppe import AssociatedPPEItem, FramePPEAssociation, WorkerPPEInventory
from backend.schemas.tracking import FrameTracks, TrackedObject
from configs.settings import get_settings

logger = logging.getLogger("intelliwatch.ppe_association")


# Anatomical definition: (y_min_relative, y_max_relative, y_ideal_relative, body_region)
ANATOMICAL_REGIONS: Dict[str, Tuple[float, float, float, str]] = {
    "hardhat": (-0.25, 0.40, 0.08, "head"),
    "goggles": (-0.05, 0.35, 0.18, "face"),
    "mask": (0.02, 0.40, 0.22, "face"),
    "safety vest": (0.10, 0.75, 0.40, "torso"),
    "gloves": (0.30, 1.10, 0.70, "hands"),
}

# Synonyms and negative violation mapping
CLASS_NAME_NORMALIZATION: Dict[str, Tuple[str, bool]] = {
    # Positive gear
    "hardhat": ("Hardhat", False),
    "helmet": ("Hardhat", False),
    "hard hat": ("Hardhat", False),
    "safety vest": ("Safety Vest", False),
    "vest": ("Safety Vest", False),
    "safety-vest": ("Safety Vest", False),
    "gloves": ("Gloves", False),
    "glove": ("Gloves", False),
    "goggles": ("Goggles", False),
    "goggle": ("Goggles", False),
    "safety glasses": ("Goggles", False),
    "glasses": ("Goggles", False),
    "mask": ("Mask", False),
    "face mask": ("Mask", False),
    # Negative violation indicators
    "no-hardhat": ("Hardhat", True),
    "no-helmet": ("Hardhat", True),
    "no-hard hat": ("Hardhat", True),
    "no_hardhat": ("Hardhat", True),
    "no-safety vest": ("Safety Vest", True),
    "no-vest": ("Safety Vest", True),
    "no_safety vest": ("Safety Vest", True),
    "no-gloves": ("Gloves", True),
    "no-glove": ("Gloves", True),
    "no_gloves": ("Gloves", True),
    "no-goggles": ("Goggles", True),
    "no-goggle": ("Goggles", True),
    "no_goggles": ("Goggles", True),
    "no-mask": ("Mask", True),
    "no_mask": ("Mask", True),
}


class PPEAssociationEngine:
    """
    Transparent geometric spatial reasoning engine that associates detected PPE items
    with persistent tracked workers (ByteTrack output).

    Spatial Evidence Model:
      1. Bounding-Box Containment: Measures what fraction of the PPE bounding box is contained
         within the candidate worker's bounding box.
      2. Relative Anatomical Sub-regions: Ensures gear items are located where expected on a human body
         (e.g., Hardhat on upper head, Vest on torso, Goggles on face, Gloves near hands/hips).
      3. Horizontal Span Verification: Rejects detections horizontally outside the worker's body bounds.
      4. Competitive Disambiguation: If a PPE item lies near multiple workers, it assigns it to the worker
         with the strongest spatial evidence.
      5. Strict False-Association Guard: Discards detections without sufficiently strong spatial fit,
         designating them as 'unassociated PPE detections'.
    """

    def __init__(
        self,
        association_threshold: Optional[float] = None,
        containment_threshold: Optional[float] = None,
        horizontal_margin: float = 0.20,
        person_classes: Optional[Set[str]] = None,
    ):
        settings = get_settings()
        self.association_threshold = (
            association_threshold
            if association_threshold is not None
            else getattr(settings, "PPE_ASSOCIATION_IOU_THRESHOLD", 0.10)
        )
        self.containment_threshold = (
            containment_threshold
            if containment_threshold is not None
            else getattr(settings, "PPE_CENTER_CONTAINMENT_THRESHOLD", 0.50)
        )
        self.horizontal_margin = horizontal_margin
        self.person_classes = person_classes or {"person", "worker"}

    def normalize_class(self, raw_class_name: str) -> Optional[Tuple[str, bool]]:
        """
        Normalizes raw detector class name to (canonical_name, is_negative).
        Returns None for general person detections or unrecognized non-PPE classes.
        """
        cleaned = raw_class_name.lower().strip()
        if cleaned in ("person", "worker"):
            return None
        return CLASS_NAME_NORMALIZATION.get(cleaned, (raw_class_name.title(), False))

    @staticmethod
    def compute_box_intersection_area(b1: BoundingBox, b2: BoundingBox) -> float:
        """Calculates area of intersection between two bounding boxes in pixels."""
        ix1 = max(b1.x1, b2.x1)
        iy1 = max(b1.y1, b2.y1)
        ix2 = min(b1.x2, b2.x2)
        iy2 = min(b1.y2, b2.y2)

        iw = max(0.0, ix2 - ix1)
        ih = max(0.0, iy2 - iy1)
        return iw * ih

    def compute_spatial_score(
        self,
        person_box: BoundingBox,
        ppe_box: BoundingBox,
        canonical_class: str,
    ) -> float:
        """
        Computes an explainable spatial association score between a candidate worker
        and a PPE bounding box in the range [0.0, 1.0].
        """
        pw = person_box.width
        ph = person_box.height
        if pw <= 0.0 or ph <= 0.0:
            return 0.0

        ppe_area = ppe_box.width * ppe_box.height
        if ppe_area <= 0.0:
            return 0.0

        cx_ppe, cy_ppe = ppe_box.center

        # 1. Horizontal Span Verification
        x_min_allowed = person_box.x1 - (self.horizontal_margin * pw)
        x_max_allowed = person_box.x2 + (self.horizontal_margin * pw)
        if cx_ppe < x_min_allowed or cx_ppe > x_max_allowed:
            return 0.0

        # 2. Anatomical Vertical Region Verification
        norm_class = canonical_class.lower().strip()
        y_min_rel, y_max_rel, y_ideal_rel, _ = ANATOMICAL_REGIONS.get(
            norm_class, (-0.20, 1.15, 0.50, "general")
        )

        y_rel = (cy_ppe - person_box.y1) / ph
        if y_rel < y_min_rel or y_rel > y_max_rel:
            return 0.0

        # 3. Containment Ratio (Fraction of PPE box inside person box)
        inter_area = self.compute_box_intersection_area(person_box, ppe_box)
        containment = min(1.0, inter_area / ppe_area)

        # 4. Center Containment bonus
        center_inside = (
            person_box.x1 <= cx_ppe <= person_box.x2 and
            person_box.y1 <= cy_ppe <= person_box.y2
        )

        # 5. Anatomical Vertical Alignment Score
        vert_diff = abs(y_rel - y_ideal_rel)
        v_span = max(0.1, y_max_rel - y_min_rel)
        v_score = max(0.0, 1.0 - (vert_diff / v_span))

        # 6. Horizontal Alignment Score (closeness to worker's vertical centerline)
        cx_person, _ = person_box.center
        h_score = max(0.0, 1.0 - (abs(cx_ppe - cx_person) / (pw / 2.0 + 1e-6)))

        # Weighted combination of geometric spatial factors
        score = (0.45 * containment) + (0.35 * v_score) + (0.20 * h_score)

        if center_inside:
            score = min(1.0, score + 0.10)

        return round(float(score), 4)

    def associate(
        self,
        tracks: Union[FrameTracks, List[TrackedObject]],
        ppe_detections: Union[FrameDetections, List[DetectionResult]],
        frame_id: Optional[int] = None,
        timestamp: Optional[float] = None,
    ) -> FramePPEAssociation:
        """
        Associates PPE detections with tracked persons for a given video frame.

        Args:
            tracks: FrameTracks schema or list of TrackedObject instances.
            ppe_detections: FrameDetections schema or list of DetectionResult objects.
            frame_id: Frame number override if lists are provided.
            timestamp: Timestamp override if lists are provided.

        Returns:
            FramePPEAssociation containing WorkerPPEInventory for each tracked person
            and unassociated PPE items.
        """
        # Unpack tracks
        if isinstance(tracks, FrameTracks):
            fid = tracks.frame_id
            ts = tracks.timestamp
            tracked_list = tracks.active_tracks
        else:
            fid = 0 if frame_id is None else frame_id
            ts = 0.0 if timestamp is None else timestamp
            tracked_list = tracks

        # Filter for tracked persons
        person_tracks: List[TrackedObject] = [
            t for t in tracked_list if t.class_name.lower().strip() in self.person_classes
        ]

        # Unpack PPE detections
        if isinstance(ppe_detections, FrameDetections):
            det_list = ppe_detections.detections
            if frame_id is None:
                fid = ppe_detections.frame_id
            if timestamp is None:
                ts = ppe_detections.timestamp
        else:
            det_list = ppe_detections

        # Prepare worker inventories
        worker_inventories: Dict[int, WorkerPPEInventory] = {}
        for p in person_tracks:
            worker_inventories[p.track_id] = WorkerPPEInventory(
                track_id=p.track_id,
                timestamp=ts,
                bbox=p.bbox,
                items=[],
                ppe_status={},
                missing_ppe=[],
                present_ppe=[],
                unknown_ppe=[],
            )

        unassociated_ppe: List[DetectionResult] = []

        if not person_tracks or not det_list:
            # If no persons or no PPE items, all PPE detections remain unassociated
            if not person_tracks and det_list:
                for det in det_list:
                    norm = self.normalize_class(det.class_name)
                    if norm is not None:
                        unassociated_ppe.append(det)

            return FramePPEAssociation(
                frame_id=fid,
                timestamp=ts,
                worker_inventories=list(worker_inventories.values()),
                unassociated_ppe=unassociated_ppe,
            )

        # Process each PPE detection
        for ppe_det in det_list:
            norm_res = self.normalize_class(ppe_det.class_name)
            if norm_res is None:
                # Skip general person detections from PPE model
                continue

            canonical_class, is_neg = norm_res
            _, _, _, body_reg = ANATOMICAL_REGIONS.get(
                canonical_class.lower(), (0, 0, 0, "general")
            )

            best_person_id: Optional[int] = None
            best_score: float = 0.0

            for p in person_tracks:
                score = self.compute_spatial_score(
                    person_box=p.bbox,
                    ppe_box=ppe_det.bbox,
                    canonical_class=canonical_class,
                )

                if score >= self.association_threshold and score > best_score:
                    best_score = score
                    best_person_id = p.track_id

            if best_person_id is not None and best_score >= self.association_threshold:
                # Successfully associated with best candidate person
                associated_item = AssociatedPPEItem(
                    class_id=ppe_det.class_id,
                    class_name=canonical_class,
                    confidence=ppe_det.confidence,
                    bbox=ppe_det.bbox,
                    association_score=best_score,
                    is_negative=is_neg,
                    body_region=body_reg,
                )
                worker_inventories[best_person_id].items.append(associated_item)
                logger.debug(
                    f"Frame {fid}: Associated {canonical_class} (score={best_score:.2f}) "
                    f"with Track #{best_person_id}"
                )
            else:
                # Weak or zero spatial association -> unassociated
                unassociated_ppe.append(ppe_det)
                logger.debug(
                    f"Frame {fid}: PPE detection {ppe_det.class_name} unassociated "
                    f"(best_score={best_score:.2f} < thresh={self.association_threshold})"
                )

        return FramePPEAssociation(
            frame_id=fid,
            timestamp=ts,
            worker_inventories=list(worker_inventories.values()),
            unassociated_ppe=unassociated_ppe,
        )
