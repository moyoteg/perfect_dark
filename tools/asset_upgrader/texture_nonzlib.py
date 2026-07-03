"""Non-zlib Perfect Dark texture decompression (port of src/game/texdecompress.c)."""

from __future__ import annotations

from tools.asset_upgrader.texture_codec import (
    TEXFORMAT_I4,
    TEXFORMAT_I8,
    TEXFORMAT_IA16,
    TEXFORMAT_IA4,
    TEXFORMAT_IA8,
    TEXFORMAT_RGB15,
    TEXFORMAT_RGB24,
    TEXFORMAT_RGBA16,
    TEXFORMAT_RGBA32,
    BitReader,
    tex_get_bit_size,
)

TEXCOMPMETHOD_UNCOMPRESSED0 = 0
TEXCOMPMETHOD_UNCOMPRESSED1 = 1
TEXCOMPMETHOD_HUFFMAN = 2
TEXCOMPMETHOD_HUFFMANPERHCHANNEL = 3
TEXCOMPMETHOD_RLE = 4
TEXCOMPMETHOD_LOOKUP = 5
TEXCOMPMETHOD_HUFFMANLOOKUP = 6
TEXCOMPMETHOD_RLELOOKUP = 7
TEXCOMPMETHOD_HUFFMANBLUR = 8
TEXCOMPMETHOD_RLEBLUR = 9

FORMAT_NUM_CHANNELS = [4, 3, 3, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1]
FORMAT_HAS_1BIT_ALPHA = [0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]
FORMAT_CHANNEL_SIZES = [256, 32, 256, 32, 256, 16, 8, 256, 16, 256, 16, 256, 16]
FORMAT_BITS_PER_PIXEL = [32, 16, 24, 15, 16, 8, 4, 8, 4, 16, 16, 16, 16]


def _rgba16_to_rgba(value: int, *, rgb15: bool = False) -> tuple[int, int, int, int]:
    r = ((value >> 11) & 0x1F) * 255 // 31
    g = ((value >> 6) & 0x1F) * 255 // 31
    b = ((value >> 1) & 0x1F) * 255 // 31
    if rgb15:
        a = 255
    else:
        a = 255 if (value & 1) else 0
    return r, g, b, a


def _ia16_to_rgba(value: int) -> tuple[int, int, int, int]:
    intensity = (value >> 8) & 0xFF
    alpha = value & 0xFF
    return intensity, intensity, intensity, alpha


def _inflate_huffman(reader: BitReader, num_iterations: int, chan_size: int) -> list[int]:
    frequencies = [reader.read(8) for _ in range(chan_size)]
    nodes: list[list[int]] = [[-1, -1] for _ in range(2048)]

    minfreq1 = 9999
    minfreq2 = 9999
    minindex1 = 0
    minindex2 = 0
    for i, freq in enumerate(frequencies):
        if freq < minfreq1:
            if minfreq2 < minfreq1:
                minfreq1 = freq
                minindex1 = i
            else:
                minfreq2 = freq
                minindex2 = i
        elif freq < minfreq2:
            minfreq2 = freq
            minindex2 = i

    done = False
    rootindex = 0
    while not done:
        sum_freq = frequencies[minindex1] + frequencies[minindex2]
        if sum_freq == 0:
            sum_freq = 1
        frequencies[minindex1] = 9999
        frequencies[minindex2] = 9999

        if nodes[minindex1][0] < 0 and nodes[minindex1][1] < 0:
            nodes[minindex1][0] = minindex1 + 10000
            rootindex = minindex1
            frequencies[minindex1] = sum_freq
            if nodes[minindex2][0] < 0 and nodes[minindex2][1] < 0:
                nodes[minindex1][1] = minindex2 + 10000
            else:
                nodes[minindex1][1] = minindex2
        elif nodes[minindex2][0] < 0 and nodes[minindex2][1] < 0:
            nodes[minindex2][0] = minindex2 + 10000
            rootindex = minindex2
            frequencies[minindex2] = sum_freq
            if nodes[minindex1][0] < 0 and nodes[minindex1][1] < 0:
                nodes[minindex2][1] = minindex1 + 10000
            else:
                nodes[minindex2][1] = minindex1
        else:
            rootindex = 0
            while (
                nodes[rootindex][0] >= 0
                or nodes[rootindex][1] >= 0
                or frequencies[rootindex] < 9999
            ):
                rootindex += 1
            frequencies[rootindex] = sum_freq
            nodes[rootindex][0] = minindex1
            nodes[rootindex][1] = minindex2

        minfreq1 = 9999
        minfreq2 = 9999
        for i, freq in enumerate(frequencies):
            if freq < minfreq1:
                if minfreq1 > minfreq2:
                    minfreq1 = freq
                    minindex1 = i
                else:
                    minfreq2 = freq
                    minindex2 = i
            elif freq < minfreq2:
                minfreq2 = freq
                minindex2 = i
        if minfreq1 == 9999 or minfreq2 == 9999:
            done = True

    dst: list[int] = []
    for _ in range(num_iterations):
        index_or_value = rootindex
        while index_or_value < 10000:
            index_or_value = nodes[index_or_value][reader.read(1)]
        dst.append(index_or_value - 10000)
    return dst


