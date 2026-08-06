from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from core.config import Settings, load_settings
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex


STATE_PATH_ATTRIBUTES = {
    "baseline": ("clean_csv", "embeddings_json"),
    "corrupted": ("corrupted_clean_csv", "corrupted_embeddings_json"),
    "repaired": ("repaired_clean_csv", "repaired_embeddings_json"),
}


def _state_paths(settings: Settings, state: str) -> tuple[Path, Path]:
    clean_attribute, manifest_attribute = STATE_PATH_ATTRIBUTES[state]
    return getattr(settings.paths, clean_attribute), getattr(settings.paths, manifest_attribute)


def _load_or_build_index(settings: Settings, state: str, rebuild: bool) -> LocalEmbeddingIndex:
    clean_path, manifest_path = _state_paths(settings, state)
    if rebuild:
        if not clean_path.exists():
            raise FileNotFoundError(f"Clean dataset for {state} does not exist: {clean_path}")
        dataframe = pd.read_csv(clean_path)
        return LocalEmbeddingIndex.build(dataframe, settings, embeddings_output_path=manifest_path)
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Embedding manifest for {state} does not exist: {manifest_path}. "
            "Run the corresponding pipeline or pass --rebuild."
        )
    return LocalEmbeddingIndex.load(settings, embeddings_path=manifest_path)


def _print_smoke_result(
    state: str,
    index: LocalEmbeddingIndex,
    query: str,
    lookup_value: str | None,
) -> None:
    print(f"\n[{state}] collection={index.collection_name} documents={index.collection.count()}")
    results = index.search(query)
    if not results:
        print("semantic_search: no results")
    for rank, result in enumerate(results, start=1):
        print(
            f"semantic_search[{rank}]: paper_id={result.paper_id} "
            f"score={result.score:.4f} title={result.title}"
        )

    exact_value = lookup_value or (index.documents[0]["paper_id"] if index.documents else None)
    exact = index.lookup(exact_value) if exact_value else None
    if exact:
        print(f"exact_lookup: paper_id={exact['paper_id']} title={exact['title']}")
    else:
        print(f"exact_lookup: no match for {exact_value!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build/load and smoke-test baseline, corrupted, or repaired RAG collections."
    )
    parser.add_argument(
        "--state",
        choices=[*STATE_PATH_ATTRIBUTES, "all"],
        default="baseline",
        help="Dataset/index state to test.",
    )
    parser.add_argument(
        "--query",
        default="retrieval augmented generation with large language models",
        help="Semantic-search query reused across selected states.",
    )
    parser.add_argument("--lookup", help="Exact paper_id or title; defaults to the first indexed paper_id.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild each selected collection from its clean CSV before testing.",
    )
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Also ask the configured LLM agent; requires a working provider and credentials.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    states = list(STATE_PATH_ATTRIBUTES) if args.state == "all" else [args.state]
    for state in states:
        index = _load_or_build_index(settings, state, args.rebuild)
        _print_smoke_result(state, index, args.query, args.lookup)
        if args.agent:
            agent = build_agent(settings, index)
            answer = run_agent_question(agent, args.query)
            print(f"agent_answer: {answer}")


if __name__ == "__main__":
    main()
