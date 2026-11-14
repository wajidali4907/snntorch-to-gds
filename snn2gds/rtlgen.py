"""Emit Verilog for an exported network (weights as constants) plus a self-checking testbench.

Architecture (P = N_in, one time step per clock per layer):

  in_valid/in_spikes -> [layer0: synapse sum + N lif] -> [layer1] -> ... -> spike counters
  Each layer registers its membrane; out_valid is in_valid delayed one cycle.

Outputs go to runs/<name>/rtl/.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import numpy as np

from .config import Config

RTL_LIB = Path(__file__).resolve().parent.parent / "rtl"


def clog2(x: int) -> int:
    return max(1, math.ceil(math.log2(x))) if x > 1 else 1


def _synapse_module(name: str, W: np.ndarray, iw: int) -> str:
    n_out, n_in = W.shape
    lines = [f"// synapse sum for {n_out} neurons x {n_in} inputs, weights as constants",
             f"module {name} (",
             f"    input  wire [{n_in - 1}:0] s,",
             f"    output wire [{n_out * iw - 1}:0] I_flat",
             ");"]
    for j in range(n_out):
        terms = []
        for i in np.nonzero(W[j])[0]:
            w = int(W[j, i])
            sign = "+" if w > 0 else "-"
            terms.append(f"{sign} (s[{i}] ? {iw}'sd{abs(w)} : {iw}'sd0)")
        expr = " ".join(terms).lstrip("+ ") if terms else f"{iw}'sd0"
        if expr.startswith("- "):
            expr = f"{iw}'sd0 " + expr
        lines.append(f"    wire signed [{iw - 1}:0] I{j} = {expr};")
        lines.append(f"    assign I_flat[{(j + 1) * iw - 1}:{j * iw}] = I{j};")
    lines.append("endmodule\n")
    return "\n".join(lines)


def _layer_module(name: str, syn: str, n_in: int, n_out: int, iw: int, ex: dict) -> str:
    return f"""// one SNN layer: synapse block + {n_out} LIF neurons
module {name} (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              clear,
    input  wire              in_valid,
    input  wire [{n_in - 1}:0]      in_spikes,
    output reg               out_valid,
    output wire [{n_out - 1}:0]      out_spikes
);
    wire [{n_out * iw - 1}:0] I_flat;
    {syn} u_syn (.s(in_spikes), .I_flat(I_flat));
    genvar j;
    generate
        for (j = 0; j < {n_out}; j = j + 1) begin : g_n
            snn_lif #(.BU({ex['bu']}), .IW({iw}), .K({ex['k']}), .THETA({ex['theta_int']})) u_n (
                .clk(clk), .rst_n(rst_n), .clear(clear), .en(in_valid),
                .I(I_flat[(j+1)*{iw}-1 -: {iw}]), .spike(out_spikes[j]));
        end
    endgenerate
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)     out_valid <= 1'b0;
        else if (clear) out_valid <= 1'b0;
        else            out_valid <= in_valid;
    end
endmodule
"""


def _top_module(top: str, sizes: list[int], T: int) -> str:
    L = len(sizes) - 1
    n_in, n_out = sizes[0], sizes[-1]
    cw = clog2(T + 1)
    s = [f"""// snn2gds top: {' -> '.join(map(str, sizes))}, T = {T}
