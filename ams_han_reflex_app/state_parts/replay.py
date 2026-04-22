from __future__ import annotations

import reflex as rx

from .common import _service


class DashboardReplayState:
    replay_path: str = ""
    replay_status_text: str = "Idle"
    replay_progress_text: str = "No replay loaded"
    replay_source_text: str = "-"

    def set_replay_path(self, value: str):
        self.replay_path = value

    def load_demo_replay(self):
        self.auto_connect_message = _service().load_demo_replay()
        self.sync_from_service(force_heavy=True)

    def load_replay(self):
        self.auto_connect_message = _service().load_replay_file(self.replay_path)
        self.sync_from_service(force_heavy=True)

    def start_replay(self):
        _service().start_replay()
        self.sync_from_service(force_heavy=True)

    def pause_or_resume_replay(self):
        _service().pause_or_resume_replay()
        self.sync_from_service(force_heavy=True)

    def stop_replay(self):
        _service().stop_replay()
        self.sync_from_service(force_heavy=True)

    async def handle_replay_upload(self, files: list[rx.UploadFile]):
        if not files:
            return
        upload = files[0]
        data = await upload.read()
        text = data.decode("utf-8", errors="replace")
        self.auto_connect_message = _service().load_replay_lines(text.splitlines(), upload.filename or "uploaded.log")
        self.replay_path = upload.filename or "uploaded.log"
        self.sync_from_service(force_heavy=True)
