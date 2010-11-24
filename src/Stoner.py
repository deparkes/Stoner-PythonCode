#----------------------------------------------------------------------------- 
#   FILE:       STONER DATA CLASS (version 0.2)
#   AUTHOR:     MATTHEW NEWMAN, CHRIS ALLEN, GAVIN BURNELL
#   DATE:       24/11/2010
#-----------------------------------------------------------------------------
#

import csv
#import sys
import re
#import string
#from scipy import *
import scipy
#import pdb # for debugging
import os
import sys
import numpy
import pylab


class DataFolder:
    
    #   CONSTANTS
    
    #   INITIALISATION
    
    def __init__(self, foldername):
        self.data = [];
        self.metadata = dict();
        self.foldername = foldername;
        self.__parseFolder();
        
    #   PRIVATE FUNCTIONS
    
    def __parseFolder(self):
        path="C:/Documents and Settings/pymn/workspace/Stonerlab/src/folder/run1"  # insert the path to the directory of interest
        dirList=os.listdir(path)
        for fname in dirList:
            print(fname)

#   PUBLIC METHODS

        
class DataFile:
    """Stoner.DataFile represents a standard Stonerlab data file as an object
    
    Provides methods to read, and manipulate data
    
    Matt Newman, Chris Allen, Gavin Burnell
    
    """
#   CONSTANTS

    __regexGetType = re.compile(r'([^\{]*)\{([^\}]*)\}') # Match the contents of the inner most{}
    __typeSignedInteger = "I64 I32 I16 I8"
    __typeUnsignedInteger="U64 U32 U16 U8"
    __typeInteger=__typeSignedInteger+__typeUnsignedInteger
    __typeFloat = "Extended Float Double Float Single Float"
    __typeBoolean = "Boolean"
    __typeString="String"
    defaultDumpLocation='C:\\dump.csv'
    
#   INITIALISATION

    def __init__(self, *args):
        """Constructor method
        
        3 forms are recognised: DataFile('filename'), DataFile(array), DataFile(dictionary), DataFile(array,dictionary)
        """
        self.data = numpy.array([])
        self.metadata = dict()
        self.typehint = dict()
        self.filename = ''
        # Now check for arguments t the constructor
        if len(args)==1:
            if isinstance(args[0], str): # Filename- load datafile
                self.get_data(args[0])
            elif isinstance(args[0], numpy.ndarray): # numpy.array - set data
                self.data=args[0]
            elif isinstance(args[0].dict): # Dictionary - use as metadata
                self.metadata=args[0]
        elif len(args)==2: # 2 argument forms either array,dict or dict,array
            if isinstance(args[0], numpy.ndarray):
                self.data=args[0]
            elif isinstance(args[0].dict):
                self.metadata=args[0]
            if isinstance(args[1], numpy.ndarray):
                self.data=args[1]
            elif isinstance(args[1].dict):
                self.metadata=args[1]

#   PRIVATE FUNCTIONS

    def __parse_metadata(self, key, value):
        """Parse the metadata string, removing the type hints into a separate dictionary from the metadata
        
        Uses the typehint to set the type correctly in the dictionary
        """
        m=self.__regexGetType.search(key)
        k= m.group(1)
        t= m.group(2)
        if self.__contains(self.__typeInteger, t) == True:
            value = int(value);
        elif self.__contains(self.__typeFloat, t) == True:
            value = float(value);
        elif self.__contains(self.__typeBoolean, t) == True:
            value = bool(value);
        else:
            value = str(value);
        self.metadata[k]=value
        self.typehint[k]=t

    def __parse_data(self):
        """Internal function to parse the tab deliminated text file
        """
        reader = csv.reader(open(self.filename, "rb"), delimiter='\t', quoting=csv.QUOTE_NONE)
        row=reader.next()
        assert row[0]=="TDI Format 1.5" # Bail out if not the correct format
        self.column_headers = row[1:len(row)]
        for row in reader:
            if self.__contains(row[0], '=') == True:
                self.__parse_metadata(row[0].split('=')[0], row[0].split('=')[1])
            if (len(row[1:len(row)]) > 1) or len(row[1]) > 0:
                self.data=numpy.append(self.data, map(lambda x: float(x), row[1:]))
        else:
            shp=(-1, len(row)-1)
            self.data=numpy.reshape(self.data,  shp)

    def __contains(self, theString, theQueryValue):
        return theString.find(theQueryValue) > -1
        
    def __find_col(self, col):
        if isinstance(col, int): #col is an int so pass on
            pass
        elif isinstance(col, str): # Ok we have a string
            if col in self.column_headers: # and it is an exact string match
                col=self.column_headers.index(col)
            else: # ok we'll try for a regular expression
                test=re.compile(col)
                possible=filter(test.search, self.column_headers)
                if len(possible)==0:
                    raise KeyError('Unable to find any possible column matches')
                col=self.column_headers.index(possible[0])
        else:
            raise TypeError('Column index must be an integer or string')
        return col