module {top} (
    input  wire               clk,
    input  wire               rst_n,
    input  wire               clear,       // synchronous: zero membranes + counters
    input  wire               in_valid,    // one time step of input spikes
    input  wire [{n_in - 1}:0]       in_spikes,
    output wire               out_valid,
    output wire [{n_out - 1}:0]       out_spikes,
    output reg  [{n_out * cw - 1}:0] out_counts,  // {cw} bits per class
    output wire               done         // T output steps seen since clear
);"""]
    s.append(f"    wire v0 = in_valid;\n    wire [{n_in - 1}:0] s0 = in_spikes;")
    for l in range(L):
        s.append(f"    wire v{l + 1};\n    wire [{sizes[l + 1] - 1}:0] s{l + 1};")
        s.append(f"    {top}_layer{l} u_l{l} (.clk(clk), .rst_n(rst_n), .clear(clear), "
                 f".in_valid(v{l}), .in_spikes(s{l}), .out_valid(v{l + 1}), .out_spikes(s{l + 1}));")
    s.append(f"""    assign out_valid  = v{L};
    assign out_spikes = s{L};
    reg [{cw - 1}:0] steps;
    assign done = (steps == {cw}'d{T});
    integer c;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_counts <= 0;
            steps <= 0;
        end else if (clear) begin
            out_counts <= 0;
            steps <= 0;
        end else if (out_valid) begin
            steps <= steps + 1'b1;
            for (c = 0; c < {n_out}; c = c + 1)
                out_counts[c*{cw} +: {cw}] <= out_counts[c*{cw} +: {cw}] + out_spikes[c];
        end
    end
endmodule
""")
    return "\n".join(s)


def _testbench(top: str, sizes: list[int], T: int, nv: int) -> str:
    L = len(sizes) - 1
    n_in, n_out = sizes[0], sizes[-1]
    cw = clog2(T + 1)
    decl = "\n".join(f"    reg [{sizes[l + 1] - 1}:0] exp{l} [0:{nv * T - 1}];\n"
                     f"    integer ptr{l} = 0, err{l} = 0;" for l in range(L))
    load = "\n".join(f'        $readmemh({{dir, "/expected_l{l}.hex"}}, exp{l});' for l in range(L))
    checks = "\n".join(f"""        if (dut.v{l + 1}) begin
            if (dut.s{l + 1} !== exp{l}[ptr{l}]) begin
                if (err{l} < 10) $display("MISMATCH layer{l} step %0d: got %h exp %h", ptr{l}, dut.s{l + 1}, exp{l}[ptr{l}]);
                err{l} = err{l} + 1;
            end
            ptr{l} = ptr{l} + 1;
        end""" for l in range(L))
    summary = " + ".join(f"err{l}" for l in range(L))
    per_layer = "\n".join(f'        $display("layer{l}: %0d / %0d steps mismatched", err{l}, ptr{l});' for l in range(L))
    return f"""`timescale 1ns/1ps
// Self-checking testbench: replays {nv} samples x {T} steps, compares every spike of every layer.
module tb;
    reg clk = 0, rst_n = 0, clear = 0, in_valid = 0;
    reg [{n_in - 1}:0] in_spikes = 0;
    wire out_valid, done;
    wire [{n_out - 1}:0] out_spikes;
    wire [{n_out * cw - 1}:0] out_counts;
    {top} dut (.clk(clk), .rst_n(rst_n), .clear(clear), .in_valid(in_valid), .in_spikes(in_spikes),
              .out_valid(out_valid), .out_spikes(out_spikes), .out_counts(out_counts), .done(done));
    always #5 clk = ~clk;

    reg [{n_in - 1}:0] stim [0:{nv * T - 1}];
{decl}
    reg [1023:0] dir;
    integer n, t, fd;

    always @(posedge clk) begin
{checks}
    end

    initial begin
        if (!$value$plusargs("REF=%s", dir)) dir = "ref";
        $readmemh({{dir, "/stim.hex"}}, stim);
{load}
        fd = $fopen("rtl_counts.txt", "w");
        repeat (2) @(posedge clk);
        rst_n <= 1;
        for (n = 0; n < {nv}; n = n + 1) begin
            @(posedge clk); clear <= 1;
            @(posedge clk); clear <= 0;
            for (t = 0; t < {T}; t = t + 1) begin
                in_valid <= 1; in_spikes <= stim[n*{T} + t];
                @(posedge clk);
            end
            in_valid <= 0; in_spikes <= 0;
            while (!done) @(posedge clk);
            @(posedge clk);
            for (t = 0; t < {n_out}; t = t + 1) $fwrite(fd, "%0d ", out_counts[t*{cw} +: {cw}]);
            $fwrite(fd, "\\n");
        end
        $fclose(fd);
{per_layer}
        if ({summary} == 0) $display("SPIKE_MATCH PASS: {nv} samples, all layers, every step");
        else                $display("SPIKE_MATCH FAIL: %0d mismatched steps", {summary});
        $finish;
    end
endmodule
"""


def generate(cfg: Config) -> Path:
    out = cfg.run_dir
    ex = json.loads((out / "export.json").read_text())
    Ws = [np.array(l["W"], dtype=np.int64) for l in ex["layers"]]
    sizes = [Ws[0].shape[1]] + [W.shape[0] for W in Ws]
    top = "snn_top"
    rtl = out / "rtl"
    rtl.mkdir(parents=True, exist_ok=True)
    files = []
    for l, W in enumerate(Ws):
        # widest possible sum: all positive (or all negative) weights firing
        span = max(int(np.clip(W, 0, None).sum(1).max()), int((-np.clip(W, None, 0)).sum(1).max()), 1)
        iw = clog2(span + 1) + 1
        syn = f"{top}_syn{l}"
        f = rtl / f"{top}_layer{l}.v"
        f.write_text(_synapse_module(syn, W, iw) + "\n" +
                     _layer_module(f"{top}_layer{l}", syn, sizes[l], sizes[l + 1], iw, ex))
        files.append(f)
    (rtl / f"{top}.v").write_text(_top_module(top, sizes, ex["T"]))
    shutil.copy(RTL_LIB / "snn_lif.v", rtl / "snn_lif.v")
    nv = int(json.loads((out / "metrics_export.json").read_text())["n_verify"])
    (rtl / "tb.v").write_text(_testbench(top, sizes, ex["T"], nv))
    print(f"wrote RTL to {rtl}")
    return rtl
