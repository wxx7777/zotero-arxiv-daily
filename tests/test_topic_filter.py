import json
from types import SimpleNamespace

import pytest
from omegaconf import OmegaConf

from zotero_arxiv_daily.protocol import Paper
from zotero_arxiv_daily.topic_filter import filter_papers, shortlist_for_embedding


def paper(title, abstract="We evaluated on a physical robotic hand.", score=7):
    return Paper("arxiv", title, [], abstract, "https://arxiv.org/abs/example", score=score)


def decision(i, *, relevance=4, excluded=False, real=None, evidence="", topics=None):
    return {
        "id": i, "relevance": relevance, "excluded": excluded,
        "real_robot": real, "real_robot_evidence": evidence,
        "topics": ["机器人"] if topics is None else topics,
        "reason": "属于机器人学习方向，依据摘要判断实验设置。",
    }


class Client:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = next(self.responses)
        if not isinstance(content, str):
            content = json.dumps({"papers": content}, ensure_ascii=False)
        return SimpleNamespace(choices=[
            SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content))
        ])


def run(papers, client, **overrides):
    return filter_papers(papers, client, {
        "api": {"base_url": "https://api.deepseek.com"},
        "generation_kwargs": {"model": "deepseek-flash"},
    }, {"enabled": True, **overrides})


def test_scope_exclusions_and_real_robot_priority():
    papers = [
        paper("simulation", score=9), paper("hardware", score=6),
        paper("pure text RLHF"), paper("autonomous driving world model"),
        paper("weak match"), paper("strong simulator", score=5),
    ]
    client = Client([[
        decision(0, real=False),
        decision(1, real=True, evidence="evaluated on a physical robotic hand"),
        decision(2, excluded=True, relevance=5),
        decision(3, excluded=True, relevance=5),
        decision(4, relevance=2),
        decision(5, relevance=5, real=False),
    ]])
    selected = run(papers, client)
    assert [p.title for p in selected] == ["strong simulator", "hardware", "simulation"]
    assert selected[1].real_robot is True
    assert selected[1].score == 6  # The old embedding score is not mislabelled.
    assert client.calls[0]["extra_body"]["thinking"]["type"] == "disabled"
    assert client.calls[0]["response_format"] == {"type": "json_object"}


def test_invented_hardware_evidence_does_not_earn_priority():
    papers = [paper("unsupported hardware claim", score=5), paper("other", score=8)]
    selected = run(papers, Client([[
        decision(0, real=True, evidence="100 experiments on a real robot"),
        decision(1, real=False),
    ]]))
    assert selected[0].title == "other"
    assert selected[1].real_robot is None
    assert selected[1].real_robot_evidence == ""


def test_no_padding_when_all_candidates_are_excluded():
    assert run([paper("excluded")], Client([[decision(0, excluded=True)]])) == []


def test_duplicate_or_missing_ids_fail_instead_of_sending_unscreened_papers():
    bad = [decision(0), decision(0)]
    with pytest.raises(RuntimeError, match="invalid decisions twice"):
        run([paper("one"), paper("two")], Client([bad, bad]))


def test_empty_response_retries_then_succeeds():
    client = Client(["", [decision(0)]])
    assert len(run([paper("one")], client)) == 1
    assert len(client.calls) == 2


def test_budget_and_batches_with_local_ids():
    client = Client([[decision(0), decision(1)], [decision(0)]])
    selected = run([paper(str(i)) for i in range(5)], client, candidate_limit=3, batch_size=2)
    assert len(selected) == 3
    assert len(client.calls) == 2


def test_zero_budget_reviews_all_candidates():
    client = Client([[decision(0), decision(1)]])
    assert len(run([paper("one"), paper("two")], client, candidate_limit=0)) == 2


def test_disabled_filter_does_not_call_api():
    papers = [paper("one")]
    assert filter_papers(papers, None, None, {"enabled": False}) is papers


@pytest.mark.parametrize("field,value", [
    ("excluded", "false"), ("real_robot", "true"), ("relevance", True),
    ("relevance", float("nan")), ("relevance", 6), ("topics", ["unrecognised"]),
])
def test_invalid_decisions_fail_closed(field, value):
    invalid = decision(0)
    invalid[field] = value
    with pytest.raises(RuntimeError):
        run([paper("one")], Client([[invalid], [invalid]]))


def test_nested_omegaconf_options_are_json_serializable():
    client = Client([[decision(0)]])
    llm = OmegaConf.create({
        "api": {"base_url": "https://api.deepseek.com"},
        "generation_kwargs": {"model": "deepseek-flash", "extra_body": {"other": True}},
    })
    filter_papers([paper("one")], client, llm, OmegaConf.create({"enabled": True}))
    json.dumps(client.calls[0])


def test_email_contains_escaped_reason_and_hardware_evidence():
    from zotero_arxiv_daily.construct_email import render_email
    p = paper("hardware")
    p.tldr = "中文总结"
    p.topic_relevance = 4
    p.matched_topics = ["机器人", "触觉"]
    p.real_robot = True
    p.real_robot_evidence = "physical <robot>"
    p.recommendation_reason = "比较控制器 <script>alert(1)</script>"
    html = render_email([p])
    assert "机器人、触觉" in html
    assert "摘要明确报告真机实验" in html
    assert "&lt;script&gt;" in html
    assert "<script>" not in html


def test_whole_boundary_tier_is_kept_for_similarity_tie_breaks():
    papers = [paper("high one"), paper("high two"), paper("lower")]
    papers[0].topic_relevance, papers[0].real_robot = 5, True
    papers[1].topic_relevance, papers[1].real_robot = 5, True
    papers[2].topic_relevance, papers[2].real_robot = 5, False
    finalists = shortlist_for_embedding(papers, 1)
    assert {p.title for p in finalists} == {"high one", "high two"}
    assert shortlist_for_embedding(papers, 0) == []


def test_parallel_batches_preserve_the_screening_decisions():
    class DynamicClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        def create(self, messages, **kwargs):
            inputs = json.loads(messages[1]["content"])
            decisions = [
                decision(x["id"], excluded=x["title"].startswith("exclude"))
                for x in inputs
            ]
            return SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=json.dumps({"papers": decisions})),
            )])
    papers = [paper("keep one"), paper("exclude one"), paper("keep two"),
              paper("exclude two"), paper("keep three")]
    selected = run(papers, DynamicClient(), candidate_limit=0, batch_size=2, workers=2)
    assert [p.title for p in selected] == ["keep one", "keep two", "keep three"]
