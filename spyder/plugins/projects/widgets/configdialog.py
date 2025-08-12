# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright © Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)
# -----------------------------------------------------------------------------
"""Project creation dialog."""

# Standard library imports
from __future__ import annotations
import os
import os.path as osp
import sys
import logging
from typing import TypedDict

# Third party imports
from qtpy.QtCore import Qt, Signal, QSize
from qtpy.QtWidgets import (
    QDialog,
    QGridLayout,
    QWidget,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

# Local imports
from spyder.api.fonts import SpyderFontType, SpyderFontsMixin
from spyder.api.translations import _
from spyder.api.widgets.dialogs import SpyderDialogButtonBox
from spyder.plugins.projects.api import EmptyProject
from spyder.utils.icon_manager import ima
from spyder.utils.stylesheet import AppStyle, MAC, WIN
from spyder.widgets.config import SpyderConfigPage
from spyder.widgets.sidebardialog import SidebarDialog
from spyder.widgets.helperwidgets import MessageLabel

# For logging
logger = logging.getLogger(__name__)

# =============================================================================
# ---- Auxiliary functions and classes
# =============================================================================
def is_writable(path):
    """
    Check if path has write access.

    Solution taken from https://stackoverflow.com/a/11170037
    """
    filepath = osp.join(path, "__spyder_write_test__.txt")

    try:
        filehandle = open(filepath, 'w')
        filehandle.close()
        os.remove(filepath)
    except (FileNotFoundError, PermissionError):
        return False

    return True


class ValidationReasons(TypedDict):
    missing_info: bool | None
    no_location: bool | None
    location_exists: bool | None
    location_not_writable: bool | None
    spyder_project_exists: bool | None


# =============================================================================
# ---- Pages
# =============================================================================
class BaseProjectPage(SpyderConfigPage, SpyderFontsMixin):
    """Base project page."""

    # SidebarPage API
    MIN_HEIGHT = 300
    MAX_WIDTH = 430 if MAC else (400 if WIN else 420)

    # SpyderConfigPage API
    LOAD_FROM_CONFIG = False

    # Own API
    LOCATION_TEXT = _("Location")
    LOCATION_TIP = None

    def __init__(self, parent):
        super().__init__(parent)

        self._location = self.create_browsefile(
            text=self.LOCATION_TEXT,
            option=None,
            alignment=Qt.Vertical,
            tip=self.LOCATION_TIP,
            status_icon=ima.icon("error"),
        )

        self._validation_label = MessageLabel(self)
        self._validation_label.setVisible(False)

        self._description_font = self.get_font(SpyderFontType.Interface)
        self._description_font.setPointSize(
            self._description_font.pointSize() + 1
        )

    # ---- Public API
    # -------------------------------------------------------------------------
    @property
    def project_location(self):
        """Where the project is going to be created."""
        raise NotImplementedError

    def validate_page(self):
        """Actions to take to validate the page contents."""
        raise NotImplementedError

    @property
    def project_type(self):
        """Project type associated to this page."""
        return EmptyProject

    # ---- Private API
    # -------------------------------------------------------------------------
    def _validate_location(
        self,
        location: str,
        reasons: ValidationReasons | None = None,
        name: str | None = None
    ) -> ValidationReasons:

        if reasons is None:
            reasons: ValidationReasons = {}

        if not location:
            self._location.status_action.setVisible(True)
            self._location.status_action.setToolTip(_("This is empty"))
            reasons["missing_info"] = True
        elif not osp.isdir(location):
            self._location.status_action.setVisible(True)
            self._location.status_action.setToolTip(
                _("This directory doesn't exist")
            )
            reasons["no_location"] = True
        elif not is_writable(location):
            self._location.status_action.setVisible(True)
            self._location.status_action.setToolTip(
                _("This directory is not writable")
            )
            reasons["location_not_writable"] = True
        elif name is not None:
            project_path = osp.join(location, name)
            if osp.isdir(project_path):
                reasons["location_exists"] = True
        else:
            spyproject_path = osp.join(location, '.spyproject')
            if osp.isdir(spyproject_path):
                self._location.status_action.setVisible(True)
                self._location.status_action.setToolTip(
                    _("You selected a Spyder project")
                )
                reasons["spyder_project_exists"] = True

        return reasons

    def _compose_failed_validation_text(self, reasons: ValidationReasons):
        n_reasons = list(reasons.values()).count(True)
        prefix = "- " if n_reasons > 1 else ""
        suffix = "<br>" if n_reasons > 1 else ""

        text = ""
        if reasons.get("location_exists"):
            text += (
                prefix
                + _(
                    "The directory you selected for this project already "
                    "exists."
                )
                + suffix
            )
        elif reasons.get("spyder_project_exists"):
            text += (
                prefix
                + _("This directory is already a Spyder project.")
                + suffix
            )
        elif reasons.get("location_not_writable"):
            text += (
                prefix
                + _(
                    "You don't have write permissions in the location you "
                    "selected."
                )
                + suffix
            )
        elif reasons.get("no_location"):
            text += (
                prefix
                + _("The location you selected doesn't exist.")
                + suffix
            )

        if reasons.get("missing_info"):
            text += (
                prefix
                + _("There are missing fields on this page.")
            )

        return text

class ExistingDirectoryPage(BaseProjectPage):
    """Existing directory project page."""

    LOCATION_TEXT = _("Project path")
    LOCATION_TIP = _("Select the directory to use for the project")

    def get_name(self):
        return _("Existing directory")

    def get_icon(self):
        return self.create_icon("DirClosedIcon")

    def setup_page(self):
        description = QLabel(
            _("Create a Spyder project in an existing directory")
        )
        description.setWordWrap(True)
        description.setFont(self._description_font)

        layout = QVBoxLayout()
        layout.addWidget(description)
        layout.addSpacing(5 * AppStyle.MarginSize)
        layout.addWidget(self._location)
        layout.addSpacing(7 * AppStyle.MarginSize)
        layout.addWidget(self._validation_label)
        layout.addStretch()
        self.setLayout(layout)

    @property
    def project_location(self):
        return osp.normpath(self._location.textbox.text())

    def validate_page(self):
        # Clear validation state
        self._validation_label.setVisible(False)
        self._location.status_action.setVisible(False)

        # Avoid using "." as location, which is the result of os.normpath("")
        location_text = self._location.textbox.text()
        location = osp.normpath(location_text) if location_text else ""

        # Perform validation
        reasons = self._validate_location(location)
        if reasons:
            self._validation_label.set_text(
                self._compose_failed_validation_text(reasons)
            )
            self._validation_label.setVisible(True)

        return False if reasons else True


# =============================================================================
# ---- Dialog
# =============================================================================
class ConfigDialog(QDialog, SpyderFontsMixin):
    """Project settings dialog."""

    def __init__(self, parent):
        """Project settings dialog."""
        QDialog.__init__(self, parent=parent)
        self.project_data = {}

        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )
        self.setWindowTitle(_('Project settings'))
        self.setWindowIcon(ima.icon("project_new"))

        self._page = ExistingDirectoryPage(self)
        self._page._location.textbox.setText(parent.current_active_project.config.get('workspace', 'interpreter')
)

        button = QPushButton(_('Save'))
        button.clicked.connect(self.accept)

        button1 = QPushButton(_('Cancel'))
        button1.clicked.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self._page)
        layout.addWidget(button)
        layout.addWidget(button1)
        self.setLayout(layout)
    

def test():
    """Local test."""
    from spyder.utils.qthelpers import qapplication
    from spyder.config.base import running_in_ci

    app = qapplication()

    dlg = ConfigDialog(None)

    if not running_in_ci():
        from spyder.utils.stylesheet import APP_STYLESHEET
        app.setStyleSheet(str(APP_STYLESHEET))

    dlg.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    test()
