#!/usr/bin/env python3
"""Export public API docs for driftpy modules to JSON.

This script parses source files with ``ast`` (no imports) and emits an API
inventory focused on public classes, methods, functions, and constants.
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SKIP_SUFFIXES = ("_pb2.py", "_pb2_grpc.py")


@dataclass
class ParameterDoc:
    name: str
    kind: str
    annotation: str | None
    required: bool
    default: str | None


@dataclass
class ReturnDoc:
    annotation: str | None


@dataclass
class SymbolDoc:
    name: str
    is_async: bool
    docstring: str | None
    arguments: list[ParameterDoc]
    returns: ReturnDoc


@dataclass
class ConstantDoc:
    name: str


@dataclass
class ClassDoc:
    name: str
    docstring: str | None
    methods: list[SymbolDoc]


@dataclass
class ModuleDoc:
    module: str
    path: str
    docstring: str | None
    constants: list[ConstantDoc]
    functions: list[SymbolDoc]
    classes: list[ClassDoc]


def is_public(name: str) -> bool:
    return not name.startswith("_")


def keep_method(name: str) -> bool:
    return name == "__init__" or is_public(name)


def clean_doc(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def annotation_to_str(annotation: ast.AST | None) -> str | None:
    if annotation is None:
        return None
    return ast.unparse(annotation)


def expr_to_str(expr: ast.AST | None) -> str | None:
    if expr is None:
        return None
    return ast.unparse(expr)


def render_signature(arguments: list[ParameterDoc], returns: ReturnDoc) -> str:
    parts: list[str] = []

    for param in arguments:
        if param.kind == "positional_only_separator":
            parts.append("/")
            continue
        if param.kind == "keyword_only_separator":
            parts.append("*")
            continue

        name = param.name
        if param.kind == "var_positional":
            name = f"*{name}"
        elif param.kind == "var_keyword":
            name = f"**{name}"

        text = name
        if param.annotation:
            text += f": {param.annotation}"
        if param.default is not None:
            text += f" = {param.default}"

        parts.append(text)

    rendered = f"({', '.join(parts)})"
    if returns.annotation:
        return f"{rendered} -> {returns.annotation}"
    return rendered


def extract_parameters(args: ast.arguments) -> list[ParameterDoc]:
    params: list[ParameterDoc] = []

    posonly = list(args.posonlyargs)
    normal = list(args.args)
    defaults = list(args.defaults)

    total_positional = len(posonly) + len(normal)
    defaults_start = total_positional - len(defaults)

    index = 0
    for arg in posonly + normal:
        default = None
        if index >= defaults_start:
            default = expr_to_str(defaults[index - defaults_start])

        params.append(
            ParameterDoc(
                name=arg.arg,
                kind="positional_only" if index < len(posonly) else "positional_or_keyword",
                annotation=annotation_to_str(arg.annotation),
                required=default is None,
                default=default,
            )
        )
        index += 1

    if posonly:
        params.append(
            ParameterDoc(
                name="/",
                kind="positional_only_separator",
                annotation=None,
                required=False,
                default=None,
            )
        )

    if args.vararg:
        params.append(
            ParameterDoc(
                name=args.vararg.arg,
                kind="var_positional",
                annotation=annotation_to_str(args.vararg.annotation),
                required=False,
                default=None,
            )
        )
    elif args.kwonlyargs:
        params.append(
            ParameterDoc(
                name="*",
                kind="keyword_only_separator",
                annotation=None,
                required=False,
                default=None,
            )
        )

    for kw_arg, kw_default in zip(args.kwonlyargs, args.kw_defaults):
        default = expr_to_str(kw_default) if kw_default is not None else None
        params.append(
            ParameterDoc(
                name=kw_arg.arg,
                kind="keyword_only",
                annotation=annotation_to_str(kw_arg.annotation),
                required=kw_default is None,
                default=default,
            )
        )

    if args.kwarg:
        params.append(
            ParameterDoc(
                name=args.kwarg.arg,
                kind="var_keyword",
                annotation=annotation_to_str(args.kwarg.annotation),
                required=False,
                default=None,
            )
        )

    return params


def extract_symbol(node: ast.FunctionDef | ast.AsyncFunctionDef) -> SymbolDoc:
    arguments = extract_parameters(node.args)
    returns = ReturnDoc(annotation=annotation_to_str(node.returns))
    return SymbolDoc(
        name=node.name,
        is_async=isinstance(node, ast.AsyncFunctionDef),
        docstring=clean_doc(ast.get_docstring(node)),
        arguments=arguments,
        returns=returns,
    )


def extract_constant_names(node: ast.Assign | ast.AnnAssign) -> list[str]:
    names: list[str] = []

    targets = node.targets if isinstance(node, ast.Assign) else [node.target]

    for target in targets:
        if isinstance(target, ast.Name) and target.id.isupper():
            names.append(target.id)

    return names


def parse_module(file_path: Path, package_root: Path, module_prefix: str) -> ModuleDoc | None:
    source = file_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    relative = file_path.relative_to(package_root)
    module_parts = list(relative.with_suffix("").parts)
    if module_parts and module_parts[-1] == "__init__":
        module_parts = module_parts[:-1]
    module_name = ".".join([module_prefix] + module_parts) if module_parts else module_prefix

    module_doc = clean_doc(ast.get_docstring(tree))

    constants: dict[str, ConstantDoc] = {}
    functions: list[SymbolDoc] = []
    classes: list[ClassDoc] = []

    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for constant_name in extract_constant_names(node):
                constants.setdefault(constant_name, ConstantDoc(name=constant_name))

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and is_public(node.name):
            functions.append(extract_symbol(node))

        if isinstance(node, ast.ClassDef) and is_public(node.name):
            methods: list[SymbolDoc] = []
            for class_node in node.body:
                if isinstance(class_node, (ast.FunctionDef, ast.AsyncFunctionDef)) and keep_method(
                    class_node.name
                ):
                    methods.append(extract_symbol(class_node))

            classes.append(
                ClassDoc(
                    name=node.name,
                    docstring=clean_doc(ast.get_docstring(node)),
                    methods=sorted(methods, key=lambda x: x.name),
                )
            )

    if not (constants or functions or classes):
        return None

    return ModuleDoc(
        module=module_name,
        path=str(relative),
        docstring=module_doc,
        constants=sorted(constants.values(), key=lambda x: x.name),
        functions=sorted(functions, key=lambda x: x.name),
        classes=sorted(classes, key=lambda x: x.name),
    )


def collect_modules(package_root: Path, module_prefix: str) -> list[ModuleDoc]:
    modules: list[ModuleDoc] = []
    for file_path in sorted(package_root.rglob("*.py")):
        if any(part.startswith(".") for part in file_path.parts):
            continue
        if file_path.name.startswith("test_"):
            continue
        if file_path.name.endswith(SKIP_SUFFIXES):
            continue

        parsed = parse_module(file_path, package_root, module_prefix)
        if parsed is not None:
            modules.append(parsed)

    return sorted(modules, key=lambda x: x.module)


def parameter_to_jsonable(parameter: ParameterDoc) -> dict[str, Any]:
    return {
        "name": parameter.name,
        "kind": parameter.kind,
        "type": parameter.annotation,
        "required": parameter.required,
        "default": parameter.default,
    }


def symbol_to_jsonable(symbol: SymbolDoc) -> dict[str, Any]:
    return {
        "name": symbol.name,
        "is_async": symbol.is_async,
        "docstring": symbol.docstring,
        "arguments": [parameter_to_jsonable(param) for param in symbol.arguments],
        "returns": {
            "type": symbol.returns.annotation,
        },
        "signature": render_signature(symbol.arguments, symbol.returns),
    }


def to_jsonable(modules: list[ModuleDoc]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for module in modules:
        payload.append(
            {
                "module": module.module,
                "path": module.path,
                "docstring": module.docstring,
                "constants": [{"name": constant.name} for constant in module.constants],
                "functions": [symbol_to_jsonable(function) for function in module.functions],
                "classes": [
                    {
                        "name": class_doc.name,
                        "docstring": class_doc.docstring,
                        "methods": [symbol_to_jsonable(method) for method in class_doc.methods],
                    }
                    for class_doc in module.classes
                ],
            }
        )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Export driftpy API docs to JSON")
    parser.add_argument("--package-root", default="src/driftpy", help="Root directory of package source")
    parser.add_argument("--module-prefix", default="driftpy", help="Python module prefix")
    parser.add_argument(
        "--output-json",
        default="docs/generated/api_reference.json",
        help="Output path for JSON export",
    )
    args = parser.parse_args()

    package_root = Path(args.package_root)
    output_json = Path(args.output_json)

    modules = collect_modules(package_root=package_root, module_prefix=args.module_prefix)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(to_jsonable(modules), indent=2), encoding="utf-8")

    print(f"Exported {len(modules)} modules")
    print(f"- JSON: {output_json}")


if __name__ == "__main__":
    main()
