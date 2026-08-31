import sys
import os
from fractions import Fraction
from typing import Optional

import pandas as pd

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QStyleFactory,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


# ----------------------------------------------------------------------
# Land measurement constants
# ----------------------------------------------------------------------

KANAL_TO_MARLA = 20
MARLA_TO_SARSAI = 9
KANAL_TO_ACRE = 0.125
KILLA_TO_KANAL = 8

SHARE_TOLERANCE = 1e-9


# ----------------------------------------------------------------------
# Appearance
# ----------------------------------------------------------------------

BG = "#1e1e2e"
CARD = "#2a2a3e"
INPUT_BG = "#181825"
ACCENT = "#89b4fa"
TEXT = "#e5e5f0"
MUTED = "#a0a0bb"
ERROR = "#f38ba8"
SUCCESS = "#a6e3a1"

HEADERS = [
    "Khewat",
    "Marba",
    "Killa",
    "Area (Kanal)",
    "Area (Marla)",
    "Owner",
    "Share Fraction",
]

EXCEL_COLUMNS = [
    "Khewat No",
    "Marba No",
    "Killa No",
    "Total Area (Kanal)",
    "Total Area (Marla)",
    "Owner Name",
    "Share Fraction",
]


# ----------------------------------------------------------------------
# Calculation helpers
# ----------------------------------------------------------------------

def parse_fraction(value: object) -> Optional[Fraction]:
    """
    Parse:
        1/2
        1 1/2
        2
        0.25
    """

    text = str(value).strip()

    if not text:
        return None

    try:
        if " " in text:
            parts = text.split()

            if len(parts) != 2:
                return None

            whole = Fraction(parts[0])
            fraction = Fraction(parts[1])

            return whole + fraction

        return Fraction(text)

    except (ValueError, ZeroDivisionError):
        return None


def fraction_to_float(value: Fraction) -> float:
    return float(value)


def format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)

    if abs(value.numerator) > value.denominator:
        whole = value.numerator // value.denominator
        remainder = abs(value.numerator) % value.denominator

        if remainder:
            return f"{whole} {remainder}/{value.denominator}"

        return str(whole)

    return f"{value.numerator}/{value.denominator}"


def breakdown_area(area_kanal: float):
    """
    Convert decimal kanal into:
        Killa, Kanal, Marla, Sarsai

    Normalisation is handled explicitly so rounding can never produce
    invalid values such as 20 marla or 9 sarsai.
    """

    if area_kanal < 0:
        raise ValueError("Area cannot be negative.")

    total_sarsai = round(
        area_kanal
        * KANAL_TO_MARLA
        * MARLA_TO_SARSAI
    )

    sarsai_per_marla = MARLA_TO_SARSAI
    sarsai_per_kanal = KANAL_TO_MARLA * sarsai_per_marla
    sarsai_per_killa = KILLA_TO_KANAL * sarsai_per_kanal

    killa, remainder = divmod(
        total_sarsai,
        sarsai_per_killa,
    )

    kanal, remainder = divmod(
        remainder,
        sarsai_per_kanal,
    )

    marla, sarsai = divmod(
        remainder,
        sarsai_per_marla,
    )

    return (
        int(killa),
        int(kanal),
        int(marla),
        int(sarsai),
    )


def estate_key(khewat, marba, killa) -> str:
    return "-".join(
        str(value).strip()
        for value in (
            khewat,
            marba,
            killa,
        )
    )


# ----------------------------------------------------------------------
# Chart
# ----------------------------------------------------------------------