#   PUBLIC METHODS

    def get_data(self,filename):
        self.filename = filename;
        self.__parse_data();
        
    def metadata_value(self, text):
        """Wrapper of DataFile.meta for compatibility"""
        return self.meta(text)

    def data(self):
        return self.data

    def metadata(self):
        return self.metadata
        
    def typehint(self):
        return self.typehint

    def column_headers(self):
        return self.column_headers
    
    def column(self, col):
        """Extracts a column of data by index or name"""
        return self.data[:, self.__find_col(col)]
        
    def meta(self, ky):
        """Returns some metadata
        
        Needs merging with Matt's metadata_value code"""
        if isinstance(ky, str): #Ok we go at it with a string
            if ky in self.metadata:
                return self.metadata[ky]
            else:
                test=re.compile(ky)
                possible=filter(test.search, self.metadata)
                if len(possible)==0:
                    raise KeyError("No metadata with that keyname")
                elif len(possible)==1:
                    return self.metadata[possible[0]]
                else:
                    d=dict()
                    for p in possible:
                        d[p]=self.metadata[p]
                    return d
        else:
            raise TypeError("Only string are supported as search keys currently")
            # Should implement using a list of strings as well
    
    def search(self, *args):
        """Searches in the numerica data part of the file for lines that match and returns  the corresponding rows

        Find row(s) that match the specified value in column:
        
        search(Column,value,columns=[list])
        
        Find rows that where the column is >= lower_limit and < upper_limit:
        
        search(Column,lower_limit,upper_limit)      
        """
        
        if len(args)==2:
            col=args[0]
            targets=[]
            val=args[1]
        elif len(args)==3:
            col=args[0]
            targets=map(self.__find_col, args[2])
            val=args[1]        
        if len(targets)==0:
            targets=range(self.data.shape[1])
        d=self.column(col)
        if callable(val):
            rows=numpy.nonzero([val(x) for x in d])[0]
        elif isinstance(val, float):
            rows=numpy.nonzero([x==val for x in d])[0]
        print targets
        return self.data[rows][:, targets]
  
    def do_polyfit(self,column_x,column_y,polynomial_order):
        x_data = self.data[:,column_x]
        y_data = self.data[:,column_y]
        return numpy.polyfit(x_data,y_data,polynomial_order)
    
    def add_column(self,column_data,column_header=''):
        self.column_headers.append(column_header)
        
        # The following 2 lines make the array we are adding a
        # [1, x] array, i.e. a column by first making it 2d and
        # then transposing it.
        
        column_data=numpy.atleast_2d(column_data)
        column_data=column_data.T # Transposes Array
        self.data=numpy.append(self.data,column_data,1)
        print('Column header "'+column_header+'" added to array')
        return True
    
    def plot_simple_xy(self,column_x, column_y,title='',save_filename='',
                    show_plot=True):
            x=self.data[:,column_x]
            y=self.data[:,column_y]
            if show_plot == True:
                pylab.ion()
            pylab.plot(x,y)
            pylab.draw()
            pylab.xlabel(str(self.column_headers[column_x]))
            pylab.ylabel(str(self.column_headers[column_y]))
            pylab.title(title)
            pylab.grid(True)
            if save_filename != '':
                pylab.savefig(str(save_filename))
            
    def csvArray(self,dump_location=defaultDumpLocation):
        spamWriter = csv.writer(open(dump_location, 'wb'), delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
        i=0
        spamWriter.writerow(self.column_headers)
        while i< self.data.shape[0]:
            spamWriter.writerow(self.data[i,:])
            i+=1
