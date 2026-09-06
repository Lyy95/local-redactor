"""PySide6 desktop interface for the local document redactor."""

from .controller import (
    DemoDesktopController,
    DesktopController,
    HiddenReviewItem,
    ImageReviewItem,
    PreviewContent,
    ReviewBundle,
    ScanInventoryItem,
)
from .image_canvas import ImageBox, ImageRegionCanvas
from .rule_dialog import RuleEditorDialog, RuleLibraryDialog
from .window import MainWindow

__all__ = [
    "DemoDesktopController",
    "DesktopController",
    "HiddenReviewItem",
    "ImageBox",
    "ImageReviewItem",
    "ImageRegionCanvas",
    "MainWindow",
    "PreviewContent",
    "RuleEditorDialog",
    "RuleLibraryDialog",
    "ReviewBundle",
    "ScanInventoryItem",
]
