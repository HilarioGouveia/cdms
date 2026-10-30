from pathlib import Path
import tomllib
import pytest

from cdms.adapters.ui import theme
from cdms.adapters.ui.components.cockpit_charts import create_funnel_cockpit_chart

ROOT = Path(__file__).resolve().parents[2]


def luminance(hex_color):
    values = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in values]
    return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + .05) / (dark + .05)


@pytest.mark.parametrize("profile", ["dark-premium", "soft-light"])
def test_text_and_semantic_colors_are_readable_on_their_surfaces(profile):
    p = tomllib.loads((ROOT / '.streamlit/themes' / (profile + '.toml')).read_text())['theme']
    for surface in ('backgroundColor', 'secondaryBackgroundColor', 'dataframeHeaderBackgroundColor'):
        assert contrast(p['textColor'], p[surface]) >= 4.5
        for color in ('blueTextColor', 'greenTextColor', 'yellowTextColor', 'redTextColor', 'violetTextColor', 'grayTextColor'):
            assert contrast(p[color], p[surface]) >= 4.5, (profile, color, surface)
    assert contrast('#FFFFFF', p['primaryColor']) >= 4.5
    for semantic in ('blue', 'green', 'yellow', 'red', 'violet'):
        assert contrast(p[semantic+'TextColor'], p[semantic+'BackgroundColor']) >= 4.5


@pytest.mark.parametrize("profile", ["dark-premium", "soft-light"])
def test_chart_uses_active_profile_without_changing_data(profile, monkeypatch):
    p = tomllib.loads((ROOT / '.streamlit/themes' / (profile + '.toml')).read_text())['theme']
    monkeypatch.setattr(theme.st, 'get_option', lambda key: p.get(key.removeprefix('theme.')))
    tokens = theme.theme_tokens()
    assert tokens['background'] == p['backgroundColor']
    figure = create_funnel_cockpit_chart(10000, 300, 60, 6)
    assert tuple(figure.data[0].x) == (10000, 300, 60, 6)
    assert figure.data[0].marker.color[-1] == p['greenTextColor']
    assert figure.layout.font.color == p['textColor']
    for fill, text in zip(figure.data[0].marker.color, figure.data[0].textfont.color):
        assert contrast(fill, text) >= 4.5
