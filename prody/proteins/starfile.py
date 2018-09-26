# -*- coding: utf-8 -*-
"""
This module defines functions for parsing `STAR files`_.

.. _STAR files: https://www2.mrc-lmb.cam.ac.uk/relion/index.php/Conventions_%26_File_formats#The_STAR_format
"""


from collections import defaultdict
import os.path

import numpy as np

from prody.utilities import openFile
from prody import LOGGER, SETTINGS

from .emdfile import parseEMD

__all__ = ['parseSTAR', 'writeSTAR', 'parseImagesFromSTAR', 
           'StarDict', 'StarDataBlock', 'StarLoop',]


class StarDict:
    def __init__(self, parsingDict, prog, title='unnamed'):
        self._title = title
        self._dict = parsingDict
        self._prog = prog
        self.dataBlocks = [StarDataBlock(self, key)
                           for key in list(self._dict.keys())]
        self.numDataBlocks = len(self.dataBlocks)

    def __getitem__(self, key):
        try:
            return np.array(self.dataBlocks)[key]
        except:
            try:
                key = np.where(np.array(list(self._dict.keys())) == key)[0][0]
                return self.dataBlocks[key]
            except:
                raise ValueError('The key for getting items should '
                                 'be the name or number of a data block')

    def getTitle(self):
        return self._title

    def setTitle(self, value):
        self._title = value

    def getDict(self):
        return self._dict

    def __repr__(self):
        if self.numDataBlocks == 1:
            return '<StarDict: {0} (1 data block)>'.format(self._title)
        return '<StarDict: {0} ({1} data blocks)>'.format(self._title, self.numDataBlocks)

    def __iter__(self):
        """Yield StarDataBlock instances."""
        for key in list(self._dict.keys()):
            yield StarDataBlock(self, key)

    def pop(self, index):
        self.dataBlocks.pop(index)

class StarDataBlock:
    def __init__(self, starDict, key):
        self._title = key
        self._dict = starDict._dict[key]
        self._prog = starDict._prog

        if list(self._dict.keys()) == ['fields','data']:
            self.loops = []
            self.numLoops = 0
            self.data = list(self._dict['data'].values())
            self.fields = list(self._dict['fields'].values())
            self.numEntries = len(self.data)
            self.numFields = len(self.fields)
        else:
            self.loops = [StarLoop(self, index)
                          for index in list(self._dict.keys())]
            self.numLoops = len(self.loops)

    def getLoop(self, index):
        try:
            return self.loops[index]
        except:
            raise ValueError('There is no loop with that index')

    def getTitle(self):
        return self._title

    def setTitle(self, title):
        self._title = title

    def __getitem__(self, key):
        if self.loops == []:
            try:
                return np.array(self._dict['data'][key])
            except:
                try:
                    return np.array(self.data)[key]
                except:
                    raise ValueError('The key for getting items should be the data entry number')

        else:
            try:
                return np.array(self.loops)[key]
            except:
                try:
                    key = np.where(np.array(list(self._dict.keys())) == key)[0][0]
                    return self.loops[key]
                except:
                    raise ValueError(
                        'The key for getting items should be the name or number of a loop')

    def __repr__(self):
        if self.numLoops == 0:
            return '<StarDataBlock: {0} ({1} entries)>'.format(self._title, self.numEntries)
        elif self.numLoops == 1:
            return '<StarDataBlock: {0} ({1} loop)>'.format(self._title, self.numLoops)
        return '<StarDataBlock: {0} ({1} loops)>'.format(self._title, self.numLoops)

    def __iter__(self):
        """Yield StarLoop instances."""
        for key in list(self._dict.keys()):
            yield StarLoop(self, key)

    def pop(self, index):
        self.loops.pop(index)


class StarLoop:
    def __init__(self, dataBlock, key):
        self._dict = dataBlock._dict[key]
        self._prog = dataBlock._prog
        self.fields = list(self._dict['fields'].values())
        self.data = list(self._dict['data'].values())
        self.numFields = len(self.fields)
        self.numRows = len(self.data)
        self._title = dataBlock._title + ' loop ' + str(key)

    def getData(self, key):
        if key in self.fields:
            return [row[key] for row in self.data]
        else:
            raise ValueError('That field is not present in this loop')

    def getTitle(self):
        return self._title

    def setTitle(self, title):
        self._title = title

    def getDict(self):
        return self._dict

    def __getitem__(self, key):
        try:
            return np.array(self.data)[key]
        except:
            try:
                key = np.where(np.array(list(self._dict.keys())) == key)[0][0]
                return self.data[key]
            except:
                try:
                    return self.getData(key)
                except:
                    raise ValueError('The key for getting items should be fields, data, '
                                     'or a field name or number corresponding to a '
                                     'row or column of data')

    def __repr__(self):
        if self.numFields == 1 and self.numRows != 1:
            return '<StarLoop: {0} (1 column and {2} rows)>'.format(self._title, self.numRows)
        elif self.numFields != 1 and self.numRows == 1:
            return '<StarLoop: {0} ({1} columns and 1 row)>'.format(self._title, self.numFields)
        elif self.numFields == 1 and self.numRows == 1:
            return '<StarLoop: {0} (1 column and 1 row)>'.format(self._title)
        else:
            return '<StarLoop: {0} ({1} columns and {2} rows)>'.format(self._title, self.numFields, self.numRows)


