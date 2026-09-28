"""
backend/schemas/scene_graph.py
Step 9 - Scene Graph and Situational Awareness schemas.
Represents factual relationships between people, machinery, objects, zones, PPE, and behavior.
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.schemas.detection import BoundingBox


class SceneNodeType(str, Enum):
    """Semantic classification of a scene graph node."""
    PERSON = "PERSON"
    VEHICLE = "VEHICLE"
    MACHINE = "MACHINE"
    OBJECT = "OBJECT"
    PPE = "PPE"
    ZONE = "ZONE"
    OTHER = "OTHER"


class SceneRelationType(str, Enum):
    """Semantic relationship between two scene graph nodes."""
    WEARING = "WEARING"                   # Person -> PPE
    MISSING = "MISSING"                   # Person -> Missing PPE item
    INSIDE = "INSIDE"                     # Entity -> Zone
    OUTSIDE = "OUTSIDE"                   # Entity -> Zone
    BEHAVIOR = "BEHAVIOR"                 # Entity -> Behavior representation
    NEAR = "NEAR"                         # Entity <-> Entity spatial proximity
    FAR = "FAR"                           # Entity <-> Entity distant
    APPROACHING = "APPROACHING"           # Entity -> Entity distance decreasing over time
    MOVING_AWAY = "MOVING_AWAY"           # Entity -> Entity distance increasing over time
    ASSOCIATED_WITH = "ASSOCIATED_WITH"   # General association
    INTERACTING_WITH = "INTERACTING_WITH" # Physical or operational interaction


class RelationLifecycle(str, Enum):
    """Lifecycle phase of a tracked relationship across consecutive frames."""
    CREATED = "CREATED"   # Newly confirmed in the current frame
    ACTIVE = "ACTIVE"     # Confirmed and persisting across frames
    ENDED = "ENDED"       # Ended in the current frame (condition ceased or actor departed)


class SceneNode(BaseModel):
    """
    Structured entity node in the industrial scene graph.
    Represents tracked entities, physical equipment, PPE, or spatial zones.
    """
    node_id: str = Field(..., description="Unique alphanumeric identifier (e.g. 'person_17', 'zone_high_voltage')")
    node_type: SceneNodeType = Field(..., description="Semantic category of the node")
    class_name: str = Field(..., description="Detector or category label (e.g. 'person', 'forklift', 'Hardhat')")
    track_id: Optional[int] = Field(default=None, description="ByteTrack persistent identifier for tracked entities")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Model detection confidence if applicable")
    bbox: Optional[BoundingBox] = Field(default=None, description="2D bounding box in original image pixels")
    centroid: Optional[Tuple[float, float]] = Field(default=None, description="(cx, cy) pixel coordinates")
    contact_point: Optional[Tuple[float, float]] = Field(default=None, description="Physical floor contact point (feet/base)")
    zone_id: Optional[str] = Field(default=None, description="Zone identifier if node represents a zone")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary verifiable properties (e.g. depth, compliance)")
    timestamp: float = Field(default=0.0, description="Video timestamp in seconds")


class SceneRelation(BaseModel):
    """
    Directed factual relationship between two scene nodes with evidence and lifecycle state.
    """
    relation_id: str = Field(..., description="Unique deterministic identifier for this relationship instance")
    source_node_id: str = Field(..., description="Origin node ID (e.g. 'person_17')")
    target_node_id: str = Field(..., description="Destination node ID (e.g. 'zone_high_voltage' or 'forklift_2')")
    relation_type: SceneRelationType = Field(..., description="Semantic relationship category")
    lifecycle: RelationLifecycle = Field(default=RelationLifecycle.ACTIVE, description="Current lifecycle state")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Explainable evidence confidence score")
    timestamp: float = Field(default=0.0, description="Timestamp of the current observation")
    first_seen_timestamp: Optional[float] = Field(default=None, description="Timestamp when relation was first observed")
    last_seen_timestamp: Optional[float] = Field(default=None, description="Timestamp when relation was most recently observed")
    duration_seconds: float = Field(default=0.0, description="Elapsed seconds this relationship has persisted")
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Factual evidence supporting this relation (e.g. distance_px, contact_point, score)",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional contextual metadata")


class SituationalSummary(BaseModel):
    """
    Machine-readable aggregate summary of current scene status.
    """
    workers_count: int = Field(default=0, description="Count of active tracked persons in scene")
    vehicles_count: int = Field(default=0, description="Count of active tracked vehicles (forklifts, trucks)")
    machines_count: int = Field(default=0, description="Count of active machinery entities")
    objects_count: int = Field(default=0, description="Count of general objects")
    active_zones_count: int = Field(default=0, description="Count of configured and active restricted zones")
    occupied_zones_count: int = Field(default=0, description="Count of restricted zones currently occupied by workers")
    workers_in_restricted_zones: int = Field(default=0, description="Count of workers confirmed inside any restricted zone")
    workers_non_compliant_ppe: int = Field(default=0, description="Count of workers missing mandatory PPE")
    rapid_movement_count: int = Field(default=0, description="Count of entities exhibiting rapid movement")
    stationary_loitering_count: int = Field(default=0, description="Count of entities exhibiting prolonged stationarity")
    possible_fall_count: int = Field(default=0, description="Count of entities flagged with possible fall heuristic")
    active_proximity_relationships: int = Field(default=0, description="Count of active NEAR spatial relationships")
    active_approaching_relationships: int = Field(default=0, description="Count of active APPROACHING relationships")
    total_active_relationships: int = Field(default=0, description="Total count of active edges in the scene graph")


class FrameScene(BaseModel):
    """
    Complete structured situational representation of a single video frame.
    """
    frame_id: Optional[int] = Field(default=None, description="Monotonically increasing frame sequence counter")
    timestamp: float = Field(..., description="Video stream elapsed time in seconds")
    camera_id: str = Field(default="cam_01", description="Identifier of the video capture source")
    nodes: List[SceneNode] = Field(default_factory=list, description="All entity and spatial nodes in this frame")
    relationships: List[SceneRelation] = Field(default_factory=list, description="All active and newly ended relationships")
    summary: SituationalSummary = Field(default_factory=SituationalSummary, description="High-level machine-readable summary")
    active_zones: List[str] = Field(default_factory=list, description="List of zone IDs evaluated in this scene")
    active_behaviors: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of node_id -> confirmed primary behavior string",
    )

    def get_node(self, node_id: str) -> Optional[SceneNode]:
        """Lookup node by its unique node_id."""
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def get_relations_for_node(self, node_id: str) -> List[SceneRelation]:
        """Find all relationships where the node is either source or target."""
        return [r for r in self.relationships if r.source_node_id == node_id or r.target_node_id == node_id]

    def get_relations_between(self, source_id: str, target_id: str) -> List[SceneRelation]:
        """Find relationships directed from source to target."""
        return [r for r in self.relationships if r.source_node_id == source_id and r.target_node_id == target_id]
