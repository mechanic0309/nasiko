# pytest routing_big_tests.py -v -s (-s to see the output on terminal)
import json
import random
import time
from pathlib import Path
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from tqdm import tqdm
from router.src.routing_agent import router
from router.src.utils import truncate_agent_cards
from router.src.models import RouterOutput
from langchain_community.vectorstores import FAISS


AGENT_CARDS_DIR = "router/data/agent_cards"
QUERIES_DIR = "router/data/queries"


def load_agent_cards():
    agent_cards_path = Path(AGENT_CARDS_DIR)
    if not agent_cards_path.exists():
        raise FileNotFoundError(
            f"Agent cards directory '{AGENT_CARDS_DIR}' does not exist."
        )
    json_files = sorted(agent_cards_path.glob("agent_card_*.json"))
    agent_cards = []
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                agent_card = json.load(f)
                agent_cards.append(agent_card)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON in {json_file.name}: {e}")
        except Exception as e:
            print(f"Error reading {json_file.name}: {e}")
    # print(f"Loaded {len(agent_cards)} agent cards from '{AGENT_CARDS_DIR}'")
    return agent_cards


def load_queries():
    queries_path = Path(QUERIES_DIR)
    if not queries_path.exists():
        raise FileNotFoundError(f"Queries directory '{QUERIES_DIR}' does not exist.")
    json_files = sorted(queries_path.glob("queries_*.json"))
    queries = []
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                query = json.load(f)
                queries.append(query)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON in {json_file.name}: {e}")
        except Exception as e:
            print(f"Error reading {json_file.name}: {e}")
    # print(f"Loaded {len(queries)} queries from '{QUERIES_DIR}'")
    return queries


# must import FAISS from langchain_community.vectorstores (as you required)
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
import faiss
import numpy as np
from typing import List, Dict, Any


# put this in a helper module (or top of your test file)
from typing import List
import numpy as np
import faiss

from langchain.schema import Document
from langchain_core.embeddings import Embeddings  # type: ignore
from langchain_community.vectorstores import FAISS

# Import the in-memory docstore implementation from the same package.
# This is the key: FAISS expects a docstore object with .search(id) implemented.
from langchain_community.vectorstores.faiss import InMemoryDocstore


def build_faiss_from_precomputed(
    docs: List[Document],
    vectors: List[List[float]],
    embedding_function: Embeddings,  # must be an Embeddings object (e.g., OpenAIEmbeddings())
) -> FAISS:
    """
    Build a langchain_community.vectorstores.FAISS vectorstore from precomputed vectors
    and Document objects (which may contain metadata).

    - docs: list of langchain.schema.Document (page_content, metadata)
    - vectors: list of vectors (same order as docs). Can be python lists or numpy arrays.
    - embedding_function: an Embeddings object used to embed queries (required).
    Returns: FAISS instance (from langchain_community.vectorstores)
    """
    if len(docs) != len(vectors):
        raise ValueError("Number of docs and vectors must match.")

    # ensure numpy float32 matrix
    vecs = np.asarray(vectors, dtype=np.float32)
    if vecs.ndim != 2:
        raise ValueError("vectors must be a 2D array (N x dim).")

    n, d = vecs.shape

    # build a simple flat L2 index (no training)
    index = faiss.IndexFlatL2(d)
    index.add(vecs)

    # Build a plain dict of docs keyed by doc_id (strings).
    # Use stable ids if you have them; here we use str(i).
    docs_dict = {str(i): docs[i] for i in range(n)}

    # Wrap with the InMemoryDocstore expected by langchain_community.vectorstores.faiss
    docstore = InMemoryDocstore(docs_dict)

    # Build index_to_docstore_id mapping (faiss index position -> doc_id string)
    index_to_docstore_id = {i: str(i) for i in range(n)}

    # instantiate the LangChain FAISS wrapper
    vectorstore = FAISS(
        index=index,
        docstore=docstore,
        index_to_docstore_id=index_to_docstore_id,
        embedding_function=embedding_function,  # required for query embedding
    )

    return vectorstore