def parseSTAR(filename):
    """Returns a dictionary containing data
    parsed from a Relion STAR file.

    :arg filename: a filename
        The .star extension can be omitted.
    """

    if not os.path.isfile(filename) and not os.path.isfile(filename + '.star'):
        raise IOError('There is no file with that name.')

    starfile = open(filename, 'r')
    lines = starfile.readlines()
    starfile.close()

    parsingDict, prog = parseSTARStream(lines)

    return StarDict(parsingDict, prog, filename)


def parseSTARStream(stream):
    prog = 'RELION'
    finalDictionary = {}
    currentLoop = -1
    fieldCounter = 0
    dataItemsCounter = 0
    lineNumber = 0
    for line in stream:
        if line.startswith('data_'):
            currentDataBlock = line[5:].strip()
            finalDictionary[currentDataBlock] = {}
            currentLoop = -1
            inLoop = False
            startingBlock = True
            fieldCounter = 0

        elif line.startswith('loop_'):
            currentLoop += 1
            inLoop = True
            finalDictionary[currentDataBlock][currentLoop] = {}
            finalDictionary[currentDataBlock][currentLoop]['fields'] = {}
            finalDictionary[currentDataBlock][currentLoop]['data'] = {}
            fieldCounter = 0

        elif line.startswith('_') or line.startswith(' _'):
            currentField = line.strip().split()[0]

            if inLoop:
                finalDictionary[currentDataBlock][currentLoop]['fields'][fieldCounter + 1] = currentField
                dataItemsCounter = 0
            else:
                if startingBlock:
                    finalDictionary[currentDataBlock]['fields'] = {}
                    finalDictionary[currentDataBlock]['data'] = {}
                    startingBlock = False
                    dataItemsCounter = 0
                finalDictionary[currentDataBlock]['fields'][fieldCounter + 1] = currentField
                finalDictionary[currentDataBlock]['data'][dataItemsCounter] = {}
                finalDictionary[currentDataBlock]['data'][dataItemsCounter][currentField] = line.strip().split()[1]
                dataItemsCounter += 1

            fieldCounter += 1

        elif line.strip() == '':
            inLoop = False

        elif len(line.split()) == fieldCounter:
            finalDictionary[currentDataBlock][currentLoop]['data'][dataItemsCounter] = {}
            fieldCounter = 0
            for fieldEntry in line.strip().split():
                currentField = finalDictionary[currentDataBlock][currentLoop]['fields'][fieldCounter + 1]
                finalDictionary[currentDataBlock][currentLoop]['data'][dataItemsCounter][currentField] = fieldEntry
                fieldCounter += 1
            dataItemsCounter += 1

        elif line.startswith('#'):
            if line.startswith('# XMIPP'):
                prog = 'XMIPP'

        else:
            raise TypeError('This file does not conform to the STAR file format.'
                            'There is a problem with line {0}:\n {1}'.format(lineNumber, line))

        lineNumber += 1

    return finalDictionary, prog


def writeSTAR(filename, starDict):
    """Writes a STAR file from a dictionary containing data
    such as that parsed from a Relion STAR file.

    :arg filename: a filename
        The .star extension can be omitted.

    :arg dictionary: a dictionary in STAR format
        This should have nested entries starting with data blocks then loops/tables then
        field names and finally data.
    """

    star = open(filename, 'w')

    for dataBlockKey in starDict:
        star.write('\ndata_' + dataBlockKey + '\n')
        for loopNumber in starDict[dataBlockKey]:
            star.write('\nloop_\n')
            for fieldNumber in starDict[dataBlockKey][loopNumber]['fields']:
                star.write('_' + starDict[dataBlockKey]
                           [loopNumber]['fields'][fieldNumber] + '\n')
            for dataItemNumber in starDict[dataBlockKey][loopNumber]['data']:
                for fieldNumber in starDict[dataBlockKey][loopNumber]['fields']:
                    currentField = starDict[dataBlockKey][loopNumber]['fields'][fieldNumber]
                    star.write(starDict[dataBlockKey][loopNumber]
                               ['data'][dataItemNumber][currentField] + ' ')
                star.write('\n')

    star.close()
    return