class PieChart(FigureCanvasQTAgg):

    COLORS = [
        "#89b4fa",
        "#a6e3a1",
        "#f9e2af",
        "#f38ba8",
        "#cba6f7",
        "#74c7ec",
        "#f5c2e7",
        "#94e2d5",
        "#fab387",
        "#b4befe",
    ]

    def __init__(self):
        self.figure = Figure(
            figsize=(5, 4),
            facecolor=CARD,
        )

        super().__init__(
            self.figure
        )

        self.ax = self.figure.add_subplot(
            111
        )

        self.setMinimumHeight(
            300
        )

        self.draw_pie(
            pd.Series(
                dtype=float
            )
        )

    def draw_pie(self, owner_areas):
        self.ax.clear()

        self.ax.set_facecolor(
            CARD
        )

        self.figure.patch.set_facecolor(
            CARD
        )

        if (
            owner_areas is None
            or len(owner_areas) == 0
        ):

            self.ax.text(
                0.5,
                0.5,
                "No data",
                ha="center",
                va="center",
                color=MUTED,
                transform=self.ax.transAxes,
            )

        else:

            if isinstance(
                owner_areas,
                dict,
            ):
                owner_areas = pd.Series(
                    owner_areas
                )

            owner_areas = (
                owner_areas[
                    owner_areas > 0
                ]
                .sort_values(
                    ascending=False
                )
            )

            if owner_areas.empty:

                self.ax.text(
                    0.5,
                    0.5,
                    "No positive share area",
                    ha="center",
                    va="center",
                    color=MUTED,
                    transform=self.ax.transAxes,
                )

            else:

                owners = list(
                    owner_areas.index.astype(
                        str
                    )
                )

                areas = list(
                    owner_areas.values
                )

                colors = [
                    self.COLORS[
                        index % len(
                            self.COLORS
                        )
                    ]
                    for index in range(
                        len(owners)
                    )
                ]

                self.ax.pie(
                    areas,
                    labels=owners,
                    autopct="%1.1f%%",
                    colors=colors,
                    startangle=90,
                    textprops={
                        "color": TEXT,
                        "fontsize": 9,
                    },
                    wedgeprops={
                        "edgecolor": CARD,
                        "linewidth": 2,
                    },
                )

        self.ax.set_title(
            "Land Share Distribution",
            color=TEXT,
            fontsize=12,
        )

        self.figure.tight_layout()

        self.draw()


