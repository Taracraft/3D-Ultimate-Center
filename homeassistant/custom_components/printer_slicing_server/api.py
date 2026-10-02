from __future__ import annotations

from aiohttp import ClientError, ClientSession, ClientTimeout

class SlicingServerApiError(Exception):
    pass

class SlicingServerApi:
    def __init__(self, session: ClientSession, host: str, port: int, token: str) -> None:
        self._session = session
        self._base_url = f"http://{host}:{port}"
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def _get(self, path: str, authenticated: bool = True) -> dict:
        try:
            async with self._session.get(self._base_url + path, headers=self._headers if authenticated else None, timeout=ClientTimeout(total=15)) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise SlicingServerApiError(f"HTTP {response.status}: {body[:300]}")
                return await response.json()
        except SlicingServerApiError:
            raise
        except (ClientError, TimeoutError) as exc:
            raise SlicingServerApiError(str(exc)) from exc

    async def _delete(self, path: str, authenticated: bool = True) -> dict:
        try:
            async with self._session.delete(self._base_url + path, headers=self._headers if authenticated else None, timeout=ClientTimeout(total=45)) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise SlicingServerApiError(f"HTTP {response.status}: {body[:300]}")
                return await response.json()
        except SlicingServerApiError:
            raise
        except (ClientError, TimeoutError) as exc:
            raise SlicingServerApiError(str(exc)) from exc

    async def health(self) -> dict:
        return await self._get("/api/v1/health", authenticated=False)

    async def info(self) -> dict:
        return await self._get("/api/v1/info")

    async def status(self) -> dict:
        return await self._get("/api/v1/status")

    async def engines(self) -> dict:
        return await self._get("/api/v1/engines")

    async def printers(self) -> dict:
        return await self._get("/api/v1/printers")

    async def capabilities(self) -> dict:
        return await self._get("/api/v1/capabilities")

    async def diagnostics(self) -> dict:
        return await self._get("/api/v1/diagnostics")

    async def files(self) -> dict:
        return await self._get("/api/v1/files")

    async def jobs(self) -> dict:
        return await self._get("/api/v1/jobs")

    async def job(self, job_id: str) -> dict:
        return await self._get(f"/api/v1/jobs/{job_id}")

    async def overview(self):
        return (
            await self.info(),
            await self.status(),
            await self.engines(),
            await self.printers(),
            await self.files(),
            await self.jobs(),
            await self.capabilities(),
            await self.diagnostics(),
        )

    async def create_job(self, payload: dict) -> dict:
        try:
            async with self._session.post(self._base_url + "/api/v1/jobs", headers=self._headers, json=payload, timeout=ClientTimeout(total=30)) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise SlicingServerApiError(f"HTTP {response.status}: {body[:300]}")
                return await response.json()
        except SlicingServerApiError:
            raise
        except (ClientError, TimeoutError) as exc:
            raise SlicingServerApiError(str(exc)) from exc

    async def upload_file(self, filename: str, content: bytes) -> dict:
        try:
            async with self._session.post(self._base_url + f"/api/v1/files/{filename}", headers=self._headers, data=content, timeout=ClientTimeout(total=300)) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise SlicingServerApiError(f"HTTP {response.status}: {body[:300]}")
                return await response.json()
        except SlicingServerApiError:
            raise
        except (ClientError, TimeoutError) as exc:
            raise SlicingServerApiError(str(exc)) from exc

    async def download_job(self, job_id: str) -> tuple[str, bytes]:
        try:
            async with self._session.get(self._base_url + f"/api/v1/jobs/{job_id}/download", headers=self._headers, timeout=ClientTimeout(total=300)) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise SlicingServerApiError(f"HTTP {response.status}: {body[:300]}")
                disposition = response.headers.get("Content-Disposition", "")
                filename = job_id + ".gcode"
                if 'filename="' in disposition:
                    filename = disposition.split('filename="', 1)[1].split('"', 1)[0]
                return filename, await response.read()
        except SlicingServerApiError:
            raise
        except (ClientError, TimeoutError) as exc:
            raise SlicingServerApiError(str(exc)) from exc

    async def delete_job(self, job_id: str) -> dict:
        """Delete a terminal job from the slicing server."""
        result = await self._delete(f"/api/v1/jobs/{job_id}")
        if not result or result.get("deleted") is not True:
            raise SlicingServerApiError("Server did not confirm deletion")
        return result