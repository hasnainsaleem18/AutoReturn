"""Unit tests for voice parsing and lightweight voice service behavior."""

from __future__ import annotations

import types
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from src.backend.models.automation_models import VoiceActivationMode
from src.backend.services.voice_service import (
    AudioCapture,
    AudioRecorderThread,
    VoiceCommandParser,
    VoiceService,
    WhisperTranscriberThread,
)
from src.backend.services.voice_intent_service import VoiceIntentService
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
    def __init__(self, model_size: str = "base", preferred_device=None, language: str = "en"):
        self.model_size = model_size
        self.preferred_device = preferred_device
        self.language = language
        self.resolved_device = preferred_device or "cpu"
        self.last_error = ""
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


class _FakeWakeListenerThread:
    instances = []

    def __init__(self, **_kwargs):
        self.wake_audio_ready = _FakeSignal()
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


class _FakeRecorderThread:
    def __init__(self, stop_on_silence: bool = False, **_kwargs):
        self.deleted = False
        self._running = True
        self.stop_on_silence = stop_on_silence

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
    # FUNCTION: test_search_query_strips_trailing_punctuation
    # Purpose: Validate cleanup of Whisper-added punctuation in search text.
    # -------------------------
    def test_search_query_strips_trailing_punctuation(self):
        command = VoiceCommandParser.parse("search for john.")
        self.assertEqual(command.action, "search")
        self.assertEqual(command.parameters["query"], "john")

    # -------------------------
    # FUNCTION: test_wake_word_inline_command_is_stripped_before_parse
    # Purpose: Validate wake-word-prefixed commands.
    # -------------------------
    def test_wake_word_inline_command_is_stripped_before_parse(self):
        command = VoiceCommandParser.parse("hey autoreturn search for john.")
        self.assertEqual(command.action, "search")
        self.assertEqual(command.parameters["query"], "john")

    # -------------------------
    # FUNCTION: test_fuzzy_ui_command_autocorrects_common_whisper_miss
    # Purpose: Validate fuzzy correction for slightly wrong command words.
    # -------------------------
    def test_fuzzy_ui_command_autocorrects_common_whisper_miss(self):
        command = VoiceCommandParser.parse("show argent")
        self.assertEqual(command.action, "filter")
        self.assertEqual(command.parameters["filter_id"], "urgent")

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


class TestVoiceIntentServiceFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: test_natural_reply_extracts_freeform_message
    # Purpose: Validate natural voice reply parsing with arbitrary dictated text.
    # -------------------------
    def test_natural_reply_extracts_freeform_message(self):
        intent = VoiceIntentService().parse("reply to Hasnain saying here is update for today")

        self.assertEqual(intent.action, "reply_to_sender")
        self.assertEqual(intent.recipient, "Hasnain")
        self.assertEqual(intent.message, "here is update for today")
        self.assertEqual(intent.send_mode, "review")

    # -------------------------
    # FUNCTION: test_context_reply_targets_current_message
    # Purpose: Validate context-aware voice reply parsing.
    # -------------------------
    def test_context_reply_targets_current_message(self):
        intent = VoiceIntentService().parse("reply to this saying I will send it today")

        self.assertEqual(intent.action, "reply_to_sender")
        self.assertEqual(intent.target, "current")
        self.assertEqual(intent.message, "I will send it today")
        self.assertEqual(intent.send_mode, "review")

    # -------------------------
    # FUNCTION: test_gmail_new_message_command_uses_gmail_channel
    # Purpose: Validate Gmail-specific new-message parsing.
    # -------------------------
    def test_gmail_new_message_command_uses_gmail_channel(self):
        intent = VoiceIntentService().parse("send email to Hasnain saying here is update")

        self.assertEqual(intent.action, "send_message")
        self.assertEqual(intent.channel, "gmail")
        self.assertEqual(intent.recipient, "Hasnain")
        self.assertEqual(intent.message, "here is update")

    # -------------------------
    # FUNCTION: test_multi_step_voice_plan
    # Purpose: Validate deterministic multi-step voice planning fallback.
    # -------------------------
    def test_multi_step_voice_plan(self):
        plan = VoiceIntentService().parse_plan("show urgent messages then open voice history")

        self.assertEqual([step.action for step in plan], ["filter_messages", "show_voice_history"])
        self.assertEqual(plan[0].target, "urgent")


