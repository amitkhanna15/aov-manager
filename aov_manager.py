import os
import sys
import collections

from PySide import QtCore
from PySide import QtGui
from PySide.QtCore import QObject, Slot
from PySide.QtUiTools import QUiLoader
from PySide.QtGui import QApplication, QMainWindow, QMessageBox
from PySide.QtUiTools import *
from PySide.QtCore import *
from PySide.QtGui import *

import pyside_houdini
from UiLoader import UiLoader
import hou


__version__ = '1.0'
__author__ = 'amit khanna'
SCRIPT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))

app = QtGui.QApplication.instance()
if app is None:
    app = QtGui.QApplication(['houdini'])



class AovManager(QtGui.QMainWindow):

    def __init__(self, name='AOVMAN', parent=None, buildthumbs=False):
        super(AovManager, self).__init__()

        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setStyleSheet('QMainWindow, QScrollArea, QWidget {background-color:#333;} \
            QListWidget { color:#fff; background-color: #333; } \
            QTreeView { color:#fff; background-color: #333; } \
            QHeaderView::section { background-color:#505050; color: white; padding: 1px 4px;border: 1px solid #6c6c6c;}\
            QMenu { color:#fff;} \
            QMenu::item:selected{ background-color: #444; } \
            QPushButton {height:30px; color: #fff; background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1 stop:0 #555, stop:1 #333); border: 1px solid #252525;} \
            QPushButton:pressed { background-color: #222; border-style: inset; } \
            QPushButton:hover { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1 stop:0 #545454, stop:1 #383838);} \
            QCheckBox, QStatusBar { color:#fff; background-color: #333; } \
            ')



        self.out = '/out/'
        self.currRop = []
        self.listOfRops = []
        self.ropDisp = True
        self.userSettings = []
        self.__aovList = []
        self.copiedImagePlanes = []
        self.ipDict = collections.OrderedDict()
        self.ipData = []
        self.imagePlaneParms = ['vm_disable_plane', 'vm_variable_plane', 'vm_vextype_plane', 'vm_channel_plane',
        'vm_usefile_plane','vm_filename_plane', 'vm_quantize_plane', 'vm_sfilter_plane', 'vm_pfilter_plane',
        'vm_componentexport', 'vm_lightexport', 'vm_lightexport_scope', 'vm_lightexport_select',
        'vm_excludedcm_plane', 'vm_gamma_plane', 'vm_gain_plane', 'vm_dither_plane', 'vm_whitepoint_plane']


        # ui loader
        self.ui = loadUi(os.path.join(SCRIPT_DIRECTORY, 'ui/aov-manager.ui'), self)
        
        self.statusBar = self.ui.findChild(QtGui.QStatusBar, "statusbar")
        self.ropList = self.ui.findChild(QtGui.QListWidget, "listWidget_rop")
        self.aovList = self.ui.findChild(QtGui.QTreeView, "treeView_aov")

        self.renderBtn = self.ui.findChild(QtGui.QPushButton, "pushButton")
        self.halfResCheck = self.ui.findChild(QtGui.QCheckBox, "checkBox")
        self.tglDispChkBx = self.ui.findChild(QtGui.QCheckBox, "checkBox_dd")

        self.ropList.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ropList.customContextMenuRequested.connect(self.ropContextMenu)

        self.aovList.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.aovList.customContextMenuRequested.connect(self.aovContextMenu)
        self.model = QtGui.QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['VEX Variable', 'Channel Name', 'VEX Type'])
        self.rootItem = self.model.invisibleRootItem()

        self.populateRopList()
        self.ropList.currentItemChanged.connect(self.getCurrentRop)
        self.ropList.doubleClicked.connect(self.selectRop)
        self.renderBtn.clicked.connect(self.render)
        self.tglDispChkBx.clicked.connect(self.toggleDisplacements)
        self.aovList.clicked.connect(self.aovListClicked)

        

    def addRemoveRopDisplacement(self):
        print("WORKING")

    '''
        Close event.
    '''
    def closeEvent(self, event):
        self.closeApp()
    

    '''
        Run on ui exit.
    '''
    def closeApp(self):
        self.revertUserSettings()
        self.close()
    

    '''
        List all rops.
    '''
    def populateRopList(self):
        typeCategory = hou.nodeType(hou.ropNodeTypeCategory(), "ifd")
        rops = typeCategory.instances()
        
        for r in rops:
            self.listOfRops.append(r)
            self.ropList.addItem(r.name())

        self.userSettings = self.getUserSettings()
        return self.listOfRops



    '''
        get existing user settings in the following format
        [<hou.RopNode>, {'trange', 0, 'override_camerares', 1, 'res_fraction', '0.5'}]
    '''
    def getUserSettings(self):
        for rop in self.listOfRops:
            self.userSettings.append([rop, {'trange': rop.parm('trange').eval(), 
                                            'override_camerares' : rop.parm('override_camerares').eval(), 
                                            'res_fraction' : rop.parm('res_fraction').eval()
                                            }])

        return self.userSettings



    '''
        Set rop settings back to original user settings
    '''
    def revertUserSettings(self):
        us = self.userSettings
        
        for s in us:
            rop = s[0]
            for key in s[1]:
                rop.parm(key).set(s[1][key])
                #print(rop.name(), key, s[1][key])



    '''
        Get value of specified parm from orig user settings.
    '''
    def getOrigParmValue(self,parmName):

        for s in self.userSettings:
            rop = s[0]
            if(rop.name() == self.currRop.name()):
                pv = s[1][parmName]
        
        return pv



    '''
        Start MPlay render.
    '''
    def render(self):

        # selected rop
        rName = self.ropList.currentItem().text()
        rop = hou.node(self.out + rName)

        # render only current frame
        rop.parm('trange').set(0)


        # render half res
        halfRes = self.halfResCheck.isChecked()

        if(halfRes):
            #print('\n*******RENDEINRG HALF\n')
            #print('\n','-------USER SETTINGS 1/2-------','\n',self.userSettings)

            rop.parm('override_camerares').set(1)
            rop.parm('res_fraction').set('.5')
            #print(rop.parm('res_fraction').eval())
        else:
            #print('\nRENDEINRG ORIGINAL\n')
            #print('\n','-------USER SETTINGS FULL-------','\n',self.userSettings)

            oc = self.getOrigParmValue('override_camerares')
            rf = str(self.getOrigParmValue('res_fraction'))
            #print('\nPARM VALUE OC-RF:', oc, rf)
            rop.parm('override_camerares').set(oc)
            rop.parm('res_fraction').set(rf)
            #print(rop.parm('res_fraction').eval())

        # render
        rop.parm('renderpreview').pressButton()




    '''
        Add dicing parm to selected rop and 
        toggle the displacements through dicing on-off.
    '''
    def toggleDisplacements(self):

        disp = not self.ropDisp

        node = self.currRop
        p = node.parm('vm_dicingquality')
        ipCount = node.parm('vm_numaux').eval()

        # FIX HOUDINI BUG which reset lightExport values on aovs when a spare parm added
        # get all light export settings and set them back after adding dicing parm
        ltExportVal = []
        for i in xrange(1, ipCount+1):
            ltExportVal.append(node.parm('vm_lightexport%d' % i).eval())


        # if parm already exist on the rop, en/dis it
        # else add parameter and then enable/disable it
        if(p):
            node.parm('vm_dicingquality').set(disp)
        else:
            ptg = node.parmTemplateGroup()

            hou_parm_template = hou.ToggleParmTemplate("vm_dicingquality", "Enable Dicing", default_value=disp)
            hou_parm_template.setJoinWithNext(True)

            target_folder = ("Rendering", "Dicing")
            ptg.appendToFolder(target_folder, hou_parm_template)
            node.setParmTemplateGroup(ptg)


        # FIX HOUDINI BUG which reset lightExport values on aovs when a spare parm added
        # get all light export settings and set them back after adding dicing parm
        for i in xrange(0, ipCount-1):
            print i, ipCount, ltExportVal[i]

            ipnum = i+1
            node.parm('vm_lightexport%d' % ipnum).set(ltExportVal[i])

        self.updateDispStatus()



    '''
        Houdini scene cam list.
    '''
    def getCameraList(self):

        typeCategory = hou.nodeType(hou.objNodeTypeCategory(), "cam")
        cams = typeCategory.instances()
        camList = []
        for c in cams:
            if(c.parent().name()=='obj'):
                camList.append(c.name())
            else:
                camList.append(c.parent().name())
            
        return camList



    '''
        List all scene cams in rop list context menu.
    '''
    def ropContextMenu(self, pos):
        
        menu = QtGui.QMenu()
        cams = self.getCameraList()
      
        for item in cams:
            action = menu.addAction(item)
            l = lambda item=item: self.setCameraForSelectedRop(item)
            action.triggered.connect(l)
            #action.triggered[()].connect(l)

        menu.exec_(QtGui.QCursor.pos())



    '''
        Create right click menu for aov tree.
    '''
    def aovContextMenu(self, pos):
        
        menu = QtGui.QMenu()

        actions = ['Delete', 'Copy', 'Paste', 'Disable', 'Enable']
        for item in actions:
            action = menu.addAction(item)
            action.triggered[()].connect(lambda item=item: self.manageAovContextMenu(item))
        
        menu.exec_(QtGui.QCursor.pos())



    '''
        Store parms and values in key:val format
        for each image plane selected in the tree.
    '''
    def buildImagePlaneData(self, id):
        node = self.currRop

        # see clear() meathod rather than creating new dict
        self.ipDict = collections.OrderedDict()

        for p in self.imagePlaneParms:
            self.ipDict[node.parm(p+'%d' % id)] = node.parm(p+'%d' % id).eval()
        
        return self.ipDict



    '''
        Show image plane data in aov tree list.
    '''
    def populateAovTree(self):
        
        # clear previous items in list
        self.ipData = []
        self.model.removeRows(0,self.model.rowCount())

        node = self.currRop

        # get image plane count
        parmCount = node.parm('vm_numaux').eval()

        # loop through them to access desired parms
        for i in xrange(1, parmCount+1):

            vexvar  = node.parm('vm_variable_plane%d' % i)
            chname  = node.parm('vm_channel_plane%d' % i)
            vextype = node.parm('vm_vextype_plane%d' % i)

            item =  [QtGui.QStandardItem(vexvar.eval()), QtGui.QStandardItem(chname.eval()), QtGui.QStandardItem(vextype.eval())]
            self.rootItem.appendRow(item)

            self.__aovList.append(vexvar.eval()) 

            # this is all image plane parms and values, which can 
            # be used in various areas like copying, resetting etc.
            self.ipData.append(self.buildImagePlaneData(i))

        self.aovList.setModel(self.model)




    '''
        Enable, Disable or Delete image plane by name.
        eg: self.wrangleImagePlanes('all_comp', 'delete')
    '''
    def wrangleImagePlanes(self, name, option):
        node    = self.currRop
        p       = node.parm('vm_numaux') 
        ipCount = node.parm('vm_numaux').eval()

        for i in xrange(1, ipCount+1):
            ipName = node.parm('vm_variable_plane%d' % i).eval()

            if(ipName==name):
                if(option=='delete'):
                    print 'Deleting image plane', ipName, name
                    p.removeMultiParmInstance(i-1)
                    break
                elif(option=='enable'):
                    print 'Disabling image plane', ipName, name
                    node.parm('vm_disable_plane%d' % i).set(0)
                    break
                elif(option=='disable'):
                    print 'Disabling image plane', ipName, name
                    node.parm('vm_disable_plane%d' % i).set(1)
                    break
                


    '''
        Manage right click options
    '''
    def manageAovContextMenu(self, action):
        
        items =  self.getSelectedItems()
        
        if(action=='Delete'):
            for item in items:
                self.wrangleImagePlanes(item,'delete')


        elif(action=='Copy'):
            #for i in range(1, len(items)+1):
            self.copyImagePlanes()


        elif(action=='Paste'):
            self.pasteImagePlanes()

        elif(action=='Enable'):
            for item in items:
                self.wrangleImagePlanes(item,'enable')

        elif(action=='Disable'):
            for item in items:
                self.wrangleImagePlanes(item,'disable')

        # update treeView
        self.populateAovTree()




    '''
        Store image plane parms & values
        based on items selected in the tree.
    '''
    def copyImagePlanes(self):
        node     = self.currRop
        p        = node.parm('vm_numaux') 
        ipCount  = node.parm('vm_numaux').eval()

        parmIds =  self.getSelectedIds()
        self.copiedImagePlanes = []

        # ipData contains all image plane data 
        # of current rop - see populateAovTree()
        for pid in parmIds:
            self.copiedImagePlanes.append(self.ipData[pid])

        #print 'COPIED PLANES\n',self.copiedImagePlanes



      
    '''
        Create new image planes on current rop and
        set their parm values to match the copied data
    '''
    def pasteImagePlanes(self):
        node     = self.currRop
        p        = node.parm('vm_numaux') 
        ipCount  = node.parm('vm_numaux').eval()

        for p in self.copiedImagePlanes:
            ipCountParm = node.parm("vm_numaux")
            ipCount = ipCountParm.evalAsInt()
            newAovIndex = ipCount + 1
            node.parm("vm_numaux").set(newAovIndex)

            # paste copied value in new image plane
            for idx , val in enumerate(self.imagePlaneParms):

                pasteInParm = val + str((newAovIndex))
                copiedParmValue = p.items()[idx][1]
                node.parm(pasteInParm).set(copiedParmValue)

        '''
        export_to_add = parm_or_bind_node.parm("parmname").evalAsString()

        # make sure export isn't already there
        for index in range(0, num_exports):
            if node.parm("vm_variable_plane%d" % (index + 1)).evalAsString() == export_to_add:
                print "Export %s already found. Skipping" % export_to_add
                return
        # if we get here the export wasn't found so add it
        new_parm_index = num_exports + 1
        node.parm("vm_numaux").set(new_parm_index)
        node.parm("vm_variable_plane%d" % new_parm_index).set(export_to_add)
        '''



    '''
        get text from first column of selected items in the tree
    '''
    def getSelectedItems(self):
        rowList = []
        itemList = []

        items =  self.aovList.selectionModel().selectedRows(0)
       
        for item in items:
           rowList.append(item.row())

        for row in rowList:
            ind = self.model.index(row,0)
            itemList.append(self.model.itemFromIndex(ind).text())

        return itemList




    '''
        get ids of items selected in the tree
    '''
    def getSelectedIds(self):
        selectedIds = []
        items =  self.aovList.selectionModel().selectedRows(0)
       
        for item in items:
           selectedIds.append(int(item.row()))

        return selectedIds




    def aovListClicked(self):
        pass
        '''
        itemList = []
        for item in items:
            # this gets you id of clicked item
            # item.row()

            # get clicked items text
            index = self.aovList.selectedIndexes()[0]
            itemList.append(item.row())
            print self.model.itemFromIndex(index).text()
            print itemList
        '''



    '''
        Select rop in houdini on double click.
    '''
    def selectRop(self):
        ropNode = self.out + str(self.currRop)
        hou.node(ropNode).setCurrent(1,1)



    '''
        Select camera in houdini, based on selected item in tree.
    '''
    def setCameraForSelectedRop(self, camName):
        rName = self.ropList.currentItem().text()
        rop = hou.node(self.out + rName)
        rop.parm('camera').set('/obj/' + camName)




    '''
        Get selected rop in list on single click.
    '''
    def getCurrentRop(self, curr, prev):
        cRop = hou.node(self.out + curr.text())
        self.currRop = cRop
        self.populateAovTree()
        
        ps           = cRop.parmTuple('vm_samples').eval()
        pixelSamples = str(ps[0]) + 'x' + str(ps[1])
        noiseLevel   = cRop.parm('vm_variance').eval()
        take         = cRop.parm('take').eval()
        
        self.updateDispStatus()
        self.statusBar.showMessage('take: ' + take + '  |  pixel samples: ' + pixelSamples + '  |  noise level: ' + str(noiseLevel)   )




    '''
        Update displacement check box state depending on
        whether dicing parm exists and is disabled or enabled.
    '''
    def updateDispStatus(self):
        disp         = self.currRop.parm('vm_dicingquality')
        if(disp):
            disp = disp.eval()
            if disp == 1:
                self.tglDispChkBx.setChecked(True)
                self.tglDispChkBx.setText("Displacements ON")
                self.ropDisp = True
            else:
                self.tglDispChkBx.setChecked(False)
                self.tglDispChkBx.setText("Displacements OFF")
                self.ropDisp = False
        else:
            self.tglDispChkBx.setChecked(True)
            self.tglDispChkBx.setText("Displacements ON")
            self.ropDisp = True



def loadUi(uifile, baseinstance=None):
    loader = UiLoader(baseinstance)
    widget = loader.load(uifile)
    QMetaObject.connectSlotsByName(widget)
    return widget



def main():
    rv = AovManager()
    rv.show()
    pyside_houdini.exec_(app, rv)
