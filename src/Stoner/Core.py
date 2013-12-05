"""Stoner.Core provides the core classes for the Stoner package.

Classes:
    `DataFile` :the base class for representing a single data set of experimental data.
    `typeHintedDict`: a dictionary subclass that tries to keep track of the underlying type of data
        stored in each element. This class facilitates the export to strongly typed
        languages such as LabVIEW.

"""
import fileinput
import re
#import pdb # for debugging
import os
import numpy
import numpy.ma as ma
import copy
import inspect
import itertools
import collections


class _evaluatable(object):
    """A very simple class that is just a placeholder"""
    pass


class typeHintedDict(dict):
    """Extends a regular dict to include type hints of what each key contains.

    Attributes:
        _typehints (dict): The backing store for the type hint information
        __regexGetType (re): USed to extract the type hint from a string
        __regexSignedInt (re): matches type hint strings for signed intergers
        __regexUnsignedInt (re): matches the type hint string for unsigned integers
        __regexFloat (re): matches the type hint strings for floats
        __regexBoolean (re): matches the type hint string for a boolean
        __regexStrng (re): matches the type hint string for a string variable
        __regexEvaluatable (re): matches the type hint string for a compoind data type
        __types (dict): mapping of type hinted types to actual Python types
        __tests (dict): mapping of the regex patterns to actual python types
    """
    _typehints = dict()

    __regexGetType = re.compile(r'([^\{]*)\{([^\}]*)\}')
                                    # Match the contents of the inner most{}
    __regexSignedInt = re.compile(r'^I\d+')
                                    # Matches all signed integers
    __regexUnsignedInt = re.compile(r'^U / d+')
                                    # Match unsigned integers
    __regexFloat = re.compile(r'^(Extended|Double|Single)\sFloat')
                                    # Match floating point types
    __regexBoolean = re.compile(r'^Boolean')
    __regexString = re.compile(r'^(String|Path|Enum)')
    __regexEvaluatable = re.compile(r'^(Cluster|\dD Array|List)')

    __types = {'Boolean': bool, 'I32': int, 'Double Float': float,
        'Cluster': dict, 'Array': numpy.ndarray,'List':list,  'String': str}
    # This is the inverse of the __tests below - this gives
    # the string type for standard Python classes

    __tests = [(__regexSignedInt, int), (__regexUnsignedInt, int),
             (__regexFloat, float), (__regexBoolean, bool),
             (__regexString, str), (__regexEvaluatable, _evaluatable())]
        # This is used to work out the correct python class for
        # some string types

    def __init__(self, *args, **kargs):
        """typeHintedDict constructor method.

        Args:
            *args, **kargs: Pass any parameters through to the dict() constructor.


        Calls the dict() constructor, then runs through the keys of the
        created dictionary and either uses the string type embedded in
        the keyname to generate the type hint (and remove the
        embedded string type from the keyname) or determines the likely
        type hint from the value of the dict element.
        """

        super(typeHintedDict, self).__init__(*args, **kargs)
        for key in self:  # Chekc through all the keys and see if they contain
                                    # type hints. If they do, move them to the
                                    # _typehint dict
            value=super(typeHintedDict,self).__getitem__(key)
            super(typeHintedDict,self).__delitem__(key)
            self[key]=value #__Setitem__ has the logic to handle embedded type hints correctly

    def __getattr__(self, name):
        """Handles attribute access"""
        if name == "types":
            return self._typehints
        else:
            raise AttributeError

    def __findtype(self,  value):
        """Determines the correct string type to return for common python
        classes. Understands booleans, strings, integers, floats and numpy
        arrays(as arrays), and dictionaries (as clusters).

        Args:
            value (any): The data value to determine the type hint for.

        Returns:
            A type hint string
        """
        typ = "String"
        for t in self.__types:
            if isinstance(value, self.__types[t]):
                if t == "Cluster":
                    elements = []
                    for k in  value:
                        elements.append(self.__findtype(value[k]))
                    tt = ','
                    tt = tt.join(elements)
                    typ = 'Cluster (' + tt + ')'
                elif t == 'Array':
                    z = numpy.zeros(1, dtype=value.dtype)
                    typ = (str(len(numpy.shape(value))) + "D Array (" +
                                                self.__findtype(z[0]) + ")")
                else:
                    typ = t
                break
        return typ

    def __mungevalue(self, t, value):
        """Based on a string type t, return value cast to an
        appropriate python class

        Args:
            t (string): is a string representing the type
            value (any): is the data value to be munged into the
                        correct class
        Returns:
            Returns the munged data value

        Detail:
            The class has a series of precompiled regular
            expressions that will match type strings, a list of these has been
            constructed with instances of the matching Python classes. These
            are tested in turn and if the type string matches the constructor of
            the associated python class is called with value as its argument."""
        ret=None
        for (regexp, valuetype) in self.__tests:
            m = regexp.search(t)
            if m is not None:
                if isinstance(valuetype, _evaluatable):
                    try:
                        ret = eval(str(value), globals(), locals())
                    except NameError:
                        ret = str(value)
                    except SyntaxError:
                        ret = ""
                    break
                else:
                    ret=valuetype(value)
                    break
        else:
            ret=str(value)
        return ret

    def string_to_type(self, value):
        """Given a string value try to work out if there is a better python type dor the value

        Args:
            value (string): string representation of he value
        Returns:
            A python object of the natural type for value"""
        ret=None
        if not isinstance(value, str):
            raise TypeError("Value must be a string not a "+str(type(value)))
        value=value.strip()
        if len(value)!=0:
            tests=['list('+value+')','dict('+value+')']
            try:
                i="[{".index(value[0])
                ret=eval(tests[i])
            except (SyntaxError,ValueError):
                if value.lower() in ['true', 'ues','on','false','no','off']:
                    ret=value.lower() in ['true','yes','on'] #Booleab
                else:
                    for trial in [int,float,str]:
                        try:
                            ret=trial(value)
                            break
                        except ValueError:
                            continue
                    else:
                        ret=None
        return ret

    def _get_name_(self,name):
        """Checks a string name for an embedded type hint and strips it out.
        Args:
            name(string): String containing the name with possible type hint embedeed
        Returns:
            (name,typehint) (tuple): A tuple containing just the name of the mateadata and (if found
        the type hint string),
        """
        name=str(name)
        m = self.__regexGetType.search(name)
        if m is not None:
            k = m.group(1)
            t = m.group(2)
            return k,t
        else:
            k=name
            t=None
            return k,None

    def __getitem__(self,name):
        """Provides a get item method that checks whether its been given a typehint in the
        item name and deals with it appropriately.
        Args:
            name (string): metadata key to retrieve
        Returns:
            metadata value
        """
        (name,typehint)=self._get_name_(name)
        value=super(typeHintedDict,self).__getitem__(name)
        if typehint is not None:
            value=self.__mungevalue(typehint,value)
        return value

    def __setitem__(self, name, value):
        """Provides a method to set an item in the dict, checking the key for
        an embedded type hint or inspecting the value as necessary.

        Args:
            name (string): The metadata keyname
            value (any): The value to store in the metadata string

        Note:
            If you provide an embedded type string it is your responsibility
            to make sure that it correctly describes the actual data
            typehintDict does not verify that your data and type string are
            compatible."""
        name,typehint=self._get_name_(name)
        if typehint is not None:
            self._typehints[name] = typehint
            if len(str(value)) == 0:  # Empty data so reset to string and set empty
                super(typeHintedDict, self).__setitem__(name, "")
                self._typehints[name] = "String"
            else:
                super(typeHintedDict, self).__setitem__(name,
                                                self.__mungevalue(typehint, value))
        else:
            self._typehints[name] = self.__findtype(value)
            super(typeHintedDict, self).__setitem__(name,
                self.__mungevalue(self._typehints[name], value))

    def __delitem__(self, name):
        """Deletes the specified key

        Args:
            name (string): The keyname to be deleted"""
        name=self._get_name_(name)[0]
        del(self._typehints[name])
        super(typeHintedDict, self).__delitem__(name)

    def copy(self):
        """Provides a copy method that is aware of the type hinting strings

        Returns:
            A copy of the current typeHintedDict
        """
        ret=typeHintedDict()
        for k in self.keys():
            t=self._typehints[k]
            nk=k+"{"+t+"}"
            ret[nk]=copy.deepcopy(self[k])
        return ret

    def type(self, key):
        """Returns the typehint for the given k(s)

        Args:
            key (string or sequence of strings): Either a single string key or a iterable type containing
                keys
        Returns:
            The string type hint (or a list of string type hints)"""
        if isinstance(key, str):
            return self._typehints[key]
        else:
            try:
                return [self._typehints[x] for x in key]
            except TypeError:
                return self._typehints[key]

    def export(self, key):
        """Exports a single metadata value to a string representation with type
        hint

        Args:
            key (string): The metadata key to export
        Returns:
            A string of the format : key{type hint} = value"""
        return key + "{" + self.type(key) + "}=" + str(self[key])




