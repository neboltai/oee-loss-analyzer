from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from runtime.contract import RuntimeContractError, analyze_request, health_document, validate_request

ROOT=Path(__file__).resolve().parents[1]


class RuntimeContractTest(unittest.TestCase):
    def request(self) -> dict:
        raw=(ROOT/"examples"/"dataset.example.json").read_bytes()
        return {
            "contract_version":"1.0",
            "platform_run_id":"01TESTOEE000000000000000",
            "product_id":"oee",
            "product_version":"0.4.0",
            "input_fingerprint":hashlib.sha256(raw).hexdigest(),
            "configuration_fingerprint":hashlib.sha256(b"{}").hexdigest(),
            "dataset":json.loads(raw),
            "configuration":{},
        }

    def test_health(self):
        health=health_document()
        self.assertEqual("ready",health["status"])
        self.assertEqual("oee",health["product_id"])
        self.assertEqual("0.4.0",health["version"])

    def test_dataset_validation(self):
        request=self.request()
        request.pop("platform_run_id")
        result=validate_request(request)
        self.assertIn(result["status"],{"valid","partial","invalid"})
        self.assertEqual("oee",result["product_id"])

    def test_analysis_is_normalized(self):
        result=analyze_request(self.request())
        self.assertEqual("1.0",result["contract_version"])
        self.assertEqual("oee",result["product_id"])
        self.assertEqual("0.4.0",result["product_version"])
        self.assertIn(result["status"],{"completed","partial","blocked"})
        self.assertTrue(result["evidence"])
        self.assertEqual("INPUT-001",result["evidence"][0]["id"])
        for finding in result["findings"]:
            self.assertNotEqual("verified-cause",finding["claim_level"])

    def test_wrong_product_version_fails_closed(self):
        request=self.request()
        request["product_version"]="9.9.9"
        with self.assertRaises(RuntimeContractError):
            analyze_request(request)


if __name__=="__main__":
    unittest.main()
