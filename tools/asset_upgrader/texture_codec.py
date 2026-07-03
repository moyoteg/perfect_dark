"""Decode and encode Perfect Dark N64 texture .bin files for the PC port mod loader.

Implements the zlib (paletted) path used by most in-game textures. Non-zlib
textures are decoded when possible; otherwise the caller receives a clear error.
"""

from __future__ import annotations

import math
import zlib
from dataclasses import dataclass, field
from typing import Iterable

from PIL import Image

# Mirror src/include/constants.h TEXFORMAT_* values.
TEXFORMAT_RGBA32 = 0x00
TEXFORMAT_RGBA16 = 0x01
TEXFORMAT_RGB24 = 0x02
TEXFORMAT_RGB15 = 0x03
TEXFORMAT_IA16 = 0x04
TEXFORMAT_IA8 = 0x05
TEXFORMAT_IA4 = 0x06
TEXFORMAT_I8 = 0x07
TEXFORMAT_I4 = 0x08
TEXFORMAT_RGBA16_CI8 = 0x09
TEXFORMAT_RGBA16_CI4 = 0x0A
TEXFORMAT_IA16_CI8 = 0x0B
TEXFORMAT_IA16_CI4 = 0x0C

CI_FORMATS = {
    TEXFORMAT_RGBA16_CI8,
    TEXFORMAT_RGBA16_CI4,
    TEXFORMAT_IA16_CI8,
    TEXFORMAT_IA16_CI4,
}

FORMAT_NAMES = {
    TEXFORMAT_RGBA32: "rgba32",
    TEXFORMAT_RGBA16: "rgba16",
    TEXFORMAT_RGB24: "rgb24",
    TEXFORMAT_RGB15: "rgb15",
    TEXFORMAT_IA16: "ia16",
    TEXFORMAT_IA8: "ia8",
    TEXFORMAT_IA4: "ia4",
    TEXFORMAT_I8: "i8",
    TEXFORMAT_I4: "i4",
    TEXFORMAT_RGBA16_CI8: "rgba16_ci8",
    TEXFORMAT_RGBA16_CI4: "rgba16_ci4",
    TEXFORMAT_IA16_CI8: "ia16_ci8",
    TEXFORMAT_IA16_CI4: "ia16_ci4",
}


class BitReader:
    """Bitstream reader matching texReadBits() in src/game/texreset.c."""

    def __init__(self, data: bytes, bit_offset: int = 0) -> None:
        self._data = data
        self._byte = bit_offset // 8
        self._accum = 0
        self._num_bits = bit_offset % 8
        if self._num_bits:
            self._accum = data[self._byte] & ((1 << self._num_bits) - 1)
            self._byte += 1

    @property
    def byte_offset(self) -> int:
        """Current byte index (may include pending fractional bits)."""
        return self._byte

    def read(self, num_bits: int) -> int:
        while self._num_bits < num_bits:
            if self._byte >= len(self._data):
                self._accum <<= 8
            else:
                self._accum = (self._accum << 8) | self._data[self._byte]
                self._byte += 1
            self._num_bits += 8

        self._num_bits -= num_bits
        mask = (1 << num_bits) - 1
        return (self._accum >> self._num_bits) & mask


class BitWriter:
    """Bitstream writer; inverse of BitReader."""

    def __init__(self) -> None:
        self._accum = 0
        self._num_bits = 0
        self._out = bytearray()

    def write(self, value: int, num_bits: int) -> None:
        self._accum = (self._accum << num_bits) | (value & ((1 << num_bits) - 1))
        self._num_bits += num_bits
        while self._num_bits >= 8:
            self._num_bits -= 8
            self._out.append((self._accum >> self._num_bits) & 0xFF)

    def flush(self) -> bytes:
        if self._num_bits:
            self._out.append((self._accum << (8 - self._num_bits)) & 0xFF)
            self._accum = 0
            self._num_bits = 0
        return bytes(self._out)


@dataclass
class TextureMip:
    width: int
    height: int
    indices: bytes = b""
    rgba: bytes = b""
    comp_method: int = 0


@dataclass
class TextureAsset:
    texture_id: str
    source_path: str
    header_byte: int
    format_id: int
    palette: list[int]
    mips: list[TextureMip] = field(default_factory=list)
    has_lod_data: bool = False
    num_lods: int = 1
    is_zlib: bool = True
    source_was_nonzlib: bool = False

    @property
    def width(self) -> int:
        return self.mips[0].width if self.mips else 0

    @property
    def height(self) -> int:
        return self.mips[0].height if self.mips else 0

    @property
    def format_name(self) -> str:
        return FORMAT_NAMES.get(self.format_id, f"unknown_{self.format_id:02x}")