# ----------------------------------------------------------------------
# Main application
# ----------------------------------------------------------------------

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Punjab Rural Land Share Calculator"
        )

        self.resize(
            1200,
            800,
        )

        self.setMinimumSize(
            950,
            650,
        )

        self.setStyleSheet(
            self._qss()
        )

        self.rows_data = []

        self.detailed_df = pd.DataFrame()
        self.summary_df = pd.DataFrame()
        self.validation_df = pd.DataFrame()

        self._build_ui()

        self.add_row()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    @staticmethod
    def _qss():

        return f"""
        QMainWindow, QWidget {{
            background: {BG};
            color: {TEXT};
        }}

        QLabel {{
            color: {TEXT};
        }}

        QLabel#title {{
            font-size: 22px;
            font-weight: bold;
            color: {TEXT};
        }}

        QLabel#sub {{
            color: {MUTED};
            font-size: 12px;
        }}

        QFrame#card {{
            background: {CARD};
            border-radius: 10px;
        }}

        QPushButton {{
            background: {ACCENT};
            color: #11111b;
            border: none;
            border-radius: 6px;
            padding: 8px 14px;
            font-weight: bold;
        }}

        QPushButton:hover {{
            background: #74c7ec;
        }}

        QPushButton:disabled {{
            background: #45475a;
            color: {MUTED};
        }}

        QPushButton#ghost {{
            background: {CARD};
            color: {ACCENT};
            border: 1px solid {ACCENT};
        }}

        QPushButton#ghost:hover {{
            background: #313244;
        }}

        QPushButton#danger {{
            background: {ERROR};
            color: #11111b;
        }}

        QComboBox, QTableWidget {{
            background: {INPUT_BG};
            color: {TEXT};
            border: 1px solid #313244;
            border-radius: 6px;
            padding: 6px;
            selection-background-color: {ACCENT};
            selection-color: #11111b;
        }}

        QComboBox:focus, QTableWidget:focus {{
            border: 1px solid {ACCENT};
        }}

        QHeaderView::section {{
            background: #313244;
            color: {TEXT};
            border: none;
            padding: 8px;
            font-weight: bold;
        }}

        QTableWidget {{
            gridline-color: #313244;
        }}

        QTableWidget::item:selected {{
            background: #45475a;
            color: {TEXT};
        }}

        QTabWidget::pane {{
            border: 1px solid #313244;
            border-radius: 8px;
        }}

        QTabBar::tab {{
            background: {CARD};
            color: {MUTED};
            padding: 8px 16px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 2px;
        }}

        QTabBar::tab:selected {{
            background: {ACCENT};
            color: #11111b;
            font-weight: bold;
        }}

        QTabBar::tab:hover:!selected {{
            background: #313244;
            color: {TEXT};
        }}

        QRadioButton {{
            color: {TEXT};
        }}

        QScrollArea {{
            border: none;
        }}

        QStatusBar {{
            background: {CARD};
            color: {MUTED};
        }}
        """

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):

        central = QWidget()

        self.setCentralWidget(
            central
        )

        root = QVBoxLayout(
            central
        )

        root.setContentsMargins(
            16,
            16,
            16,
            16,
        )

        root.setSpacing(
            12
        )

        title = QLabel(
            "Punjab Rural Land Share Calculator"
        )

        title.setObjectName(
            "title"
        )

        root.addWidget(
            title
        )

        subtitle = QLabel(
            "Compute validated land shares with "
            "killa / kanal / marla / sarsai breakdown "
            "and estate-wise owner charts."
        )

        subtitle.setObjectName(
            "sub"
        )

        subtitle.setWordWrap(
            True
        )

        root.addWidget(
            subtitle
        )

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        splitter.addWidget(
            self._build_input_panel()
        )

        splitter.addWidget(
            self._build_results_panel()
        )

        splitter.setSizes(
            [
                560,
                640,
            ]
        )

        splitter.setStretchFactor(
            0,
            1,
        )

        splitter.setStretchFactor(
            1,
            1,
        )

        root.addWidget(
            splitter,
            1,
        )

        self._setup_toolbar()

        self.setStatusBar(
            QStatusBar(
                self
            )
        )

        self.statusBar().showMessage(
            "Ready"
        )

    def _setup_toolbar(self):

        toolbar = self.addToolBar(
            "Actions"
        )

        toolbar.setMovable(
            False
        )

        toolbar.setStyleSheet(
            f"""
            QToolBar {{
                background: {CARD};
                spacing: 4px;
            }}
            """
        )

        compute_action = QAction(
            "Compute",
            self,
        )

        compute_action.triggered.connect(
            self.compute
        )

        toolbar.addAction(
            compute_action
        )

        export_action = QAction(
            "Export to Excel",
            self,
        )

        export_action.triggered.connect(
            self.export_excel
        )

        toolbar.addAction(
            export_action
        )

        clear_action = QAction(
            "Clear All",
            self,
        )

        clear_action.triggered.connect(
            self.clear_all
        )

        toolbar.addAction(
            clear_action
        )

    def _card(self, title):

        frame = QFrame()

        frame.setObjectName(
            "card"
        )

        layout = QVBoxLayout(
            frame
        )

        layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )

        heading = QLabel(
            title
        )

        heading.setFont(
            QFont(
                "Helvetica",
                14,
                QFont.Weight.Bold,
            )
        )

        layout.addWidget(
            heading
        )

        return frame, layout

    def _build_input_panel(self):

        scroll = QScrollArea()

        scroll.setWidgetResizable(
            True
        )

        panel = QWidget()

        scroll.setWidget(
            panel
        )

        layout = QVBoxLayout(
            panel
        )

        layout.setContentsMargins(
            4,
            4,
            12,
            4,
        )

        card, box = self._card(
            "Land Entries"
        )

        layout.addWidget(
            card,
            1,
        )

        mode_row = QHBoxLayout()

        self.mode_manual = QRadioButton(
            "Manual Entry"
        )

        self.mode_upload = QRadioButton(
            "Upload Excel File"
        )

        self.mode_manual.setChecked(
            True
        )

        self.mode_group = QButtonGroup(
            self
        )

        self.mode_group.addButton(
            self.mode_manual
        )

        self.mode_group.addButton(
            self.mode_upload
        )

        mode_row.addWidget(
            self.mode_manual
        )

        mode_row.addWidget(
            self.mode_upload
        )

        mode_row.addStretch()

        box.addLayout(
            mode_row
        )

        upload_row = QHBoxLayout()

        self.upload_btn = QPushButton(
            "Choose Excel File..."
        )

        self.upload_btn.setObjectName(
            "ghost"
        )

        self.upload_btn.clicked.connect(
            self.upload_excel
        )

        self.upload_file_label = QLabel(
            ""
        )

        self.upload_file_label.setObjectName(
            "sub"
        )

        self.upload_file_label.setWordWrap(
            True
        )

        upload_row.addWidget(
            self.upload_btn
        )

        upload_row.addWidget(
            self.upload_file_label,
            1,
        )

        box.addLayout(
            upload_row
        )

        self.table = QTableWidget(
            0,
            len(HEADERS),
        )

        self.table.setHorizontalHeaderLabels(
            HEADERS
        )

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.table.verticalHeader().setVisible(
            False
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self.table.setMinimumHeight(
            380
        )

        box.addWidget(
            self.table,
            1,
        )

        button_row = QHBoxLayout()

        self.add_btn = QPushButton(
            "+ Add Row"
        )

        self.remove_btn = QPushButton(
            "- Remove Selected"
        )

        self.remove_btn.setObjectName(
            "ghost"
        )

        self.add_btn.clicked.connect(
            self.add_row
        )

        self.remove_btn.clicked.connect(
            self.remove_selected_rows
        )

        button_row.addWidget(
            self.add_btn
        )

        button_row.addWidget(
            self.remove_btn
        )

        button_row.addStretch()

        box.addLayout(
            button_row
        )

        hint = QLabel(
            "Area = kanal + marla. "
            "Share fractions support 1/2, 1 1/2, "
            "2 or 0.25."
        )

        hint.setObjectName(
            "sub"
        )

        hint.setWordWrap(
            True
        )

        box.addWidget(
            hint
        )

        self.mode_manual.toggled.connect(
            self._toggle_mode
        )

        self._toggle_mode()

        return scroll

    def _toggle_mode(self):

        manual = self.mode_manual.isChecked()

        self.upload_btn.setVisible(
            not manual
        )

        self.upload_file_label.setVisible(
            not manual
        )

        self.table.setEnabled(
            manual
        )

        self.add_btn.setEnabled(
            manual
        )

        self.remove_btn.setEnabled(
            manual
        )

    def _build_results_panel(self):

        widget = QWidget()

        layout = QVBoxLayout(
            widget
        )

        layout.setContentsMargins(
            4,
            4,
            0,
            4,
        )

        self.results_tabs = QTabWidget()

        # Detailed output

        detailed_card, detailed_box = self._card(
            "Individual Share Calculations"
        )

        self.detailed_table = QTableWidget(
            0,
            11,
        )

        self.detailed_table.setHorizontalHeaderLabels(
            [
                "Khewat",
                "Marba",
                "Killa",
                "Owner",
                "Share Fraction",
                "Share Area (Kanal)",
                "Killa",
                "Kanal",
                "Marla",
                "Sarsai",
                "Acre",
            ]
        )

        self._configure_result_table(
            self.detailed_table
        )

        detailed_box.addWidget(
            self.detailed_table
        )

        self.results_tabs.addTab(
            detailed_card,
            "Detailed Output",
        )

        # Owner summary

        summary_card, summary_box = self._card(
            "Owner-wise Summary"
        )

        self.summary_table = QTableWidget(
            0,
            6,
        )

        self.summary_table.setHorizontalHeaderLabels(
            [
                "Owner",
                "Area (Kanal)",
                "Killa",
                "Kanal",
                "Marla",
                "Sarsai",
            ]
        )

        self._configure_result_table(
            self.summary_table
        )

        summary_box.addWidget(
            self.summary_table
        )

        self.results_tabs.addTab(
            summary_card,
            "Owner Summary",
        )

        # Estate chart

        chart_card, chart_box = self._card(
            "Estate-wise Share Distribution"
        )

        estate_row = QHBoxLayout()

        self.estate_combo = QComboBox()

        self.estate_combo.currentTextChanged.connect(
            self.refresh_chart
        )

        estate_row.addWidget(
            QLabel(
                "Select Estate:"
            )
        )

        estate_row.addWidget(
            self.estate_combo,
            1,
        )

        chart_box.addLayout(
            estate_row
        )

        self.chart = PieChart()

        chart_box.addWidget(
            self.chart,
            1,
        )

        self.results_tabs.addTab(
            chart_card,
            "Estate Chart",
        )

        # Validation

        validation_card, validation_box = self._card(
            "Validation Report"
        )

        self.validation_label = QLabel(
            "No computation performed yet."
        )

        self.validation_label.setWordWrap(
            True
        )

        validation_box.addWidget(
            self.validation_label
        )

        self.validation_table = QTableWidget(
            0,
            3,
        )

        self.validation_table.setHorizontalHeaderLabels(
            [
                "Estate",
                "Total Share",
                "Status",
            ]
        )

        self._configure_result_table(
            self.validation_table
        )

        validation_box.addWidget(
            self.validation_table
        )

        self.results_tabs.addTab(
            validation_card,
            "Validation",
        )

        layout.addWidget(
            self.results_tabs,
            1,
        )

        return widget

    @staticmethod
    def _configure_result_table(table):

        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        table.verticalHeader().setVisible(
            False
        )

        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

    # ------------------------------------------------------------------
    # Input management
    # ------------------------------------------------------------------

    def add_row(self):

        row = self.table.rowCount()

        self.table.insertRow(
            row
        )

        if row == 0:
            self.table.setCurrentCell(
                row,
                0,
            )

    def remove_selected_rows(self):

        rows = sorted(
            {
                index.row()
                for index in self.table.selectionModel().selectedRows()
            },
            reverse=True,
        )

        if not rows:

            QMessageBox.information(
                self,
                "Remove Rows",
                "Select one or more rows first.",
            )

            return

        for row in rows:

            self.table.removeRow(
                row
            )

        if self.table.rowCount() == 0:
            self.add_row()

    def clear_all(self):

        self.table.setRowCount(
            0
        )

        self.add_row()

        self.upload_file_label.setText(
            ""
        )

        self.mode_manual.setChecked(
            True
        )

        self.detailed_df = pd.DataFrame()
        self.summary_df = pd.DataFrame()
        self.validation_df = pd.DataFrame()

        self.detailed_table.setRowCount(
            0
        )

        self.summary_table.setRowCount(
            0
        )

        self.validation_table.setRowCount(
            0
        )

        self.validation_label.setText(
            "No computation performed yet."
        )

        self.validation_label.setStyleSheet(
            f"color: {MUTED};"
        )

        self.estate_combo.blockSignals(
            True
        )

        self.estate_combo.clear()

        self.estate_combo.blockSignals(
            False
        )

        self.chart.draw_pie(
            pd.Series(
                dtype=float
            )
        )

        self.statusBar().showMessage(
            "Cleared"
        )

    def upload_excel(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Excel File",
            "",
            "Excel files (*.xlsx *.xls)",
        )

        if not path:
            return

        try:

            df = pd.read_excel(
                path
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Load Error",
                f"Could not read Excel file:\n{error}",
            )

            return

        missing = [
            column
            for column in EXCEL_COLUMNS
            if column not in df.columns
        ]

        if missing:

            QMessageBox.critical(
                self,
                "Format Error",
                "The Excel file is missing:\n\n"
                + "\n".join(
                    f"• {column}"
                    for column in missing
                )
                + "\n\nRequired columns:\n"
                + "\n".join(
                    EXCEL_COLUMNS
                ),
            )

            return

        df = df[
            EXCEL_COLUMNS
        ].fillna(
            ""
        )

        self.table.setRowCount(
            0
        )

        for _, excel_row in df.iterrows():

            row = self.table.rowCount()

            self.table.insertRow(
                row
            )

            for column, value in enumerate(
                excel_row.tolist()
            ):

                if isinstance(
                    value,
                    float,
                ) and value.is_integer():

                    value = int(
                        value
                    )

                self.table.setItem(
                    row,
                    column,
                    QTableWidgetItem(
                        str(value)
                    ),
                )

        self.upload_file_label.setText(
            os.path.basename(
                path
            )
        )

        self.statusBar().showMessage(
            f"Loaded {self.table.rowCount()} row(s) "
            f"from {os.path.basename(path)}"
        )

    # ------------------------------------------------------------------
    # Reading and validation
    # ------------------------------------------------------------------

    def _cell_text(
        self,
        row,
        column,
    ):

        # ----------------------------------------------------------
        # First check whether this cell is currently being edited.
        # ----------------------------------------------------------

        if (
            self.table.currentRow() == row
            and self.table.currentColumn() == column
        ):

            editor = self.table.focusWidget()

            if (
                editor is not None
                and hasattr(editor, "text")
            ):

                try:

                    value = editor.text()

                    if value is not None:

                        return str(
                            value
                        ).strip()

                except Exception:

                    pass

        # ----------------------------------------------------------
        # Normal QTableWidgetItem value.
        # ----------------------------------------------------------

        item = self.table.item(
            row,
            column,
        )

        if item is None:

            return ""

        return item.text().strip()

    def read_entries(self):

        entries = []
        errors = []

        for row in range(
            self.table.rowCount()
        ):

            values = [
                self._cell_text(
                    row,
                    column,
                )
                for column in range(
                    len(HEADERS)
                )
            ]

            if not any(
                values
            ):
                continue

            (
                khewat,
                marba,
                killa,
                kanal_text,
                marla_text,
                owner,
                share_text,
            ) = values

            row_number = row + 1

            required = {
                "Khewat": khewat,
                "Marba": marba,
                "Killa": killa,
                "Owner": owner,
                "Share Fraction": share_text,
            }

            missing = [
                name
                for name, value in required.items()
                if not value
            ]

            if missing:

                errors.append(
                    f"Row {row_number}: Missing "
                    + ", ".join(
                        missing
                    )
                    + "."
                )

                continue

            try:

                kanal = float(
                    kanal_text or 0
                )

                marla = float(
                    marla_text or 0
                )

            except ValueError:

                errors.append(
                    f"Row {row_number}: "
                    "Area values must be numeric."
                )

                continue

            if kanal < 0 or marla < 0:

                errors.append(
                    f"Row {row_number}: "
                    "Area cannot be negative."
                )

                continue

            if kanal == 0 and marla == 0:

                errors.append(
                    f"Row {row_number}: "
                    "Total area must be greater than zero."
                )

                continue

            fraction = parse_fraction(
                share_text
            )

            if fraction is None:

                errors.append(
                    f"Row {row_number}: Invalid share "
                    f"fraction '{share_text}'."
                )

                continue

            if fraction < 0:

                errors.append(
                    f"Row {row_number}: "
                    "Share fraction cannot be negative."
                )

                continue

            total_area_kanal = (
                kanal
                + marla / KANAL_TO_MARLA
            )

            share_area = (
                total_area_kanal
                * fraction_to_float(
                    fraction
                )
            )

            (
                killa_out,
                kanal_out,
                marla_out,
                sarsai_out,
            ) = breakdown_area(
                share_area
            )

            entries.append(
                {
                    "Khewat": khewat,
                    "Marba": marba,
                    "Killa": killa,
                    "Owner": owner,
                    "Share Fraction": format_fraction(
                        fraction
                    ),
                    "Share Fraction Value": fraction,
                    "Share Area (Kanal)": share_area,
                    "Kila": killa_out,
                    "Kanal": kanal_out,
                    "Marla": marla_out,
                    "Sarsai": sarsai_out,
                    "Acre": share_area
                    * KANAL_TO_ACRE,
                }
            )

        return entries, errors

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------

    def compute(self):
        
        # Commit the currently edited table cell before reading data.
        self.table.clearFocus()
        QApplication.processEvents()
        
        entries, errors = self.read_entries()

        if not entries:

            message = (
                "No valid entries were found."
            )

            if errors:

                message += (
                    "\n\n"
                    + "\n".join(
                        errors[:10]
                    )
                )

            QMessageBox.warning(
                self,
                "No Valid Data",
                message,
            )

            return

        df = pd.DataFrame(
            entries
        )

        df["Estate"] = df.apply(
            lambda row: estate_key(
                row["Khewat"],
                row["Marba"],
                row["Killa"],
            ),
            axis=1,
        )

        # Keep the display/export dataframe separate from internal
        # Fraction objects used for exact share validation.

        fraction_totals = (
            df.groupby(
                "Estate",
                sort=True,
            )["Share Fraction Value"]
            .apply(
                lambda values: sum(
                    values,
                    Fraction(0),
                )
            )
        )

        validation_rows = []

        for estate, total in fraction_totals.items():

            status = (
                "OK"
                if total == Fraction(1)
                else "MISMATCH"
            )

            validation_rows.append(
                {
                    "Estate": estate,
                    "Total Share": format_fraction(
                        total
                    ),
                    "Total Share Decimal": float(
                        total
                    ),
                    "Status": status,
                }
            )

        validation_df = pd.DataFrame(
            validation_rows
        )

        summary = (
            df.groupby(
                "Owner",
                sort=True,
                as_index=False,
            )["Share Area (Kanal)"]
            .sum()
        )

        breakdown = summary[
            "Share Area (Kanal)"
        ].apply(
            breakdown_area
        )

        summary[
            [
                "Kila",
                "Kanal",
                "Marla",
                "Sarsai",
            ]
        ] = pd.DataFrame(
            breakdown.tolist(),
            index=summary.index,
        )

        summary["Acre"] = (
            summary[
                "Share Area (Kanal)"
            ]
            * KANAL_TO_ACRE
        )

        display_df = df.drop(
            columns=[
                "Share Fraction Value",
            ]
        ).copy()

        self.detailed_df = display_df
        self.summary_df = summary
        self.validation_df = validation_df

        self._populate_detailed(
            display_df
        )

        self._populate_summary(
            summary
        )

        self._populate_validation(
            validation_df,
            errors,
        )

        estates = sorted(
            display_df[
                "Estate"
            ].unique()
        )

        self.estate_combo.blockSignals(
            True
        )

        self.estate_combo.clear()

        self.estate_combo.addItems(
            estates
        )

        self.estate_combo.blockSignals(
            False
        )

        self.refresh_chart()

        self.results_tabs.setCurrentIndex(
            0
        )

        valid_count = (
            validation_df[
                validation_df["Status"] == "OK"
            ].shape[0]
        )

        self.statusBar().showMessage(
            f"Computed {len(display_df)} valid share(s) "
            f"across {len(estates)} estate(s). "
            f"{valid_count}/{len(estates)} estate(s) "
            f"have shares summing exactly to 1."
        )

        if errors:

            QMessageBox.warning(
                self,
                "Computation Completed With Input Errors",
                f"{len(display_df)} valid entry/entries were "
                "computed.\n\n"
                f"{len(errors)} row(s) were skipped:\n\n"
                + "\n".join(
                    errors[:10]
                ),
            )

    # ------------------------------------------------------------------
    # Results tables
    # ------------------------------------------------------------------

    def _populate_detailed(
        self,
        df,
    ):

        columns = [
            "Khewat",
            "Marba",
            "Killa",
            "Owner",
            "Share Fraction",
            "Share Area (Kanal)",
            "Kila",
            "Kanal",
            "Marla",
            "Sarsai",
            "Acre",
        ]

        self.detailed_table.setRowCount(
            len(df)
        )

        for row_index, (_, row) in enumerate(
            df.iterrows()
        ):

            values = []

            for column in columns:

                value = row[
                    column
                ]

                if column in {
                    "Share Area (Kanal)",
                    "Acre",
                }:

                    value = round(
                        float(value),
                        6,
                    )

                values.append(
                    value
                )

            for column_index, value in enumerate(
                values
            ):

                self._set_item(
                    self.detailed_table,
                    row_index,
                    column_index,
                    value,
                )

    def _populate_summary(
        self,
        df,
    ):

        columns = [
            "Owner",
            "Share Area (Kanal)",
            "Kila",
            "Kanal",
            "Marla",
            "Sarsai",
        ]

        self.summary_table.setRowCount(
            len(df)
        )

        for row_index, (_, row) in enumerate(
            df.iterrows()
        ):

            for column_index, column in enumerate(
                columns
            ):

                value = row[
                    column
                ]

                if column == "Share Area (Kanal)":

                    value = round(
                        float(value),
                        6,
                    )

                self._set_item(
                    self.summary_table,
                    row_index,
                    column_index,
                    value,
                )

    def _populate_validation(
        self,
        validation_df,
        entry_errors,
    ):

        self.validation_table.setRowCount(
            len(validation_df)
        )

        for row_index, (_, row) in enumerate(
            validation_df.iterrows()
        ):

            values = [
                row["Estate"],
                row["Total Share"],
                row["Status"],
            ]

            for column_index, value in enumerate(
                values
            ):

                item = QTableWidgetItem(
                    str(value)
                )

                if column_index == 2:

                    color = (
                        SUCCESS
                        if row["Status"] == "OK"
                        else ERROR
                    )

                    item.setForeground(
                        QColor(
                            color
                        )
                    )

                else:

                    item.setForeground(
                        QColor(
                            TEXT
                        )
                    )

                self.validation_table.setItem(
                    row_index,
                    column_index,
                    item,
                )

        mismatch_count = (
            validation_df[
                validation_df["Status"] == "MISMATCH"
            ].shape[0]
        )

        messages = []

        if entry_errors:

            messages.append(
                f"<b style='color:{ERROR}'>"
                f"Input errors: {len(entry_errors)}"
                "</b><br>"
                + "<br>".join(
                    entry_errors[:8]
                )
            )

        if mismatch_count:

            messages.append(
                f"<b style='color:{ERROR}'>"
                f"{mismatch_count} estate(s) have "
                "shares that do not sum to 1."
                "</b>"
            )

        if not entry_errors and not mismatch_count:

            messages.append(
                f"<b style='color:{SUCCESS}'>"
                "All input rows are valid and all "
                "estate shares sum exactly to 1."
                "</b>"
            )

        self.validation_label.setText(
            "<br><br>".join(
                messages
            )
        )

    # ------------------------------------------------------------------
    # Chart
    # ------------------------------------------------------------------

    def refresh_chart(self):

        if (
            self.estate_combo.count() == 0
            or self.detailed_df.empty
        ):

            self.chart.draw_pie(
                pd.Series(
                    dtype=float
                )
            )

            return

        estate = (
            self.estate_combo.currentText()
        )

        estate_df = self.detailed_df[
            self.detailed_df[
                "Estate"
            ]
            == estate
        ]

        # Grouping fixes the original duplicate-owner overwrite bug.
        owner_areas = (
            estate_df.groupby(
                "Owner",
                sort=True,
            )[
                "Share Area (Kanal)"
            ]
            .sum()
        )

        self.chart.draw_pie(
            owner_areas
        )

    # ------------------------------------------------------------------
    # Excel export
    # ------------------------------------------------------------------

    def export_excel(self):

        if self.detailed_df.empty:

            QMessageBox.information(
                self,
                "Nothing to Export",
                "Compute the shares first.",
            )

            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Results",
            "land_share_results.xlsx",
            "Excel files (*.xlsx)",
        )

        if not path:
            return

        if not path.lower().endswith(
            ".xlsx"
        ):

            path += ".xlsx"

        try:

            with pd.ExcelWriter(
                path,
                engine="openpyxl",
            ) as writer:

                self.detailed_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Detailed Output",
                )

                self.summary_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Owner Summary",
                )

                self.validation_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Validation Report",
                )

                for worksheet in writer.book.worksheets:

                    worksheet.freeze_panes = "A2"

                    worksheet.auto_filter.ref = (
                        worksheet.dimensions
                    )

                    for column_cells in (
                        worksheet.columns
                    ):

                        column_letter = (
                            column_cells[0].column_letter
                        )

                        maximum = max(
                            len(
                                str(cell.value)
                                if cell.value is not None
                                else ""
                            )
                            for cell in column_cells
                        )

                        worksheet.column_dimensions[
                            column_letter
                        ].width = min(
                            maximum + 2,
                            40,
                        )

            self.statusBar().showMessage(
                f"Exported to {path}"
            )

            QMessageBox.information(
                self,
                "Export Complete",
                f"Saved to:\n{path}",
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Export Error",
                f"Could not export:\n{error}",
            )

    # ------------------------------------------------------------------
    # Table helper
    # ------------------------------------------------------------------

    @staticmethod
    def _set_item(
        table,
        row,
        column,
        value,
    ):

        item = QTableWidgetItem(
            str(value)
        )

        item.setForeground(
            QColor(
                TEXT
            )
        )

        table.setItem(
            row,
            column,
            item,
        )


# ----------------------------------------------------------------------
# Application entry point
# ----------------------------------------------------------------------

def main():

    QApplication.setStyle(
        QStyleFactory.create(
            "Fusion"
        )
    )

    app = QApplication(
        sys.argv
    )

    app.setFont(
        QFont(
            "Helvetica",
            10,
        )
    )

    window = MainWindow()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
