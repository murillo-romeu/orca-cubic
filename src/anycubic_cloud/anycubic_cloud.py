# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "paho-mqtt>=2.0.0",
#     "requests>=2.31.0",
# ]
# [tool.orcaslicer.plugin]
# name = "anycubic-cloud"
# version = "1.0.0"
# description = "Native Anycubic Cloud Connection for OrcaSlicer"
# author = "Anycubic & OrcaSlicer Community"
# ///

"""
Anycubic Cloud Plugin for OrcaSlicer.
Enables native connection, status monitoring, and cloud print dispatching for Anycubic printers
(such as Kobra 3, Kobra X, Kobra S1, and Kobra series) directly inside OrcaSlicer.
"""

import sys
import os

# Ensure local module directory is in sys.path
plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

import orca
from agent import AnycubicPrinterAgent


@orca.plugin
class AnycubicCloudPlugin(orca.base):
    def register_capabilities(self):
        """Register the Anycubic Cloud Printer Agent into OrcaSlicer."""
        orca.register_capability(AnycubicPrinterAgent)
        try:
            orca.request_permissions(
                network=["mqtt-universe.anycubic.com", "cloud-universe.anycubic.com", "api.anycubic.com"]
            )
        except Exception:
            pass
