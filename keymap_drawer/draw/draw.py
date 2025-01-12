"""
Module that contains the KeymapDrawer class which takes a physical layout,
keymap with layers and optionally combo definitions, then can draw an SVG
representation of the keymap using these two.
"""

from html import escape
from copy import deepcopy
from typing import Sequence, TextIO

from keymap_drawer.keymap import KeymapData, LayoutKey
from keymap_drawer.physical_layout import Point, PhysicalKey
from keymap_drawer.config import DrawConfig
from keymap_drawer.draw.utils import UtilsMixin
from keymap_drawer.draw.combo import ComboDrawerMixin


class KeymapDrawer(ComboDrawerMixin, UtilsMixin):
    """Class that draws a keyboard representation in SVG."""

    def __init__(self, config: DrawConfig, out: TextIO, **kwargs) -> None:
        self.cfg = config
        self.keymap = KeymapData(config=config, **kwargs)
        self.init_glyphs()
        assert self.keymap.layout is not None, "A PhysicalLayout must be provided for drawing"
        assert self.keymap.config is not None, "A DrawConfig must be provided for drawing"
        self.layout = self.keymap.layout
        self.out = out

    def print_layer_header(self, p: Point, header: str) -> None:
        """Print a layer header that precedes the layer visualization."""
        if self.cfg.append_colon_to_layer_header:
            header += ":"
        self.out.write(f'<text x="{p.x}" y="{p.y}" class="label">{escape(header)}</text>\n')

    def print_key(self, p_0: Point, p_key: PhysicalKey, l_key: LayoutKey, key_ind: int) -> None:
        """
        Given anchor coordinates p_0, print SVG code for a rectangle with text representing
        the key, which is described by its physical representation (p_key) and what it does in
        the given layer (l_key).
        """
        p, w, h, r = (
            p_0 + p_key.pos,
            p_key.width,
            p_key.height,
            p_key.rotation,
        )
        transform_attr = f' transform="rotate({r}, {round(p.x)}, {round(p.y)})"' if r != 0 else ""
        class_str = self._to_class_str(["key", l_key.type, f"keypos-{key_ind}"])
        self.out.write(f"<g{transform_attr}{class_str}>\n")

        self._draw_key(
            p, Point(w - 2 * self.cfg.inner_pad_w, h - 2 * self.cfg.inner_pad_h), classes=["key", l_key.type]
        )

        tap_words = self._split_text(l_key.tap)

        # auto-adjust vertical alignment up/down if there are two lines and either hold/shifted is present
        shift = 0
        if len(tap_words) == 2:
            if l_key.shifted and not l_key.hold:  # shift down
                shift = -1
            elif l_key.hold and not l_key.shifted:  # shift up
                shift = 1

        # auto-shift middle legend if key sides are drawn
        tap_shift = Point(self.cfg.legend_rel_x, self.cfg.legend_rel_y)
        if self.cfg.draw_key_sides:
            tap_shift -= Point(self.cfg.key_side_pars.rel_x, self.cfg.key_side_pars.rel_y)

        self._draw_legend(
            p + tap_shift,
            tap_words,
            classes=["key", l_key.type],
            legend_type="tap",
            shift=shift,
        )
        self._draw_legend(
            p + Point(0, h / 2 - self.cfg.inner_pad_h - self.cfg.small_pad),
            [l_key.hold],
            classes=["key", l_key.type],
            legend_type="hold",
        )
        self._draw_legend(
            p - Point(0, h / 2 - self.cfg.inner_pad_h - self.cfg.small_pad),
            [l_key.shifted],
            classes=["key", l_key.type],
            legend_type="shifted",
        )

        self.out.write("</g>\n")

    def print_layer(self, p_0: Point, layer_keys: Sequence[LayoutKey], empty_layer: bool = False) -> None:
        """
        Given anchor coordinates p_0, print SVG code for keys for a given layer.
        """
        for key_ind, (p_key, l_key) in enumerate(zip(self.layout.keys, layer_keys)):
            self.print_key(p_0, p_key, l_key if not empty_layer else LayoutKey(), key_ind)

    def print_board(
        self,
        draw_layers: Sequence[str] | None = None,
        keys_only: bool = False,
        combos_only: bool = False,
        ghost_keys: Sequence[int] | None = None,
    ) -> None:
        """Print SVG code representing the keymap."""
        layers = deepcopy(self.keymap.layers)
        if draw_layers:
            assert all(l in layers for l in draw_layers), "Some layer names selected for drawing are not in the keymap"
            layers = {name: layer for name, layer in layers.items() if name in draw_layers}

        if ghost_keys:
            for key_position in ghost_keys:
                assert (
                    0 <= key_position < len(self.layout)
                ), "Some key positions for `ghost_keys` are negative or too large for the layout"
                for layer in layers.values():
                    layer[key_position].type = "ghost"

        if not keys_only:
            combos_per_layer = self.keymap.get_combos_per_layer(layers)
        else:
            combos_per_layer = {layer_name: [] for layer_name in layers}
        offsets_per_layer = self.get_offsets_per_layer(combos_per_layer)

        board_w = self.layout.width + 2 * self.cfg.outer_pad_w
        board_h = (
            len(layers) * self.layout.height
            + (len(layers) + 1) * self.cfg.outer_pad_h
            + sum(top_offset + bot_offset for top_offset, bot_offset in offsets_per_layer.values())
        )
        self.out.write(
            f'<svg width="{board_w}" height="{board_h}" viewBox="0 0 {board_w} {board_h}" class="keymap" '
            'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">\n'
        )

        self.out.write(self.get_glyph_defs())

        self.out.write(f"<style>{self.cfg.svg_style}</style>\n")

        p = Point(self.cfg.outer_pad_w, 0.0)
        for name, layer_keys in layers.items():
            # per-layer class group
            self.out.write(f'<g class="layer-{name}">\n')

            # draw layer name
            self.print_layer_header(p + Point(0, self.cfg.outer_pad_h / 2), name)

            # get offsets added by combo alignments, draw keys and combos
            p += Point(0, self.cfg.outer_pad_h + offsets_per_layer[name][0])
            self.print_layer(p, layer_keys, empty_layer=combos_only)
            self.print_combos_for_layer(p, combos_per_layer[name])
            p += Point(0, self.layout.height + offsets_per_layer[name][1])

            self.out.write("</g>\n")

        self.out.write("</svg>\n")
