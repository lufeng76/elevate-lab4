"""Track A — RAG retrieval tool (Vertex AI Search).

The agent uses this to semantically search the handbook corpus you ingested into
a Vertex AI Search data store (see rag/). It returns grounded context + citations.

Prerequisite: complete rag/README.md (terraform apply, ingest, verify) first.
"""
import logging
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import GoogleAPICallError, RetryError
from google.cloud import discoveryengine_v1 as discoveryengine

from .. import config

logger = logging.getLogger(__name__)


def search_policy_docs(query: str) -> dict:
    """Semantic search over the HR policy corpus in Vertex AI Search.

    Args:
        query: a natural-language policy question or search phrase.

    Returns:
        {"grounded_context": str, "citations": [str, ...]}
    """
    project_id = config.GOOGLE_CLOUD_PROJECT
    location = config.VERTEX_AI_SEARCH_LOCATION or "global"
    engine_id = config.VERTEX_AI_SEARCH_ENGINE_ID or "hr-policies-lab-engine"

    if not project_id:
        return {
            "grounded_context": "Error: GOOGLE_CLOUD_PROJECT is not configured.",
            "citations": [],
        }

    client_options = (
        ClientOptions(api_endpoint=f"{location}-discoveryengine.googleapis.com")
        if location != "global"
        else None
    )

    try:
        client = discoveryengine.SearchServiceClient(client_options=client_options)
        serving_config = (
            f"projects/{project_id}/locations/{location}/collections/default_collection"
            f"/engines/{engine_id}/servingConfigs/default_search"
        )
        content_spec = discoveryengine.SearchRequest.ContentSearchSpec(
            extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                max_extractive_answer_count=3,
                max_extractive_segment_count=3,
            )
        )
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=5,
            content_search_spec=content_spec,
        )
        response = client.search(request)

        context_chunks = []
        citations = []

        for i, result in enumerate(response.results, 1):
            struct_data = result.document.derived_struct_data or {}
            title = struct_data.get("title", f"Document {i}")
            link = struct_data.get("link", "")
            if link and link not in citations:
                citations.append(link)
            elif title and title not in citations:
                citations.append(title)

            doc_text_parts = []
            for answer in struct_data.get("extractive_answers", []):
                content = answer.get("content", "").strip()
                if content:
                    doc_text_parts.append(content)

            for segment in struct_data.get("extractive_segments", []):
                content = segment.get("content", "").strip()
                if content and content not in doc_text_parts:
                    doc_text_parts.append(content)

            for snippet in struct_data.get("snippets", []):
                snippet_text = snippet.get("snippet", "").strip()
                if snippet_text and snippet_text not in doc_text_parts:
                    doc_text_parts.append(snippet_text)

            if doc_text_parts:
                combined_text = "\n".join(doc_text_parts)
                context_chunks.append(f"[{title}]\n{combined_text}")

        if not context_chunks:
            return {
                "grounded_context": "No matching policy sections found in Vertex AI Search.",
                "citations": [],
            }

        return {
            "grounded_context": "\n\n".join(context_chunks),
            "citations": citations,
        }

    except (GoogleAPICallError, RetryError) as e:
        logger.error(
            "Vertex AI Search API call failed for query %r (project=%s, engine=%s): %s",
            query,
            project_id,
            engine_id,
            e,
            exc_info=True,
        )
        return {
            "grounded_context": f"Vertex AI Search API error: {e}",
            "citations": [],
        }
    except (KeyError, AttributeError, ValueError) as e:
        logger.error(
            "Data structure parsing error processing Vertex AI Search results for query %r: %s",
            query,
            e,
            exc_info=True,
        )
        return {
            "grounded_context": f"Error parsing policy search response: {e}",
            "citations": [],
        }
    except Exception as e:
        logger.error(
            "Unexpected error in search_policy_docs for query %r: %s",
            query,
            e,
            exc_info=True,
        )
        return {
            "grounded_context": f"Unexpected error searching policy documents: {e}",
            "citations": [],
        }

