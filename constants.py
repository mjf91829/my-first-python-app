"""Shared constants for the application."""

from typing import Literal


PROJECT = "project"
AREA = "area"
TASK = "task"


ParaType = Literal[PROJECT, AREA]
LinkableType = Literal[PROJECT, AREA, TASK]