class DataFile(object):
    """:py:class:`Stoner.Core.DataFile` is the base class object that represents
    a matrix of data, associated metadata and column headers.

    Attributes:
        data (2D Array) A numpy masked array of data (usually floats)
        metadata (typeHintedDict): of key-value metadata pairs. The dictionary
            tries to retain information about the type of data so as to aid import and
            export from CM group LabVIEw code.
        column_headers (list): of strings of the column names of the data
        title (string): The title of the measurement
        filename (string): The current filename of the data if loaded from or
            already saved to disc. This is the default filename used by the @b load() and @b save()

    Methods:
        mask: Returns the current mask applied to the numerical data equivalent to self.data.mask
        shape: Returns the shape of the data (rows,columns) - equivalent to self.data.shape
        records: Returns the data in the form of a list of dictionaries
        clone: Creates a deep copy of the :py:class`DataFile` object
    """

    #Class attributes
    #Priority is the load order for the class
    priority=32

    _conv_string=numpy.vectorize(lambda x:str(x))
    _conv_float=numpy.vectorize(lambda x:float(x))
    file_pattern="Data Files (*.csv;*.dat;*.txt;*.dql;*.fld;*.*.tdi;*.spc)|*.csv *.dat *.txt *.dql *.fld *.tdi *.spc| All Files (*.*)|*.*|"

    #   INITIALISATION

    def __init__(self, *args, **kargs):
        """Constructor method for :py:class:`DataFile`

        various forms are recognised:
        :function DataFile('filename',<optional filetype>,<args>)
            Creates the new DataFile object and then executes the @b DataFile.load
            method to load data from the given @a filename
        :function DataFile(array)
            Creates a new DataFile object and assigns the @a array to the
            `DataFile.data`  attribute.
        :function DataFile(dictionary)
            Creates the new DataFile object, but initialises the metadata with
            :parameter dictionary
        :function DataFile(array,dictionary),
            Creates the new DataFile object and does the combination of the
            previous two forms.
        :function DataFile(DataFile)
            Creates the new DataFile object and initialises all data from the
            existing :py:class:`DataFile` instance. This on the face of it does the same as
            the assignment operator, but is more useful when one or other of the
            DataFile objects is an instance of a sub - class of DataFile

        Args:
            *args Variable number of arguments that match one of the
            definitions above
        Returns:
            A new instance of the DataFile class.
        """
        # init instance attributes
        self.debug=False
        self._masks=[False]
        self.metadata=typeHintedDict()
        self.data = ma.masked_array([])
        self.filename = None
        self.column_headers = list()
        i=len(args) if len(args)<2 else 2
        handler=[None,self._init_single,self._init_double,self._init_many][i]
        if handler is not None:
            handler(*args,**kargs)
        self.metadata["Stoner.class"]=self.__class__.__name__
        self.mask=False

    # Special Methods

    def _init_single(self,*args,**kargs):
        """Handles constructor with 1 arguement - called from __init__."""
        arg=args[0]
        if (isinstance(arg, (str,unicode)) or (isinstance(arg, bool) and not arg)):
                                    # Filename- load datafile
            t = self.load(arg, **kargs)
            self.data = ma.masked_array(t.data)
            self.metadata = t.metadata
            self.column_headers = t.column_headers
        elif isinstance(arg, numpy.ndarray):
                                                # numpy.array - set data
            self.data = ma.masked_array(arg)
            self.column_headers = ['Column' + str(x)
                                for x in range(numpy.shape(args[0])[1])]
        elif isinstance(arg, dict):  # Dictionary - use as metadata
            self.metadata = arg.copy()
        elif isinstance(arg, DataFile):
            self.metadata = arg.metadata.copy()
            self.data = ma.masked_array(arg.data)
            self.column_headers = copy.copy(arg.column_headers)
            self.filename=arg.filename
        else:
            raise SyntaxError("No constructor")

    def _init_double(self,*args,**kargs):
        """Two argument constructors handled here. Called form __init__"""
        (arg0,arg1)=args
        if isinstance(arg0, numpy.ndarray):
            self.data = ma.masked_array(arg0)
        elif isinstance(arg0, dict):
            self.metadata = arg0.copy()
        elif isinstance(arg0, str) and isinstance(arg1, str):
            self.load(arg0, arg1)
        if isinstance(arg1, numpy.ndarray):
            self.data = ma.masked_array(arg1)
        elif isinstance(arg1, dict):
            self.metadata = arg1.copy()

    def _init_many(self,*args,**kargs):
        """Handles more than two arguments to the constructor - called from init."""
        self.load(*args, **kargs)


    def __add__(self, other):
        """ Implements a + operator to concatenate rows of data

        Args:
            other (numpy arra `Stoner.Core.DataFile` or a dictionary or a list):

        Note:
            * If other is a dictionary then the keys of the dictionary are passed to
            :py:meth:`find_col` to see if they match a column, in which case the
            corresponding value will be used for theat column in the new row.
            Columns which do not have a matching key will be set to NaN. If other has keys
            that are not found as columns in self, additional columns are added.
            * If other is a list, then the add method is called recursively for each element
            of the list.
            * Returns: A Datafile object with the rows of @a other appended
            to the rows of the current object.
            * If other is a 1D numopy array with the same number of
            elements as their are columns in @a self.data then the numpy
            array is treated as a new row of data If @a ither is a 2D numpy
            array then it is appended if it has the same number of
            columns and @a self.data."""
        if isinstance(other, numpy.ndarray):
            if len(self.data) == 0:
                t = numpy.atleast_2d(other)
                c = numpy.shape(t)[1]
                if len(self.column_headers) < c:
                    self.column_headers.extend(["Column_{}".format(x) for x in range(c - len(self.column_headers))])
                newdata = self.__class__(self)
                newdata.data = t
                ret=newdata
            elif len(numpy.shape(other)) == 1:
                                    # 1D array, so assume a single row of data
                if numpy.shape(other)[0] == numpy.shape(self.data)[1]:
                    newdata = self.__class__(self)
                    newdata.data = numpy.append(self.data,
                                                numpy.atleast_2d(other), 0)
                    ret=newdata
                else:
                    ret=NotImplemented
            elif len(numpy.shape(other)) == 2 and numpy.shape(
                    other)[1] == numpy.shape(self.data)[1]:
                            # DataFile + array with correct number of columns
                newdata = self.__class__(self)
                newdata.data = numpy.append(self.data, other, 0)
                ret=newdata
            else:
                ret=NotImplemented
        elif isinstance(other, DataFile):  # Appending another DataFile
            new_data=numpy.zeros((len(other), len(self.column_headers)))*numpy.nan
            for i in range(len(self.column_headers)):
                column=self.column_headers[i]
                try:
                    new_data[:, i]=other.column(column)
                except KeyError:
                    pass
            newdata = self.__class__(other)
            for x in self.metadata:
                newdata[x] = self[x]
            newdata.data = numpy.append(self.data, new_data, 0)
            ret=newdata
        elif isinstance(other,dict):
            newdata=self
            added_row=False
            for k in other:
                try:
                    newdata.find_col(k)
                except KeyError:
                    newdata=newdata.clone
                    if len(newdata)==0:
                        added_row=True
                        cl=1
                    else:
                        cl=len(newdata)
                    newdata=newdata&numpy.ones(cl)*numpy.nan
                    newdata.column_headers[-1]=k
            new_data=numpy.nan*numpy.ones(len((newdata.column_headers)))
            for k in other:
                new_data[newdata.find_col(k)]=other[k]
            new_data=numpy.atleast_2d(new_data)
            newdata.data=numpy.append(newdata.data,new_data,0)
            if added_row:
                newdata.data=newdata.data[1:,:]
            ret=newdata
        elif isinstance(other,list):
            newdata=self
            for o in other:
                newdata=newdata+o
            ret=newdata
        else:
            ret=NotImplemented('Failed in DataFile')
        return ret

    def __and__(self, other):
        """Implements the & operator to concatenate columns of data in a
        :py:class:`DataFile` object.

        Args:
            other  (numpy array or :py:class:`DataFile`): Data to be added to this DataFile instance

        Returns:
            A :py:class:`DataFile` object with the columns of other con
        catenated as new columns at the end of the self object.

        Note:
            Whether other is a numopy array of :py:class:`DataFile`, it must
            have the same or fewer rows than the self object.
            The size of @a other is increased with zeros for the extra rows.
            If other is a 1D numpy array it is treated as a column vector.
            The new columns are given blank column headers, but the
            length of the @b Stoner.DataFile.column_headers is
            increased to match the actual number of columns.
        """
        newdata=self.__class__(self.clone)
        if len(newdata.data.shape)<2:
            newdata.data=numpy.atleast_2d(newdata.data)
        if isinstance(other, numpy.ndarray):
            if len(other.shape) != 2:  # 1D array, make it 2D column
                other = numpy.atleast_2d(other)
                other = other.T
            if numpy.product(self.data.shape)==0: #Special case no data yet
                newdata.data=other
                newdata.column_headers=["Coumn "+str(i) for i in range(other.shape[1])]
            elif self.data.shape[0]==other.shape[0]:
                newdata.data=numpy.append(newdata.data,other,1)
                newdata.column_headers.extend(["Column "+str(i+len(newdata.column_headers)) for i in range(other.shape[1])])
            elif self.data.shape[0]<other.shape[0]: #Need to extend self.data
                newdata.data=numpy.append(self.data,numpy.zeros((other.shape[0]-self.data.shape[0],self.data.shape[1])),0)
                newdata.data=numpy.append(self.data,other,1)
                newdata.column_headers.extend(["Column "+str(i+len(newdata.column_headers)) for i in range(other.shape[1])])
            else:                    # DataFile + array with correct number of rows
                if other.shape[0] < self.data.shape[0]:
                    # too few rows we can extend with zeros
                    other = numpy.append(other, numpy.zeros((self.data.shape[0]
                                    - other.shape[0], other.shape[1])), 0)
                newdata.column_headers.extend([""
                                               for x in range(other.shape[1])])
                newdata.data = numpy.append(self.data, other, 1)
        elif isinstance(other, DataFile):  # Appending another datafile
            if len(other.data.shape)<2:
                other=other.clone
                other.data=numpy.atleast_2d(other.data)
            (myrows,mycols)=newdata.data.shape
            (yourrows,yourcols)=other.data.shape
            if myrows>yourrows:
                other=other.clone
                other.data=numpy.append(other.data,numpy.zeros((myrows-yourrows,yourcols)),0)
            elif myrows<yourrows:
                newdata.data=numpy.append(newdata.data,numpy.zeros((yourrows-myrows,mycols)),0)

            newdata.column_headers.extend(other.column_headers)
            newdata.metadata.update(other.metadata)
            newdata.data = numpy.append(newdata.data, other.data, 1)
        else:
            newdata=NotImplemented
        return newdata

    def __contains__(self, item):
        """Operator function for membertship tests - used to check metadata contents

        Args:
            item(string): name of metadata key

        Returns:
            iem in self.metadata"""
        return item in self.metadata

    def __delitem__(self,item):
        """Implements row or metadata deletion.

        Args:
            item (ingteger or string):  row index or name of metadata to delete"""
        if isinstance(item,str):
            del(self.metadata[item])
        else:
            self.del_rows(item)

    def __dir__(self):
        """Reeturns the attributes of the current object by augmenting the keys of self.__dict__ with
        the attributes that __getattr__ will handle.
        """
        attr=self.__dict__.keys()
        attr.extend(['records', 'clone','subclasses', 'shape', 'mask', 'dict_records'])
        return attr

    def __file_dialog(self, mode):
        """Creates a file dialog box for loading or saving ~b DataFile objects

        Args:
            mode (string): The mode of the file operation  'r' or 'w'

        Returns:
            A filename to be used for the file operation."""
        try:
            from enthought.pyface.api import FileDialog, OK
        except ImportError:
            from pyface.api import FileDialog, OK
        # Wildcard pattern to be used in file dialogs.
        file_wildcard = self.file_pattern

        if mode == "r":
            mode = "open"
        elif mode == "w":
            mode = "save as"

        if self.filename is not None:
            filename = os.path.basename(self.filename)
            dirname = os.path.dirname(self.filename)
        else:
            filename = ""
            dirname = ""
        dlg = FileDialog(action=mode, wildcard=file_wildcard)
        dlg.default_filename=filename
        dlg.default_directory=dirname
        dlg.open()
        if dlg.return_code == OK:
            self.filename = dlg.path
            return self.filename
        else:
            return None

    def __getattr__(self, name):
        """
        Called for :py:class:`DataFile`.x to handle some special pseudo attributes
        and otherwise to act as a shortcut for @b DataFile.column

        Args:
            name (string): The name of the attribute to be returned.

        Returns:
            the DataFile object in various forms

        Supported attributes:
        - records - return the DataFile data as a numpy structured
        array - i.e. rows of elements whose keys are column headings
        - clone - returns a deep copy of the current DataFile instance

        Otherwise the name parameter is tried as an argument to
        :py:meth:`DataFile.column` and the resultant column isreturned. If
        DataFile.column raises a KeyError this is remapped as an
        AttributeError.
       """

        easy={"clone":self._getattr_clone,
              "dict_records":self._getattr_dict_records,
              "dtype":self._getattr_dtype,
              "mask":self._getattr_mask,
              "T":self._getattr_by_columns,
              "records":self._getattr_records,
              "shape":self._getattr_shape,
              "subclasses":self._getattr_subclasses
              }
        if name in easy:
            return easy[name]()
        elif len(self.column_headers)>0:
            try:
                col=self.find_col(name)
                return self.column(col)
            except KeyError:
                pass
        raise AttributeError("{} is not an attribute of DataFile nor a column name".format(name))

    def _getattr_by_columns(self):
        """Gets the current data transposed
        """
        return self.data.T


    def _getattr_clone(self):
        """Gets a deep copy of the current DataFile
        """
        return self.__class__(copy.deepcopy(self))

    def _getattr_dict_records(self):
        """Return the data as a dictionary of single columns with column headers for the keys.
        """
        return numpy.array([dict(zip(self.column_headers, r)) for r in self.rows()])

    def _getattr_dtype(self):
        """Return the numpy dtype attribute of the data
        """
        return self.data.dtype

    def _getattr_mask(self):
        """Returns the mask of the data array.
        """
        return ma.getmaskarray(self.data)

    def _getattr_records(self):
        """Returns the data as a numpy structured data array. If columns names are duplicated then they
        are made unique
        """
        ch=copy.copy(self.column_headers) # renoved duplicated column headers for structured record
        for i in range(len(ch)):
            header=ch[i]
            j=0
            while ch[i] in ch[i+1:] or ch[i] in ch[0:i]:
                j=j+1
                ch[i]="{}_{}".format(header,j)
        print ch
        dtype = [(x, self.dtype) for x in ch]
        return self.data.view(dtype=dtype).reshape(len(self))

    def _getattr_shape(self):
        """Pass through the numpy shape attribute of the data
        """
        return self.data.shape

    def _getattr_subclasses(self):
        """Return a list of all in memory subclasses of this DataFile
        """
        return {x.__name__:x for x in itersubclasses(DataFile)}

    def __getitem__(self, name):
        """Called for DataFile[x] to return either a row or iterm of
        metadata

        Args:
            name (string or slice or int): The name, slice or number of the part of the
            :py:class:`DataFile` to be returned.

        Returns:
            an item of metadata or row(s) of data.

        - If name is an integer then the corresponding single row will be returned
        - if name is a slice, then the corresponding rows of data will be returned.
        - If name is a string then the metadata dictionary item             with the correspondoing key will be returned.
        - If name is a numpy array then the corresponding rows of the data are returned.
        - If a tuple is supplied as the arguement then there are a number of possible behaviours.
            - If the first element of the tuple is a string, then it is assumed that it is the nth element of the named metadata is required.
            - Otherwise itis assumed that it is a particular element within a column determined by the second part of the tuple that is required.

        Examples:
            DataFile['Temp',5] would return the 6th element of the
            list of elements in the metadata called 'Temp', while

            DataFile[5,'Temp'] would return the 6th row of the data column
            called 'Temp'

            and DataFile[5,3] would return the 6th element of the
            4th column.
        """
        if isinstance(name, slice):
            indices = name.indices(len(self))
            name = range(*indices)
            d = self.data[name[0], :]
            d = numpy.atleast_2d(d)
            for x in range(1, len(name)):
                d = numpy.append(d, numpy.atleast_2d(self.data[x, :]), 0)
            return d
        elif isinstance(name, int):
            return self.data[name, :]
        elif isinstance(name, numpy.ndarray) and len(name.shape)==1:
            return self.data[name, :]
        elif isinstance(name, str) or isinstance(name, unicode):
            name=str(name)
            return self.meta(name)
        elif isinstance(name, tuple) and len(name) == 2:
            x, y = name
            if isinstance(x, str):
                return self[x][y]
            else:
                d = numpy.atleast_2d(self[x])
                y = self.find_col(y)
                r = d[:, y]
                if len(r) == 1:
                    r = r[0]
                return r
        else:
            raise TypeError("Key must be either numeric of string")

    def __getstate__(self):
        return {"data": self.data,  "column_headers":
            self.column_headers,  "metadata": self.metadata}

    def __len__(self):
        """Return the length of the data.shape
                Returns: Returns the number of rows of data
                """
        return numpy.shape(self.data)[0]

    def __lshift__(self, other):
        """Overird the left shift << operator for a string or an iterable object to import using the :py:meth:`__read_iterable` function

        Args:
            other (string or iterable object): Used to source the DataFile object

        Returns:
            A new DataFile object

        TODO:
            Make code work better with streams
        """
        newdata=self.__class__()
        if isinstance(other, str):
            lines=itertools.imap(lambda x:x,  other.splitlines())
            newdata.__read_iterable(lines)
        elif isinstance(other, collections.Iterable):
            newdata.__read_iterable(other)
        return newdata

    def __parse_data(self):
        """Internal function to parse the tab deliminated text file
        """

        self.__read_iterable(fileinput.FileInput(self.filename))

    def __parse_metadata(self, key, value):
        """Parse the metadata string, removing the type hints into a separate
        dictionary from the metadata

        Args:
            key (string): The name of the metadata parameter to be written,
        possibly including a type hinting string.
            value (any): The value of the item of metadata.

        Returns:
            Nothing, but the current instance's metadata is changed.

        Note:
            Uses the typehint to set the type correctly in the dictionary

            All the clever work of managing the typehinting is done in the
        metadata dictionary object now.
        """
        self.metadata[key] = value

    def __read_iterable(self, reader):
        """Internal method to read a string representation of py:class:`DataFile` in line by line."""

        row=reader.next().split('\t')
        if row[0].strip()!="TDI Format 1.5":
            raise RuntimeError("Not a TDI File")
        col_headers_tmp=[x.strip() for x in row[1:]]
        cols=len(col_headers_tmp)
        self.data=ma.masked_array([])
        for r in reader:
            if r.strip()=="": # Blank line
                continue
            row=r.rstrip().split('\t')
            cols=max(cols, len(row)-1)
            if row[0].strip()!='':
                md=row[0].split('=')
                if len(md)==2:
                    md[1]="=".join(md[1:])
                elif len(md)<=1:
                    md.extend(['',''])

                self.metadata[md[0].strip()]=md[1].strip()
            if len(row)<2:
                continue
            self.data=numpy.append(self.data, self._conv_float(row[1:]))
        self.data=numpy.reshape(self.data, (-1, cols))
        self.column_headers=["Column "+str(i) for i in range(cols)]
        for i in range(len(col_headers_tmp)):
            self.column_headers[i]=col_headers_tmp[i]


    def __reduce_ex__(self, p):
        return (DataFile, (), self.__getstate__())

    def __repr__(self):
        """Outputs the :py:class:`DataFile` object in TDI format.
        This allows one to print any :py:class:`DataFile` to a stream based
                object andgenerate a reasonable textual representation of
                the data.shape

                Returns:
                    self in a textual format. """
        outp = "TDI Format 1.5\t" + "\t".join(self.column_headers)+"\n"
        m = len(self.metadata)
        self.data=ma.masked_array(numpy.atleast_2d(self.data))
        r = numpy.shape(self.data)[0]
        md = [self.metadata.export(x) for x in sorted(self.metadata)]
        for x in range(min(r, m)):
            outp = outp + md[x] + "\t" + "\t".join([str(y) for y in self.data[x].filled()])+ "\n"
        if m > r:  # More metadata
            for x in range(r, m):
                outp = outp + md[x] + "\n"
        elif r > m:  # More data than metadata
            for x in range(m, r):
                outp = outp + "\t" + "\t".join([str(y) for y in self.data[x].filled()])+ "\n"
        return outp


    def __setattr__(self, name, value):
        """Handles attempts to set attributes not covered with class attribute variables.

        Args:
            name (string): Name of attribute to set. Details of possible attributes below:

        - mask Passes through to the mask attribute of self.data (which is a numpy masked array). Also handles the case where you pass a callable object to nask where we pass each row to the function and use the return reult as the mask
        - data Ensures that the :py:attr:`data` attribute is always a :py:class:`numpy.ma.maskedarray`
        """
        if name=="mask":
            if callable(value):
                self._set_mask(value, invert=False)
            else:
                self.data.mask=value
        elif name=="data":
            self.__dict__[name]=ma.masked_array(value)
        elif name=="T":
            self.data.T=value
        else:
            self.__dict__[name] = value

    def __setitem__(self, name, value):
        """Called for @b DataFile[@em name ] = @em value to write mewtadata
        entries.

        Args:
            name (string): The string key used to access the metadata
            value (any): The value to be written into the metadata. Currently bool, int, float and string values are correctly handled. Everythign else is treated as a string.

        Returns:
            Nothing."""
        self.metadata[name] = value

    def __setstate__(self, state):
        """Internal function for pickling."""
        self.data = ma.masked_array(state["data"])
        self.column_headers = state["column_headers"]
        self.metadata = state["metadata"]

    #Private Functions

    def _set_mask(self, func, invert=False,  cumulative=False, col=0):
        """Applies func to each row in self.data and uses the result to set the mask for the row

        Args:
            func (callable): A Callable object of the form lambda x:True where x is a row of data (numpy
            invert (bool): Optionally invert te reult of the func test so that it unmasks data instead
            cumulative (bool): if tru, then an unmask value doesn't unmask the data, it just leaves it as it is."""

        i=-1
        args=len(inspect.getargs(func.__code__)[0])
        for r in self.rows():
            i+=1
            if args==2:
                t=func(r[col], r)
            else:
                t=func(r)
            if isinstance(t, bool) or isinstance(t, numpy.bool_):
                if t^invert:
                    self.data[i]=ma.masked
                elif not cumulative:
                    self.data[i]=self.data.data[i]
            else:
                for j in range(min(len(t), numpy.shape(self.data)[1])):
                    if t[j]^invert:
                        self.data[i, j]=ma.masked
                    elif not cumulative:
                        self.data[i, j]=self.data.data[i, j]

    def _push_mask(self, mask=None):
        """Copy the current data mask to a temporary store and replace it with a new mask if supplied

        Args:
            mask (:py:class:numpy.array of bool or bool or None):
                The new data mask to apply (defaults to None = unmask the data

        Returns:
            Nothing"""
        self._masks.append(self.mask)
        if mask is None:
            self.data.mask=False
        else:
            self.mask=mask

    def _pop_mask(self):
        """Replaces the mask on the data with the last one stored by _push_mask()

        Returns:
            Nothing"""
        self.mask=False
        self.mask=self._masks.pop()
        if len(self._masks)==0:
            self._masks=[False]

    #   PUBLIC METHODS

    def add_column(self, column_data, column_header=None, index=None,
                   func_args=None, replace=False):
        """Appends a column of data or inserts a column to a datafile

        Args:
            column_data (:py:class:`numpy.array` or list or callable): Data to append or insert or a callable function that will generate new data

        Keyword Arguments:
            column_header (string): The text to set the column header to, if not supplied then defaults to 'col#'
            index (int or string): The  index (numeric or string) to insert (or replace) the data
            func_args (dict): If column_data is a callable object, then this argument can be used to supply a dictionary of function arguments to the callable object.
        :   replace (bool): Replace the data or insert the data (default)

        Returns:
            The :py:class:`DataFile` instance with the additonal column inserted.

        Note:
            Also modifies the original DataFile Instance."""
        if index is None:
            index = len(self.column_headers)
            replace = False
            if column_header is None:
                column_header = "Col" + str(index)
        else:
            index = self.find_col(index)
            if column_header is None:
                column_header = self.column_headers[index]
        if not replace:
            if len(self.column_headers) == 0:
                self.column_headers=[column_header]
            else:
                self.column_headers.insert(index, column_header)
        else:
            self.column_headers[index] = column_header

        # The following 2 lines make the array we are adding a
        # [1, x] array, i.e. a column by first making it 2d and
        # then transposing it.
        if isinstance(column_data, numpy.ndarray):
            if len(numpy.shape(column_data)) != 1:
                raise ValueError('Column data must be 1 dimensional')
            else:
                numpy_data = column_data
        elif callable(column_data):
            if isinstance(func_args, dict):
                new_data = [column_data(x, **func_args) for x in self]
            else:
                new_data = [column_data(x) for x in self]
            numpy_data = numpy.array(new_data)
        elif isinstance(column_data,  list):
            numpy_data=numpy.array(column_data)
        else:
            return NotImplemented
        #Sort out the sizes of the arrays
        cl=len(numpy_data)
        if len(self.data.shape)==2:
            (dr,dc)=self.data.shape
        elif len(self.data.shape)==1:
            self.data=numpy.atleast_2d(self.data).T
            (dr,dc)=self.data.shape
        elif len(self.data.shape)==0:
            self.data=numpy.array([[]])
            (dr,dc)=(0,0)
        if cl>dr and dc*dr>0:
            self.data=numpy.append(self.data,numpy.zeros((cl-dr,dc)),0)
        elif cl<dr:
            numpy_data=numpy.append(numpy_data,numpy.zeros(dr-cl))
        print dr,dc,cl
        if replace:
            self.data[:, index] = numpy_data
        else:
            if dc*dr == 0:
                self.data=ma.masked_array(numpy.transpose(numpy.atleast_2d(numpy_data)))
            else:
                self.data = ma.masked_array(numpy.insert(self.data, index, numpy_data, 1))
        return self

    def column(self, col):
        """Extracts a column of data by index or name

        Args:
            col (int, string, list or re): is the column index as defined for :py:meth:`DataFile.find_col`

        Returns:s
            one or more columns of data"""
        return self.data[:, self.find_col(col)]

    def columns(self):
        """Generator method that will iterate over columns of data

        Yields:
            Returns the next column of data."""
        c = numpy.shape(self.data)[1]
        for col in range(c):
            yield self.data[col]

    def del_column(self, col=None,duplicates=False):
        """Deletes a column from the current @b DataFile object

        Args:
            col (int, string, list or re): is the column index as defined for :py:meth:`DataFile.find_col` to the column to be deleted

        Keyword Arguments:
            duplicates (bool): (default False) look for duplicated columns

        Returns:
            The :py:class:`DataFile` object with the column deleted.

        Note:
            - If duplicates is True and col is None then all duplicate columns are removed,
            - if col is not None and duplicates is True then all duplicates of the specified column are removed.
            - If duplicates is false then @a col must not be None otherwise a RuntimeError is raised.
            - If col is a list (duplicates should not be None) then the all the matching columns are found.
            """

        if duplicates:
            ch=self.column_headers
            dups=[]
            if col is None:
                for i in range(len(ch)):
                    if ch[i] in ch[i+1:]:
                        dups.append(ch.index(ch[i],i+1))
            else:
                col=ch[self.find_col(col)]
                i=ch.index(col)
                while True:
                    try:
                        i=ch.index(col,i+1)
                        dups.append(i)
                    except ValueError:
                        break
            return self.del_column(dups,duplicates=False)
        else:
            if col is None:
                raise RuntimeError("Column must not be None unless removing duplicates in DataFile.del_column")
            c = self.find_col(col)
            self.data = numpy.ma.masked_array(numpy.delete(self.data, c, 1), mask=numpy.delete(self.data.mask, c, 1))
            if isinstance(c, list):
                c.sort(reverse=True)
            else:
                c = [c]
            for col in c:
                del self.column_headers[col]
            return self

    def del_rows(self, col, val=None):
        """Searchs in the numerica data for the lines that match and deletes
        the corresponding rows

        Args:
            col (list,slice,int,string or re) Column containg values to search for.
            val (float or callable): Specifies rows to delete. Maybe
                - None - in which case whole columns are deleted,
                - a float in which case rows whose columncol = val are deleted
                - or a function - in which case rows where the function evaluates to be true are deleted.

        Returns:
            The current object

        Note:
            If val is a function it should take two arguments - a float and a
            list. The float is the value of the current row that corresponds to column col abd the second
            argument is the current row.

        TODO:
            Implement val is a tuple for deletinging in a range of values.
            """
        if isinstance(col, slice) and val is None:
            indices = col.indices(len(self))
            col -= range(*indices)
        if isinstance(col, list) and val is None:
            col.sort(reverse=True)
            for c in col:
                self.del_rows(c)
        elif isinstance(col,  int) and val is None:
            self.data = numpy.delete(self.data, col, 0)
        else:
            col = self.find_col(col)
            d = self.column(col)
            if callable(val):
                rows = numpy.nonzero([bool(val(x[col], x) and x[col] is not ma.masked) for x in self])[0]
            elif isinstance(val, float):
                rows = numpy.nonzero([x == val for x in d])[0]
            self.data = ma.masked_array(numpy.delete(self.data, rows, 0), mask=numpy.delete(self.data.mask, rows, 0))
        return self

    def dir(self, pattern=None):
        """ Return a list of keys in the metadata, filtering wiht a regular
        expression if necessary

        Keyword Arguments:
            pattern (re): is a regular expression or None to list all keys

        Returns:
            Returns a list of metadata keys."""
        if pattern == None:
            return self.metadata.keys()
        else:
            test = re.compile(pattern)
            possible = [x for x in self.metadata.keys() if test.search(x)]
            return possible

    def filter(self,func=None,cols=None,reset=True):
        """Function to set the mask on rows of data by evaluating a function for each row

        Args:
            func (callable): is a callable object that should take a single listas a p[arameter representing one row.
            cols (list): a list of column indices that are used to form the list of values passed to func.
            reset (bool): determines whether the mask is reset before doing the filter (otherwise rows already masked out will be ignored in the filter (so the filter is logically or'd)) The default value of None results in a complete row being passed into func.

        Returns:
            The current object with the mask set
        """
        if cols is None:
            cols=range(self.data.shape[1])
        cols=[self.find_col(c) for c in cols]
        self.data.mask=ma.getmaskarray(self.data)
        i=0
        if reset: self.data.mask=False
        for r in self.rows():
            self.data.mask[i,:]=not func(r[cols])
            i=i+1
        return self

    def find_col(self, col):
        """Indexes the column headers in order to locate a column of data.shape

        Indexing can be by supplying an integer, a string, a regular experssion, a slice or a list of any of the above.
        -   Integer indices are simply checked to ensure that they are in range
        -   String indices are first checked for an exact match against a column header
            if that fails they are then compiled to a regular expression and the first
            match to a column header is taken.
        -   A regular expression index is simply matched against the column headers and the
            first match found is taken. This allows additional regular expression options
            such as case insensitivity.
        -   A slice index is converted to a list of integers and processed as below
        -   A list index returns the results of feading each item in the list at @b find_col
            in turn.

        Args:
            col (int, a string, a re, a slice or a list):  Which column(s) to retuirn indices for.

        Returns:
            The matching column index as an integer or a @b KeyError
        """
        if isinstance(col, int):  # col is an int so pass on
            if not 0<=col<self.data.shape[1]:
                raise IndexError('Attempting to index a non - existant column '+str(col))
        elif isinstance(col, str) or isinstance(col, unicode):  # Ok we have a string
            col=str(col)
            if col in self.column_headers:  # and it is an exact string match
                col = self.column_headers.index(col)
            else:  # ok we'll try for a regular expression
                test = re.compile(col)
                possible =[x for x in self.column_headers if test.search(x)]
                if len(possible) == 0:
                    try:
                        col=int(col)
                    except ValueError:
                        raise KeyError('Unable to find any possible column matches for '+str(col))
                    if col<0 or col>=self.data.shape[1]:
                        raise KeyError('Column index out of range')
                else:
                    col = self.column_headers.index(possible[0])
        elif isinstance(col,re._pattern_type):
            test = col
            possible = [x for x in self.column_headers if test.search(x)]
            if len(possible) == 0:
                raise KeyError('Unable to find any possible column matches for '+str(col.pattern))
            else:
                col = self.column_headers.index(possible[0])
        elif isinstance(col, slice):
            indices = col.indices(numpy.shape(self.data)[1])
            col = range(*indices)
            col = self.find_col(col)
        elif isinstance(col, list):
            col = [self.find_col(x) for x in col]
        else:
            raise TypeError('Column index must be an integer, string, \
            list or slice')
        return col


    def get(self, item):
        """A wrapper around __get_item__ that handles missing keys by returning None. This is useful for the :py:class:`Stoner.Folder.DataFolder` class

        Args:
            item (string): A string representing the metadata keyname

        Returns:
            self.metadata[item] or None if item not in self.metadata"""
        try:
            return self[item]
        except KeyError:
            return None

    def get_filename(self, mode):
        self.filename = self.__file_dialog(mode)
        return self.filename

    def insert_rows(self, row, new_data):
        """Insert new_data into the data array at position row. This is a wrapper for numpy.insert

        Args:
            row (int):  Data row to insert into
            new_data (numpy array): An array with an equal number of columns as the main data array containing the new row(s) of data to insert

        Returns:
            A copy of the modified DataFile object"""
        self.data=numpy.insert(self.data, row,  new_data, 0)
        return self

    def keys(self):
        """An alias for @b DataFile.dir(None)

        Returns:
            a list of all the keys in the metadata dictionary"""
        return self.dir(None)

    def load(self, filename=None, auto_load=True,  filetype=None,  *args, **kargs):
        """Loads the :py:class:`DataFile` in from disc guessing a better subclass if necessary.

        Args:
            filename (string or None): path to file to load

        Keyword Arguments:
            auto_load (bool): If True (default) then the load routine tries all the subclasses of :py:class:`DataFile` in turn to load the file
            filetype (:py:class:`DataFile`): If not none then tries using filetype as the loader

        Returns:
            A copy of the loaded instance

        Note:
            Possible subclasses to try and load from are identified at run time using the speciall :py:attr:`DataFile.subclasses` attribute.

            Some subclasses can be found in the :py:mod:`Stoner.FileFormats` module.

            Each subclass is scanned in turn for a class attribute priority which governs the order in which they are tried. Subclasses which can
            make an early positive determination that a file has the correct format can have higher priority levels. Classes should return
            a suitable expcetion if they fail to load the file.

            If not class can load a file successfully then a RunttimeError exception is raised.
            """

        if filename is None or (isinstance(filename, bool) and not filename):
            filename = self.__file_dialog('r')
        else:
            self.filename = filename

        failed=True
        cls=self.__class__
        try:
            if filetype is None:
                self.__parse_data()
                self["Loaded as"]=cls.__name__
            else:
                self.__class__(filetype(filename))
                self["Loaded as"]=filetype.__name__
            failed=False
            return self
        except RuntimeError: # We failed to parse assuming this was a TDI
            if auto_load: # We're going to try every subclass we can
                subclasses={x:x.priority for x in itersubclasses(DataFile)}
                for cls, priority in sorted(subclasses.iteritems(), key=lambda (k,v): (v,k)):
                    if self.debug:
                        print cls.__class__.__name__
                    try:
                        test=cls()
                        test.load(self.filename, auto_load=False)
                        failed=False
                        break
                    except Exception:
                        continue

        if failed:
            raise SyntaxError("Failed to load file")
        else:
            self.data=ma.masked_array(test.data)
            self.metadata=test.metadata
            self.column_headers=test.column_headers
            self["Loaded as"]=cls.__name__

        return self

    def meta(self, ky):
        """Returns some metadata

        Args:
            ky (string): The name of the metadata item to be returned.

        Returns:
            Returns the item of metadata.

        Note:
           If key is not an exact match for an item of metadata,
            then a regular expression match is carried out.
            """
        if isinstance(ky, str):  # Ok we go at it with a string
            if ky in self.metadata:
                return self.metadata[ky]
            else:
                test = re.compile(ky)
                possible = [x for x in self.metadata if test.search(x)]
                if len(possible) == 0:
                    raise KeyError("No metadata with keyname: " + ky)
                elif len(possible) == 1:
                    return self.metadata[possible[0]]
                else:
                    d = dict()
                    for p in possible:
                        d[p] = self.metadata[p]
                    return d
        else:
            raise TypeError("Only string are supported as search \
            keys currently")
            # Should implement using a list of strings as well

    def rename(self, old_col, new_col):
        """Renames columns without changing the underlying data

        Args:
            old_col (string, int, re):  Old column index or name (using standard rules)
            new_col (string): New name of column

        Returns:
            A copy of self
        """

        old_col=self.find_col(old_col)
        self.column_headers[old_col]=new_col
        return self

    def reorder_columns(self, cols, headers_too=True):
        """Construct a new data array from the original data by assembling
        the columns in the order given

        Args:
            cols (list of column indices): (referred to the oriignal
                data set) from which to assemble the new data set
            headers_too (bool): Reorder the column headers in the same
                way as the data (defaults to True)

        Returns:
            A copy of the modified DataFile object"""
        if headers_too:
            self.column_headers = [self.column_headers[self.find_col(x)]
                                                            for x in cols]

        newdata = numpy.atleast_2d(self.data[:, self.find_col(cols.pop(0))])
        for col in cols:
            newdata = numpy.append(newdata, numpy.atleast_2d(self.data[:,
                                                self.find_col(col)]), axis=0)
        self.data = ma.masked_array(numpy.transpose(newdata))
        return self

    def rows(self):
        """Generator method that will iterate over rows of data

        Yields:
            Returns the next row of data"""
        r = numpy.shape(self.data)[0]
        for row in range(r):
            yield self.data[row]


    def save(self, filename=None):
        """Saves a string representation of the current DataFile object into
        the file 'filename'

        Args:
            filename (string, bool or None): Filename to save data as, if this is
                None then the current filename for the object is used
                If this is not set, then then a file dialog is used. If f
                ilename is False then a file dialog is forced.

        Returns:
            The current object
                """
        if filename is None:
            filename = self.filename
        if filename is None or (isinstance(filename, bool) and not filename):
            # now go and ask for one
            filename = self.__file_dialog('w')
        f = open(filename, 'w')
        f.write(repr(self))
        f.close()
        self.filename = filename
        return self

    def search(self, xcol,value,columns=None):
        """Searches in the numerica data part of the file for lines
        that match and returns  the corresponding rows

        Args:
            col (int,string.re) is a Search Column Index
            value (float, tuple, list or callable): Value to look for
            columns (index or array of indices or None (default)): columns of data to return - none represents all columns.

        Returns:
            numpy array of matching rows or column values depending on the arguements.

        Note:
            The value is interpreted as follows:
            - a float looks for an exact match
            - a list is a list of exact matches
            - a tuple should contain a (min,max) value.
            - A callable object should have accept a float and an array representing the value of
                the search col for the the current row and the entire row.


        """
        rows=[]
        for (r,x) in zip(range(len(self)),self.column(xcol)):
            if isinstance(value,tuple) and value[0]<=x<=value[1]:
                rows.append(r)
            elif isinstance(value,list):
                for v in value:
                    if isinstance(v,tuple) and v[0]<=x<=v[1]:
                        rows.append(r)
                        break
                    elif x==v:
                        rows.append(r)
                        break
            elif callable(value) and value(x,self[r]):
                rows.append(r)
            elif x==value:
                rows.append(r)
        if columns is None: #Get the whole slice
            return self.data[rows,:]
        elif isinstance(columns,str) or isinstance(columns,int):
            columns=self.find_col(columns)
            if len(rows)==1:
                return self.data[rows,columns]
            else:
                return self.data[rows][:, columns]
        else:
            targets=[self.find_col(t) for t in columns]
            return self.data[rows][:, targets]

    def sort(self, order=None):
        """Sorts the data by column name. Sorts in place and returns a
        copy of the sorted data object for chaining methods

        Args:
            order (column index or list of indices): Represent the sort order

        Returns:
            A copy of the sorted object

        TODO:
            Add a reversed keyword and also a key keyword to take a sorting function
        """

        if order is None:
            order=range(len(self.column_headers))
        recs=self.records
        if isinstance(order, list) or isinstance(order, tuple):
            order = [recs.dtype.names[self.find_col(x)] for x in order]
        else:
            order = [recs.dtype.names[self.find_col(order)]]
        d = numpy.sort(recs, order=order)
        self.data = ma.masked_array(d.view(dtype=self.dtype).reshape(len(self), len(self.
                                                              column_headers)))
        return self

    def swap_column(self, swp, headers_too=True):
        """Swaps pairs of columns in the data. Useful for reordering
        data for idiot programs that expect columns in a fixed order.

        Args:
            swp  (tuple of list of tuples of two elements): Each
                element will be iused as a column index (using the normal rules
                for matching columns).  The two elements represent the two
                columns that are to be swapped.
            headers_too (bool): Indicates the column headers
                are swapped as well

            Returns:
                A copy of the modified DataFile objects

            Note:
                If swp is a list, then the function is called recursively on each
                element of the list. Thus in principle the @swp could contain
                lists of lists of tuples
        """
        if isinstance(swp, list):
            for item in swp:
                self.swap_column(item, headers_too)
        elif isinstance(swp, tuple):
            col1 = self.find_col(swp[0])
            col2 = self.find_col(swp[1])
            self.data[:,  [col1, col2]] = self.data[:, [col2, col1]]
            if headers_too:
                self.column_headers[col1], self.column_headers[col2] =\
                self.column_headers[col2], self.column_headers[col1]
        else:
            raise TypeError("Swap parameter must be either a tuple or a \
            list of tuples")
        return self

    def unique(self, col, return_index=False, return_inverse=False):
        """Return the unique values from the specified column - pass through
        for numpy.unique

        Args:
            col (index): Column to look for unique values in

        Keyword Arguments:

        """
        return numpy.unique(self.column(col), return_index, return_inverse)


# Module level functions

def itersubclasses(cls, _seen=None):
    """
    itersubclasses(cls)

    Generator over all subclasses of a given class, in depth first order.

    >>> list(itersubclasses(int)) == [bool]
    True
    >>> class A(object): pass
    >>> class B(A): pass
    >>> class C(A): pass
    >>> class D(B,C): pass
    >>> class E(D): pass
    >>>
    >>> for cls in itersubclasses(A):
    ...     print(cls.__name__)
    B
    D
    E
    C
    >>> # get ALL (new-style) classes currently defined
    >>> [cls.__name__ for cls in itersubclasses(object)] #doctest: +ELLIPSIS
    ['type', ...'tuple', ...]
    """

    if not isinstance(cls, type):
        raise TypeError('itersubclasses must be called with '
                        'new-style classes, not %.100r' % cls)
    if _seen is None: _seen = set()
    try:
        subs = cls.__subclasses__()
    except TypeError: # fails only when cls is type
        subs = cls.__subclasses__(cls)
    for sub in subs:
        if sub not in _seen:
            _seen.add(sub)
            yield sub
            for sub in itersubclasses(sub, _seen):
                yield sub