class TestVoiceServiceFormal(unittest.TestCase):
    @classmethod
    # -------------------------
    # FUNCTION: setUpClass
    # Purpose: Execute setUpClass logic for this module.
    # -------------------------
    def setUpClass(cls):
        cls.app = get_qapp()

    # -------------------------
    # FUNCTION: test_start_gracefully_disables_when_core_dependencies_missing
    # Purpose: Validate graceful disable when essential voice deps are missing.
    # -------------------------
    def test_start_gracefully_disables_when_core_dependencies_missing(self):
        with patch("src.backend.services.voice_service.sys.platform", "linux"), \
                patch(
                    "src.backend.services.voice_service._optional_import",
                    side_effect=lambda name: None if name == "sounddevice" else object(),
                ):
            service = VoiceService()
            self.assertFalse(service.start())
            self.assertIn("sounddevice", service.startup_error())

    # -------------------------
    # FUNCTION: test_start_keeps_button_mode_when_hotkey_backend_missing
    # Purpose: Validate voice remains available without the global hotkey backend.
    # -------------------------
    def test_start_keeps_button_mode_when_hotkey_backend_missing(self):
        _FakeWakeListenerThread.instances.clear()
        with patch("src.backend.services.voice_service.sys.platform", "linux"), patch(
            "src.backend.services.voice_service._optional_import",
            side_effect=lambda name: None if name == "keyboard" else object(),
        ), patch("src.backend.services.voice_service.WakeWordListenerThread", _FakeWakeListenerThread), patch(
            "src.backend.services.voice_service.WhisperWarmupThread", _FakeWarmupThread
        ):
            service = VoiceService()
            self.assertTrue(service.start())
            self.assertTrue(service.is_available())
            self.assertFalse(service.is_prepared())
            self.assertIn("click mic", service.usage_hint().lower())
            self.assertEqual(len(_FakeWakeListenerThread.instances), 0)
            service.stop()

    # -------------------------
    # FUNCTION: test_start_keeps_button_mode_when_quartz_missing_on_macos
    # Purpose: Validate the macOS fallback when Quartz hotkeys are unavailable.
    # -------------------------
    def test_start_keeps_button_mode_when_quartz_missing_on_macos(self):
        _FakeWakeListenerThread.instances.clear()
        with patch("src.backend.services.voice_service.sys.platform", "darwin"), patch(
            "src.backend.services.voice_service._optional_import",
            side_effect=lambda name: None if name == "Quartz" else object(),
        ), patch("src.backend.services.voice_service.WakeWordListenerThread", _FakeWakeListenerThread), patch(
            "src.backend.services.voice_service.WhisperWarmupThread", _FakeWarmupThread
        ):
            service = VoiceService()
            self.assertTrue(service.start())
            self.assertTrue(service.is_available())
            self.assertFalse(service.is_prepared())
            self.assertNotIn("hold", service.usage_hint().lower())
            self.assertEqual(len(_FakeWakeListenerThread.instances), 0)
            service.stop()

    # -------------------------
    # FUNCTION: test_start_uses_quartz_backend_on_macos
    # Purpose: Validate backend selection for macOS hotkeys.
    # -------------------------
    def test_start_uses_quartz_backend_on_macos(self):
        _FakeHotkeyThread.instances.clear()
        _FakeWakeListenerThread.instances.clear()
        with patch("src.backend.services.voice_service.sys.platform", "darwin"), patch(
            "src.backend.services.voice_service._optional_import",
            side_effect=lambda _name: object(),
        ), patch("src.backend.services.voice_service.HotkeyListenerThread", _FakeHotkeyThread), patch(
            "src.backend.services.voice_service.WakeWordListenerThread", _FakeWakeListenerThread
        ), patch(
            "src.backend.services.voice_service.WhisperWarmupThread", _FakeWarmupThread
        ):
            service = VoiceService()
            self.assertTrue(service.start())
            self.assertEqual(_FakeHotkeyThread.instances[-1].backend, "quartz")
            self.assertFalse(service.is_prepared())
            self.assertEqual(len(_FakeWakeListenerThread.instances), 0)
            service.stop()

    # -------------------------
    # FUNCTION: test_start_wake_word_mode_starts_background_listener
    # Purpose: Validate explicit wake-word mode startup behavior.
    # -------------------------
    def test_start_wake_word_mode_starts_background_listener(self):
        _FakeWakeListenerThread.instances.clear()
        with patch("src.backend.services.voice_service.sys.platform", "linux"), patch(
            "src.backend.services.voice_service._optional_import",
            side_effect=lambda _name: object(),
        ), patch("src.backend.services.voice_service.HotkeyListenerThread", _FakeHotkeyThread), patch(
            "src.backend.services.voice_service.WakeWordListenerThread", _FakeWakeListenerThread
        ), patch("src.backend.services.voice_service.WhisperWarmupThread", _FakeWarmupThread), patch(
            "src.backend.services.voice_service.AudioRecorderThread.check_microphone_available",
            return_value=(True, "", 0),
        ):
            service = VoiceService(activation_mode=VoiceActivationMode.WAKE_WORD.value)
            self.assertTrue(service.start())
            self.assertFalse(service.is_prepared())
            self.assertIn("hey autoreturn", service.usage_hint().lower())
            self.assertEqual(len(_FakeWakeListenerThread.instances), 1)
            self.assertTrue(_FakeWakeListenerThread.instances[0].isRunning())
            service.stop()

    # -------------------------
    # FUNCTION: test_cached_model_marks_voice_prepared_immediately
    # Purpose: Validate prepared state when Whisper is already cached.
    # -------------------------
    def test_cached_model_marks_voice_prepared_immediately(self):
        service = VoiceService()
        service._enabled = True
        service._resolved_device = "cpu"
        with patch(
            "src.backend.services.voice_service.WhisperTranscriberThread.is_model_cached",
            return_value=True,
        ):
            service._start_model_warmup()
        self.assertTrue(service.is_prepared())

    # -------------------------
    # FUNCTION: test_button_capture_starts_auto_stop_recorder
    # Purpose: Validate Mic button capture path.
    # -------------------------
    def test_button_capture_starts_auto_stop_recorder(self):
        service = VoiceService()
        starts = []

        class _RecorderForStart(_FakeRecorderThread):
            def __init__(self, stop_on_silence: bool = False, **kwargs):
                super().__init__(stop_on_silence=stop_on_silence, **kwargs)
                self.recording_stopped = _FakeSignal()
                self.recording_failed = _FakeSignal()
                self.finished = _FakeSignal()

            def start(self):
                starts.append(self.stop_on_silence)

        service._enabled = True
        with patch("src.backend.services.voice_service.AudioRecorderThread", _RecorderForStart):
            self.assertTrue(service.start_button_capture())

        self.assertEqual(starts, [True])
        self.assertEqual(service.current_activation_source(), "button")

    # -------------------------
    # FUNCTION: test_button_capture_rejects_missing_microphone_before_recorder_starts
    # Purpose: Validate macOS microphone preflight before native audio thread startup.
    # -------------------------
    def test_button_capture_rejects_missing_microphone_before_recorder_starts(self):
        service = VoiceService()
        service._enabled = True
        errors = []
        service.error_occurred.connect(errors.append)

        with patch("src.backend.services.voice_service.sys.platform", "linux"), \
                patch.object(
                    AudioRecorderThread,
                    "check_microphone_available",
                    return_value=(False, "Microphone access is unavailable.", None),
                ):
            self.assertFalse(service.start_button_capture())

        self.assertEqual(errors, ["Microphone access is unavailable."])
        self.assertEqual(service.last_recording_error(), "Microphone access is unavailable.")

    # -------------------------
    # FUNCTION: test_macos_button_capture_skips_parent_sounddevice_preflight
    # Purpose: Validate macOS recording keeps PortAudio checks out of the main process.
    # -------------------------
    def test_macos_button_capture_skips_parent_sounddevice_preflight(self):
        service = VoiceService()
        service._enabled = True
        starts = []

        class _RecorderForStart(_FakeRecorderThread):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.recording_stopped = _FakeSignal()
                self.recording_failed = _FakeSignal()
                self.finished = _FakeSignal()

            def start(self):
                starts.append(getattr(self, "input_device", None))

        with patch("src.backend.services.voice_service.sys.platform", "darwin"), \
                patch.dict("src.backend.services.voice_service.os.environ", {}, clear=True), \
                patch.object(AudioRecorderThread, "check_microphone_available") as mic_check, \
                patch("src.backend.services.voice_service._optional_import") as optional_import, \
                patch("src.backend.services.voice_service.AudioRecorderThread", _RecorderForStart):
            optional_import.side_effect = lambda name: object() if name in {"numpy", "scipy.signal"} else None
            self.assertTrue(service.start_button_capture())

        mic_check.assert_not_called()
        optional_import.assert_not_called()
        self.assertEqual(starts, [None])

    # -------------------------
    # FUNCTION: test_microphone_check_requires_visible_input_device
    # Purpose: Validate missing/blocked mic detection before sounddevice opens a stream.
    # -------------------------
    def test_microphone_check_requires_visible_input_device(self):
        class _FakeDefault:
            device = [-1, -1]

        class _FakeSoundDevice:
            default = _FakeDefault()

            @staticmethod
            def query_devices():
                return []

            @staticmethod
            def check_input_settings(**_kwargs):
                raise AssertionError("should not check settings without an input device")

        ok, error, input_device = AudioRecorderThread.check_microphone_available(_FakeSoundDevice)
        self.assertFalse(ok)
        self.assertIsNone(input_device)
        self.assertIn("Microphone access is unavailable", error)

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
    # FUNCTION: test_transcription_cleanup_strips_terminal_punctuation
    # Purpose: Validate cleanup of terminal punctuation from Whisper output.
    # -------------------------
    def test_transcription_cleanup_strips_terminal_punctuation(self):
        cleaned = VoiceCommandParser._cleanup_transcribed_text(" search for john. ")
        self.assertEqual(cleaned, "search for john")

    # -------------------------
    # FUNCTION: test_wake_word_only_starts_followup_recording_after_transcriber_finishes
    # Purpose: Validate wake-word-only follow-up recording flow.
    # -------------------------
    def test_wake_word_only_starts_followup_recording_after_transcriber_finishes(self):
        service = VoiceService()
        starts = []

        def _fake_start_recording_session(source, stop_on_silence):
            starts.append((source, stop_on_silence))
            return True

        service._enabled = True
        service._wake_transcriber = _FakeTranscriber(audio_input=None)
        service._on_wake_transcription_ready("hey autoreturn")
        self.assertTrue(service._pending_wake_followup)

        with patch.object(service, "_start_recording_session", side_effect=_fake_start_recording_session):
            service._on_wake_transcriber_finished()

        self.assertEqual(starts, [("wake-word", True)])

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
    # FUNCTION: test_macos_transcriber_uses_isolated_process
    # Purpose: Validate macOS Whisper/Torch work does not run in the main process.
    # -------------------------
    def test_macos_transcriber_uses_isolated_process(self):
        ready = []
        failed = []
        calls = []
        transcriber = WhisperTranscriberThread(np.ones(16000, dtype=np.float32))
        transcriber.transcription_ready.connect(ready.append)
        transcriber.transcription_failed.connect(failed.append)

        def _fake_run(args, **_kwargs):
            calls.append(args)
            return types.SimpleNamespace(
                returncode=0,
                stdout='{"text": " Show gmail messages. ", "device": "cpu"}\n',
                stderr="",
            )

        with patch("src.backend.services.voice_service.sys.platform", "darwin"), \
                patch.dict("src.backend.services.voice_service.os.environ", {}, clear=True), \
                patch(
                    "src.backend.services.voice_service._optional_import",
                    side_effect=lambda name: np if name == "numpy" else object(),
                ), \
                patch.object(
                    WhisperTranscriberThread,
                    "load_cached_model",
                    side_effect=AssertionError("parent process should not load Whisper"),
                ), \
                patch("src.backend.services.voice_service.subprocess.run", side_effect=_fake_run):
            transcriber.run()

        self.assertEqual(ready, ["Show gmail messages"])
        self.assertEqual(failed, [])
        self.assertEqual(transcriber.resolved_device, "cpu")
        self.assertTrue(calls)

    # -------------------------
    # FUNCTION: test_macos_transcriber_uses_audio_path_without_parent_numpy
    # Purpose: Validate macOS command audio stays file-based in the main process.
    # -------------------------
    def test_macos_transcriber_uses_audio_path_without_parent_numpy(self):
        ready = []
        failed = []
        calls = []

        def _fake_run(args, **_kwargs):
            calls.append(args)
            return types.SimpleNamespace(
                returncode=0,
                stdout='{"text": " Show all messages. ", "device": "cpu"}\n',
                stderr="",
            )

        with tempfile.NamedTemporaryFile(suffix=".npy") as audio_file:
            transcriber = WhisperTranscriberThread(audio_file.name)
            transcriber.transcription_ready.connect(ready.append)
            transcriber.transcription_failed.connect(failed.append)

            with patch("src.backend.services.voice_service.sys.platform", "darwin"), \
                    patch.dict("src.backend.services.voice_service.os.environ", {}, clear=True), \
                    patch(
                        "src.backend.services.voice_service._optional_import",
                        side_effect=AssertionError("parent process should not import NumPy for file audio"),
                    ), \
                    patch.object(
                        WhisperTranscriberThread,
                        "load_cached_model",
                        side_effect=AssertionError("parent process should not load Whisper"),
                    ), \
                    patch("src.backend.services.voice_service.subprocess.run", side_effect=_fake_run):
                transcriber.run()

        self.assertEqual(ready, ["Show all messages"])
        self.assertEqual(failed, [])
        self.assertEqual(transcriber.resolved_device, "cpu")
        self.assertTrue(calls)

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
