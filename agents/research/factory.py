from agents.research.claims import LLMClaimGenerator
from agents.research.evidence import SnippetEvidenceExtractor
from agents.research.pipeline import ResearchPipeline
from agents.research.providers.tavily import TavilySearchProvider
from agents.research.search import SearchService
from agents.research.synthesizer import LLMResearchSynthesizer
from core.config import settings


def create_research_pipeline() -> ResearchPipeline:
    """
    Build the production ResearchPipeline.

    Tavily:
        real web search

    SnippetEvidenceExtractor:
        converts search snippets into Evidence

    LLMClaimGenerator:
        creates evidence-linked claims

    LLMResearchSynthesizer:
        produces summary and caveats
    """

    if not settings.tavily_api_key:
        raise RuntimeError(
            "TAVILY_API_KEY is required to run "
            "the web-backed Research Agent."
        )

    search_provider = TavilySearchProvider(
        settings.tavily_api_key
    )

    search_service = SearchService(
        search_provider
    )

    evidence_extractor = (
        SnippetEvidenceExtractor()
    )

    claim_generator = (
        LLMClaimGenerator()
    )

    synthesizer = (
        LLMResearchSynthesizer()
    )

    return ResearchPipeline(
        search_service=search_service,
        evidence_extractor=evidence_extractor,
        claim_generator=claim_generator,
        synthesizer=synthesizer,
    )