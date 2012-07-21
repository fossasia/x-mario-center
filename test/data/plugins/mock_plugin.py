
import softwarecenter.plugin

class MockPlugin(softwarecenter.plugin.Plugin):
    """ mock plugin """

    def init_plugin(self):
            self.i_am_happy = True