def _inflate_rle(reader: BitReader, blocks_total: int) -> list[int]:
    btfieldsize = reader.read(3)
    rlfieldsize = reader.read(3)
    blocksize = reader.read(4)
    cost = btfieldsize + rlfieldsize + blocksize + 1
    fudge = 0
    while cost > 0:
        cost = cost - blocksize - 1
        fudge += 1

    dst: list[int] = []
    blocks_done = 0
    while blocks_done < blocks_total:
        if reader.read(1) == 0:
            dst.append(reader.read(blocksize))
            blocks_done += 1
        else:
            start = blocks_done - reader.read(btfieldsize) - 1
            run_len = reader.read(rlfieldsize) + fudge
            for i in range(start, start + run_len):
                dst.append(dst[i])
                blocks_done += 1
            dst.append(reader.read(blocksize))
            blocks_done += 1
    return dst


def _build_lookup(reader: BitReader, bits_per_pixel: int) -> tuple[list[int], int]:
    num_colours = reader.read(11)
    lookup: list[int] = []
    for _ in range(num_colours):
        if bits_per_pixel <= 16:
            lookup.append(reader.read(bits_per_pixel))
        elif bits_per_pixel <= 24:
            lookup.append(reader.read(bits_per_pixel))
        else:
            lookup.append((reader.read(24) << 8) | reader.read(bits_per_pixel - 24))
    return lookup, num_colours


def _read_alpha_bits(reader: BitReader, count: int) -> list[int]:
    return [reader.read(1) for _ in range(count)]


