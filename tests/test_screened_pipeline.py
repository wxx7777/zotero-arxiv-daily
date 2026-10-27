from types import SimpleNamespace

from omegaconf import OmegaConf

from zotero_arxiv_daily.executor import Executor
from zotero_arxiv_daily.protocol import Paper, _request_llm
from tests.test_topic_filter import Client, decision, paper


def make_executor(papers, decisions):
    executor = Executor.__new__(Executor)
    executor.config = OmegaConf.create({
        "executor": {"source": ["arxiv"], "max_paper_num": 1, "send_empty": False},
        "screening": {"enabled": True, "candidate_limit": 0},
        "llm": {
            "api": {"base_url": "https://api.deepseek.com"},
            "generation_kwargs": {"model": "deepseek-flash"},
        },
    })
    enriched = []
    executor.retrievers = {
        "arxiv": SimpleNamespace(
            retrieve_papers=lambda: papers, enrich_paper=lambda p: enriched.append(p.title),
        ),
    }
    executor.reranker = SimpleNamespace(rerank=lambda ps, corpus: ps)
    executor.openai_client = Client([decisions])
    executor.fetch_zotero_corpus = lambda: [object()]
    executor.filter_corpus = lambda corpus: corpus
    return executor, enriched


def test_final_limit_applies_after_semantic_screening(monkeypatch):
    papers = [paper("excluded"), paper("simulator", score=9), paper("hardware", score=5)]
    executor, enriched = make_executor(papers, [
        decision(0, excluded=True),
        decision(1, real=False),
        decision(2, real=True, evidence="evaluated on a physical robotic hand"),
    ])
    summaries, emails = [], []
    def summarize(p, *_):
        summaries.append(p.title)
        p.tldr = "中文总结"
    monkeypatch.setattr(Paper, "generate_tldr", summarize)
    monkeypatch.setattr(Paper, "generate_affiliations", lambda *_: None)
    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", lambda cfg, body: emails.append(body))
    executor.run()
    assert enriched == ["hardware"]
    assert summaries == ["hardware"]
    assert len(emails) == 1
    assert "推荐理由" in emails[0] and "摘要明确报告真机实验" in emails[0]


def test_all_rejected_stops_before_summary_or_email(monkeypatch):
    executor, enriched = make_executor([paper("excluded")], [decision(0, excluded=True)])
    emails = []
    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", lambda cfg, body: emails.append(body))
    executor.run()
    assert emails == [] and enriched == []


def test_global_screening_only_embeds_tiers_that_can_enter_the_digest(monkeypatch):
    papers = [paper("excluded"), paper("lower tier"), paper("top hardware")]
    executor, enriched = make_executor(papers, [
        decision(0, excluded=True, relevance=5),
        decision(1, relevance=3),
        decision(2, relevance=5, real=True, evidence="evaluated on a physical robotic hand"),
    ])
    embedded = []
    def rerank(selected, corpus):
        embedded.extend(p.title for p in selected)
        return selected
    executor.reranker = SimpleNamespace(rerank=rerank)
    monkeypatch.setattr(Paper, "generate_tldr", lambda *_: None)
    monkeypatch.setattr(Paper, "generate_affiliations", lambda *_: None)
    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", lambda *_: None)
    executor.run()
    assert embedded == ["top hardware"]
    assert enriched == ["top hardware"]


def test_arxiv_full_text_is_loaded_only_for_selected_papers(config, monkeypatch):
    from zotero_arxiv_daily.retriever.arxiv_retriever import ArxivRetriever
    from omegaconf import open_dict
    with open_dict(config):
        config.screening.enabled = True
    retriever = ArxivRetriever(config)
    raw = SimpleNamespace(
        title="paper", authors=[], summary="abstract", pdf_url="https://arxiv.org/pdf/example",
        entry_id="https://arxiv.org/abs/example",
    )
    calls = []
    def extract(raw):
        calls.append(raw.entry_id)
        return "Full paper text"
    monkeypatch.setattr(retriever, "_extract_full_text", extract)
    converted = retriever.convert_to_paper(raw)
    assert converted.full_text is None and calls == []
    retriever.enrich_paper(converted)
    assert converted.full_text == "Full paper text" and len(calls) == 1


def test_summary_nested_configuration_is_json_serializable():
    import json
    client = Client(["中文总结"])
    llm = OmegaConf.create({
        "generation_kwargs": {
            "model": "deepseek-flash",
            "extra_body": {"thinking": {"type": "disabled"}},
        },
    })
    assert _request_llm(client, llm, [{"role": "user", "content": "总结"}]) == "中文总结"
    json.dumps(client.calls[0])
