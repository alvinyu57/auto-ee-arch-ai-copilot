"""Offline acceptance probe with a controlled HTTP LLM; no production mock fallback.

uv run python scripts/verify_phase2.py --output /tmp/phase2-workflow.json
"""

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

import httpx

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.main import create_app
from ee_arch_copilot.rag.generation.answer_generator import CompatibleLLMProvider
from ee_arch_copilot.rag.ingestion.loader import load_file
from ee_arch_copilot.rag.service import KnowledgeService


async def verify(output: Path) -> None:
    provider_calls = 0

    def controlled_llm(request: httpx.Request) -> httpx.Response:
        nonlocal provider_calls
        provider_calls += 1
        context = json.loads(json.loads(request.content)["messages"][1]["content"])
        evidence = context["untrusted_evidence"][0]
        response = {
            "answer": evidence["text"] + " [S1]",
            "citation_ids": ["S1"],
            "referenced_requirement_ids": [evidence["requirement_id"]],
        }
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(response)}}]}
        )

    with tempfile.TemporaryDirectory(prefix="ee-rag-workflow-") as directory:
        settings = Settings(vector_db_path=Path(directory), llm_model="controlled-e2e-llm")
        provider = CompatibleLLMProvider(settings, httpx.MockTransport(controlled_llm))
        service = KnowledgeService(settings, llm_provider=provider)
        app = create_app(settings, service)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            ingestions = []
            for path in sorted(Path("data/knowledge/synthetic").glob("*.md")):
                source = load_file(path, document_id=path.stem, version="1.0")
                response = await client.post(
                    "/api/v1/knowledge/documents", json=source.model_dump()
                )
                response.raise_for_status()
                assert response.json()["status"] == "created"
                ingestions.append(response.json())
                repeated = await client.post(
                    "/api/v1/knowledge/documents", json=source.model_dump()
                )
                assert repeated.json()["status"] == "unchanged"
            assert len(ingestions) == 4
            request = {
                "question": (
                    "Which requirements define Ethernet bandwidth between "
                    "the Central Gateway and ADAS controller?"
                ),
                "options": {"method": "hybrid", "final_top_k": 3},
            }
            response = await client.post("/api/v1/knowledge/search", json=request)
            response.raise_for_status()
            search = response.json()
            assert search["hits"][0]["chunk"]["requirement_id"] == "REQ-ETH-002"
            for hit in search["hits"]:
                citation = await client.get("/api/v1/knowledge/chunks/" + hit["chunk"]["chunk_id"])
                assert citation.json() == hit["chunk"]
            modes = {}
            for method in ("keyword", "semantic", "hybrid"):
                result = await client.post(
                    "/api/v1/knowledge/search",
                    json={
                        "question": "REQ-SOA-015",
                        "options": {"method": method},
                    },
                )
                assert result.json()["hits"][0]["chunk"]["requirement_id"] == "REQ-SOA-015"
                modes[method] = result.status_code
            ask_request = {"question": "REQ-ETH-002"}
            answer = (await client.post("/api/v1/knowledge/ask", json=ask_request)).json()
            assert answer["evidence_status"] == "cited"
            assert answer["referenced_requirement_ids"] == ["REQ-ETH-002"]
            missing = (
                await client.post("/api/v1/knowledge/ask", json={"question": "REQ-BATTERY-999"})
            ).json()
            assert missing["evidence_status"] == "insufficient" and provider_calls == 1
            phase1 = await client.post(
                "/api/v1/architectures/validate",
                json=json.loads(Path("data/examples/centralized_architecture.json").read_text()),
            )
            assert phase1.status_code == 200 and phase1.json()["status"] == "NOT_EVALUATED"
            reopened = KnowledgeService(settings)
            assert len(reopened.store.chunks()) == len(service.store.chunks())
            assert reopened.search("REQ-TSN-008").hits[0].chunk.requirement_id == "REQ-TSN-008"
            old_ids = {
                chunk.chunk_id
                for chunk in service.store.chunks()
                if chunk.document_id == "ethernet"
            }
            updated = load_file(
                Path("data/knowledge/synthetic/ethernet.md"), document_id="ethernet", version="1.1"
            )
            replacement = await client.post(
                "/api/v1/knowledge/documents", json=updated.model_dump()
            )
            assert replacement.json()["status"] == "replaced"
            assert all(service.store.get_chunk(chunk_id) is None for chunk_id in old_ids)
            assert (await client.delete("/api/v1/knowledge/documents/ethernet")).status_code == 204
            assert service.search("REQ-ETH-002").hits == []
            report = {
                "live_llm_tested": False,
                "generation_provider": provider.model,
                "generation_transport": "controlled HTTP response; no external API calls",
                "ingestions": ingestions,
                "search_request": request,
                "search_response": search,
                "ask_request": ask_request,
                "ask_response": answer,
                "no_evidence_response": missing,
                "retrieval_modes_http_status": modes,
                "persistence_verified": True,
                "replacement_verified": True,
                "deletion_verified": True,
                "citations_resolved_at_retrieval": True,
                "phase1_validation_status": phase1.json()["status"],
            }
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2) + "\n")
            print(f"Verified the full offline workflow. Evidence: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/phase2-workflow.json"))
    asyncio.run(verify(parser.parse_args().output))


if __name__ == "__main__":
    main()
