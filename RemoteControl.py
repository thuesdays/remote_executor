import subprocess
from PyQt5.QtWidgets import QMainWindow, QApplication
import sys
from PyQt5 import uic
from lya import lya
from tasks import Task, PyQtEngine

engine = PyQtEngine()
form_class = uic.loadUiType("remote.ui")[0]


class MyWindowClass(QMainWindow, form_class):
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.setupUi(self)
        self.execute_btn.clicked.connect(self.execute_btn_clicked)
        operation = ['restart explorer']
        self.operations.addItems(operation)
        self.stagings = ['windows_7_x64', 'windows_7_x64_2']

    def run(self, host_string, command):
        cmd = ["ssh", host_string]
        cmd.extend(command)
        if self.output.toPlainText() != '':
            self.output.setPlainText(self.output.toPlainText() + '\r\n%s : %s' % (host_string, cmd))
        else:
            self.output.setPlainText('%s : %s' % (host_string, cmd))
        ssh = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = ssh.stdout.readlines()
        if not result:
            data = ssh.stderr.readlines()
            self.output.setPlainText(self.output.toPlainText() + '\r\n%s' % data[0].decode('cp866'))
        else:
            self.output.setPlainText(self.output.toPlainText() + '\r\n%s' % result[0].decode('cp866'))

    @engine.async
    def execute_btn_clicked(self, *args):
        try:
            for stg in self.stagings:
                cfg = lya.AttrDict.from_yaml('conf/' + stg + '.yaml')
                host_string = '%s@%s' % (cfg.wgc.user, cfg.ip)
                if self.operations.currentText() == 'restart explorer':
                    cmd = ['taskkill', '/f', '/im', 'explorer.exe']
                    yield Task(self.run, host_string, cmd)
                    cmd = ['/cygdrive/c/Windows/explorer.exe']
                    yield Task(self.run, host_string, cmd)
        except Exception as e:
            self.output.setPlainText(self.output.toPlainText() + '\r\n%s' % e)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    engine.main_app = app
    myWindow = MyWindowClass(None)
    myWindow.show()
    myWindow.setFixedSize(myWindow.size())
    app.exec_()
