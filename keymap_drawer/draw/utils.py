"""Module containing lower-level SVG drawing utils, to be used as a mixin."""

from html import escape
from typing import Sequence, Literal, TextIO

from keymap_drawer.physical_layout import Point
from keymap_drawer.config import DrawConfig
from keymap_drawer.draw.glyph import GlyphMixin


LegendType = Literal["tap", "hold", "shifted"]


class UtilsMixin(GlyphMixin):
    """Mixin that adds low-level SVG drawing methods for KeymapDrawer."""

    # initialized in KeymapDrawer
    cfg: DrawConfig
    out: TextIO

    @staticmethod
    def _to_class_str(classes: Sequence[str]) -> str:
        return (' class="' + " ".join(c for c in classes if c) + '"') if classes else ""

    @staticmethod
    def _split_text(text: str) -> list[str]:
        # do not split on double spaces, but do split on single
        return [word.replace("\x00", " ") for word in text.replace("  ", "\x00").split()]

    def _draw_rect(self, p: Point, dims: Point, radii: Point, classes: Sequence[str]) -> None:
        self.out.write(
            f'<rect rx="{round(radii.x)}" ry="{round(radii.y)}"'
            f' x="{round(p.x - dims.x / 2)}" y="{round(p.y - dims.y / 2)}" '
            f'width="{round(dims.x)}" height="{round(dims.y)}"{self._to_class_str(classes)}/>\n'
        )

    def _draw_key(self, p: Point, dims: Point, classes: Sequence[str]) -> None:
        if self.cfg.draw_key_sides:
            # draw side rectangle
            self._draw_rect(
                p,
                dims,
                Point(self.cfg.key_rx, self.cfg.key_ry),
                classes=[*classes, "side"],
            )
            # draw internal rectangle
            self._draw_rect(
                p - Point(self.cfg.key_side_pars.rel_x, self.cfg.key_side_pars.rel_y),
                dims - Point(self.cfg.key_side_pars.rel_w, self.cfg.key_side_pars.rel_h),
                Point(self.cfg.key_side_pars.rx, self.cfg.key_side_pars.ry),
                classes=classes,
            )
        else:
            # default key style
            self._draw_rect(
                p,
                dims,
                Point(self.cfg.key_rx, self.cfg.key_ry),
                classes=classes,
            )

    def _get_scaling(self, width: int) -> str:
        if not self.cfg.shrink_wide_legends or width <= self.cfg.shrink_wide_legends:
            return ""
        return f' style="font-size: {max(60.0, 100 * self.cfg.shrink_wide_legends / width):.0f}%"'

    def _draw_text(self, p: Point, word: str, classes: Sequence[str]) -> None:
        if not word:
            return
        self.out.write(
            f'<text x="{round(p.x)}" y="{round(p.y)}"{self._to_class_str(classes)}{self._get_scaling(len(word))}>'
            f"{escape(word)}</text>\n"
        )

    def _draw_textblock(self, p: Point, words: Sequence[str], classes: Sequence[str], shift: float = 0) -> None:
        self.out.write(
            f'<text x="{round(p.x)}" y="{round(p.y)}"{self._to_class_str(classes)}'
            f"{self._get_scaling(max(len(w) for w in words))}>\n"
        )
        dy_0 = (len(words) - 1) * (self.cfg.line_spacing * (1 + shift) / 2)
        self.out.write(f'<tspan x="{p.x}" dy="-{dy_0}em">{escape(words[0])}</tspan>')
        for word in words[1:]:
            self.out.write(f'<tspan x="{p.x}" dy="{self.cfg.line_spacing}em">{escape(word)}</tspan>\n')
        self.out.write("</text>\n")

    def _draw_glyph(self, p: Point, name: str, legend_type: LegendType, classes: Sequence[str]) -> None:
        width, height, d_y = self.get_glyph_dimensions(name, legend_type)

        classes = [*classes, "glyph", name]
        self.out.write(
            f'<use href="#{name}" xlink:href="#{name}" x="{round(p.x - (width / 2))}" y="{round(p.y - d_y)}" '
            f'height="{height}" width="{width}"{self._to_class_str(classes)}/>\n'
        )

    def _draw_legend(  # pylint: disable=too-many-arguments
        self, p: Point, words: Sequence[str], classes: Sequence[str], legend_type: LegendType, shift: float = 0
    ) -> None:
        if not words:
            return

        classes = [*classes, legend_type]

        if len(words) == 1:
            if glyph := self.legend_is_glyph(words[0]):
                self._draw_glyph(p, glyph, legend_type, classes)
                return

            self._draw_text(p, words[0], classes)
            return

        self._draw_textblock(p, words, classes, shift)
