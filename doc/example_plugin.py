
from gi.repository import GObject
import sys

import softwarecenter.plugin


class ExamplePlugin(softwarecenter.plugin.Plugin):
    """ example plugin that will hide the exhibits banner """

    def _try_to_hide_banner(self):
        if not self.app.available_pane.view_initialized:
            # wait for the pane to fully initialize
            return True
        self.app.available_pane.cat_view.vbox.get_children()[0].hide()
        return False

    def init_plugin(self):
        sys.stderr.write("init_plugin\n")

        GObject.timeout_add(100, self._try_to_hide_banner)