def _blur(pixels: list[int], width: int, height: int, method: int, chan_size: int) -> None:
    for y in range(height):
        for x in range(width):
            cur = pixels[y * width + x] + chan_size * 2
            left = pixels[y * width + x - 1] if x > 0 else 0
            above = pixels[(y - 1) * width + x] if y > 0 else 0
            aboveleft = pixels[(y - 1) * width + x - 1] if x > 0 and y > 0 else 0
            if method == 0:
                pixels[y * width + x] = (cur + left) % chan_size
            elif method == 1:
                pixels[y * width + x] = (cur + above) % chan_size
            elif method == 2:
                pixels[y * width + x] = (cur + aboveleft) % chan_size
            elif method == 3:
                pixels[y * width + x] = (cur + (left + above - aboveleft)) % chan_size
            elif method == 4:
                pixels[y * width + x] = (cur + ((above - aboveleft) // 2 + left)) % chan_size
            elif method == 5:
                pixels[y * width + x] = (cur + ((left - aboveleft) // 2 + above)) % chan_size
            elif method == 6:
                pixels[y * width + x] = (cur + ((left + above) // 2)) % chan_size


def _read_uncompressed(reader: BitReader, width: int, height: int, format_id: int) -> list[tuple[int, int, int, int]]:
    pixels: list[tuple[int, int, int, int]] = []
    for _y in range(height):
        row: list[tuple[int, int, int, int]] = []
        for _x in range(width):
            if format_id == TEXFORMAT_RGBA32:
                hi = reader.read(16)
                lo = reader.read(16)
                value = (hi << 16) | lo
                row.append(((value >> 24) & 0xFF, (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF))
            elif format_id == TEXFORMAT_RGB24:
                value = reader.read(24)
                row.append(((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF, 255))
            elif format_id == TEXFORMAT_RGBA16:
                row.append(_rgba16_to_rgba(reader.read(16)))
            elif format_id == TEXFORMAT_IA16:
                row.append(_ia16_to_rgba(reader.read(16)))
            elif format_id == TEXFORMAT_RGB15:
                row.append(_rgba16_to_rgba(reader.read(15) << 1 | 1, rgb15=True))
            elif format_id in (TEXFORMAT_IA8, TEXFORMAT_I8):
                value = reader.read(8)
                if format_id == TEXFORMAT_I8:
                    row.append((value, value, value, 255))
                else:
                    row.append(((value >> 4) * 17, (value >> 4) * 17, (value >> 4) * 17, (value & 0xF) * 17))
            elif format_id in (TEXFORMAT_IA4, TEXFORMAT_I4):
                value = reader.read(8)
                if format_id == TEXFORMAT_I4:
                    row.append(((value >> 4) * 17, (value >> 4) * 17, (value >> 4) * 17, (value & 0xF) * 17))
                else:
                    row.append((((value >> 5) & 7) * 36, ((value >> 5) & 7) * 36, ((value >> 5) & 7) * 36, (value & 0xF) * 17))
        pixels.extend(row)
    return pixels


def _channels_to_rgba(
    channels: list[int], width: int, height: int, format_id: int, alpha_bits: list[int] | None = None
) -> list[tuple[int, int, int, int]]:
    mult = width * height
    pixels: list[tuple[int, int, int, int]] = []

    if format_id == TEXFORMAT_I4:
        pos = 0
        for _y in range(height):
            for x in range(0, width, 2):
                hi = channels[pos]
                lo = channels[pos + 1] if x + 1 < width else hi
                pixels.append((hi * 17, hi * 17, hi * 17, 255))
                if x + 1 < width:
                    pixels.append((lo * 17, lo * 17, lo * 17, 255))
                pos += 2
    else:
        pos = 0
        for _y in range(height):
            for _x in range(width):
                if format_id == TEXFORMAT_RGBA32:
                    r, g, b, a = channels[pos], channels[pos + mult], channels[pos + 2 * mult], channels[pos + 3 * mult]
                    pixels.append((r, g, b, a))
                elif format_id == TEXFORMAT_RGB24:
                    pixels.append((channels[pos], channels[pos + mult], channels[pos + 2 * mult], 255))
                elif format_id == TEXFORMAT_RGBA16:
                    value = (
                        channels[pos] << 11
                        | channels[pos + mult] << 6
                        | channels[pos + 2 * mult] << 1
                        | (alpha_bits[pos] if alpha_bits else channels[pos + 3 * mult])
                    )
                    pixels.append(_rgba16_to_rgba(value))
                elif format_id == TEXFORMAT_IA16:
                    pixels.append(_ia16_to_rgba(channels[pos] << 8 | channels[pos + mult]))
                elif format_id == TEXFORMAT_RGB15:
                    value = channels[pos] << 11 | channels[pos + mult] << 6 | channels[pos + 2 * mult] << 1 | 1
                    pixels.append(_rgba16_to_rgba(value, rgb15=True))
                elif format_id == TEXFORMAT_IA8:
                    i = channels[pos]
                    a = channels[pos + mult]
                    pixels.append((i * 17, i * 17, i * 17, a * 17))
                elif format_id == TEXFORMAT_I8:
                    value = channels[pos]
                    pixels.append((value, value, value, 255))
                elif format_id == TEXFORMAT_IA4:
                    i = channels[pos]
                    a = channels[pos + mult * 3]
                    pixels.append((i * 36, i * 36, i * 36, a * 17))
                pos += 1

    if alpha_bits and format_id == TEXFORMAT_RGBA16:
        pass  # alpha already merged per pixel above
    return pixels


def _lookup_to_rgba(
    reader: BitReader, width: int, height: int, lookup: list[int], num_colours: int, format_id: int
) -> list[tuple[int, int, int, int]]:
    bits = tex_get_bit_size(num_colours)
    pixels: list[tuple[int, int, int, int]] = []
    for _y in range(height):
        for _x in range(width):
            idx = reader.read(bits)
            value = lookup[idx]
            if format_id == TEXFORMAT_RGBA32:
                pixels.append(((value >> 24) & 0xFF, (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF))
            elif format_id == TEXFORMAT_RGB24:
                pixels.append(((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF, 255))
            elif format_id == TEXFORMAT_RGBA16:
                pixels.append(_rgba16_to_rgba(value))
            elif format_id == TEXFORMAT_IA16:
                pixels.append(_ia16_to_rgba(value))
            elif format_id == TEXFORMAT_RGB15:
                pixels.append(_rgba16_to_rgba(value << 1 | 1, rgb15=True))
            elif format_id == TEXFORMAT_IA8:
                pixels.append(((value >> 4) * 17, (value >> 4) * 17, (value >> 4) * 17, (value & 0xF) * 17))
            elif format_id == TEXFORMAT_I8:
                pixels.append((value, value, value, 255))
            elif format_id == TEXFORMAT_IA4:
                pixels.append((((value >> 4) & 0xF) * 17, ((value >> 4) & 0xF) * 17, ((value >> 4) & 0xF) * 17, (value & 0xF) * 17))
            elif format_id == TEXFORMAT_I4:
                pixels.append(((value >> 4) * 17, (value >> 4) * 17, (value >> 4) * 17, (value & 0xF) * 17))
    return pixels


def _lookup_buffer_to_rgba(
    indices: list[int], width: int, height: int, lookup: list[int], format_id: int
) -> list[tuple[int, int, int, int]]:
    pixels: list[tuple[int, int, int, int]] = []
    pos = 0
    for _y in range(height):
        for _x in range(width):
            value = lookup[indices[pos]]
            pos += 1
            if format_id == TEXFORMAT_I8:
                pixels.append((value, value, value, 255))
            elif format_id == TEXFORMAT_IA8:
                pixels.append(((value >> 4) * 17, (value >> 4) * 17, (value >> 4) * 17, (value & 0xF) * 17))
            elif format_id == TEXFORMAT_RGBA16:
                pixels.append(_rgba16_to_rgba(value))
            else:
                pixels.append((value & 0xFF, value & 0xFF, value & 0xFF, 255))
    return pixels


def decode_nonzlib_mip(reader: BitReader, format_id: int, width: int, height: int, comp_method: int) -> bytes:
    """Return RGBA8888 bytes for one mip level."""
    if width * height > 0x2000 and comp_method not in (
        TEXCOMPMETHOD_UNCOMPRESSED0,
        TEXCOMPMETHOD_UNCOMPRESSED1,
    ):
        raise ValueError(f"non-zlib mip too large ({width}x{height})")

    num_channels = FORMAT_NUM_CHANNELS[format_id]
    chan_size = FORMAT_CHANNEL_SIZES[format_id]
    block = width * height

    if comp_method in (TEXCOMPMETHOD_UNCOMPRESSED0, TEXCOMPMETHOD_UNCOMPRESSED1):
        pixels = _read_uncompressed(reader, width, height, format_id)
    elif comp_method == TEXCOMPMETHOD_HUFFMAN:
        channels = _inflate_huffman(reader, num_channels * block, chan_size)
        if FORMAT_HAS_1BIT_ALPHA[format_id]:
            alpha = _read_alpha_bits(reader, block)
            pixels = _channels_to_rgba(channels, width, height, format_id, alpha)
        else:
            pixels = _channels_to_rgba(channels, width, height, format_id)
    elif comp_method == TEXCOMPMETHOD_HUFFMANPERHCHANNEL:
        channels: list[int] = []
        for _j in range(num_channels):
            channels.extend(_inflate_huffman(reader, block, chan_size))
        if FORMAT_HAS_1BIT_ALPHA[format_id]:
            alpha = _read_alpha_bits(reader, block)
            pixels = _channels_to_rgba(channels, width, height, format_id, alpha)
        else:
            pixels = _channels_to_rgba(channels, width, height, format_id)
    elif comp_method == TEXCOMPMETHOD_RLE:
        channels = _inflate_rle(reader, num_channels * block)
        if FORMAT_HAS_1BIT_ALPHA[format_id]:
            alpha = _read_alpha_bits(reader, block)
            pixels = _channels_to_rgba(channels, width, height, format_id, alpha)
        else:
            pixels = _channels_to_rgba(channels, width, height, format_id)
    elif comp_method == TEXCOMPMETHOD_LOOKUP:
        lookup, num_colours = _build_lookup(reader, FORMAT_BITS_PER_PIXEL[format_id])
        pixels = _lookup_to_rgba(reader, width, height, lookup, num_colours, format_id)
    elif comp_method == TEXCOMPMETHOD_HUFFMANLOOKUP:
        lookup, num_colours = _build_lookup(reader, FORMAT_BITS_PER_PIXEL[format_id])
        indices = _inflate_huffman(reader, block, num_colours)
        pixels = _lookup_buffer_to_rgba(indices, width, height, lookup, format_id)
    elif comp_method == TEXCOMPMETHOD_RLELOOKUP:
        lookup, num_colours = _build_lookup(reader, FORMAT_BITS_PER_PIXEL[format_id])
        indices = _inflate_rle(reader, block)
        pixels = _lookup_buffer_to_rgba(indices, width, height, lookup, format_id)
    elif comp_method == TEXCOMPMETHOD_HUFFMANBLUR:
        blur = reader.read(3)
        channels = _inflate_huffman(reader, num_channels * block, chan_size)
        _blur(channels, width, num_channels * height, blur, chan_size)
        if FORMAT_HAS_1BIT_ALPHA[format_id]:
            alpha = _read_alpha_bits(reader, block)
            pixels = _channels_to_rgba(channels, width, height, format_id, alpha)
        else:
            pixels = _channels_to_rgba(channels, width, height, format_id)
    elif comp_method == TEXCOMPMETHOD_RLEBLUR:
        blur = reader.read(3)
        channels = _inflate_rle(reader, num_channels * block)
        _blur(channels, width, num_channels * height, blur, chan_size)
        if FORMAT_HAS_1BIT_ALPHA[format_id]:
            alpha = _read_alpha_bits(reader, block)
            pixels = _channels_to_rgba(channels, width, height, format_id, alpha)
        else:
            pixels = _channels_to_rgba(channels, width, height, format_id)
    else:
        raise ValueError(f"unsupported compression method {comp_method}")

    out = bytearray(width * height * 4)
    for i, (r, g, b, a) in enumerate(pixels[: width * height]):
        base = i * 4
        out[base : base + 4] = bytes((r, g, b, a))
    return bytes(out)


def rgba_bytes_to_image_size(rgba: bytes, width: int, height: int) -> tuple[int, int]:
    return width, height
