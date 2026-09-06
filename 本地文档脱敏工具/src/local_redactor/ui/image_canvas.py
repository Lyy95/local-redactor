from __future__ import annotations

import math
from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

ImageBox = tuple[int, int, int, int]


class ImageRegionCanvas(QWidget):
    """In-memory image preview with source-pixel rectangle selection."""

    regionsChanged = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("imageRegionCanvas")
        self.setMinimumSize(300, 116)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAccessibleName("图片敏感区域框选画布")
        self._pixmap = QPixmap()
        self._regions: list[ImageBox] = []
        self._drag_start: QPointF | None = None
        self._drag_current: QPointF | None = None

    def sizeHint(self) -> QSize:
        return QSize(440, 220)

    def set_preview(
        self,
        preview_png: bytes,
        regions: Sequence[ImageBox] = (),
    ) -> bool:
        """Decode preview bytes in memory and replace current regions."""

        pixmap = QPixmap()
        loaded = bool(preview_png) and pixmap.loadFromData(preview_png)
        self._pixmap = pixmap if loaded else QPixmap()
        self._regions = [box for box in regions if self._valid_box(box)]
        self._drag_start = None
        self._drag_current = None
        self.update()
        return loaded

    def clear_preview(self) -> None:
        self._pixmap = QPixmap()
        self._regions.clear()
        self._drag_start = None
        self._drag_current = None
        self.update()

    def source_size(self) -> QSize:
        return QSize(self._pixmap.width(), self._pixmap.height())

    def regions(self) -> tuple[ImageBox, ...]:
        return tuple(self._regions)

    def set_regions(self, regions: Sequence[ImageBox]) -> None:
        self._regions = [box for box in regions if self._valid_box(box)]
        self.update()

    def clear_regions(self) -> None:
        if not self._regions:
            return
        self._regions.clear()
        self.update()
        self.regionsChanged.emit(self.regions())

    def display_rect(self) -> QRectF:
        """Return the fitted image rectangle in widget coordinates."""

        if self._pixmap.isNull() or self.width() <= 0 or self.height() <= 0:
            return QRectF()
        margin = 10.0
        available_width = max(float(self.width()) - margin * 2, 1.0)
        available_height = max(float(self.height()) - margin * 2, 1.0)
        scale = min(
            available_width / self._pixmap.width(),
            available_height / self._pixmap.height(),
        )
        width = self._pixmap.width() * scale
        height = self._pixmap.height() * scale
        return QRectF(
            (self.width() - width) / 2,
            (self.height() - height) / 2,
            width,
            height,
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#263238"))
        target = self.display_rect()
        if self._pixmap.isNull() or target.isEmpty():
            painter.setPen(QColor("#E5E7EB"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "图片预览不可用\n请改为整图移除或返回检查图片",
            )
            return

        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
        for index, box in enumerate(self._regions, start=1):
            self._draw_region(painter, self._source_box_to_view(box), index)

        if self._drag_start is not None and self._drag_current is not None:
            current = self._source_points_to_view_rect(self._drag_start, self._drag_current)
            pen = QPen(QColor("#FDE047"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(253, 224, 71, 45))
            painter.drawRect(current)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() is not Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        source_point = self._view_to_source(event.position())
        if source_point is None:
            return
        self._drag_start = source_point
        self._drag_current = source_point
        self.update()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is None:
            super().mouseMoveEvent(event)
            return
        source_point = self._view_to_source(event.position(), clamp=True)
        if source_point is not None:
            self._drag_current = source_point
            self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() is not Qt.MouseButton.LeftButton or self._drag_start is None:
            super().mouseReleaseEvent(event)
            return
        source_point = self._view_to_source(event.position(), clamp=True)
        if source_point is not None:
            box = self._points_to_source_box(self._drag_start, source_point)
            if self._valid_box(box):
                self._regions.append(box)
                self.regionsChanged.emit(self.regions())
        self._drag_start = None
        self._drag_current = None
        self.update()
        event.accept()

    def _view_to_source(
        self,
        point: QPointF,
        *,
        clamp: bool = False,
    ) -> QPointF | None:
        target = self.display_rect()
        if target.isEmpty() or self._pixmap.isNull():
            return None
        if not target.contains(point) and not clamp:
            return None
        x = min(max(point.x(), target.left()), target.right())
        y = min(max(point.y(), target.top()), target.bottom())
        source_x = (x - target.left()) * self._pixmap.width() / target.width()
        source_y = (y - target.top()) * self._pixmap.height() / target.height()
        return QPointF(
            min(max(source_x, 0.0), float(self._pixmap.width())),
            min(max(source_y, 0.0), float(self._pixmap.height())),
        )

    def _source_box_to_view(self, box: ImageBox) -> QRectF:
        left, top, right, bottom = box
        return self._source_points_to_view_rect(
            QPointF(float(left), float(top)),
            QPointF(float(right), float(bottom)),
        )

    def _source_points_to_view_rect(self, first: QPointF, second: QPointF) -> QRectF:
        target = self.display_rect()
        scale_x = target.width() / max(self._pixmap.width(), 1)
        scale_y = target.height() / max(self._pixmap.height(), 1)
        first_view = QPointF(
            target.left() + first.x() * scale_x,
            target.top() + first.y() * scale_y,
        )
        second_view = QPointF(
            target.left() + second.x() * scale_x,
            target.top() + second.y() * scale_y,
        )
        normalized = QRectF(first_view, second_view).normalized()
        return QRectF(normalized)

    def _points_to_source_box(self, first: QPointF, second: QPointF) -> ImageBox:
        left = max(0, math.floor(min(first.x(), second.x())))
        top = max(0, math.floor(min(first.y(), second.y())))
        right = min(self._pixmap.width(), math.ceil(max(first.x(), second.x())))
        bottom = min(self._pixmap.height(), math.ceil(max(first.y(), second.y())))
        return (left, top, right, bottom)

    def _valid_box(self, box: ImageBox) -> bool:
        if self._pixmap.isNull():
            return False
        left, top, right, bottom = box
        return (
            left >= 0
            and top >= 0
            and right <= self._pixmap.width()
            and bottom <= self._pixmap.height()
            and right - left >= 2
            and bottom - top >= 2
        )

    @staticmethod
    def _draw_region(painter: QPainter, rect: QRectF, index: int) -> None:
        painter.setPen(QPen(QColor("#B42318"), 2))
        painter.setBrush(QColor(180, 35, 24, 70))
        painter.drawRect(rect)
        label_rect = QRectF(rect.left(), rect.top(), 26, 22)
        painter.fillRect(label_rect, QColor("#B42318"))
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, str(index))
