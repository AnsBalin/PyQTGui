__author__ = 'R.Bates'

import sys
from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSlot
from PyQt4.QtGui import QImage
import skimage as sk
from skimage import filter
from skimage import io
from skimage.viewer import ImageViewer
import vtk
import numpy as np
from vtk.qt4.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
import nifti
from nifti import NiftiImage
from matplotlib import pyplot as plt


class Editor(QtGui.QDialog):

        def __init__(self):
            super(Editor,self).__init__()
            self.loadedImage = 0
            self.loadedSegmentation = 0
            self.images = []
            self.img_data = []
            self.vols = []
            self.ui = uic.loadUi('window.ui',self)
            self.minVal = 10000;
            self.maxVal = -10000;


            self.initRenderWindow()
            self.initFunctionality()
            self.show()
            self.vtkWidget.resize(self.frame.width(),self.frame.height())

        def initFunctionality(self):

            self.quitButton.clicked.connect(QtCore.QCoreApplication.instance().quit)
            self.searchButton.clicked.connect(lambda: self.loadImage())
            self.segmentationButton.clicked.connect(lambda: self.loadSegmentation())
            self.spinBox.valueChanged.connect(lambda: self.horizontalSlider.setValue(self.spinBox.value()))
            self.horizontalSlider.valueChanged.connect(lambda: self.spinBox.setValue(self.horizontalSlider.value()))
            self.horizontalSlider.valueChanged.connect(lambda: self.updateImage())
            self.horizontalSlider.setValue(0)

            self.verticalSlider.valueChanged.connect(lambda: self.updateOpacityTransferFunction())
            self.verticalSlider_2.valueChanged.connect(lambda: self.updateOpacityTransferFunction())
            self.checkBox.stateChanged.connect(lambda: self.segmentationOnOff())

        def initRenderWindow(self):

            pix_diag = 5.0
            self.nVolumes = 0

            self.vtkWidget = QVTKRenderWindowInteractor(self.frame)
            self.ren = vtk.vtkRenderer()
            self.ren.SetBackground(1.0, 1.0, 1.0)
            self.vtkWidget.GetRenderWindow().AddRenderer(self.ren)
            self.window = self.vtkWidget.GetRenderWindow()
            self.iren = self.vtkWidget.GetRenderWindow().GetInteractor()



            drange = [0,400]

            self.vtkWidget.opacity_tf = vtk.vtkPiecewiseFunction()
            self.vtkWidget.opacity_tf.AddPoint(drange[0],0.0)
            self.vtkWidget.opacity_tf.AddPoint(drange[1],0.0)
            self.vtkWidget.color_tf = vtk.vtkColorTransferFunction()
            self.vtkWidget.color_tf.AddRGBPoint(drange[0], 0.0, 0.0, 0.0)
            self.vtkWidget.color_tf.AddRGBPoint(drange[1], 1.0, 1.0, 1.0)
            self.vtkWidget.volProperty = vtk.vtkVolumeProperty()
            self.vtkWidget.volProperty.SetColor(self.vtkWidget.color_tf);
            self.vtkWidget.volProperty.SetScalarOpacity(self.vtkWidget.opacity_tf)
            self.vtkWidget.volProperty.ShadeOn()
            self.vtkWidget.volProperty.SetInterpolationTypeToLinear()
            self.vtkWidget.volProperty.SetScalarOpacityUnitDistance(pix_diag)







        def getImage(self,filename):

            if str(filename).endswith('nii') or str(filename).endswith('nii.gz'):
                nim = NiftiImage(str(filename))
                shape = nim.data.shape

                img_data = nim.data

                miny = np.amin(img_data)
                arr = img_data.astype(float)
                arr -= miny
                maxy = np.amax(arr)
                arr = arr / (maxy/2)
                arr -= 1
                arr = sk.img_as_ubyte(arr)

                img_data = arr

            elif str(filename).endswith('hdr'):
                # Use the header to figure out the shape of the data
                # then load the raw data and reshape the array

                img_data = np.frombuffer(open(str(filename).replace('.hdr', '.dat'), 'rb').read(),
                                            np.uint8)\
                            .reshape((shape[2], shape[1], shape[0]))

            return (img_data,shape)

        def addVolumeToRenderer(self,img):

            pix_diag = 5.0

            self.compositeFunction = vtk.vtkVolumeRayCastCompositeFunction()
            self.compositeFunction.SetCompositeMethodToInterpolateFirst()

            self.vtkWidget.Render()
            self.volMapper = vtk.vtkVolumeRayCastMapper()
            self.window.Render()
            self.extensions = vtk.vtkOpenGLExtensionManager()
            self.extensions.SetRenderWindow(self.window)
            self.extensions.Update()


            string = self.extensions.GetExtensionsString()

            print(self.extensions.GetExtensionsString())


            self.volMapper.SetVolumeRayCastFunction(self.compositeFunction)
            self.volMapper.SetSampleDistance(pix_diag / 5.0)

            self.volMapper.SetInputConnection(img.GetOutputPort())


            self.updateColourTransferFunction()
            self.updateOpacityTransferFunction()

            self.plane = vtk.vtkPlanes()

            def ClipVolumeRender(obj, event):
                obj.GetPlanes(self.plane)
                self.volMapper.SetClippingPlanes(self.plane)

            self.boxWidget = vtk.vtkBoxWidget()
            self.boxWidget.SetInteractor(self.vtkWidget)
            self.boxWidget.SetPlaceFactor(1.0)

            self.boxWidget.SetInput(img.GetOutput())
            self.boxWidget.PlaceWidget()
            self.boxWidget.InsideOutOn()
            self.boxWidget.AddObserver("InteractionEvent", ClipVolumeRender)

            self.outlineProperty = self.boxWidget.GetOutlineProperty()
            self.outlineProperty.SetRepresentationToWireframe()
            self.outlineProperty.SetAmbient(1.0)
            self.outlineProperty.SetAmbientColor(0, 0, 0)
            self.outlineProperty.SetLineWidth(3)

            self.selectedOutlineProperty = self.boxWidget.GetSelectedOutlineProperty()
            self.selectedOutlineProperty.SetRepresentationToWireframe()
            self.selectedOutlineProperty.SetAmbient(1.0)
            self.selectedOutlineProperty.SetAmbientColor(1, 0, 0)
            self.selectedOutlineProperty.SetLineWidth(3)

            self.outline = vtk.vtkOutlineFilter()
            self.outline.SetInputConnection(img.GetOutputPort())
            self.outlineMapper = vtk.vtkPolyDataMapper()
            self.outlineMapper.SetInputConnection(self.outline.GetOutputPort())
            self.outlineActor = vtk.vtkActor()
            self.outlineActor.SetMapper(self.outlineMapper)

            self.vol = vtk.vtkVolume()
            self.vol.SetMapper(self.volMapper)
            self.vol.SetProperty(self.vtkWidget.volProperty)

            self.ren.AddVolume(self.vol)
            self.ren.AddActor(self.outlineActor)

            self.window.Render()

        def arrayToVTKImage(self, array, shape):

            if len(shape) == 4 and shape[0] == 1:
                shape = (shape[1], shape[2], shape[3])

            image = vtk.vtkImageImport()
            image.CopyImportVoidPointer(array, array.nbytes)
            image.SetDataScalarTypeToUnsignedChar()
            image.SetNumberOfScalarComponents(1)
            image.SetDataExtent(0, shape[2]-1, 0, shape[1]-1, 0, shape[0]-1)
            image.SetWholeExtent(0, shape[2]-1, 0, shape[1]-1, 0, shape[0]-1)

            return image

        def addSegmentationToImage(self):

            dmc = vtk.vtkDiscreteMarchingCubes()
            dmc.SetInputConnection(self.segImage.GetOutputPort())
            dmc.GenerateValues(1, 255, 255)
            dmc.Update()
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(dmc.GetOutputPort())

            self.checkBox.setEnabled(True)
            self.checkBox.setCheckState(2)


            actor = vtk.vtkActor()
            actor.SetMapper(mapper)

            self.ren.AddActor(actor)
            self.window.Render()


        @pyqtSlot()
        def loadImage(self):

            filename = QtGui.QFileDialog.getOpenFileName(self, 'Open File', '/media/My Passport/CTPaperCTData/Russ/C34R1/VesselSegmentation');

            self.img_data, shape = self.getImage(filename)

            self.image = self.arrayToVTKImage(self.img_data, shape)

            self.maxVal = max(self.maxVal, np.amax(self.img_data))
            self.minVal = min(self.minVal, np.amin(self.img_data))
            self.range = self.maxVal - self.minVal

            self.addVolumeToRenderer(self.image)

            self.ren.ResetCamera()
            self.cam1 = self.ren.GetActiveCamera()

            self.style = vtk.vtkInteractorStyleTrackballCamera()
            self.vtkWidget.SetInteractorStyle(self.style)
            self.vtkWidget.lighting = True

            self.update()

            self.iren.Render()

            self.loadedImage = 1

        def loadSegmentation(self):


            filename = QtGui.QFileDialog.getOpenFileName(self, 'Open File', '/media/My Passport/CTPaperCTData/Russ/C34R1/VesselSegmentation');

            self.seg_data, self.seg_shape = self.getImage(filename)

            self.segImage = self.arrayToVTKImage(self.seg_data, self.seg_shape)

            self.addSegmentationToImage()





        def updateOpacityTransferFunction(self):


            bottomSliderVal = self.verticalSlider.value()
            topSliderVal = self.verticalSlider_2.value()

            upperVal = min(self.maxVal, bottomSliderVal+topSliderVal/2)
            lowerVal = max(self.minVal, bottomSliderVal-topSliderVal/2)

            self.vtkWidget.opacity_tf.RemoveAllPoints()
            self.vtkWidget.opacity_tf.AddPoint(self.minVal, 0.0)
            self.vtkWidget.opacity_tf.AddPoint(lowerVal, 0.0)
            self.vtkWidget.opacity_tf.AddPoint(upperVal, 1.0)
            self.vtkWidget.opacity_tf.AddPoint(self.maxVal, 1.0)

            self.vtkWidget.color_tf.RemoveAllPoints()
            self.vtkWidget.color_tf.AddRGBPoint(self.minVal, 0, 0, 0)
            self.vtkWidget.color_tf.AddRGBPoint(lowerVal, 0, 0, 0)
            self.vtkWidget.color_tf.AddRGBPoint(upperVal, 1, 1, 1)
            self.vtkWidget.color_tf.AddRGBPoint(self.maxVal, 1, 1, 1)

            self.vtkWidget.Render()

        def updateColourTransferFunction(self):


            self.vtkWidget.color_tf.RemoveAllPoints()
            self.vtkWidget.color_tf.AddRGBPoint(self.minVal, 0, 0, 0)
            self.vtkWidget.color_tf.AddRGBPoint(self.maxVal, 1, 1, 1)

        def resizeEvent(self, QResizeEvent):
            if self.loadedImage == 1:
                    self.vtkWidget.resize(self.frame.width(), self.frame.height())

        def segmentationOnOff(self):
            props = self.ren.GetViewProps()
            props.InitTraversal()
            if self.checkBox.checkState() == 0:
                props.GetNextProp()
                props.GetNextProp()
                props.GetNextProp().VisibilityOff()
                self.vtkWidget.Render()
            elif self.checkBox.checkState() == 2:
                props.GetNextProp()
                props.GetNextProp()
                props.GetNextProp().VisibilityOn()
                self.vtkWidget.Render()


def main():
    app = QtGui.QApplication(sys.argv)
    ex = Editor()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()