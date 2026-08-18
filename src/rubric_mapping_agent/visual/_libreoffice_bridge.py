"""Small pyuno bridge used by the visual inspection backends.

This module is executed with LibreOffice's bundled Python, not the project's
Python environment. Keep it dependency-free apart from ``uno`` and the Python
standard library.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import uno
from com.sun.star.beans import PropertyValue


def _property(name, value):
    prop = PropertyValue()
    prop.Name = name
    prop.Value = value
    return prop


def _desktop(port):
    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver",
        local_context,
    )
    context = resolver.resolve(
        "uno:socket,host=127.0.0.1,port={};urp;"
        "StarOffice.ComponentContext".format(port)
    )
    return context.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop",
        context,
    )


def _load_properties(hidden):
    try:
        from com.sun.star.document.MacroExecMode import NEVER_EXECUTE
    except ImportError:
        NEVER_EXECUTE = 0
    try:
        from com.sun.star.document.UpdateDocMode import NO_UPDATE
    except ImportError:
        NO_UPDATE = 3

    return (
        _property("Hidden", hidden),
        _property("ReadOnly", True),
        _property("MacroExecutionMode", NEVER_EXECUTE),
        _property("UpdateDocMode", NO_UPDATE),
    )


def _component_for_url(desktop, document_url):
    components = desktop.getComponents().createEnumeration()
    while components.hasMoreElements():
        component = components.nextElement()
        if getattr(component, "URL", None) == document_url:
            return component
    return None


def _open_document(desktop, path, hidden):
    document_url = uno.systemPathToFileUrl(path)
    document = _component_for_url(desktop, document_url)
    if document is None:
        document = desktop.loadComponentFromURL(
            document_url,
            "_blank",
            0,
            _load_properties(hidden),
        )
    if document is None:
        raise RuntimeError("LibreOffice did not open the workbook")
    return document


def _sheet(document, name):
    sheets = document.getSheets()
    if not sheets.hasByName(name):
        available = ", ".join(sheets.getElementNames())
        raise ValueError(
            "Unknown worksheet {!r}; available worksheets: {}".format(
                name,
                available,
            )
        )
    sheet = sheets.getByName(name)
    if not getattr(sheet, "IsVisible", True):
        raise ValueError("Worksheet {!r} is hidden".format(name))
    return sheet


def _close_without_saving(document):
    try:
        document.close(True)
    except Exception:
        document.dispose()


def _range_name(document, address):
    sheet_names = document.getSheets().getElementNames()
    sheet_name = sheet_names[address.Sheet]

    def column_name(index):
        index += 1
        letters = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            letters = chr(65 + remainder) + letters
        return letters

    start = "{}{}".format(column_name(address.StartColumn), address.StartRow + 1)
    end = "{}{}".format(column_name(address.EndColumn), address.EndRow + 1)
    return "{}!{}:{}".format(sheet_name, start, end)


def _render(desktop, args):
    document = _open_document(desktop, args.workbook, hidden=True)
    try:
        sheets = document.getSheets()
        target = _sheet(document, args.sheet)
        target_range = target.getCellRangeByName(args.cell_range)

        for sheet_name in sheets.getElementNames():
            current = sheets.getByName(sheet_name)
            if hasattr(current, "setPrintAreas"):
                current.setPrintAreas(())
        target.setPrintAreas((target_range.getRangeAddress(),))

        # Keep the selected viewport on one PDF page. The agent-facing tool
        # limits viewport size so the result remains legible.
        try:
            page_styles = document.getStyleFamilies().getByName("PageStyles")
            page_style = page_styles.getByName(target.PageStyle)
            page_style.ScaleToPagesX = 1
            page_style.ScaleToPagesY = 1
        except Exception:
            pass

        filter_data = (_property("SinglePageSheets", True),)
        export_properties = (
            _property("FilterName", "calc_pdf_Export"),
            _property("Overwrite", True),
            _property("FilterData", filter_data),
        )
        document.storeToURL(
            uno.systemPathToFileUrl(args.output),
            export_properties,
        )
        return {
            "sheet": args.sheet,
            "visible_range": "{}!{}".format(args.sheet, args.cell_range),
        }
    finally:
        _close_without_saving(document)


def _position(desktop, args):
    document = _open_document(desktop, args.workbook, hidden=False)
    sheet = _sheet(document, args.sheet)
    cell_range = sheet.getCellRangeByName(args.cell_range)
    address = cell_range.getRangeAddress()
    controller = document.getCurrentController()
    controller.setActiveSheet(sheet)
    controller.select(cell_range)

    try:
        controller.ZoomType = 3  # com.sun.star.view.DocumentZoomType.BY_VALUE
        controller.ZoomValue = args.zoom
    except Exception:
        pass

    pane = controller
    try:
        pane_count = controller.getCount()
        if pane_count:
            # With frozen/split panes, the final pane is the scrollable
            # bottom-right pane. For an unsplit view this is the only pane.
            pane = controller.getByIndex(pane_count - 1)
    except Exception:
        pass

    pane.setFirstVisibleColumn(address.StartColumn)
    pane.setFirstVisibleRow(address.StartRow)
    try:
        controller.getFrame().getContainerWindow().setFocus()
    except Exception:
        pass

    # Allow the controller to apply the sheet, scroll, and zoom changes before
    # reporting the range that is really visible.
    time.sleep(0.05)
    visible = pane.getVisibleRange()
    return {
        "sheet": args.sheet,
        "requested_range": "{}!{}".format(args.sheet, args.cell_range),
        "visible_range": _range_name(document, visible),
        "zoom": args.zoom,
    }


def _shutdown(desktop):
    components = desktop.getComponents().createEnumeration()
    documents = []
    while components.hasMoreElements():
        documents.append(components.nextElement())
    for document in documents:
        _close_without_saving(document)
    desktop.terminate()
    return {"status": "terminated"}


def _parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ping")

    render = subparsers.add_parser("render")
    render.add_argument("--workbook", required=True)
    render.add_argument("--sheet", required=True)
    render.add_argument("--cell-range", required=True)
    render.add_argument("--output", required=True)

    position = subparsers.add_parser("position")
    position.add_argument("--workbook", required=True)
    position.add_argument("--sheet", required=True)
    position.add_argument("--cell-range", required=True)
    position.add_argument("--zoom", required=True, type=int)

    subparsers.add_parser("shutdown")
    return parser


def main():
    args = _parser().parse_args()
    desktop = _desktop(args.port)
    if args.command == "ping":
        result = {"status": "ready"}
    elif args.command == "render":
        result = _render(desktop, args)
    elif args.command == "position":
        result = _position(desktop, args)
    else:
        result = _shutdown(desktop)
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {"error": "{}: {}".format(type(exc).__name__, exc)},
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        raise
