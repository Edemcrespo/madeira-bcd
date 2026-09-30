#!/usr/bin/env python3
"""Give the D3D10/11 (DXBC) vertex fetch D3D's out-of-range rule.

airconv pulls vertex attributes in the shader: base address + stride * index
+ element offset, straight into device memory. The table entry carries the
binding's valid length, but only the D3D9 path (dxso_compile.cpp) consults it;
the DXBC path never did. D3D10 defines a fetch past the end of the bound
vertex buffer as zero; Metal has no robustness, so such a fetch reads whatever
memory follows -- vertices flung across the screen. 32-bit Crysis draws its
trees and branches as long streaks with D3D10 and correctly with -dx9 (owner,
2026-09-30, builds 249-256), whose path clamps; the short-constant-buffer and
16-bit index realignment fixes did not change the picture.

A DXBC attribute whose byte offset lies at or past the binding's length now
reads (0,0,0,0), through the null-binding branch pull_vec4_from_addr already
has. MADEIRA_VFETCH_BOUNDS=0 (read when a shader is converted) turns it off.
The shader cache version is bumped so shaders converted before this are not
reused (the committed 64-bit PE d3d11.dll keeps its own version).

Idempotent; fails by name if an anchor moves. Run from the repository root.
"""
import pathlib
import sys

ROOT = pathlib.Path("research/dxmt/src")
MARKER = "madeira-bcd: vertex fetch bounds"


def edit(rel, pairs):
    path = ROOT / rel
    s = path.read_text()
    if MARKER in s:
        print(f"{rel}: already patched")
        return
    for old, new in pairs:
        if s.count(old) != 1:
            sys.exit(f"patch-dxmt-vfetch-bounds: anchor found {s.count(old)} times (want 1) in {rel}:\n{old}")
        s = s.replace(old, new)
    if MARKER not in s:
        sys.exit(f"patch-dxmt-vfetch-bounds: marker missing after editing {rel}")
    path.write_text(s)
    print(f"{rel}: patched")


edit("airconv/dxbc_converter_basicblock.cpp", [
    ("#include <stack>\n", "#include <stack>\n#include <cstdio>\n#include <cstdlib>\n"),
    ("""    auto base_addr = builder.CreateExtractValue(vertex_buffer_entry, {0});
    auto stride = builder.CreateExtractValue(vertex_buffer_entry, {1});
    auto byte_offset = builder.CreateAdd(
      builder.CreateMul(stride, index),
      builder.getInt32(element_info.aligned_byte_offset)
    );
""",
     """    auto base_addr = builder.CreateExtractValue(vertex_buffer_entry, {0});
    auto stride = builder.CreateExtractValue(vertex_buffer_entry, {1});
    auto byte_offset = builder.CreateAdd(
      builder.CreateMul(stride, index),
      builder.getInt32(element_info.aligned_byte_offset)
    );
    /* madeira-bcd: vertex fetch bounds (tools/patch-dxmt-vfetch-bounds.py) --
     * D3D10 reads zero past the end of the binding; route such a fetch to the
     * null-binding branch of pull_vec4_from_addr instead of reading on. */
    static int madeira_vfetch_bounds = -1;
    if (madeira_vfetch_bounds < 0) {
      const char *e = getenv("MADEIRA_VFETCH_BOUNDS");
      madeira_vfetch_bounds = !(e && e[0] == '0');
      fprintf(stderr, "[vfetch-bounds] madeira-bcd DXBC vertex fetch bounds %s\\n",
              madeira_vfetch_bounds ? "on" : "off (MADEIRA_VFETCH_BOUNDS=0)");
    }
    if (madeira_vfetch_bounds) {
      auto vb_length = builder.CreateExtractValue(vertex_buffer_entry, {2});
      base_addr = builder.CreateSelect(
        builder.CreateICmpULT(byte_offset, vb_length), base_addr,
        llvm::ConstantPointerNull::get(llvm::cast<llvm::PointerType>(base_addr->getType()))
      );
    }
"""),
])

edit("dxmt/dxmt_shader_cache.hpp", [
    ("constexpr int kDXMTShaderCacheVersion = 15;",
     "constexpr int kDXMTShaderCacheVersion = 16; /* madeira-bcd: vertex fetch bounds */"),
])