def rarezip_compress(raw: bytes) -> bytes:
    """Compress with PD's 0x1173 rarezip header."""
    co = zlib.compressobj(level=9, wbits=-15)
    payload = co.compress(raw) + co.flush()
    return b"\x11\x73" + len(raw).to_bytes(3, "big") + payload


def rarezip_decompress(src: bytes) -> bytes:
    """Decompress 0x1173 (PD) or 0x1172 (GE-style) rarezip blocks."""
    out, _ = rarezip_decompress_with_consumed(src)
    return out


def rarezip_decompress_with_consumed(src: bytes) -> tuple[bytes, int]:
    if len(src) < 3:
        raise ValueError("rarezip block too small")

    if src[0:2] == b"\x11\x73":
        if len(src) < 5:
            raise ValueError("truncated 0x1173 header")
        out_len = int.from_bytes(src[2:5], "big")
        dec = zlib.decompressobj(wbits=-15)
        payload = src[5:]
        out = dec.decompress(payload)
        if len(out) < out_len:
            out += dec.flush()
        consumed = 5 + (len(payload) - len(dec.unused_data))
        return out[:out_len], consumed

    if src[0:2] == b"\x11\x72":
        dec = zlib.decompressobj(wbits=-15)
        payload = src[2:]
        out = dec.decompress(payload) + dec.flush()
        consumed = 2 + (len(payload) - len(dec.unused_data))
        return out, consumed

    raise ValueError(f"expected 0x1172/0x1173 rarezip block, got {src[0:2].hex()}")


def palette_entry_to_rgba(entry: int, format_id: int) -> tuple[int, int, int, int]:
    if format_id in (TEXFORMAT_IA16_CI8, TEXFORMAT_IA16_CI4):
        intensity = (entry >> 8) & 0xFF
        alpha = entry & 0xFF
        return intensity, intensity, intensity, alpha

    r = ((entry >> 11) & 0x1F) * 255 // 31
    g = ((entry >> 6) & 0x1F) * 255 // 31
    b = ((entry >> 1) & 0x1F) * 255 // 31
    a = 255 if (entry & 1) else 0
    return r, g, b, a


