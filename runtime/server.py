from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from runtime.contract import RuntimeContractError, analyze_request, health_document, validate_request

MAX_BODY_BYTES=int(os.environ.get("OEE_RUNTIME_MAX_BODY_BYTES","26214400"))


class Handler(BaseHTTPRequestHandler):
    server_version="IndulayerOEERuntime/1.0"

    def do_GET(self) -> None:
        if self.path=="/health/ready":
            self._json(200,health_document())
            return
        self._json(404,{"error":"not_found"})

    def do_POST(self) -> None:
        if self.path not in {"/api/v1/analysis-runs","/api/v1/validate"}:
            self._json(404,{"error":"not_found"})
            return
        if not self._authorized():
            self._json(401,{"error":"unauthorized"})
            return

        try:
            length=int(self.headers.get("Content-Length","0"))
        except ValueError:
            self._json(400,{"error":"invalid_content_length"})
            return
        if length<=0 or length>MAX_BODY_BYTES:
            self._json(413,{"error":"invalid_body_size"})
            return

        try:
            payload=json.loads(self.rfile.read(length).decode("utf-8"))
            result=validate_request(payload) if self.path=="/api/v1/validate" else analyze_request(payload)
        except (UnicodeDecodeError,json.JSONDecodeError) as exc:
            self._json(400,{"error":"invalid_json","detail":str(exc)})
            return
        except RuntimeContractError as exc:
            self._json(422,{"error":"contract_error","detail":str(exc)})
            return
        except Exception:
            self._json(500,{"error":"runtime_failure"})
            return

        self._json(200,result)

    def log_message(self,format: str,*args: Any) -> None:
        return

    def _authorized(self) -> bool:
        token=os.environ.get("OEE_RUNTIME_TOKEN","")
        if not token:
            return False
        return self.headers.get("Authorization","")==f"Bearer {token}"

    def _json(self,status: int,payload: dict[str,Any]) -> None:
        body=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--host",default=os.environ.get("OEE_RUNTIME_HOST","127.0.0.1"))
    parser.add_argument("--port",type=int,default=int(os.environ.get("OEE_RUNTIME_PORT","8081")))
    args=parser.parse_args()

    if not os.environ.get("OEE_RUNTIME_TOKEN"):
        parser.error("OEE_RUNTIME_TOKEN is required")

    server=ThreadingHTTPServer((args.host,args.port),Handler)
    server.serve_forever()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
