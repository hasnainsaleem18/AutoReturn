"""Unit tests for voice parsing and lightweight voice service behavior."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from src.backend.services.voice_service import (
    AudioCapture,
    AudioRecorderThread,
    VoiceCommandParser,
    VoiceService,
    WhisperTranscriberThread,
)
from testing_formal.tests.qt_utils import get_qapp


class _FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _FakeTranscriber:
    def __init__(self, audio_input, model_size: str = "base", language: str = "en", preferred_device=None):
        self.audio_input = audio_input
        self.audio_path = audio_input
        self.model_size = model_size
        self.language = language
        self.preferred_device = preferred_device
        self.resolved_device = preferred_device or "cpu"
        self.transcription_ready = _FakeSignal()
        self.transcription_failed = _FakeSignal()
        self.finished = _FakeSignal()

    def start(self):
        self.transcription_ready.emit("sync gmail")
        self.finished.emit()

    def deleteLater(self):
        return None

    def isRunning(self):
        return False

    def wait(self, _timeout):
        return True


class _FakeWarmupThread:
    def __init__(self, model_size: str = "base", preferred_device=None):
        self.model_size = model_size
        self.preferred_device = preferred_device
        self.warmup_complete = _FakeSignal()
        self.warmup_failed = _FakeSignal()
        self.finished = _FakeSignal()
        self._running = False

    def start(self, _priority=None):
        self._running = True
        self.warmup_complete.emit(self.preferred_device or "cpu")
        self.finished.emit()
        self._running = False

    def isRunning(self):
        return self._running

    def wait(self, _timeout):
        return True

    def deleteLater(self):
        return None


class _FakeRecorderThread:
    def __init__(self):
        self.deleted = False
        self._running = True

    def isRunning(self):
        return self._running

    def stop_recording(self):
        self._running = False

    def wait(self, _timeout):
        self._running = False
        return True

    def deleteLater(self):
        self.deleted = True
        return None


class _FakeHotkeyThread:
    instances = []

    def __init__(self, hotkey: str = "ctrl+shift+v", backend: str = "keyboard"):
        self.hotkey = hotkey
        self.backend = backend
        self.hotkey_pressed = _FakeSignal()
        self.hotkey_released = _FakeSignal()
        self.listener_error = _FakeSignal()
        self._running = False
        self.__class__.instances.append(self)

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

    def wait(self, _timeout):
        return True

    def deleteLater(self):
        return None

    def isRunning(self):
        return self._running

    @staticmethod
    def _macos_access_granted(_quartz_module):
        return True


class TestVoiceCommandParserFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: test_exact_ui_command
    # Purpose: Validate the exact UI command scenario.
    # -------------------------
    def test_exact_ui_command(self):
        command = VoiceCommandParser.parse("show urgent")
        self.assertEqual(command.action_type, "ui_action")
        self.assertEqual(command.action, "filter")
        self.assertEqual(command.parameters["filter_id"], "urgent")

    # -------------------------
    # FUNCTION: test_search_query_extraction
    # Purpose: Validate the voice search extraction scenario.
    # -------------------------
    def test_search_query_extraction(self):
        command = VoiceCommandParser.parse("search for invoice report")
        self.assertEqual(command.action, "search")
        self.assertEqual(command.parameters["query"], "invoice report")

    # -------------------------
    # FUNCTION: test_sender_extraction_for_reply_and_draft
    # Purpose: Validate sender extraction for targeted commands.
    # -------------------------
    def test_sender_extraction_for_reply_and_draft(self):
        reply = VoiceCommandParser.parse("reply to john")
        draft = VoiceCommandParser.parse("draft for sarah")
        self.assertEqual(reply.action, "reply_to_sender")
        self.assertEqual(reply.parameters["sender_name"], "John")
        self.assertEqual(draft.action, "draft_for_sender")
        self.assertEqual(draft.parameters["sender_name"], "Sarah")

    # -------------------------
    # FUNCTION: test_message_index_extraction
    # Purpose: Validate message index extraction scenario.
    # -------------------------
    def test_message_index_extraction(self):
        ordinal = VoiceCommandParser.parse("open first message")
        numeric = VoiceCommandParser.parse("open message 3")
        self.assertEqual(ordinal.action, "open_message_by_index")
        self.assertEqual(ordinal.parameters["index"], 0)
        self.assertEqual(numeric.parameters["index"], 2)

    # -------------------------
    # FUNCTION: test_backend_trigger_classification
    # Purpose: Validate backend trigger classification scenario.
    # -------------------------
    def test_backend_trigger_classification(self):
        command = VoiceCommandParser.parse("sync gmail")
        self.assertEqual(command.action_type, "agent_action")
        self.assertEqual(command.parameters["command"], "sync gmail")

        sync_all = VoiceCommandParser.parse("sync all messages")
        self.assertEqual(sync_all.action_type, "agent_action")

    # -------------------------
    # FUNCTION: test_noop_for_short_unknown_command
    # Purpose: Validate short-noise rejection scenario.
    # -------------------------
    def test_noop_for_short_unknown_command(self):
        command = VoiceCommandParser.parse("hmm")
        self.assertEqual(command.action, "noop")

    # -------------------------
    # FUNCTION: test_hybrid_fallback_for_multi_word_unknown
    # Purpose: Validate hybrid fallback scenario.
    # -------------------------
    def test_hybrid_fallback_for_multi_word_unknown(self):
        command = VoiceCommandParser.parse("please check what arrived")
        self.assertEqual(command.action_type, "agent_action")
        self.assertEqual(command.action, "orchestrator")


class TestVoiceServiceFormal(unittest.TestCase):
    @classmethod
    # -------------------------
    # FUNCTION: setUpClass
    # Purpose: Execute setUpClass logic for this module.
    # -------------------------
    def setUpClass(cls):
        cls.app = get_qapp()

    # -------------------------
    # FUNCTION: test_start_gracefully_disables_when_dependencies_missing
    # Purpose: Validate graceful disable when voice deps are missing.
    # -------------------------
    def test_start_gracefully_disables_when_dependencies_missing(self):
        with patch("src.backend.services.voice_service.sys.platform", "linux"), patch(
            "src.backend.services.voice_service._optional_import",
            side_effect=lambda name: None if name == "keyboard" else object(),
        ):
            service = VoiceService()
            self.assertFalse(service.start())
            self.assertIn("keyboard", service.startup_error())

    # -------------------------
    # FUNCTION: test_start_gracefully_disables_when_quartz_missing_on_macos
    # Purpose: Validate the macOS dependency path for global hotkeys.
    # -------------------------
    def test_start_gracefully_disables_when_quartz_missing_on_macos(self):
        with patch("src.backend.services.voice_service.sys.platform", "darwin"), patch(
            "src.backend.services.voice_service._optional_import",
            side_effect=lambda name: None if name == "Quartz" else object(),
        ):
            service = VoiceService()
            self.assertFalse(service.start())
            self.assertIn("Quartz", service.startup_error())

    # -------------------------
    # FUNCTION: test_start_uses_quartz_backend_on_macos
    # Purpose: Validate backend selection for macOS hotkeys.
    # -------------------------
    def test_start_uses_quartz_backend_on_macos(self):
        _FakeHotkeyThread.instances.clear()
        with patch("src.backend.services.voice_service.sys.platform", "darwin"), patch(
            "src.backend.services.voice_service._optional_import",
            side_effect=lambda _name: object(),
        ), patch("src.backend.services.voice_service.HotkeyListenerThread", _FakeHotkeyThread), patch(
            "src.backend.services.voice_service.WhisperWarmupThread", _FakeWarmupThread
        ):
            service = VoiceService()
            self.assertTrue(service.start())
            self.assertEqual(_FakeHotkeyThread.instances[-1].backend, "quartz")
            service.stop()

    # -------------------------
    # FUNCTION: test_recording_stopped_rejects_empty_or_short_audio
    # Purpose: Validate empty and short audio rejection scenario.
    # -------------------------
    def test_recording_stopped_rejects_empty_or_short_audio(self):
        service = VoiceService()
        errors = []
        completions = []
        service.error_occurred.connect(errors.append)
        service.transcription_done.connect(lambda: completions.append(True))

        service._on_recording_stopped(None)
        self.assertIn("No audio captured.", errors)

        short_capture = AudioCapture(
            samples=[0.01, 0.02, 0.01],
            sample_rate=16000,
            duration_seconds=0.2,
            peak_level=0.02,
            rms_level=0.01,
        )
        service._on_recording_stopped(short_capture)
        self.assertIn("Recording too short - speak longer.", errors)

        self.assertEqual(len(completions), 2)

    # -------------------------
    # FUNCTION: test_recorder_cleanup_waits_for_finished_signal
    # Purpose: Validate that the recorder thread is not deleted from the data callback.
    # -------------------------
    def test_recorder_cleanup_waits_for_finished_signal(self):
        service = VoiceService()
        recorder = _FakeRecorderThread()
        service._recorder = recorder

        service._on_recording_stopped(None)
        self.assertIs(service._recorder, recorder)
        self.assertFalse(recorder.deleted)

        service._on_recorder_finished(recorder)
        self.assertIsNone(service._recorder)
        self.assertTrue(recorder.deleted)

    # -------------------------
    # FUNCTION: test_successful_transcription_emits_command_ready
    # Purpose: Validate successful transcription scenario.
    # -------------------------
    def test_successful_transcription_emits_command_ready(self):
        service = VoiceService()
        commands = []
        completions = []
        service.command_ready.connect(commands.append)
        service.transcription_done.connect(lambda: completions.append(True))

        capture = AudioCapture(
            samples=[0.1] * 16000,
            sample_rate=16000,
            duration_seconds=1.0,
            peak_level=0.1,
            rms_level=0.1,
        )

        with patch("src.backend.services.voice_service.WhisperTranscriberThread", _FakeTranscriber):
            service._on_recording_stopped(capture)

        self.assertEqual(commands, ["sync gmail"])
        self.assertEqual(completions, [True])

    # -------------------------
    # FUNCTION: test_prepare_capture_trims_and_normalizes_quiet_speech
    # Purpose: Validate mic preprocessing for quiet speech and silence.
    # -------------------------
    def test_prepare_capture_trims_and_normalizes_quiet_speech(self):
        raw = np.concatenate(
            [
                np.zeros(3200, dtype=np.float32),
                np.ones(2400, dtype=np.float32) * 0.04,
                np.zeros(3200, dtype=np.float32),
            ]
        )

        capture = AudioRecorderThread.prepare_capture(raw, sample_rate=16000, np_module=np)
        self.assertIsNotNone(capture)
        self.assertLess(capture.duration_seconds, len(raw) / 16000)
        self.assertGreater(capture.peak_level, 0.04)

    # -------------------------
    # FUNCTION: test_detect_device_prefers_mps_when_available
    # Purpose: Validate accelerator detection on Apple Silicon.
    # -------------------------
    def test_detect_device_prefers_mps_when_available(self):
        class _FakeCuda:
            @staticmethod
            def is_available():
                return False

        class _FakeMPS:
            @staticmethod
            def is_available():
                return True

        class _FakeBackends:
            mps = _FakeMPS()

        class _FakeTorch:
            cuda = _FakeCuda()
            backends = _FakeBackends()

        WhisperTranscriberThread._device_cache = None
        try:
            with patch(
                "src.backend.services.voice_service._optional_import",
                side_effect=lambda name: _FakeTorch if name == "torch" else object(),
            ):
                self.assertEqual(WhisperTranscriberThread.detect_device(), "mps")
        finally:
            WhisperTranscriberThread._device_cache = None


if __name__ == "__main__":
    unittest.main()
