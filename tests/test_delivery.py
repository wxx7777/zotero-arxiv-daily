import json

import pytest

from tests.test_screened_pipeline import make_executor


def test_receipt_is_written_only_after_smtp_acceptance(monkeypatch, tmp_path):
    receipt = tmp_path / "receipt.json"
    output = tmp_path / "outputs"
    monkeypatch.setenv("DIGEST_RECEIPT_PATH", str(receipt))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    executor, _ = make_executor([], [])
    executor.config.executor.send_empty = True

    def smtp_accept(*_):
        assert not receipt.exists()

    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", smtp_accept)
    executor.run()
    result = json.loads(receipt.read_text())
    assert result["status"] == "smtp_accepted"
    assert result["paper_count"] == 0
    assert result["run_id"] == "123"
    assert f"delivery_date={result['date']}" in output.read_text()
    assert set(result) == {"status", "date", "accepted_at", "paper_count", "run_id"}


def test_failed_smtp_never_creates_a_receipt(monkeypatch, tmp_path):
    receipt = tmp_path / "receipt.json"
    monkeypatch.setenv("DIGEST_RECEIPT_PATH", str(receipt))
    executor, _ = make_executor([], [])
    executor.config.executor.send_empty = True

    def smtp_fail(*_):
        raise ConnectionError("SMTP unavailable")

    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", smtp_fail)
    with pytest.raises(ConnectionError):
        executor.run()
    assert not receipt.exists()


def test_silent_no_email_does_not_create_a_receipt(monkeypatch, tmp_path):
    receipt = tmp_path / "receipt.json"
    monkeypatch.setenv("DIGEST_RECEIPT_PATH", str(receipt))
    executor, _ = make_executor([], [])
    executor.run()
    assert not receipt.exists()


def test_empty_reference_library_is_a_failure(monkeypatch, tmp_path):
    receipt = tmp_path / "receipt.json"
    monkeypatch.setenv("DIGEST_RECEIPT_PATH", str(receipt))
    executor, _ = make_executor([], [])
    executor.fetch_zotero_corpus = lambda: []
    with pytest.raises(RuntimeError, match="No Zotero papers"):
        executor.run()
    assert not receipt.exists()
