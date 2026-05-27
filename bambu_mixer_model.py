"""Bambu Studio compatible mixed-filament swatch reconstruction.

The polynomial coefficients below are a compact representation of
`FilamentMixerModel.hpp` in BambuStudio. The upstream mixer is MIT licensed:

Copyright (c) 2026 Justin Hayes

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import base64
from itertools import combinations_with_replacement
import lzma
import struct

# Binary packed little-endian doubles: 330 x 3 coefficient matrix followed by
# three intercepts, compressed only to avoid carrying hundreds of noisy lines
# through the application source.
_PAYLOAD = (
    "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"
)

_VALUES = struct.unpack("<993d", lzma.decompress(base64.b64decode(_PAYLOAD)))
_COEFFICIENTS = tuple(_VALUES[index:index + 3] for index in range(0, 990, 3))
_INTERCEPT = _VALUES[990:]


def _powers():
    output = []
    for degree in range(5):
        for terms in combinations_with_replacement(range(7), degree):
            values = [0] * 7
            for term in terms:
                values[term] += 1
            output.append(tuple(values))
    return tuple(output)


_POWERS = _powers()
assert len(_POWERS) == 330


def _float32(value):
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _hex_rgb(value):
    value = str(value).lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _lerp(first, second, ratio):
    ratio = _float32(ratio)
    if ratio <= 0.0:
        return first
    if ratio >= 1.0:
        return second
    values = first + second + (float(ratio),)
    features = []
    for powers in _POWERS:
        feature = 1.0
        for value, exponent in zip(values, powers):
            if exponent:
                feature *= value ** exponent
        features.append(feature)
    channels = []
    for channel in range(3):
        total = _INTERCEPT[channel]
        for feature, coefficient in zip(features, _COEFFICIENTS):
            total += feature * coefficient[channel]
        channels.append(max(0, min(255, int(total))))
    return tuple(channels)


def blend_color_multi(hex_colors, weights):
    """Match Bambu Studio's pairwise mixed-filament swatch reconstruction."""
    if not hex_colors:
        return "#000000"
    accumulated = 0
    result = (128, 128, 128)
    for color, weight in zip(hex_colors, weights):
        weight = int(weight)
        if weight <= 0:
            continue
        current = _hex_rgb(color)
        if accumulated == 0:
            result = current
            accumulated = weight
        else:
            total = accumulated + weight
            result = _lerp(result, current, _float32(weight / total))
            accumulated = total
    if accumulated == 0:
        return "#000000"
    return "#{:02X}{:02X}{:02X}".format(*result)
