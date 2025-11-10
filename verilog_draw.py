#!/usr/bin/env python3
"""
Minimal Verilog visualiser tailored for the maj_baseline_strict_* netlists.

Parses a structural Verilog module composed of:
  * bused primary inputs (e.g. input wire [8:0] x)
  * wire declarations, optionally with aliases (wire hw = s; wire T0 = 1'b1;)
  * fa instances (module fa(...))
  * assign statements for simple aliases (assign maj = c2_m;)

Generates a Graphviz DOT graph highlighting:
  - Primary inputs (ellipses)
  - Constant taps (gold boxes)
  - Full adders (rounded blue boxes)
  - Module output (double circle)
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple


INST_RE = re.compile(r"\bfa\s+(\w+)\s*\(([^;]+)\);")
PIN_RE = re.compile(r"\.(\w+)\(([^)]+)\)")


def sanitize_net(net: str) -> str:
    return net.strip()


def expand_bus(decl: str, name: str) -> List[str]:
    msb, lsb = [int(x) for x in decl.strip("[]").split(":")]
    if msb >= lsb:
        rng = range(lsb, msb + 1)
    else:
        rng = range(lsb, msb - 1, -1)
    return [f"{name}[{i}]" for i in rng]


def parse_verilog(path: Path, top: str | None = None) -> Tuple[str, Dict[str, Dict], List[Tuple[str, str]], List[str]]:
    code = path.read_text()

    if top:
        pattern = re.compile(rf"module\s+{re.escape(top)}\b")
        m = pattern.search(code)
        module_name = top
    else:
        m = re.search(r"module\s+(\w+)\b", code)
        if not m:
            raise ValueError("No module declaration found")
        module_name = m.group(1)
    if not m:
        raise ValueError(f"Module {top} not found")

    start = m.start()
    header_end = code.find(";", start)
    if header_end == -1:
        raise ValueError("Malformed module header")
    header_text = code[start:header_end]
    body_end = code.find("endmodule", header_end)
    if body_end == -1:
        raise ValueError("Missing endmodule")
    module_body = code[header_end + 1:body_end]

    inputs: List[str] = []
    outputs: List[str] = []
    const_nets: Dict[str, str] = {}
    alias: Dict[str, str] = {}

    # Inputs
    # Parse ports from header
    port_section = header_text[header_text.find("(") + 1:]
    for entry in port_section.split(","):
        entry = entry.strip()
        if not entry:
            continue
        tokens = entry.split()
        if tokens[0] not in {"input", "output"}:
            continue
        direction = tokens[0]
        idx = 1
        if idx < len(tokens) and tokens[idx] == "wire":
            idx += 1
        bus = None
        if idx < len(tokens) and tokens[idx].startswith("["):
            bus = tokens[idx]
            idx += 1
        if idx >= len(tokens):
            continue
        name = tokens[idx].rstrip(")")
        if direction == "input":
            if bus:
                inputs.extend(expand_bus(bus, name))
            else:
                inputs.append(name)
        else:
            outputs.append(name.rstrip(")"))

    # Outputs declared later
    for line in re.findall(r"output\s+wire\s+[^;]+;", module_body):
        names = line.split()[2:]
        for name in "".join(names).split(","):
            name = sanitize_net(name.strip().strip(";"))
            if name and name not in outputs:
                outputs.append(name)

    # Inputs declared later
    for line in re.findall(r"input\s+wire\s+[^;]+;", module_body):
        names = line.split()[2:]
        for name in "".join(names).split(","):
            name = sanitize_net(name.strip().strip(";"))
            if name and name not in inputs:
                inputs.append(name)

    # Wire aliases and constants
    for line in re.findall(r"wire\s+[^;]+;", module_body):
        line = line.strip().strip(";")
        if "=" in line:
            lhs, rhs = line.replace("wire", "", 1).split("=")
            lhs = sanitize_net(lhs.strip())
            rhs = sanitize_net(rhs.strip())
            if rhs in ("1'b0", "1'b1"):
                const_nets[lhs] = rhs
            else:
                alias[lhs] = rhs

    # assign statements (aliases)
    for line in re.findall(r"assign\s+[^;]+;", module_body):
        lhs, rhs = line.replace("assign", "", 1).strip().strip(";").split("=")
        alias[sanitize_net(lhs)] = sanitize_net(rhs)

    # Parse FA instances
    net_drivers: Dict[str, str] = {}
    nodes: Dict[str, Dict] = {}
    edges: List[Tuple[str, str]] = []
    fa_order: List[str] = []

    # Primary inputs as explicit nodes
    for net in inputs:
        node_id = f"PI:{net}"
        nodes[node_id] = {"label": net, "type": "pi"}
        net_drivers[net] = node_id

    # Literal constants available globally
    for literal in ("1'b0", "1'b1"):
        node_id = f"CONST:{literal}"
        nodes.setdefault(node_id, {"label": literal, "type": "literal"})
        net_drivers[literal] = node_id

    def resolve(net: str) -> str:
        net = sanitize_net(net)
        while net in alias:
            net = alias[net]
        return net

    # Constant aliases (e.g., T0 = 1'b1)
    for name, value in const_nets.items():
        value_res = resolve(value)
        node_id = f"CONST_ALIAS:{name}"
        nodes[node_id] = {"label": name, "type": "const_alias", "value": value_res}
        net_drivers[name] = node_id
        src = net_drivers.get(value_res)
        if src:
            edges.append((src, node_id))

    for inst_name, pin_blob in INST_RE.findall(module_body):
        pins = dict((pin, sanitize_net(sig)) for pin, sig in PIN_RE.findall(pin_blob))
        node_id = inst_name
        node_type = "fa_comp" if "_th_" in inst_name else "fa"
        nodes[node_id] = {
            "label": inst_name,
            "type": node_type,
            "a": pins.get("a"),
            "b": pins.get("b"),
            "cin": pins.get("cin"),
            "sum": pins.get("sum"),
            "cout": pins.get("cout"),
        }
        fa_order.append(node_id)
        for out_pin in ("sum", "cout"):
            net = resolve(pins[out_pin])
            net_drivers[net] = node_id

    def add_edge(src_net: str, dst_node: str) -> None:
        src = resolve(src_net)
        driver = net_drivers.get(src)
        if driver is None:
            # treat as PI if un-driven
            driver = f"PI:{src}"
            nodes.setdefault(driver, {"label": src, "type": "pi"})
            net_drivers[src] = driver
        edges.append((driver, dst_node))

    for node_id, data in list(nodes.items()):
        if data.get("type") != "fa":
            continue
        for pin in ("a", "b", "cin"):
            net = data[pin]
            add_edge(net, node_id)

    # Output nodes
    for out in outputs:
        base = resolve(out)
        driver = net_drivers.get(base)
        out_node = f"PO:{out}"
        nodes[out_node] = {"label": out, "type": "po"}
        if driver is None:
            driver = f"PI:{base}"
            nodes.setdefault(driver, {"label": base, "type": "pi"})
        edges.append((driver, out_node))

    return module_name, nodes, edges, fa_order


def emit_dot(module_name: str, nodes: Dict[str, Dict], edges: List[Tuple[str, str]], fa_order: List[str]) -> str:
    lines = [
        f'digraph "{module_name}" {{',
        "  rankdir=LR;",
        "  nodesep=0.4;",
        "  ranksep=0.8;",
        '  labelloc="t";',
        '  label="";',
    ]

    fa_label_map = {node_id: f"FA{i}" for i, node_id in enumerate(fa_order, start=1)}

    for node_id, info in nodes.items():
        label = info["label"]
        if info["type"] == "fa":
            label = fa_label_map.get(node_id, label)
            lines.append(f'  "{node_id}" [shape=box, style="rounded,filled", fillcolor="#d6eaf8", label="{label}"];')
        elif info["type"] == "fa_comp":
            label = fa_label_map.get(node_id, label)
            lines.append(f'  "{node_id}" [shape=box, style="rounded,filled", fillcolor="#aed6f1", label="{label}"];')
        elif info["type"] == "pi":
            lines.append(f'  "{node_id}" [shape=ellipse, style="filled", fillcolor="#e6f2ff", label="{label}"];')
        elif info["type"] == "po":
            lines.append(f'  "{node_id}" [shape=doublecircle, style="filled", fillcolor="#d5f5e3", label="{label}"];')
        elif info["type"] == "literal":
            lines.append(f'  "{node_id}" [shape=box, style="filled", fillcolor="#fdebd0", label="{label}"];')
        elif info["type"] == "const_alias":
            value = info.get("value", "")
            lines.append(f'  "{node_id}" [shape=hexagon, style="filled", fillcolor="#f9e79f", label="{label}"];')
            if value:
                lines.append(f'  "{node_id}" [xlabel="{value}"];')
        else:
            lines.append(f'  "{node_id}" [label="{label}"];')

    for src, dst in edges:
        lines.append(f'  "{src}" -> "{dst}";')

    lines.append("}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render simple structural Verilog with fa instances.")
    parser.add_argument("verilog", type=Path)
    parser.add_argument("--top", type=str)
    parser.add_argument("--out-dot", type=Path)
    parser.add_argument("--out-img", type=Path)
    parser.add_argument("--dot-bin", type=str, default="dot")
    args = parser.parse_args()

    module_name, nodes, edges, fa_order = parse_verilog(args.verilog, args.top)
    dot_text = emit_dot(module_name, nodes, edges, fa_order)
    out_dot = args.out_dot or args.verilog.with_suffix(".raw.dot")
    out_dot.write_text(dot_text)
    print(f"Wrote DOT: {out_dot}")

    if args.out_img:
        args.out_img.parent.mkdir(parents=True, exist_ok=True)
        import subprocess

        subprocess.check_call([args.dot_bin, f"-T{args.out_img.suffix.lstrip('.')}", str(out_dot), "-o", str(args.out_img)])
        print(f"Wrote image: {args.out_img}")


if __name__ == "__main__":
    main()
