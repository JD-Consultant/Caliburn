"""Memory 查閱沿固定發布身分，導覽共用同一物件描述。"""

from pydantic import StrictStr

from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.http.models.common import HttpModel, NonnegativeInteger, WireUuid


class MemoryMapItem(HttpModel):
    object_id: WireUuid
    title: StrictStr
    description: StrictStr


class PublishedMemory(HttpModel):
    snapshot_id: WireUuid | None
    covered_through_sequence: NonnegativeInteger
    work_situations: list[MemoryMapItem]
    work_understandings: list[MemoryMapItem]


class PublishedMemoryObject(HttpModel):
    snapshot_id: WireUuid
    object_id: WireUuid
    layer: MemoryLayer
    title: StrictStr
    description: StrictStr
    body: StrictStr
