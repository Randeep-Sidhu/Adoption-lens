from streamlit.testing.v1 import AppTest

from adoption_lens.config import ROOT


def test_the_dashboard_renders_and_responds_to_selections():
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=120).run()
    assert not at.exception and not at.warning
    assert len(at.tabs) == 8 and len(at.get("plotly_chart")) == 6
    at.selectbox[0].select("CA-ON").run()
    at.selectbox[1].select("US").run()
    at.slider[0].set_value(60).run()
    assert not at.exception and not at.warning
