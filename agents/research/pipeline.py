from agents.research.synthesizer import (
    ResearchSynthesizer,
)

from agents.research.assembler import (
    ResearchResultAssembler,
)
from agents.research.claims import (
    ClaimGenerator,
)
from agents.research.evidence import (
    EvidenceExtractor,
)
from agents.research.schemas import (
    Claim,
    Evidence,
    ResearchResult,
    Source,
)
from agents.research.search import (
    SearchService,
)
from agents.research.sources import (
    search_hits_to_sources,
)



class ResearchPipeline:
    """
    Coordinates the complete structured research flow.

    Question
        -> Search
        -> Sources
        -> Evidence
        -> Claims
        -> Synthesis
        -> ResearchResult
    """

    def __init__(
        self,
        *,
        search_service: SearchService,
        evidence_extractor: EvidenceExtractor,
        claim_generator: ClaimGenerator,
        synthesizer: ResearchSynthesizer,
        assembler: ResearchResultAssembler | None = None,
    ) -> None:
        self.search_service = search_service
        self.evidence_extractor = evidence_extractor
        self.claim_generator = claim_generator
        self.synthesizer = synthesizer
        self.assembler = (
            assembler
            or ResearchResultAssembler()
        )

    async def run(
        self,
        question: str,
        *,
        max_results: int = 5,
        max_evidence: int = 10,
        max_claims: int = 8,
    ) -> ResearchResult:
        question = question.strip()

        if not question:
            raise ValueError(
                "Question cannot be empty."
            )

        hits = await self.search_service.search(
            question,
            max_results=max_results,
        )

        if not hits:
            return self.assembler.assemble(
                question=question,
                summary=(
                    "No supporting web evidence "
                    "was retrieved for this question."
                ),
                sources=[],
                evidence=[],
                claims=[],
                caveats=[
                    (
                        "The research pipeline could not "
                        "retrieve supporting sources."
                    )
                ],
            )

        sources = search_hits_to_sources(
            hits
        )

        evidence = (
            await self.evidence_extractor.extract(
                question,
                hits,
                sources,
                max_evidence=max_evidence,
            )
        )

        claims = (
            await self.claim_generator.generate(
                question,
                evidence,
                max_claims=max_claims,
            )
        )

        synthesis = (
            await self.synthesizer.synthesize(
                question,
                claims,
                evidence,
                sources,
            )
        )

        return self.assembler.assemble(
            question=question,
            summary=synthesis.summary,
            sources=sources,
            evidence=evidence,
            claims=claims,
            caveats=list(
                synthesis.caveats
            ),
        )