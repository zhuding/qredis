import os
import re
import pprint
import collections

import redis

from .qt import Qt, QMainWindow, QApplication, QDialog, QMdiSubWindow, QLabel, \
                QTreeWidgetItem, QMessageBox, QIcon, QFont, ui_loadable


_this_dir = os.path.dirname(__file__)
_res_dir = os.path.join(_this_dir, 'images')
_redis_icon = os.path.join(_res_dir, 'redis_logo.png')
_key_icon = os.path.join(_res_dir, 'key.png')


def redis_strs(redis):
    info = redis.connection_pool.connection_kwargs
    if 'path' in info: # unix socket
        addr = info['path']
    elif 'host' in info:
        addr = '{0}:{1}'.format(info['host'], info['port'])
    else:
        addr = '???'
    return 'Redis({0})'.format(addr), 'db={0}'.format(info['db']), '', ''

#key, type, TTL, value

def fill_item(item, data, max_expand_level=1, level=0):
    for key, value in data.items():
        child = Item(key, value, item)
        children = value['children']
        fill_item(child, children, level=level+1)

    if level < max_expand_level:
        item.setExpanded(True)


class RedisItem(QTreeWidgetItem):

    SplitRE = re.compile("\:|\.")

    def __init__(self, redis, parent=None):
        super(RedisItem, self).__init__(parent, redis_strs(redis))
        self.setIcon(0, QIcon(_redis_icon))
        self.setToolTip(0, 'Double click to update')
        self.redis = redis

    def update(self):
        self.takeChildren()
        root_children = collections.OrderedDict()
        for key in sorted(self.redis.keys()):
            children = root_children
            for sub_key in self.SplitRE.split(key):
                item = children.setdefault(sub_key, collections.OrderedDict(type='', children={}))
                children = item['children']
            item['key'] = key
        fill_item(self, root_children)
        self.setExpanded(True)

class Item(QTreeWidgetItem):

    def __init__(self, key, data, parent):
        super(Item, self).__init__(parent, [key] + 3*[''])
        self.setToolTip(0, 'Double click to update')
        if 'key' in data:
            icon = QIcon(_key_icon)
        else:
            icon = QIcon.fromTheme('folder')
        self.setIcon(0, icon)
        self.setFont(3, QFont("Monospace"))
        self.__data = data

    @property
    def root(self):
        root = self
        while root.parent():
            root = root.parent()
        return root

    @property
    def redis(self):
        return self.root.redis

    def update(self):
        key = self.__data.get('key')
        if key is None:
            return
        redis = self.redis
        dtype = redis.type(key)
        ttl = redis.ttl(key)
        self.setText(1, dtype)
        self.setText(2, str(ttl or ''))
        value = None
        if dtype == 'string':
            value = redis.get(key)
        elif dtype == 'hash':
            value = redis.hgetall(key)
        elif dtype == 'list':
            value = redis.lrange(key, 0, -1)
        elif dtype == 'set':
            value = redis.smembers(key)
        elif dtype == 'none':
            self.parent().removeChild(self)
            return
        if value is not None:
            self.setText(3, pprint.pformat(value))
        self.setExpanded(True)

@ui_loadable
class RedisWindow(QMainWindow):

    def __init__(self, parent=None):
        super(RedisWindow, self).__init__(parent)
        self.load_ui()
        self.setWindowIcon(QIcon(_redis_icon))
        ui = self.ui
        ui.about_dialog = AboutDialog()
        ui.quit_action.triggered.connect(QApplication.quit)
        ui.about_action.triggered.connect(lambda: ui.about_dialog.exec_())
        ui.db_tree.currentItemChanged.connect(self.__on_item_changed)
        #ui.db_tree.itemDoubleClicked.connect(self.__on_update_item)
        ui.db_tree.itemActivated.connect(self.__on_update_item)

    def __on_item_changed(self, current, previous):
        pass

    def __on_update_item(self, item, column):
        print 'update'
        try:
            item.update()
        except redis.ConnectionError as ce:
            QMessageBox.critical(self, "Connection Error", str(ce))

    def add(self, redis):
        RedisItem(redis, self.ui.db_tree)


class AboutDialog(QDialog):
    """Create the necessary elements to show helpful text in a dialog."""

    def __init__(self, parent=None):
        """Display a dialog that shows application information."""
        super(AboutDialog, self).__init__(parent)
        self.setWindowTitle('About')


def main():
    import sys
    #from bliss.config.conductor.client import get_cache
    #r = get_cache()
    import redis
    r = redis.Redis()
    application = QApplication(sys.argv)
    window = RedisWindow()
    window.add(r)
    window.show()
    sys.exit(application.exec_())
