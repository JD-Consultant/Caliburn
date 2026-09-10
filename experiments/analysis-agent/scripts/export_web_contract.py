"""Export actual API Pydantic models without constructing services or clients."""
import json
from pydantic import TypeAdapter
from analysis_agent.jd_routes import ManualSaveRejection
from analysis_agent.api import (DocumentInput, DocumentOutput, MessageInput, MessageOutput,
    RunOutput, MemoryStatusOutput, DocumentMetadataInput, RunLookupOutput)

if __name__ == '__main__':
    schema = TypeAdapter(DocumentInput | DocumentOutput | MessageInput | MessageOutput |
        RunOutput | MemoryStatusOutput | DocumentMetadataInput | RunLookupOutput | ManualSaveRejection).json_schema()
    print(json.dumps(schema, ensure_ascii=False))
