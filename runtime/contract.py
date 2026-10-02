from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SCRIPTS=Path(__file__).resolve().parents[1]/"skills"/"oee-loss-analyzer"/"scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0,str(SCRIPTS))

from oee_lib import DEFAULT_RULESET, ENGINE_VERSION, analyse  # noqa:E402

PRODUCT_ID="oee"
PRODUCT_VERSION=ENGINE_VERSION
CONTRACT_VERSION="1.0"


class RuntimeContractError(ValueError):
    pass


def health_document() -> dict[str,Any]:
    return {
        "status":"ready",
        "product_id":PRODUCT_ID,
        "version":PRODUCT_VERSION,
        "engine_version":ENGINE_VERSION,
        "runtime_contract_version":CONTRACT_VERSION,
    }


def validate_request(request: dict[str,Any]) -> dict[str,Any]:
    validated=_validate_request(request, require_run=False)
    result=analyse(validated["dataset"],ruleset=DEFAULT_RULESET,threshold_overrides=None)
    engine_status=str(result.get("status") or "data_error")
    return {
        "contract_version":CONTRACT_VERSION,
        "product_id":PRODUCT_ID,
        "product_version":PRODUCT_VERSION,
        "engine_version":ENGINE_VERSION,
        "status":"invalid" if engine_status=="data_error" else ("partial" if engine_status=="insufficient_evidence" else "valid"),
        "issues":result.get("issues") or [],
    }


def analyze_request(request: dict[str,Any]) -> dict[str,Any]:
    validated=_validate_request(request, require_run=True)
    platform_run_id=validated["platform_run_id"]
    input_fingerprint=validated["input_fingerprint"]
    dataset=validated["dataset"]
    configuration=validated["configuration"]

    return {
        "platform_run_id":platform_run_id,
        "input_fingerprint":input_fingerprint,
        "dataset":dataset,
        "configuration":configuration,
    }


def _validate_request(request: dict[str,Any], *, require_run: bool) -> dict[str,Any]:
    if not isinstance(request,dict):
        raise RuntimeContractError("request must be a JSON object")
    if request.get("contract_version")!=CONTRACT_VERSION:
        raise RuntimeContractError("unsupported runtime contract version")
    if request.get("product_id")!=PRODUCT_ID:
        raise RuntimeContractError("product_id must be oee")
    if request.get("product_version")!=PRODUCT_VERSION:
        raise RuntimeContractError(
            f"product_version must be {PRODUCT_VERSION}"
        )

    platform_run_id=str(request.get("platform_run_id") or "").strip()
    if require_run and not platform_run_id:
        raise RuntimeContractError("platform_run_id is required")

    input_fingerprint=str(request.get("input_fingerprint") or "").strip()
    configuration_fingerprint=str(request.get("configuration_fingerprint") or "").strip()
    if len(input_fingerprint)!=64:
        raise RuntimeContractError("input_fingerprint must be a SHA-256 hex digest")
    if len(configuration_fingerprint)!=64:
        raise RuntimeContractError("configuration_fingerprint must be a SHA-256 hex digest")

    dataset=request.get("dataset")
    if not isinstance(dataset,dict):
        raise RuntimeContractError("dataset must be a canonical OEE JSON object")

    configuration=request.get("configuration") or {}
    if not isinstance(configuration,dict):
        raise RuntimeContractError("configuration must be an object")

    ruleset=str(configuration.get("ruleset") or DEFAULT_RULESET)
    if ruleset!=DEFAULT_RULESET:
        raise RuntimeContractError(
            f"runtime permits only shipped ruleset {DEFAULT_RULESET}"
        )
    thresholds=configuration.get("thresholds")
    if thresholds is not None and not isinstance(thresholds,dict):
        raise RuntimeContractError("configuration.thresholds must be an object")

    result=analyse(dataset,ruleset=ruleset,threshold_overrides=thresholds)
    return normalize_result(
        platform_run_id=platform_run_id,
        input_fingerprint=input_fingerprint,
        result=result,
    )


def normalize_result(
    *,
    platform_run_id: str,
    input_fingerprint: str,
    result: dict[str,Any],
) -> dict[str,Any]:
    engine_status=str(result.get("status") or "data_error")
    status={
        "ok":"completed",
        "insufficient_evidence":"partial",
        "data_error":"blocked",
    }.get(engine_status,"failed")

    evidence:list[dict[str,Any]]=[{
        "id":"INPUT-001",
        "kind":"raw-record",
        "source_refs":[f"sha256:{input_fingerprint}"],
        "description":"Canonical OEE dataset supplied to the deterministic engine.",
    }]
    findings:list[dict[str,Any]]=[]

    for find_index,finding in enumerate(result.get("findings") or [],start=1):
        if not isinstance(finding,dict):
            continue
        finding_id=f"OEE-F{find_index:03d}"
        refs:list[str]=[]
        for evidence_index,description in enumerate(finding.get("evidence") or [],start=1):
            evidence_id=f"{finding_id}-E{evidence_index:03d}"
            refs.append(evidence_id)
            evidence.append({
                "id":evidence_id,
                "kind":"event",
                "source_refs":[f"sha256:{input_fingerprint}"],
                "description":str(description),
            })

        cause_gate=bool(finding.get("cause_claimed"))
        limitations=list(result.get("missing_evidence") or [])
        if cause_gate:
            limitations.append(
                "The OEE evidence gate supports a finding but is not a completed root-cause investigation."
            )

        findings.append({
            "id":finding_id,
            "classification":str(
                (result.get("primary_loss") or {}).get("bucket") or "oee-loss"
            ),
            "statement":str(finding.get("problem") or "OEE loss finding"),
            "evidence_refs":refs,
            "claim_level":"finding" if cause_gate else "hypothesis",
            "limitations":[str(x) for x in limitations],
        })

    warnings=[
        str(issue.get("message"))
        for issue in (result.get("issues") or [])
        if isinstance(issue,dict) and issue.get("severity")=="warning"
    ]
    limitations=[str(x) for x in (result.get("missing_evidence") or [])]

    return {
        "contract_version":CONTRACT_VERSION,
        "platform_run_id":platform_run_id,
        "product_id":PRODUCT_ID,
        "product_version":PRODUCT_VERSION,
        "engine_version":str(result.get("engine_version") or ENGINE_VERSION),
        "status":status,
        "external_run_id":f"oee:{platform_run_id}",
        "summary":{
            "engine_status":engine_status,
            "ruleset":result.get("ruleset"),
            "metrics":result.get("metrics"),
            "losses":result.get("losses") or [],
            "primary_loss":result.get("primary_loss"),
            "reason":result.get("reason"),
        },
        "findings":findings,
        "evidence":evidence,
        "limitations":limitations,
        "warnings":warnings,
        "raw":result,
    }
