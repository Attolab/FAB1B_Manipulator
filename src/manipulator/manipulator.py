from pymodaq.daq_utils import gui_utils as gutils
from pymodaq.daq_utils import daq_utils as utils

from pyqtgraph.parametertree import Parameter, ParameterTree
from pymodaq.daq_utils.parameter import utils as putils
import pymodaq.daq_utils.parameter.pymodaq_ptypes as pymodaq_ptypes

from qtpy import QtWidgets, QtCore

from PyQt5 import uic
import pyqtgraph as pg

import keyboard
import sys, os
import pandas as pd
import numpy as np

from pymodaq.daq_utils.config import get_set_config_path

from manipulator import icons_resources

config = utils.load_config()
logger = utils.set_logger(utils.get_module_name(__file__))

def popup_message(title, text):
    msg = QtWidgets.QMessageBox()
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
    msg.setIcon(QtWidgets.QMessageBox.Warning)
    return msg.exec_()


class TableModelPosition(gutils.TableModel):
    def __init__(self, data, axes_name=None, editable=None, **kwargs):
        if axes_name is None:
            if 'header' in kwargs:  # when saved as XML the header will be saved and restored here
                axes_name = [h for h in kwargs['header']]
                kwargs.pop('header')
            else:
                raise Exception('Invalid header')

        header = [name for name in axes_name]
        if editable is None:
            editable = [True for name in axes_name]
        super().__init__(data, header, editable=editable, **kwargs)

    def load_txt(self):
        print('bla')

    def set_data_all(self, data):
        self.clear()
        for row in data:
            self.insert_data(self.rowCount(self.index(-1, -1)), row)

    def remove_row(self, row):
        self.removeRows(row, 1, self.index(-1, -1))


class Manipulator_Interface(QtWidgets.QWidget):
    def __init__(self):
        super(Manipulator_Interface, self).__init__()
        uic.loadUi(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'manipulator.ui'), self)

class New_Position_Dialog(QtWidgets.QWidget):
    def __init__(self):
        super(New_Position_Dialog, self).__init__()
        uic.loadUi(os.path.join(os.path.dirname(os.path.abspath(__file__)),'new_position_dialog.ui'), self)
        self.pushButton_2.clicked.connect(self.hide)


