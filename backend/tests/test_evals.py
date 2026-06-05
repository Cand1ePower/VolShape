from evals.run_evals import run_all_evals


def test_offline_evals_pass():
    report = run_all_evals()

    assert report["summary"]["failed"] == 0, report["results"]
    assert report["summary"]["passed"] == report["summary"]["total"]
    assert report["prompt_manifest"]["prompts"]
