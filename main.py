import os
import json
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup
import pandas as pd
import networkx as nx
from pyvis.network import Network
import streamlit as st


def fetch_article(url: str) -> str:
    """Fetch article text from a URL."""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    article = soup.find("article")
    if article:
        paragraphs = article.find_all("p")
    else:
        paragraphs = soup.find_all("p")
    text = "\n".join(p.get_text(strip=True) for p in paragraphs)
    if not text:
        raise ValueError("No article text found")
    return text


def extract_graph(text: str, provider: str = "gemini") -> Dict[str, Any]:
    """Call Gemini or Kluster.ai to produce a knowledge graph."""
    prompt = (
        "Analyze the article and return a JSON knowledge graph as "
        '{"nodes": [{"id":"","type":"","quote":""}], '  # Schema description
        '"edges": [{"source":"","target":"","relation":"","quote":""}]}.'
        " Only return JSON."
    )
    query = f"{prompt}\n\nArticle:\n{text}"

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-pro")
        resp = model.generate_content(query)
        output = resp.text
    else:
        api_key = os.getenv("KLUSTER_API_KEY")
        if not api_key:
            raise RuntimeError("KLUSTER_API_KEY is not set")
        import openai
        openai.api_key = api_key
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": query}],
        )
        output = resp.choices[0].message.content

    start = output.find("{")
    end = output.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON found in LLM output")
    json_str = output[start : end + 1]
    return json.loads(json_str)


def to_networkx(graph_json: Dict[str, Any]) -> nx.DiGraph:
    """Convert JSON dict to a NetworkX directed graph."""
    G = nx.DiGraph()
    for node in graph_json.get("nodes", []):
        node_id = node.get("id")
        if node_id is not None:
            G.add_node(node_id, **{k: v for k, v in node.items() if k != "id"})
    for edge in graph_json.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if source is not None and target is not None:
            G.add_edge(
                source,
                target,
                **{k: v for k, v in edge.items() if k not in {"source", "target"}},
            )
    return G


def to_pyvis_html(nx_graph: nx.DiGraph) -> str:
    """Generate PyVis HTML from a NetworkX graph."""
    net = Network(height="600px", width="100%", directed=True)
    net.from_nx(nx_graph)
    net.show_buttons(filter_=["physics"])
    return net.generate_html(notebook=False)


def batch_process(urls: List[str], provider: str) -> List[Dict[str, Any]]:
    """Process URLs to generate graphs."""
    results = []
    for url in urls:
        try:
            st.write(f"Processing {url}")
            with st.spinner("Fetching…"):
                text = fetch_article(url)
            with st.spinner("Analyzing…"):
                graph_json = extract_graph(text, provider=provider)
            with st.spinner("Rendering…"):
                nx_graph = to_networkx(graph_json)
                html = to_pyvis_html(nx_graph)
            results.append({"url": url, "graph_json": graph_json, "html": html})
        except Exception as exc:
            st.session_state.setdefault("log", []).append(f"{url}: {exc}")
    return results


def main() -> None:
    """Run the Streamlit application."""
    st.title("News Knowledge-Graph Explorer")
    provider = st.sidebar.selectbox("LLM Provider", ["gemini", "kluster"])

    url_text = st.text_area("Enter bdnews24 URLs, one per line")
    uploaded = st.file_uploader("Or upload CSV of URLs", type="csv")

    urls: List[str] = []
    if url_text:
        urls.extend([u.strip() for u in url_text.splitlines() if u.strip()])
    if uploaded:
        try:
            df = pd.read_csv(uploaded)
            urls.extend(df.iloc[:, 0].dropna().tolist())
        except Exception as exc:
            st.error(f"Failed to read CSV: {exc}")

    if "log" not in st.session_state:
        st.session_state["log"] = []

    if st.button("Process"):
        if not urls:
            st.warning("No URLs provided")
        else:
            results = batch_process(urls, provider)
            for i, res in enumerate(results, 1):
                st.subheader(f"Graph for: {res['url']}")
                st.components.v1.html(res["html"], height=600, scrolling=True)
                st.download_button(
                    "Download JSON",
                    json.dumps(res["graph_json"], indent=2),
                    file_name=f"graph_{i}.json",
                    mime="application/json",
                )
                st.download_button(
                    "Download HTML",
                    res["html"],
                    file_name=f"graph_{i}.html",
                    mime="text/html",
                )

    if st.session_state["log"]:
        with st.expander("Errors"):
            for entry in st.session_state["log"]:
                st.write(entry)


if __name__ == "__main__":
    st.set_page_config(page_title="News Knowledge-Graph Explorer")
    main()

# requirements.txt
# streamlit
# requests
# beautifulsoup4
# pandas
# networkx
# pyvis
# google-generativeai
# openai
# python-dotenv
