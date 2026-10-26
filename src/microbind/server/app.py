import hmac
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .. import __version__
from ..model_config import enabled as model_enabled
from .config import Settings
from .sources import unpack
from .store import Store


class JobRequest(BaseModel):
    project_id: str
    kind: str = "scan"
    smart: bool = False
    repair: bool = True


def create_app(settings=None):
    settings = settings or Settings.env()
    store = Store(settings.data)
    if settings.samples:
        for id, name in [
            ("neo-http", "NEO · 原始 HTTP 通信样例"),
            ("neo-role", "NEO · Java/Python 角色修改样例"),
            ("litemall", "PCFinder 项目列表 · litemall 原始源码子集"),
        ]:
            folder = settings.samples / id
            if (folder / "project.yml").is_file():
                store.add_project(name, folder, False, "sample-" + id)
    if (settings.demo / "project.yml").is_file():
        store.add_project("订单微服务 · 内置靶场", settings.demo, True, "demo")
    app = FastAPI(
        title="MicroBind API", version=__version__, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.store, app.state.settings = store, settings
    bearer = HTTPBearer(auto_error=False)

    def auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if not credentials or not hmac.compare_digest(credentials.credentials, settings.token):
            raise HTTPException(401, "访问令牌无效")

    def get_job(id):
        job = store.job(id)
        if not job:
            raise HTTPException(404, "任务不存在")
        return job

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/capabilities", dependencies=[Depends(auth)])
    def capabilities():
        return {
            "version": __version__,
            "verify_enabled": settings.verify_enabled,
            "smart_enabled": model_enabled(),
            "smart_configured": model_enabled()
            and bool(os.getenv("MICROBIND_LLM_BASE_URL") and os.getenv("MICROBIND_LLM_MODEL")),
            "model": os.getenv("MICROBIND_LLM_MODEL", ""),
            "upload_limit_mb": settings.max_upload // 1024**2,
            "tools": ["get_method", "get_sql", "get_path", "get_policy", "search_methods"],
        }

    @app.get("/api/skills", dependencies=[Depends(auth)])
    def skills():
        from ..workflows.registry import catalog

        return catalog()

    @app.get("/api/projects", dependencies=[Depends(auth)])
    def projects():
        return [{k: v for k, v in p.items() if k != "path"} for p in store.projects()]

    @app.post("/api/projects", dependencies=[Depends(auth)], status_code=201)
    async def upload(file: UploadFile = File(...)):
        id = uuid.uuid4().hex
        destination = settings.data / "projects" / id
        try:
            with tempfile.NamedTemporaryFile(suffix=".zip") as temp:
                size = 0
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_upload:
                        raise ValueError("ZIP 超过 50 MB")
                    temp.write(chunk)
                temp.flush()
                manifest = await run_in_threadpool(unpack, Path(temp.name), destination)
            name = Path(file.filename or "project.zip").stem[:100]
            store.add_project(name, manifest.parent, id=id)
            return {"id": id, "name": name}
        except Exception as e:
            shutil.rmtree(destination, ignore_errors=True)
            raise HTTPException(400, "导入失败：" + str(e)[:200]) from None
        finally:
            await file.close()

    @app.post("/api/jobs", dependencies=[Depends(auth)], status_code=202)
    def start(request: JobRequest):
        project = store.project(request.project_id)
        if not project:
            raise HTTPException(404, "项目不存在")
        if request.kind not in {"scan", "verify"}:
            raise HTTPException(400, "任务类型错误")
        if request.kind == "verify" and (
            project["id"] != "demo" or not project["builtin"] or not settings.verify_enabled
        ):
            raise HTTPException(400, "运行验证仅支持启用验证容器后的内置靶场")
        if request.smart and not capabilities()["smart_configured"]:
            raise HTTPException(400, "请先在服务端配置模型地址和模型名")
        try:
            id = store.enqueue(
                request.project_id, request.kind, {"smart": request.smart, "repair": request.repair}
            )
        except ValueError as e:
            raise HTTPException(429, str(e)) from None
        return store.job(id)

    @app.get("/api/jobs", dependencies=[Depends(auth)])
    def jobs():
        return store.jobs()

    @app.get("/api/jobs/{id}", dependencies=[Depends(auth)])
    def job(id: str):
        return get_job(id)

    @app.get("/api/jobs/{id}/result", dependencies=[Depends(auth)])
    def result(id: str):
        get_job(id)
        path = settings.data / "jobs" / id / "result.json"
        if not path.is_file():
            raise HTTPException(409, "结果尚未就绪")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/jobs/{id}/download", dependencies=[Depends(auth)])
    def download(id: str):
        if get_job(id)["status"] != "succeeded":
            raise HTTPException(409, "任务尚未成功完成")
        return FileResponse(
            settings.data / "jobs" / id / "bundle.zip", filename=f"microbind-{id[:8]}.zip"
        )

    @app.post("/api/jobs/{id}/cancel", dependencies=[Depends(auth)])
    def cancel(id: str):
        get_job(id)
        if not store.cancel_queued(id):
            raise HTTPException(409, "仅能取消排队任务；运行任务由超时上限约束")
        return {"cancelled": True}

    @app.delete("/api/jobs/{id}", dependencies=[Depends(auth)])
    def delete(id: str):
        get_job(id)
        if not store.delete(id):
            raise HTTPException(409, "请先等待任务结束或取消排队任务")
        shutil.rmtree(settings.data / "jobs" / id, ignore_errors=True)
        return {"deleted": True}

    return app