def test_routing(total_queries=5):
    # Load agent queries
    agent_cards = load_agent_cards()
    embeddings = OpenAIEmbeddings()
    agent_names = [agent["name"] for agent in agent_cards]
    agent_cards_embeddings = embeddings.embed_documents(
        [agent_card["description"] for agent_card in agent_cards]
    )
    # Create dict with keys as agent_ids and values as embeddings
    name_embedding_dict = dict(zip(agent_names, agent_cards_embeddings))
    num_agents = len(agent_cards)

    # Load queries
    queries = load_queries()
    assert len(agent_cards) == len(queries)

    results = []
    correct_count = 0
    not_shortlisted_count = 0
    total_time = 0

    # Wrap your loop with tqdm
    for i in tqdm(range(total_queries), desc="Routing requests"):
        # pick one correct agent
        correct_agent_idx = random.randint(0, num_agents - 1)
        correct_agent = agent_cards[correct_agent_idx]
        correct_agent_name = correct_agent["name"]

        query = random.choice(queries[correct_agent_idx]["queries"])

        # pick 9 random distractor agents
        distractors = random.sample(
            [a for a in agent_cards if a["name"] != correct_agent_name],
            19,
        )

        # form 20 agent cards
        test_agent_cards = [correct_agent] + [d for d in distractors]
        truncated_agent_cards = truncate_agent_cards(test_agent_cards)
        random.shuffle(truncated_agent_cards)

        docs = []
        vecs = []
        for agent_card in truncated_agent_cards:
            agent_name = agent_card["name"]
            docs.append(
                Document(
                    page_content=agent_card["description"],
                    metadata={"name": agent_name},
                )
            )
            vecs.append(name_embedding_dict[agent_name])

        vectorstore = build_faiss_from_precomputed(docs, vecs, embeddings)

        start = time.time()
        shortlisted_agents, router_output = router(
            query, truncated_agent_cards, vectorstore
        )
        elapsed = time.time() - start
        total_time += elapsed

        if isinstance(router_output, RouterOutput):
            agent_name = router_output.agent_name
        elif isinstance(router_output, dict):
            agent_name = router_output.get("agent_name")
        else:
            print(f"Error parsing router output: {e}")

        if agent_name == correct_agent_name:
            correct_count += 1
            print(f"Accuracy so far: {correct_count}/{i+1}")
        else:
            if agent_name not in shortlisted_agents:
                not_shortlisted_count += 1
                print(
                    f"Not shortlisted so far: {not_shortlisted_count}/{i+1 - correct_count}"
                )
            print(f"   Query: {query}")
            print(f"   Correct agent: {correct_agent_name}")
            print(f"   Router selected agent: {agent_name}")
            print(f"   Shortlisted agents: {shortlisted_agents}")

        result = {
            "query": query,
            "correct_agent_name": correct_agent_name,
            "routed_agent_name": agent_name,
            "shortlisted_agents": shortlisted_agents,
            "correct": agent_name == correct_agent_name,
            "time_taken": elapsed,
        }
        results.append(result)

        # save results to file
        Path("router/results").mkdir(exist_ok=True)
        with open("router/results/routing_results.json", "w") as f:
            json.dump(results, f, indent=2)

    avg_time = total_time / len([r for r in results if r["time_taken"]])
    print(f"Saved results to router/results/routing_results.json")
    print(f"Average response time: {avg_time:.3f}s")

    accuracy = correct_count / total_queries * 100 if total_queries else 0
    vec_search_failure = (
        not_shortlisted_count / (total_queries - correct_count) * 100
        if (total_queries - correct_count)
        else 0
    )
    print(f"Correctly routed: {correct_count}/{total_queries} ({accuracy:.2f}%)")
    print(
        f"Not shortlisted: {not_shortlisted_count}/{total_queries - correct_count} ({vec_search_failure:.2f}%)"
    )


if __name__ == "__main__":
    test_routing(total_queries=100)
