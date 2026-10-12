"""If the UI thread ever stalls, crash.log must say where."""

import subprocess
import sys
import textwrap


def test_stalled_main_thread_dumps_its_stack(tmp_path):
    log = tmp_path / "crash.log"
    code = textwrap.dedent(
        f"""
        import time
        from usage_hud import app
        app._HANG_DUMP_SECONDS = 1
        app._hang_log = open(r"{log}", "a", buffering=1)
        app._arm_hang_dump()
        def stuck_in_a_system_call():
            time.sleep(2.5)
        stuck_in_a_system_call()
        """
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=30)
    text = log.read_text(encoding="utf-8")
    assert "stuck_in_a_system_call" in text


def test_rearming_keeps_a_healthy_ui_thread_silent(tmp_path):
    log = tmp_path / "crash.log"
    code = textwrap.dedent(
        f"""
        import time
        from usage_hud import app
        app._HANG_DUMP_SECONDS = 1
        app._hang_log = open(r"{log}", "a", buffering=1)
        for _ in range(6):
            app._arm_hang_dump()
            time.sleep(0.3)
        """
    )
    subprocess.run([sys.executable, "-c", code], check=True, timeout=30)
    assert log.read_text(encoding="utf-8") == ""
