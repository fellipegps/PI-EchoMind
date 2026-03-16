# Exporta todos os modelos para facilitar o import no init_db
from app.models.admin import Admin
from app.models.faq import FAQ
from app.models.document import Document, DocumentChunk
from app.models.event import Event
from app.models.interaction import Interaction
from app.models.unanswered import UnansweredQuestion

__all__ = [
    "Admin",
    "FAQ",
    "Document",
    "DocumentChunk",
    "Event",
    "Interaction",
    "UnansweredQuestion",
]
