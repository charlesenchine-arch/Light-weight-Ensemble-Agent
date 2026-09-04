from agentflow.theme import INTRO_EN, INTRO_ZH, SKINS, banner, set_skin


def test_skins_exist():
    assert set(SKINS) >= {"lea", "hermes", "claude"}
    for name in SKINS:
        skin = set_skin(name)
        assert skin.accent.startswith("#")
        panel = banner("/tmp", "balanced", "cny")
        assert panel is not None
    assert "your cost is our concern" in INTRO_EN
    assert "你的成本" in INTRO_ZH


def test_user_turn_keeps_every_line():
    from agentflow.theme import user_turn

    text = "line1\nline2\nline3\nline4\nline5"
    panel = user_turn(text, 3)
    assert panel is not None
    body = panel.renderable
    assert isinstance(body, type(panel.renderable))
    shown = getattr(body, "plain", str(body))
    for line in text.splitlines():
        assert line in shown


def test_unknown_skin():
    try:
        set_skin("not-a-skin")
        raise AssertionError("expected failure")
    except ValueError:
        pass
    set_skin("lea")


def test_live_stdout_degrades_glyphs_for_gbk(monkeypatch):
    import agentflow.theme as theme

    class GbkStream:
        encoding = "gbk"

        def __init__(self):
            self.value = ""

        def write(self, text):
            text.encode(self.encoding)
            self.value += text
            return len(text)

    stream = GbkStream()
    monkeypatch.setattr(theme.sys, "stdout", stream)
    writer = theme._LiveStdout()

    writer.write("✶ 中文")

    assert stream.value == "? 中文"
