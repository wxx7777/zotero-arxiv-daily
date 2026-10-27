"""Live one-shot check using four labelled synthetic abstracts, not real papers."""

import os
import re

from openai import OpenAI
from omegaconf import OmegaConf

from zotero_arxiv_daily.protocol import Paper
from zotero_arxiv_daily.topic_filter import filter_papers


def main():
    config = OmegaConf.merge(
        OmegaConf.load("config/base.yaml"),
        OmegaConf.create(os.environ["CUSTOM_CONFIG"]),
    )
    llm = OmegaConf.to_container(config.llm, resolve=True)
    settings = OmegaConf.to_container(config.screening, resolve=True)
    settings.update(enabled=True, candidate_limit=0)
    client = OpenAI(
        api_key=llm["api"]["key"], base_url=llm["api"]["base_url"],
        timeout=120, max_retries=1,
    )
    examples = [
        ("Synthetic: tactile dexterous manipulation",
         "We use tactile feedback and reinforcement learning for dexterous manipulation. "
         "We evaluated the policy on a physical robotic hand in 100 grasping trials."),
        ("Synthetic: robot VLA policy",
         "We study a vision-language-action policy for robot arm manipulation. "
         "All evaluations are in a simulated robot environment; no hardware tests were performed."),
        ("Synthetic: language-only alignment",
         "We use an existing RLHF algorithm to align a text-only language model. "
         "We evaluate only text benchmarks and make no robotics or general RL algorithm contribution."),
        ("Synthetic: autonomous driving world model",
         "We learn a world model for autonomous driving and evaluate road-vehicle planning "
         "on a driving simulator and real driving video datasets."),
    ]
    papers = [
        Paper("test", title, [], abstract, "", score=7)
        for title, abstract in examples
    ]
    selected = filter_papers(papers, client, llm, settings)
    assert {p.title for p in selected} == {papers[0].title, papers[1].title}, \
        "Scope check failed: expected robotics/VLA, and exclusions for language-only/driving"
    assert papers[0].real_robot is True, "Physical-robot evidence was not recognised"
    for paper in selected:
        # This raises on API failure instead of falling back to the English abstract.
        summary = paper._generate_tldr_with_llm(client, llm)
        assert summary and re.search(r"[\u4e00-\u9fff]", summary), "Missing Chinese summary"
        print(f"\n标题：{paper.title}\n主题：{'、'.join(paper.matched_topics)}")
        print(f"真机：{paper.real_robot}\n推荐理由：{paper.recommendation_reason}\n中文总结：{summary}")
    print("\nPASS: 主题纳入、排除、真机证据和中文总结测试通过（人工示例）")


if __name__ == "__main__":
    main()
