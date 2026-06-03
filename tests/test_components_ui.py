"""Tests for components/ui.py — pure HTML helpers and display constants."""


from components.ui import (
    AREA_LABEL,
    EFFORT_LABEL,
    IMPACT_LABEL,
    PRIORITY_LABEL,
    PRIORITY_NUM,
    STATUS_COLOR,
    STATUS_HEX,
    STATUS_LABEL,
    area_chip,
    pbadge,
    sdot,
    stat_grid,
)


class TestPbadge:
    def test_returns_span(self):
        result = pbadge("3", "#1e293b")
        assert result.startswith("<span")
        assert result.endswith("</span>")

    def test_contains_number(self):
        assert ">3<" in pbadge("3", "#1e293b")

    def test_contains_bg_color(self):
        assert "#1e293b" in pbadge("3", "#1e293b")

    def test_custom_fg(self):
        result = pbadge("1", "#aaa", fg="#000")
        assert "#000" in result

    def test_default_fg_is_white(self):
        assert "#fff" in pbadge("2", "#64748b")


class TestSdot:
    def test_returns_span(self):
        result = sdot("backlog")
        assert result.startswith("<span")
        assert result.endswith("</span>")

    def test_known_status_uses_correct_color(self):
        assert STATUS_HEX["concluído"] in sdot("concluído")

    def test_unknown_status_uses_fallback_color(self):
        result = sdot("unknown_status_xyz")
        assert "#9CA3AF" in result

    def test_size_parameter_applied(self):
        assert "14px" in sdot("backlog", size=14)

    def test_default_size_is_10(self):
        assert "10px" in sdot("backlog")


class TestAreaChip:
    def test_none_area_returns_dash(self):
        result = area_chip(None)
        assert "—" in result

    def test_empty_string_returns_dash(self):
        result = area_chip("")
        # empty string is falsy
        assert "—" in result

    def test_known_area_uses_english_label(self):
        result = area_chip("produto")
        assert "Product" in result

    def test_unknown_area_uses_title_case(self):
        result = area_chip("custom-area")
        assert "Custom-Area" in result or "Custom" in result

    def test_returns_span(self):
        result = area_chip("gestão")
        assert "<span" in result and "</span>" in result


class TestConstants:
    def test_status_hex_has_all_statuses(self):
        expected = {
            "backlog", "em análise", "análise - aprovado", "análise - rejeitado",
            "aguardando desenvolvimento", "em desenvolvimento", "em validação",
            "concluído", "descartado",
        }
        assert expected == set(STATUS_HEX.keys())

    def test_status_label_values_are_english(self):
        for v in STATUS_LABEL.values():
            # Should not contain Portuguese-only chars that signal untranslated text
            assert "ção" not in v and "ído" not in v

    def test_priority_num_has_three_levels(self):
        assert set(PRIORITY_NUM.keys()) == {"alta", "média", "baixa"}

    def test_priority_num_values_are_html(self):
        for v in PRIORITY_NUM.values():
            assert "<span" in v

    def test_status_color_built_from_status_hex(self):
        # Every key in STATUS_HEX should appear in STATUS_COLOR
        assert set(STATUS_COLOR.keys()) == set(STATUS_HEX.keys())

    def test_all_labels_non_empty(self):
        for d in (STATUS_LABEL, PRIORITY_LABEL, IMPACT_LABEL, EFFORT_LABEL, AREA_LABEL):
            for k, v in d.items():
                assert v, f"Empty label for key: {k}"


class TestStatGrid:
    def test_tuples_render_label_and_value(self):
        html = stat_grid([("Sessions", 40), ("Messages", "1,234")])
        assert 'class="cc-sg"' in html
        assert html.count('class="cc-sc"') == 2
        assert ">Sessions<" in html and ">40<" in html
        assert ">1,234<" in html

    def test_columns_in_template(self):
        assert "repeat(6,1fr)" in stat_grid([("a", 1)], columns=6)
        assert "repeat(4,1fr)" in stat_grid([("a", 1)])  # default

    def test_color_applies_value_style(self):
        html = stat_grid([{"label": "Bugs", "value": 3, "color": "#EF4444"}])
        assert 'style="color:#EF4444"' in html

    def test_vstyle_overrides_color(self):
        html = stat_grid([{"label": "Model", "value": "Sonnet", "vstyle": "font-size:.9rem"}])
        assert 'style="font-size:.9rem"' in html

    def test_extra_html_appended_inside_card(self):
        html = stat_grid([{"label": "Done", "value": 2, "extra": "<div class='bar'></div>"}])
        assert "<div class='bar'></div>" in html

    def test_empty_cards(self):
        html = stat_grid([])
        assert 'class="cc-sg"' in html
        assert 'class="cc-sc"' not in html