class Manipulator(gutils.CustomApp):
    # list of dicts enabling the settings tree on the user interface
    params = [
        {'title': 'Main settings:', 'name': 'main_settings', 'type': 'group', 'children': [
            {'title': 'Refresh time (ms)', 'name': 'refresh_time', 'type': 'int', 'value': 100},
            {'title': 'Save current position', 'name': 'save_current', 'type': 'bool_push'},
        ]},
    ]

    def __init__(self, dockarea, dashboard):
        super().__init__(dockarea, dashboard)

        # Clean up module manager
        self.modules_manager.settings.child('data_dimensions').hide()
        self.modules_manager.settings.child('actuators_positions').hide()
        self.modules_manager.settings.child('modules', 'detectors').hide()
        self.modules_manager.settings.child('det_done').hide()

        self.position_tree = None
        self.table_model = None
        self.table_view = None

        self.position_folder = get_set_config_path(config_name='manipulator')
        self.new_position_dialog = New_Position_Dialog()

        self.setup_position_dock()
        self.setup_ui()
        self.load_positions()
        self.update_position_plot()

        self.timerPos = self.startTimer(100)


    def setup_position_dock(self):
        params = [
            {'title': 'Positions', 'name': 'tabular_table', 'type': 'table_view',
             'delegate': gutils.SpinBoxDelegate, 'menu': True}]
        self.positions = Parameter.create(name='settings', type='group', children=params)
        self.position_tree = ParameterTree()
        self.position_tree.setParameters(self.positions, showTop=False)

        self.table_model = TableModelPosition([['Default', 10., 12.]], ['Name', 'X', 'Y'], editable= [False, True, True])
        self.table_view = putils.get_widget_from_tree(self.position_tree, pymodaq_ptypes.TableViewCustom)[0]
        self.positions.child('tabular_table').setValue(self.table_model)

    def load_positions(self):
        self.file_list = []
        files = os.listdir(self.position_folder)

        # If there are no files yet
        if files == []:
            fname = 'default.txt'
            self.position_df = pd.DataFrame(self.table_model.get_data_all())
            self.position_df.columns = ['Name', 'X', 'Y']
            self.position_df.to_csv(os.path.join(self.position_folder, fname), index=False)

            self.file_list.append(fname)

        # Otherwise we add them to the list
        else:
            for file in files:
                if file.endswith(".txt"):
                    self.file_list.append(file)
        self.file_list_combo.addItems(self.file_list)
        self.current_file = self.file_list_combo.currentText()

        # Then empty the tree
        self.table_model.clear()
        # And load it
        self.position_df = pd.read_csv(os.path.join(self.position_folder, self.current_file))
        data = self.position_df.to_numpy().tolist()
        self.table_model.set_data_all(data)


    def setup_docks(self):
        """
        to be subclassed to setup the docks layout
        for instance:

        self.docks['ADock'] = gutils.Dock('ADock name)
        self.dockarea.addDock(self.docks['ADock"])
        self.docks['AnotherDock'] = gutils.Dock('AnotherDock name)
        self.dockarea.addDock(self.docks['AnotherDock"], 'bottom', self.docks['ADock"])

        See Also
        ########
        pyqtgraph.dockarea.Dock
        """

        # Module manager
        #------------------------------------------
        self.docks['modmanager'] = gutils.Dock('Module Manager', size=(1, 1), autoOrientation=False)
        self.dockarea.addDock(self.docks['modmanager'])  # add dock

        self.modules_manager.settings_tree.setMinimumWidth(400)
        self.docks['modmanager'].addWidget(self.modules_manager.settings_tree)

        # Manipulator
        #------------------------------------------

        self.manipulator_interface = Manipulator_Interface()
        self.docks['manipulator'] = gutils.Dock('Manipulator', size=(1, 1), autoOrientation=False)
        self.dockarea.addDock(self.docks['manipulator'], 'bottom', self.docks['modmanager'])
        self.docks['manipulator'].addWidget(self.manipulator_interface)
        self.manipulator_interface.stepsizeSpinbox_3.setValue(1)
        self.manipulator_interface.stepsizeSpinbox.setValue(0)
        self.manipulator_interface.stepsizeSpinbox_2.setValue(0)
        self.manipulator_interface.stepsizeSpinbox_5.setValue(50.8)
        self.manipulator_interface.stepsizeSpinbox_4.setValue(25.4)

        self.manipulator_interface.stepsizeSpinbox_6.setValue(100)

        # Positions
        #------------------------------------------

        self.docks['positions'] = gutils.Dock('Saved Positions')
        self.dockarea.addDock(self.docks['positions'], 'right')

        pos_widget = QtWidgets.QWidget()
        pos_widget.setLayout(QtWidgets.QVBoxLayout())
        pos_widget.layout().addWidget(self.position_tree)
        self.new_position_pb = QtWidgets.QPushButton('Create new position')
        self.new_position_pb.setFixedWidth(200)
        self.new_position_pb.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        pos_widget.layout().addWidget(self.new_position_pb)

        files = QtWidgets.QWidget()
        files.setLayout(QtWidgets.QHBoxLayout())
        files.layout().addWidget(QtWidgets.QLabel('Available files:'))
        self.file_list_combo = QtWidgets.QComboBox()
        files.layout().addWidget(self.file_list_combo)
        files.setMinimumHeight(40)
        files.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)

        self.docks['positions'].addWidget(pos_widget)
        self.docks['positions'].addWidget(files)
        self.docks['viewer1D'] = gutils.Dock('Viewers')
        self.dockarea.addDock(self.docks['viewer1D'],  'bottom', self.docks['positions'])

        # self.docks['viewer2D'] = gutils.Dock('Viewers')
        # self.dockarea.addDock(self.docks['viewer2D'], 'bottom', self.docks['positions'])

        # Viewer
        #--------

        self.plot = pg.plot()
        n = 300
        self.scatter = pg.ScatterPlotItem(
            size=10, brush=pg.mkBrush(255, 50, 50, 120))
        self.spots = [{'pos': [0, 0], 'data': 'Current Position', 'size': 25, 'symbol':'+'}]
        self.scatter.addPoints(self.spots)
        self.scatter.sigClicked.connect(self.scatter_clicked)
        self.plot.addItem(self.scatter)
        self.plot.setRange(xRange=(0, 50.8), yRange=(0, 25.4))
        self.docks['viewer1D'].addWidget(self.plot)

        # layout.addWidget(plot, 0, 1, 3, 1)
        # widg1 = QtWidgets.QWidget()
        # self.viewer2D = Viewer2D(widg1)
        # self.docks['viewer2D'].addWidget(widg1)


        # self.docks['settings'] = gutils.Dock('Settings')
        # self.dockarea.addDock(self.docks['settings'], 'right', self.docks['positions'])
        # self.docks['settings'].addWidget(self.settings_tree)


    def update_position_plot(self):
        current_pos = self.spots[0]
        self.spots = []
        for position in self.table_model.get_data_all():
            name, x, y = position
            self.spots.append({'pos': [x, y], 'data': name, 'size': 15, 'symbol':'o', 'brush':(50,50,200,200)})

        self.spots.insert(0, current_pos)
        self.scatter.setData(self.spots, hoverable=True, hoverSize = 25, tip=self.tooltip)

    def tooltip(self,x, y, data):
        return data

    def scatter_clicked(self, plot, points):
        x = points[0].pos()[0]
        y = points[0].pos()[1]
        name = points[0].data()

        self.move_manipulator_abs(x, y, name)

    def position_table_clicked(self, index):
        if index.column() == 0:  # User double-clicked on name
            name = self.table_model.get_data(index.row(), 0)
            x = self.table_model.get_data(index.row(), 1)
            y = self.table_model.get_data(index.row(), 2)

            self.move_manipulator_abs(x, y, name)

    def setup_menu(self):
        '''
        to be subclassed
        create menu for actions contained into the self.actions_manager, for instance:

        For instance:

        file_menu = self.menubar.addMenu('File')
        self.actions_manager.affect_to('load', file_menu)
        self.actions_manager.affect_to('save', file_menu)

        file_menu.addSeparator()
        self.actions_manager.affect_to('quit', file_menu)
        '''
        pass

    def update_saved_positions(self):
        self.update_position_plot()

        self.position_df = pd.DataFrame(self.table_model.get_data_all())
        self.position_df.columns = ['Name', 'X', 'Y']
        self.position_df.to_csv(os.path.join(self.position_folder, self.current_file), index=False)

    def open_new_position_dialog(self):
        self.new_position_dialog.textEdit.setText('')
        self.new_position_dialog.stepsizeSpinbox_3.setValue(self.x_pos.value())
        self.new_position_dialog.stepsizeSpinbox_2.setValue(self.y_pos.value())
        self.new_position_dialog.show()

    def create_new_position(self):
        self.new_position_dialog.hide()
        name = self.new_position_dialog.textEdit.toPlainText()
        x = self.new_position_dialog.stepsizeSpinbox_3.value()
        y = self.new_position_dialog.stepsizeSpinbox_2.value()
        self.table_model.insert_data(self.table_model.rowCount(self.table_model.index(-1, -1)), [name, x, y])
        self.update_saved_positions()

    def keyboardEventReceived(self, event):
        if event.event_type == 'down':
            if event.name == 'droite':
                event.name = 'right'
            if event.name == 'gauche':
                event.name = 'left'
            if event.name == 'haut':
                event.name = 'up'
            if event.name == 'bas':
                event.name = 'down'

            if event.name in ['right', 'left', 'up', 'down']:
                self.move_manipulator(event.name, self.manipulator_interface.stepsizeSpinbox_3.value())

    def connect_things(self):
        self.x_pos = self.manipulator_interface.doubleSpinBox
        self.y_pos = self.manipulator_interface.doubleSpinBox_2

        self.x_pos.editingFinished.connect(self.manual_move)
        self.y_pos.editingFinished.connect(self.manual_move)

        self.manipulator_interface.pushButton.clicked.connect(lambda: self.move_manipulator('right', self.manipulator_interface.stepsizeSpinbox_3.value()))
        self.manipulator_interface.pushButton_4.clicked.connect(lambda: self.move_manipulator('left', self.manipulator_interface.stepsizeSpinbox_3.value()))
        self.manipulator_interface.pushButton_2.clicked.connect(lambda: self.move_manipulator('up', self.manipulator_interface.stepsizeSpinbox_3.value()))
        self.manipulator_interface.pushButton_3.clicked.connect(lambda: self.move_manipulator('down', self.manipulator_interface.stepsizeSpinbox_3.value()))

        self.manipulator_interface.checkBox.toggled.connect(self.listenToKeyboard)
        self.manipulator_interface.stepsizeSpinbox_6.valueChanged.connect(self.change_refresh_time)
        self.manipulator_interface.stepsizeSpinbox.valueChanged.connect(self.change_plot_axis)
        self.manipulator_interface.stepsizeSpinbox_5.valueChanged.connect(self.change_plot_axis)
        self.manipulator_interface.stepsizeSpinbox_2.valueChanged.connect(self.change_plot_axis)
        self.manipulator_interface.stepsizeSpinbox_4.valueChanged.connect(self.change_plot_axis)

        self.new_position_pb.clicked.connect(self.open_new_position_dialog)
        self.new_position_dialog.pushButton.clicked.connect(self.create_new_position)

        self.table_view.doubleClicked.connect(self.position_table_clicked)

        self.table_view.valueChanged.connect(self.update_saved_positions)
        self.table_view.add_data_signal[int].connect(self.open_new_position_dialog)
        self.table_view.remove_row_signal[int].connect(self.remove_position)
        # self.table_view.load_data_signal.connect(self.table_model.load_txt)
        # self.table_view.save_data_signal.connect(self.table_model.save_txt)

    def remove_position(self, row):
        self.table_model.remove_row(row)
        self.update_saved_positions()

    def move_manipulator(self, direction, step):
        actuators = self.modules_manager.actuators
        if direction == 'right':
            actuators[0].move_Rel(step)
        elif direction == 'left':
            actuators[0].move_Rel(-step)
        elif direction == 'up':
            actuators[1].move_Rel(step)
        elif direction == 'down':
            actuators[1].move_Rel(-step)

    def move_manipulator_abs(self, x, y, name):

        message = 'Do you want to move to \''+name+'\' position ('+str(x)+' ,'+str(y)+') ?'
        reply = popup_message('Move confirmation', message)

        if reply == QtWidgets.QMessageBox.Yes:
            actuators = self.modules_manager.actuators
            if len(actuators) == 0:
                popup_message('No actuator', 'Select XY actuators first!')
            else:
                actuators[0].move_Abs(x)
                actuators[1].move_Abs(y)

    def manual_move(self):
        x = self.x_pos.value()
        y = self.y_pos.value()
        actuators = self.modules_manager.actuators
        if len(actuators) == 0:
            popup_message('No actuator', 'Select XY actuators first!')
        else:
            actuators[0].move_Abs(x)
            actuators[1].move_Abs(y)

    def change_refresh_time(self, time):
        self.killTimer(self.timerPos)
        self.timerPos = self.startTimer(time)

    def change_plot_axis(self):
        x1 = self.manipulator_interface.stepsizeSpinbox.value()
        x2 = self.manipulator_interface.stepsizeSpinbox_5.value()
        y1 = self.manipulator_interface.stepsizeSpinbox_2.value()
        y2 = self.manipulator_interface.stepsizeSpinbox_4.value()
        self.plot.setRange(xRange=(x1, x2), yRange=(y1, y2))


    def timerEvent(self, event):
        """
          Timer event to periodically check the position
        """
        actuators = self.modules_manager.actuators
        if len(actuators) > 0:
            x = actuators[0].current_position
            self.x_pos.setValue(x)
        if len(actuators) > 1:
            y = actuators[1].current_position
            self.y_pos.setValue(y)
            self.spots[0]['pos'] = [x ,y]
            self.scatter.setData(self.spots)

    def listenToKeyboard(self, enable):
        if enable:
            # on_press returns a hook that can be used to "disconnect" the callback
            # function later, if required
            self.hook = keyboard.on_press(self.keyboardEventReceived)
        else:
            keyboard.unhook(self.hook)

    def param_deleted(self, param):
        ''' to be subclassed for actions to perform when one of the param in self.settings has been deleted

        Parameters
        ----------
        param: (Parameter) the parameter that has been deleted
        '''
        raise NotImplementedError

    def child_added(self, param):
        ''' to be subclassed for actions to perform when a param  has been added in self.settings

        Parameters
        ----------
        param: (Parameter) the parameter that has been deleted
        '''
        raise NotImplementedError

    def setup_actions(self):
        pass

    def show_data(self, data_all):
        self.viewer1D.show_data(data_all)
        # self.viewer2D.setImage(*data2D[:min(3, len(data2D))])




def main():
    import sys
    from pymodaq.dashboard import DashBoard
    from pathlib import Path
    app = QtWidgets.QApplication(sys.argv)
    mainwindow = QtWidgets.QMainWindow()


    dockarea = gutils.DockArea()
    mainwindow.setCentralWidget(dockarea)

    #  init the dashboard
    mainwindow_dash = QtWidgets.QMainWindow()
    area_dash = gutils.DockArea()
    mainwindow_dash.setCentralWidget(area_dash)
    dashboard = DashBoard(area_dash)
    file = Path(utils.get_set_preset_path()).joinpath("manipulator_mock.xml")
    if file.exists():
        dashboard.set_preset_mode(file)
    else:
        msgBox = QtWidgets.QMessageBox()
        msgBox.setText(f"The default file specified in the configuration file does not exists!\n"
                       f"{file}\n"
                       f"Impossible to load the DAQ_Scan Module")
        msgBox.setStandardButtons(msgBox.Ok)
        ret = msgBox.exec()

    prog = Manipulator(dockarea, dashboard)

    mainwindow.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()


