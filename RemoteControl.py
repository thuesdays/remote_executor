from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget
import sys
from PyQt5 import uic
import chardet
from lya import lya
from paramiko import SSHClient, SSHException
from tasks import Task, PyQtEngine

engine = PyQtEngine()
form_class = uic.loadUiType("remote.ui")[0]


class MyWindowClass(QMainWindow, form_class):
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.setupUi(self)
        self.execute_btn.clicked.connect(self.execute_btn_clicked)
        self.connect_ssh.clicked.connect(self.connect_ssh_clicked)
        operation = ['restart explorer']
        self.operations.addItems(operation)
        self.execution.installEventFilter(self)
        self.sessions = {}
        self.hosts = {}

    def active_stg(self):
        stg = []
        for index in range(self.stagings.count()):
            if self.stagings.item(index).checkState() == Qt.Checked:
                stg.append(self.stagings.item(index).text())
        return stg

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress:
            if ev.key() == Qt.Key_Return:
                text = self.execution.toPlainText().split('\n')
                self.execute(text[-1])
                return self.execution.event(ev)
        QWidget.eventFilter(self, obj, ev)
        return False

    def run(self, stg, command):
        cmd = ''
        if isinstance(command, list):
            for i in command:
                cmd += i + ' '
        if isinstance(command, tuple):
            for i in command:
                cmd += i + ' '
        if isinstance(command, str):
            cmd = command

        if self.output.toPlainText() != '':
            self.output.setPlainText(self.output.toPlainText() + '\r\n%s : %s' % (self.hosts[stg], cmd))
        else:
            self.output.setPlainText('%s : %s' % (self.hosts[stg], cmd))
        stdin, stdout, stderr = self.sessions[stg].exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        output = ''
        error = ''
        stdin.flush()
        stdin.channel.shutdown_write()
        try:
            for s in stdout.readlines():
                output += s
            for s in stderr.readlines():
                error += s
            if error != '':
                self.output.setPlainText(
                    self.output.toPlainText() + '\r\n%s\r\nExit code %s' % (error.encode().decode('cp866'), exit_status))
            if output:
                self.output.setPlainText(
                    self.output.toPlainText() + '\r\n%s' % (output.encode().decode('cp866')))
        except UnicodeDecodeError:
            self.output.setPlainText(self.output.toPlainText() + '\r\nExit code %s' % exit_status)

    @engine.async
    def execute_btn_clicked(self, *args):
        try:
            for stg in self.active_stg():
                if self.operations.currentText() == 'restart explorer':
                    cmd = ['taskkill', '/f', '/im', 'explorer.exe']
                    yield Task(self.run, stg, cmd)
                    cmd = ['/cygdrive/c/Windows/explorer.exe']
                    yield Task(self.run, stg, cmd)
        except Exception as e:
            self.output.setPlainText(self.output.toPlainText() + '\r\n%s' % e)

    def connect_ssh_clicked(self, *args):
        self.sessions = {}
        for stg in self.active_stg():
            cfg = lya.AttrDict.from_yaml('conf/' + stg + '.yaml')
            user = cfg.wgc.user
            ip = cfg.ip
            password = str(cfg.wgc.password)
            host_string = '%s@%s' % (user, ip)
            client = SSHClient()
            client.load_system_host_keys('.ssh\\known_hosts')
            try:
                client.connect(ip, username=user, password=password)
                self.sessions[stg] = client
                self.output.setPlainText(self.output.toPlainText() + '\r\n%s successfully connection' % host_string)
            except SSHException as e:
                self.output.setPlainText(self.output.toPlainText() + '\r\n%s' % e)

            self.hosts[stg] = host_string

    @engine.async
    def execute(self, *args):
        try:
            for stg in self.active_stg():
                yield Task(self.run, stg, args)
        except Exception as e:
            self.output.setPlainText(self.output.toPlainText() + '\r\n%s' % e)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    engine.main_app = app
    myWindow = MyWindowClass(None)
    myWindow.show()
    myWindow.setFixedSize(myWindow.size())
    app.exec_()
