"""Source port double only; artifacts use real InMemoryStore/StoreBackend."""
import re


class ExampleSource:
    def __init__(self, document_id="document-a"):
        self.document_id = document_id
        self.reference = f"conversation:{document_id}:original"
        self.context_reference = f"conversation:{document_id}:context"
        self.material = {self.reference: "原話\r\n  例外由主管核准。",
            self.context_reference: "誰負責核准？"}
        self.validations = []
        self.reads = []
        self.unavailable = False

    def validate_reference(self, reference):
        self.validations.append(reference)
        if not isinstance(reference, str) or re.fullmatch(
                rf"conversation:{re.escape(self.document_id)}:[a-z]+", reference) is None:
            raise ValueError("Invalid source reference or document")

    def read(self, reference):
        self.validate_reference(reference)
        self.reads.append(reference)
        if self.unavailable or reference not in self.material:
            raise ValueError("Source unavailable")
        return self.material[reference]

    def validate_pair(self, source_reference, context_reference):
        """This double issues no planned pairs, so it only checks addresses."""
        self.validate_reference(source_reference)
        self.validate_reference(context_reference)