def parseImagesFromSTAR(particlesSTAR, **kwargs):
    '''
    Parses particle images using data from a STAR file containing information about them.


    arg particlesSTAR: a dictionary containing STAR file data about particles or
        a filename for a STAR file from which such data can be parsed.
        A dictionary or list-like object containing row dictionaries can also be used.
    type particlesSTAR: str, StarDict, StarDataBlock, StarLoop, dict, list, tuple, :class:`~numpy.ndarray`

    arg indices: multi-dimensional indices for rows corresponding to images
        array-like objects with too few indices can be used and then the same indices
        will be considered across data blocks and loop tables 
    type indices: list, tuple, :class:`~numpy.ndarray`

    arg saveImageArrays: whether to save the numpy array for each image to file
        default is False
    type saveImageArrays: bool

    arg saveDirectory: directory where numpy image arrays are saved
        default is None, which means save to the current working directory
    type saveDirectory: str, None

    arg rotateImages: whether to apply in plane translations and rotations using 
        provided psi and origin data, default is True
    type rotateImages: bool 
    '''
    from skimage.transform import rotate

    kw_indices = kwargs.get('indices', None)
    saveImageArrays = kwargs.get('saveImageArrays', False)
    saveDirectory = kwargs.get('saveDirectory', None)
    rotateImages = kwargs.get('rotateImages', True)

    if not isinstance(particlesSTAR, (StarDict, StarDataBlock, StarLoop, 
                                      dict, list, tuple, np.ndarray)):
        try:
            particlesSTAR = parseSTAR(particlesSTAR)
        except:
            raise ValueError('particlesSTAR should be a dictionary parsed from a STAR file, '
                             'a filename corresponding to one, or equivalent data dictionaries in '
                             'a list-like object or a dictionary that can be indexed numerically')

    if isinstance(particlesSTAR, (dict, list, tuple, np.ndarray)):
        try:
            particle = particlesSTAR[0]
            particleData0 = particle[list(particle.keys())[0]]
        except:
            raise TypeError('particlesSTAR should be a dictionary parsed from a STAR file, '
                            'a filename corresponding to one, or equivalent data dictionaries in '
                            'a list-like object or a dictionary that can be indexed numerically')

    # Check dimensions and generate full indices
    if isinstance(particlesSTAR, StarDict):
        dataBlocks = []
        maxLoops = 0
        maxRows = 0
        for dataBlock in particlesSTAR:

            foundImageField = False
            for loop in dataBlock:
                if ('_image' in loop.fields) or ('_rlnImageName' in loop.fields):
                    foundImageField = True
                    if loop.numRows > maxRows:
                        maxRows = loop.numRows
                else:
                    dataBlock.pop(int(loop.getTitle().split(' ')[-1]))

            if dataBlock.numLoops > maxLoops:
                maxLoops = dataBlock.numLoops

            if foundImageField:
                dataBlocks.append(dataBlock)

        indices = np.zeros((len(dataBlocks),maxLoops,maxRows,3),dtype=int)
        for i, dataBlock in enumerate(dataBlocks):
            for j, loop in enumerate(dataBlock):
                for k in range(maxRows):
                    if k < loop.numRows:
                        indices[i,j,k] = np.array([i,j,k])
                    else:
                        indices[i,j,k] = np.array([0,0,0])

    elif isinstance(particlesSTAR, StarDataBlock):
        loops = []
        maxRows = 0

        for loop in particlesSTAR:
            if ('_image' in loop.fields) or ('_rlnImageName' in loop.fields):
                loops.append(loop)
                if loop.numRows > maxRows:
                    maxRows = loop.numRows

        indices = np.zeros((len(loops),maxRows,2),dtype=int)
        for j, loop in enumerate(particlesSTAR):
            for k in range(loop.numRows):
                indices[j,k] = np.array([j,k])

    elif isinstance(particlesSTAR, StarLoop):
        indices = np.array(particlesSTAR.getDict()['data'].keys())


    if kw_indices is not None:
    # Convert keyword indices to valid indices if possible
        try:
            kw_indices = np.array(kw_indices)
        except:
            raise TypeError('indices should be array-like')

        ndim = kw_indices.ndim
        shape = kw_indices.shape

        if ndim == indices.ndim:
            for dim in range(ndim):
                if kw_indices.shape[dim] > indices.shape[dim]:
                    raise ValueError('provided indices has too many entries for dimension {0}'.format(dim))

            indices = kw_indices

        elif isinstance(particlesSTAR, StarDict):
            if ndim == 1:
                if particlesSTAR[0].numLoops == 0:
                    indices = kw_indices
                else:
                    indices = np.fromiter([(i, j, index) for index in kw_indices 
                                            for j, loop in enumerate(dataBlock)
                                            for i, dataBlock in enumerate(particlesSTAR)], 
                                            dtype=[('dataBlockNumber', int), 
                                                   ('loopNumber', int), 
                                                   ('rowNumber', int)])
                    if particlesSTAR[0].numLoops != 1:
                        # This will almost never happen but we should warn about it anyway
                        LOGGER.warn('particlesSTAR has multiple loop tables but '
                                    'a 1D array-like object was provided as indices. '
                                    'The same indices will therefore be used to parse '
                                    'images from each loop.')

            if ndim == 2:
                pass
                # to be dealt with soon

        elif isinstance(particlesSTAR, StarDataBlock):
            if ndim == 1:
                if particlesSTAR.numLoops == 0:
                    indices = kw_indices
                else:
                    indices = np.fromiter(((j, index) for index in kw_indices 
                                            for j, loop in enumerate(particlesSTAR)), 
                                          dtype=[('loopNumber', int), 
                                                 ('rowNumber', int)])
                    if particlesSTAR.numLoops != 1:
                        # This will almost never happen but we should warn about it anyway
                        LOGGER.warn('particlesSTAR has multiple loop tables but '
                                    'a 1D array-like object was provided as indices. '
                                    'The same indices will therefore be used to parse '
                                    'images from each loop.')

            else:
                # ndim is not 1 or 2
                raise ValueError('indices should be a 1D or ideally 2D array-like object '
                                 'when particlesSTAR')

        elif isinstance(particlesSTAR, StarLoop):
            raise ValueError('indices should be a 1D array-like object '
                             'when particlesSTAR is a loop table')

    if indices is np.array([]):
        raise ValueError('particlesSTAR does not contain any loops with image fields')

    # Use indices to collect particle data dictionaries
    particles = []

    if kw_indices is not None:
        for k in indices:
            if isinstance(particlesSTAR, StarDict):
                particles.append(dataBlocks[k[0]][k[1]][k[2]])
            elif isinstance(particlesSTAR, StarDataBlock):
                particles.append(particlesSTAR[k[0]][k[1]])
            elif isinstance(particlesSTAR, StarLoop):
                particles.append(particlesSTAR[k])
    else:
        if isinstance(particlesSTAR, StarDict):
            for i, index_i in enumerate(indices):
                for j, index_j in enumerate(index_i):
                    for k, index_k in enumerate(index_j):
                        if not (np.array_equal(index_k, np.array([0,0,0])) 
                        and not (i == 0 and j == 0 and k == 0)):
                            particles.append(dataBlocks[index_k[0]][index_k[1]][index_k[2]])

        elif isinstance(particlesSTAR, StarDataBlock):
            for j, index_j in enumerate(indices):
                for k, index_k in enumerate(index_j):
                    if not (np.array_equal(index_k, np.array([0,0,0])) 
                    and not (j == 0 and k == 0)):
                        particles.append(particlesSTAR[index_k[0]][index_k[1]])

        elif isinstance(particlesSTAR, StarLoop):
            for k in indices:
                particles.append(particlesSTAR[k])

    # Parse images using particle dictionaries
    image_stacks = {}
    images = []
    stk_images = []
    if particlesSTAR._prog == 'RELION':
        imageFieldKey = '_rlnImageName'
    else:
        imageFieldKey = '_image'
        
    for i, particle in enumerate(particles):
        try:
            image_index = int(particle[imageFieldKey].split('@')[0])-1
            filename = particle[imageFieldKey].split('@')[1]
        except:
            raise ValueError('particlesSTAR does not contain data about particle image '
                             '{0} location in either RELION or XMIPP format'.format(i))

        if filename.endswith('.stk'):
            stk_images.append(i)

        if not filename in list(image_stacks.keys()):
            image_stacks[filename] = parseEMD(filename).density

        image = image_stacks[filename][image_index]

        if saveImageArrays:
            if saveDirectory is not None:
                np.save('{0}/{1}'.format(saveDirectory, i), image)
            else:
                np.save('{1}'.format(i), image)

        if rotateImages:
            if particlesSTAR._prog == 'RELION':
                anglePsi = float(particle['_rlnAnglePsi'])
                originX = float(particle['_rlnOriginX'])
                originY = float(particle['_rlnOriginY'])
            elif particlesSTAR._prog == 'XMIPP':
                anglePsi = float(particle['_anglePsi'])
                originX = float(particle['_shiftX'])
                originY = float(particle['_shiftY'])
            images.append(rotate(image, anglePsi,
                                 center=(float(image.shape[0])-originX,
                                         float(image.shape[1])-originY)))
        else:
            images.append(image)

        if len(stk_images) > 0:
            LOGGER.warn('ProDy currently cannot parse images from XMIPP .stk files. '
                        'Please be aware that images {0} and {1} will be None '
                        'from the final array.'.format(', '.join(stk_images[:-1]),stk_images[-1]))

    return np.array(images)