def rgba_to_palette_entry(r: int, g: int, b: int, a: int, format_id: int) -> int:
    if format_id in (TEXFORMAT_IA16_CI8, TEXFORMAT_IA16_CI4):
        intensity = max(0, min(255, (r + g + b) // 3))
        return (intensity << 8) | max(0, min(255, a))
    r5 = max(0, min(31, round(r * 31 / 255)))
    g5 = max(0, min(31, round(g * 31 / 255)))
    b5 = max(0, min(31, round(b * 31 / 255)))
    a1 = 1 if a >= 128 else 0
    return (r5 << 11) | (g5 << 6) | (b5 << 1) | a1


def indices_to_image(asset: TextureAsset, mip_index: int = 0) -> Image.Image:
    mip = asset.mips[mip_index]
    if mip.rgba:
        return Image.frombytes("RGBA", (mip.width, mip.height), mip.rgba)
    img = Image.new("RGBA", (mip.width, mip.height))
    px = img.load()
    indices = mip.indices
    for y in range(mip.height):
        row_base = y * mip.width
        for x in range(mip.width):
            idx = indices[row_base + x]
            px[x, y] = palette_entry_to_rgba(asset.palette[idx], asset.format_id)
    return img


def image_to_indices(image: Image.Image, asset: TextureAsset) -> tuple[list[int], list[int]]:
    """Quantize an RGBA image back into palette entries and per-pixel indices."""
    image = image.convert("RGBA")
    max_colours = len(asset.palette)
    if max_colours < 2:
        max_colours = 256

    quant = image.quantize(
        colors=max_colours,
        method=Image.Quantize.FASTOCTREE,
        dither=Image.Dither.NONE,
    )
    palette_img = quant.convert("RGBA")
    px = palette_img.load()

    unique: dict[tuple[int, int, int, int], int] = {}
    palette: list[int] = []
    indices: list[int] = []

    for y in range(image.height):
        for x in range(image.width):
            rgba = px[x, y]
            if rgba not in unique:
                if len(palette) >= max_colours:
                    # Reuse nearest palette colour when over budget.
                    idx = _nearest_palette_index(rgba, palette, asset.format_id)
                else:
                    entry = rgba_to_palette_entry(*rgba, asset.format_id)
                    unique[rgba] = len(palette)
                    palette.append(entry)
                    idx = len(palette) - 1
            else:
                idx = unique[rgba]
            indices.append(idx)

    if len(palette) < max_colours:
        # Pad palette to original size so downstream metadata stays stable.
        while len(palette) < max_colours:
            palette.append(palette[-1] if palette else 0)

    return palette, indices


def _nearest_palette_index(rgba: tuple[int, int, int, int], palette: list[int], format_id: int) -> int:
    best = 0
    best_dist = 1 << 30
    for i, entry in enumerate(palette):
        pr, pg, pb, pa = palette_entry_to_rgba(entry, format_id)
        dist = (pr - rgba[0]) ** 2 + (pg - rgba[1]) ** 2 + (pb - rgba[2]) ** 2 + (pa - rgba[3]) ** 2
        if dist < best_dist:
            best_dist = dist
            best = i
    return best


def decode_texture(texture_id: str, source_path: str, data: bytes) -> TextureAsset:
    if len(data) < 2:
        raise ValueError(f"{texture_id}: texture blob too small")

    header = data[0]
    has_lod_data = bool(header & 0x80)
    is_zlib = bool(header & 0x40)
    num_lods = header & 0x3F
    if num_lods > 5:
        num_lods = 5

    if is_zlib:
        return _decode_zlib_texture(texture_id, source_path, data, header, has_lod_data, num_lods)
    return _decode_nonzlib_texture(texture_id, source_path, data, header, has_lod_data, num_lods)


def _decode_zlib_texture(
    texture_id: str,
    source_path: str,
    data: bytes,
    header: int,
    has_lod_data: bool,
    num_lods: int,
) -> TextureAsset:
    reader = BitReader(data, bit_offset=8)
    format_id = reader.read(8)
    num_colours = reader.read(8) + 1
    palette = [reader.read(16) for _ in range(num_colours)]

    num_images = num_lods if has_lod_data and num_lods else 1
    mips: list[TextureMip] = []

    for _ in range(num_images):
        width = reader.read(8)
        height = reader.read(8)
        if reader._num_bits:
            reader._byte += 1
            reader._accum = 0
            reader._num_bits = 0
        zip_start = reader._byte
        if zip_start >= len(data) or data[zip_start : zip_start + 2] not in (b"\x11\x73", b"\x11\x72"):
            raise ValueError(
                f"{texture_id}: missing rarezip block at offset {zip_start} "
                f"(magic={data[zip_start:zip_start+2].hex() if zip_start < len(data) else 'eof'})"
            )
        raw, consumed = rarezip_decompress_with_consumed(data[zip_start:])
        if format_id in CI_FORMATS:
            if format_id in (TEXFORMAT_RGBA16_CI8, TEXFORMAT_IA16_CI8):
                indices = raw[: width * height]
            else:
                indices = _ci4_raw_to_indices(raw, width, height)
        else:
            raise ValueError(
                f"{texture_id}: unsupported zlib format {FORMAT_NAMES.get(format_id, format_id)}"
            )
        mips.append(TextureMip(width=width, height=height, indices=bytes(indices)))
        reader = BitReader(data, bit_offset=(zip_start + consumed) * 8)

    return TextureAsset(
        texture_id=texture_id,
        source_path=source_path,
        header_byte=header,
        format_id=format_id,
        palette=palette,
        mips=mips,
        has_lod_data=has_lod_data,
        num_lods=num_lods,
        is_zlib=True,
    )


def _decode_nonzlib_texture(
    texture_id: str,
    source_path: str,
    data: bytes,
    header: int,
    has_lod_data: bool,
    num_lods: int,
) -> TextureAsset:
    from tools.asset_upgrader.texture_nonzlib import decode_nonzlib_mip

    reader = BitReader(data, bit_offset=8)
    num_images = num_lods if has_lod_data and num_lods else 1
    mips: list[TextureMip] = []
    format_id = 0

    for _ in range(num_images):
        format_id = reader.read(4)
        width = reader.read(8)
        height = reader.read(8)
        comp_method = reader.read(4)
        rgba = decode_nonzlib_mip(reader, format_id, width, height, comp_method)
        mips.append(
            TextureMip(
                width=width,
                height=height,
                rgba=rgba,
                comp_method=comp_method,
            )
        )
        # Match texInflateNonZlib post-mip bitstream alignment.
        if reader._num_bits == 0:
            reader._byte += 1
        else:
            reader._accum = 0
            reader._num_bits = 0

    return TextureAsset(
        texture_id=texture_id,
        source_path=source_path,
        header_byte=header,
        format_id=format_id,
        palette=[],
        mips=mips,
        has_lod_data=has_lod_data,
        num_lods=num_lods,
        is_zlib=False,
        source_was_nonzlib=True,
    )


def _ci4_raw_to_indices(raw: bytes, width: int, height: int) -> list[int]:
    out: list[int] = []
    pos = 0
    for _ in range(height):
        for x in range(0, width, 2):
            byte = raw[pos]
            pos += 1
            out.append((byte >> 4) & 0x0F)
            if x + 1 < width:
                out.append(byte & 0x0F)
    return out


def _indices_to_ci4_raw(indices: Iterable[int], width: int, height: int) -> bytes:
    out = bytearray()
    flat = list(indices)
    idx = 0
    for _ in range(height):
        for x in range(0, width, 2):
            hi = flat[idx]
            idx += 1
            lo = flat[idx] if x + 1 < width else 0
            if x + 1 < width:
                idx += 1
            out.append(((hi & 0x0F) << 4) | (lo & 0x0F))
    return bytes(out)


def _encode_zlib_ci(asset: TextureAsset, palette: list[int], indices: list[int]) -> bytes:
    """Encode upgraded texture as zlib paletted CI (PC-port friendly)."""
    format_id = TEXFORMAT_RGBA16_CI8 if len(palette) > 16 else TEXFORMAT_RGBA16_CI4
    header_byte = (asset.header_byte & 0xBF) | 0x40
    if asset.num_lods > 1 and not asset.has_lod_data:
        header_byte = (header_byte & 0xC0) | (asset.num_lods & 0x3F)

    writer = BitWriter()
    writer.write(format_id, 8)
    writer.write(len(palette) - 1, 8)
    for entry in palette:
        writer.write(entry, 16)

    mip = asset.mips[0]
    if format_id == TEXFORMAT_RGBA16_CI8:
        raw = bytes(indices[: mip.width * mip.height])
    else:
        raw = _indices_to_ci4_raw(indices, mip.width, mip.height)

    block = BitWriter()
    block.write(mip.width, 8)
    block.write(mip.height, 8)

    out = bytes([header_byte]) + writer.flush() + block.flush() + rarezip_compress(raw)
    if len(out) > 4096:
        raise ValueError(
            f"{asset.texture_id}: encoded size {len(out)} exceeds PC mod loader limit (4096 bytes)"
        )
    return out


def encode_texture(asset: TextureAsset, palette: list[int] | None = None, indices: list[int] | None = None) -> bytes:
    """Re-encode a texture, optionally with new palette/indices for mip 0."""
    if asset.source_was_nonzlib or not asset.is_zlib or asset.format_id not in CI_FORMATS:
        if palette is None or indices is None:
            raise ValueError(f"{asset.texture_id}: non-zlib textures must be encoded via png_to_asset()")
        return _encode_zlib_ci(asset, palette, indices)

    palette = palette or asset.palette
    writer = BitWriter()
    writer.write(asset.format_id, 8)
    writer.write(len(palette) - 1, 8)
    for entry in palette:
        writer.write(entry, 16)

    payload = bytes(writer.flush())
    header = bytes([asset.header_byte])
    chunks = [header, payload]

    for mip_index, mip in enumerate(asset.mips):
        mip_indices = indices if mip_index == 0 and indices is not None else list(mip.indices)
        if asset.format_id in (TEXFORMAT_RGBA16_CI8, TEXFORMAT_IA16_CI8):
            raw = bytes(mip_indices[: mip.width * mip.height])
        else:
            raw = _indices_to_ci4_raw(mip_indices, mip.width, mip.height)

        block = BitWriter()
        block.write(mip.width, 8)
        block.write(mip.height, 8)
        block_bytes = block.flush()
        chunks.append(block_bytes)
        chunks.append(rarezip_compress(raw))

    out = b"".join(chunks)
    if len(out) > 4096:
        raise ValueError(
            f"{asset.texture_id}: encoded size {len(out)} exceeds PC mod loader limit (4096 bytes)"
        )
    return out


def asset_to_png(asset: TextureAsset, out_path: str) -> None:
    img = indices_to_image(asset)
    img.save(out_path)


def png_to_asset(asset: TextureAsset, png_path: str) -> bytes:
    image = Image.open(png_path).convert("RGBA")
    if image.size != (asset.width, asset.height):
        image = image.resize((asset.width, asset.height), Image.Resampling.LANCZOS)

    if asset.source_was_nonzlib or not asset.is_zlib:
        unique_colours = len({px for px in image.getdata()})
        max_colours = 256 if unique_colours > 16 else 16
        quant_asset = TextureAsset(
            texture_id=asset.texture_id,
            source_path=asset.source_path,
            header_byte=asset.header_byte,
            format_id=TEXFORMAT_RGBA16_CI8,
            palette=[0] * max_colours,
            mips=asset.mips,
            has_lod_data=asset.has_lod_data,
            num_lods=asset.num_lods,
            is_zlib=True,
            source_was_nonzlib=True,
        )
        palette, indices = image_to_indices(image, quant_asset)
        return _encode_zlib_ci(asset, palette, indices)

    palette, indices = image_to_indices(image, asset)
    return encode_texture(asset, palette=palette, indices=indices)


def tex_get_bit_size(num_colours: int) -> int:
    if num_colours <= 1:
        return 1
    return int(math.ceil(math.log2(num_colours)))
